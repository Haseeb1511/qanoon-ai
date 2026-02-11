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
from backend.services.log_token_usage import log_token_usage

router = APIRouter()


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

    # prepare initial state - now returns doc_ids array
    state, thread_id, doc_ids = await prepare_initial_state(pdf, question,request)
    
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
                "doc_ids": doc_ids,
                "user_id":user.id, # add supbase user id for auth
                "messages": [
                    {"role": "human", "content": question},
                    {"role": "ai", "content": answer}
                ],
                "summary": final_state.get("summary", "")  # Save summary(just for consitency as ask endpoint never create summary it only trigger when first message is sent)
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
                doc_ids[0] if doc_ids else "",  #  Use first doc_id for logging
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
    previous_messages, doc_ids,summary = await load_thread_messages(thread_id,user.id)


    if not doc_ids:
        raise HTTPException(status_code=404, detail="No documents found for this thread")

    # Use user-based collection name for multi-PDF support
    collection_name = f"user_{user.id}"


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

    # Fetch custom prompt for this user
    custom_prompt = None
    try:
        settings_response = await run_in_threadpool(
            lambda: supabase_client.table("user_settings")
                .select("custom_prompt")
                .eq("user_id", str(user.id))
                .limit(1)
                .execute()
        )
        if settings_response.data and len(settings_response.data) > 0:
            custom_prompt = settings_response.data[0].get("custom_prompt")
    except Exception:
        pass  # Use default prompt if fetch fails

    # now we will pass the state to the graph
    state = {
        "user_id": user.id,   # unique user id from supbase
        "doc_ids": doc_ids,  # which doc_id we are using
        "collection_name": collection_name,  # which vectorstore collection to use,
        "summary": summary or " ", # previous summary of the document if exist
        "messages": messages, # list of all previous messages + new question(to provide context to the model)
        "vectorstore_uploaded": True, # PDF already ingested, skip document ingestion
        "custom_prompt": custom_prompt  # User's custom prompt (None = use default)
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
                lambda:supabase_client
                .table("threads")
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


# ===================== Add PDF to Existing Thread =====================
from src.utils.file_hash import get_file_hash
from pathlib import Path
import aiofiles

UPLOAD_DIR = Path("uploaded_docs")

@router.post("/add_pdf")
async def add_pdf_to_thread(
    request: Request,
    background_tasks: BackgroundTasks,
    pdf: UploadFile = File(...),
    thread_id: str = Form(...),
    user=Depends(get_current_user)
):
    """
    Add a new PDF to an existing thread.
    This will:
    1. Save the PDF file
    2. Generate doc_id
    3. Add doc_id to thread's doc_ids array
    4. Trigger document ingestion (Background Task)
    """
    # Save PDF
    pdf_path = UPLOAD_DIR / pdf.filename
    async with aiofiles.open(pdf_path, "wb") as f:
        while chunk := await pdf.read(1024 * 1024):
            await f.write(chunk)
    
    # Generate doc_id with user-based collection
    # Run hashing in threadpool to avoid blocking event loop
    new_doc_id = await run_in_threadpool(get_file_hash, str(pdf_path))
    collection_name = f"user_{user.id}"  # User-based collection for multi-PDF
    
    # Get existing thread to retrieve current doc_ids
    thread_response = await run_in_threadpool(
        lambda: supabase_client.table("threads")
            .select("doc_ids")
            .eq("thread_id", thread_id)
            .eq("user_id", user.id)
            .single()
            .execute()
    )
    
    if not thread_response.data:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    existing_doc_ids = thread_response.data.get("doc_ids", []) or []
    
    # Check if this doc already exists in thread
    if new_doc_id in existing_doc_ids:
        return {"status": "exists", "message": "PDF already in this thread", "doc_id": new_doc_id}
    
    # Add new doc_id to array
    updated_doc_ids = existing_doc_ids + [new_doc_id]
    
    # Update thread with new doc_ids
    await run_in_threadpool(
        lambda: supabase_client.table("threads")
            .update({"doc_ids": updated_doc_ids})
            .eq("thread_id", thread_id)
            .execute()
    )
    
    # Prepare state for document ingestion only (no question)
    state = {
        "user_id": user.id,
        "documents_path": str(pdf_path),
        "doc_ids": [new_doc_id],  # Only the new doc for ingestion check
        "collection_name": collection_name,
        "messages": [],  # No messages, just ingestion
        "summary": "",
        "vectorstore_uploaded": False
    }
    
    # Import nodes from builder
    from src.graph.builder import nodes
    
    # Check if already uploaded and ingest if needed
    state = await nodes.check_pdf_already_uploaded(state)
    
    processing_status = "completed"
    message = f"PDF '{pdf.filename}' added to thread"
    
    if not state.get("vectorstore_uploaded"):
        # Move heavy ingestion to background task to avoid timeout
        background_tasks.add_task(nodes.document_ingestion, state)
        processing_status = "processing_started"
        message = f"PDF '{pdf.filename}' uploaded. Processing in background..."
    
    return {
        "status": "success",
        "processing_status": processing_status,
        "message": message,
        "doc_id": new_doc_id,
        "doc_ids": updated_doc_ids
    }