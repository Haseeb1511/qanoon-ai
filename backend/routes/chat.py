from fastapi import HTTPException, UploadFile, Form, File, Request,Depends
from langchain_core.messages import HumanMessage, AIMessage
from src.db_connection.connection import supabase_client
from backend.services.initial_state import prepare_initial_state
from backend.services.streaming import stream_graph
from backend.routes.threads import load_thread_messages

from backend.routes.auth import get_current_user  # for user authentication
from fastapi import APIRouter

from fastapi.concurrency import run_in_threadpool
import time
import asyncio
from backend.services.token_limit import check_token_limit
router = APIRouter()


# ============================= Log token usage =============
from tenacity import retry,stop_after_attempt,wait_exponential
@retry(stop=stop_after_attempt(3),wait = wait_exponential(multiplier=1,min=2,max=10))
async def log_token_usage(user_id:str,doc_id:str,thread_id:str,token_usage:dict):
    """
    Background task to log token usage to Supabase with retry logic.
    """
    print(f"BACKGROUND TASK STARTED ") 
    try:
        await run_in_threadpool(
            lambda: supabase_client.table("usage").insert({
                "user_id": user_id,
                "doc_id": doc_id,
                "thread_id": thread_id,
                "total_tokens": token_usage["total_tokens"],
                "prompt_tokens": token_usage["prompt_tokens"],
                "completion_tokens": token_usage["completion_tokens"],
                "query": token_usage["query"],
                "answer": token_usage["answer"]
            }).execute()
        )
    except Exception as e:
        print(f"Failed to log token usage for thread {thread_id}: {e}")
        raise





#==================== Initial Question Endpoint =====================
from fastapi import BackgroundTasks

@router.post("/ask")
async def ask_question(
    request: Request,
    background_tasks:BackgroundTasks,
    pdf: UploadFile = File(...),
    question: str = Form(...),
    user=Depends(get_current_user)
):

    # check token limits first (raises HTTPException if limit exceeded)
    await check_token_limit(user.id)

    # prepare initial state
    state, thread_id, doc_id = await prepare_initial_state(pdf, question,request)
    
    start_time = time.time()  # start timer before streaming

    # as above when streaming is done and message is append as single sting we need to store the question and answer in database
    # so we define on_complete function to do that
    async def on_complete(answer: str, final_state: dict):
        end_time = time.time()  # stop timer after streaming finishes
        duration = end_time - start_time
        print(f"/ask query took {duration:.2f} seconds")

        # UPDATE THREADS
        try:
            await run_in_threadpool(
                lambda:supabase_client.table("threads").upsert({
                "thread_id": thread_id,
                "doc_id": doc_id,
                "user_id":user.id, # add supbase user id for auth
                "messages": [
                    {"role": "human", "content": question},
                    {"role": "ai", "content": answer}
                ]
            }).execute())
            print("Thread upserted successfully in ask endpoint.")

        except asyncio.TimeoutError:
            print("Supbase timeout error while upserting thread data")

        # schedule token usage logging in database in background task
        token_usage = final_state.get("token_usage")
        if token_usage:
            background_tasks.add_task(
                log_token_usage,
                user.id,
                doc_id,
                thread_id,
                token_usage
            )
            print("Tokens logged to supbase successfully")

            
    config = {"configurable": {"thread_id": thread_id}}
    graph = request.app.state.graph # we fetch the graph instance from app state
    
    # Pass thread_id so it gets sent to frontend in first SSE event
    # we can not store stream_graph in variable as it is streaming response 
    return await stream_graph(graph, state, config, on_complete, thread_id=thread_id)



# User asks first question → /ask called
# Backend streams: {"type": "thread_created", "thread_id": "abc123"} ← first event
# Frontend immediately sets activeThread = { thread_id: "abc123" }
# User asks second question → activeThread exists → /follow_up called 







# ===================== Follow-up Question Endpoint =====================

@router.post("/follow_up")
async def follow_up(
    request: Request,
    background_tasks: BackgroundTasks,
    thread_id: str = Form(...),
    question: str = Form(...),
    user=Depends(get_current_user)
):

     # check token limits first (raises HTTPException if limit exceeded)
    await check_token_limit(user.id)


    # first we will load previous message for the seelcted thread id that user had previously used
    previous_messages, doc_id,summary = await load_thread_messages(thread_id,user.id)

    # then we will fetch document info to get collection name
    # as our langgraph vectorstore is used collection name to fetch relevant chunks from vectorstore
    # this enusre that retriver fetches from correct document
    response = await run_in_threadpool(
        lambda: supabase_client
        .table("documents")
        .select("file_name")
        .eq("doc_id", doc_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Document not found")

    # rsplit (sep, maxsplit) 
    # maxsplit -->maximum number of splits starting from the right.
    # Here we split the file name at the last period to separate the name from the extension
    collection_name = response.data[0]["file_name"].rsplit(".", 1)[0].lower().replace(" ", "_")

    messages = []
    # we will append previous message + new message in the messages list  to provide the contet to the model
    # as our query_rewiter node use previous context to rewrite the query so we have to pass aprevious msg along with new quesiton to get contextuall aware query
    for m in previous_messages:
        if m["role"] == "human":
            messages.append(HumanMessage(content=m["content"]))
        else:
            messages.append(AIMessage(content=m["content"]))

    # we will append the new quesion in th messages list
    messages.append(HumanMessage(content=question))

    # now we will pass the state to the graph
    state = {
        "user_id": user.id,   # unique user id from supbase
        "doc_id": doc_id,  # which doc_id we are using
        "collection_name": collection_name,  # which vectorstore collection to use,
        "summary": summary or " ", # previous summary of the document if exist
        "messages": messages, # list of all previous messages + new question(to provide context to the model)
        "vectorstore_uploaded": True # PDF already ingested, skip document ingestion

    }
    start_time = time.time()  # start timer before streaming

    # after streaming is done we need to append the new question and answer to the previous messages and update the database
    async def on_complete(answer: str, final_state: dict):
        end_time = time.time()  # stop timer after streaming finishes
        duration = end_time - start_time
        print(f"/follow_up query took {duration:.2f} seconds")

        
        #UPDATE THREAD
        # first apppend the new ai message in state["messages"]
        state["messages"].append(AIMessage(content=answer))
        clean_messages = [
                {"role":"human","content":m.content}
                if isinstance(m, HumanMessage)
                else {"role":"ai","content":m.content}
                for m in state["messages"]
        ]
        # here we will use update insted of upsert as the thread already exist we just need to update the messages field
        try:
            
            await run_in_threadpool(
                lambda:supabase_client.table("threads")
                .update({
                "messages": clean_messages,
                "summary": final_state.get("summary", state.get("summary", ""))
                })
                .eq("thread_id", thread_id).execute())
            print("Thread updated successfully in follow_up endpoint.")

        except asyncio.TimeoutError:
            print("Supbase timeout error while updating thread data")


        # Schedule token usage logging as background task
        token_usage = final_state.get("token_usage")
        if token_usage:
            background_tasks.add_task(
                log_token_usage,
                user.id,
                doc_id,
                thread_id,
                token_usage
            )
            print(f"token logged to supbase in follow up endpoint")

    config = {"configurable": {"thread_id": thread_id}}

    graph = request.app.state.graph  # we fetch the graph instance from app state
    return await stream_graph(graph, state, config, on_complete)
    




# as soon the fastapi app is created and graph is initialized in the lifespan function. and stored in app.state.graph
# we can access the graph instance in our route handlers via request.app.state.graph 
# FastAPI allows you to store global-ish objects in the app that are initialized at runtime,using app.state
# graph = request.app.state.graph