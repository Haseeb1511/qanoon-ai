import os, sys, uuid, json, asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import aiofiles
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.graph.builder import GraphBuilder
from src.db_connection.connection import CONNECTION_STRING, supabase_client
from src.utils.file_hash import get_file_hash


# -------------------- APP SETUP --------------------



UPLOAD_DIR = Path("uploaded_docs")
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)

graph = None  # global graph variable default is None
checkpointer = None  # global checkpointer variable default is None



# -------------------- LIFESPAN --------------------
# we will use asyn context manager as it help in writing async context manager whiich is useful for fastapi as we will use  async funciton in fastapi
# This is useful for resources that take time to initialize or clean up,like a database
# connection or, in your case, a LangGraph workflow and Postgres checkpointer
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager handles startup and shutdown.
    - On startup: Initialize checkpointer and build graph
    - On shutdown: Cleanup happens automatically via async context manager
    """
    global graph, checkpointer

    async with AsyncPostgresSaver.from_conn_string(CONNECTION_STRING) as cp:
        await cp.setup()
        checkpointer = cp
        graph = GraphBuilder(checkpointer=checkpointer).build_graph()
        print("Graph + Checkpointer ready")
        yield


# it tell fast api to use the lifespan context to handle app startup and shutdown
# Before the first request(quesion) it will initlize hte checkpointer and graph 
# after the app stpops it can clean up resources if needed
# with out this our enpoint would fail because graph and chekcpointer would be None.
# app.router.lifespan_context = lifespan



app = FastAPI(title="QanoonAI",lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- HELPERS --------------------

# Initail state for the graph
async def prepare_initial_state(pdf, question: str):
    pdf_path = UPLOAD_DIR / pdf.filename

    async with aiofiles.open(pdf_path, "wb") as f:
        while chunk := await pdf.read(1024 * 1024):
            await f.write(chunk)

    doc_id = get_file_hash(str(pdf_path))  # generate unique doc id based on file content using get_file_hash funciton
    collection_name = pdf_path.stem.lower().replace(" ", "_")  # "law.pdf".stem -> "law"
    thread_id = str(uuid.uuid4())  # genearate thread id for the conversation

    state = {
        "documents_path": str(pdf_path),
        "doc_id": doc_id,
        "collection_name": collection_name,
        "messages": [HumanMessage(content=question)],
        "summary": ""
    }

    return state, thread_id, doc_id




# ===================== Streaming Graph =====================
def stream_graph(graph, state, config, on_complete=None):

    async def event_generator():
        tokens = []

        try:
            async for event in graph.astream_events(state, config=config, version="v2"):
                # workflow.add_node("agent_response", nodes.agent_response) ==> as we have this node we check that we only stream from this node(agent)
                if (
                        event["event"] == "on_chat_model_stream"
                        and event.get("metadata", {}).get("langgraph_node") == "agent_response"
                    ):
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and getattr(chunk, "content", None):
                        tokens.append(chunk.content) # we also append token in list as to persist the wole content is databse as otherwise we are genrating token by token so it will save incorrectly in database
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                        await asyncio.sleep(0)

        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"
            return

        final_answer = "".join(tokens)  # join all the tokens in single string

        # do this after the entier streaming is finshed(here when all token are streamed and final_answer is joined then we store the the content in the database)
        if on_complete:
            await on_complete(final_answer)
        
        # In SSE every msg is sent as data: <message>\n\n
        # The double newline \n\n is required by SSE protocol to signal end of the event.
        # our froned can detect this done message to know that the streaming is complete
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache", # ensures the browser does not cache the streamed response. Each stream should be fresh.
            "X-Accel-Buffering": "no",  # used mainly with Nginx or reverse proxies to disable buffering. Without this, tokens may be delivered in large chunks instead of real-time.
            "Connection": "keep-alive" # keeps the HTTP connection open so multiple messages (tokens) can flow continuously.
        }
    )



#THIS LINE HVAE ISSUE SINCE RE-RWITTEN QUERY ALSO USE LLM IT START STREAMING REWRITTEN QUERY ALONG WIH THE LLM FINAL RESPONESE
# so we need to filter only on_chat_model_stream event for final LLM response not for re-written query
# so we can check the event metadata or tags to differentiate between them
# async for event in graph.astream_events(state, config=config, version="v2"):
#     if event["event"] == "on_chat_model_stream":


# event = {
#   "event": "on_chat_model_stream",
#   "name": "ChatOpenAI",
#   "data": {
#       "chunk": AIMessageChunk(content="Hel")
#   },
#   "tags": ["llm"],
#   "metadata": {...}
# }

# langgraph has many kind of event
# Event name	   ===> Meaning
# on_chain_start	===> A chain/node started
# on_chain_end	===> A chain/node finished
# on_chat_model_start ===>	LLM started
# on_chat_model_stream ===>	LLM produced a token
# on_chat_model_end  ===>	LLM finished
# on_tool_start	 ===> Tool execution started
# on_tool_end ===>	Tool execution finished





# ============================= Load Thread Messages =============================
async def load_thread_messages(thread_id: str):
    response = (
        supabase_client
        .table("threads")
        .select("messages, doc_id")
        .eq("thread_id", thread_id)
        .single()
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Thread not found")

    return response.data["messages"], response.data["doc_id"]


# -------------------- ENDPOINTS --------------------


#==================== Initial Question Endpoint =====================
@app.post("/ask")
async def ask_question(
    pdf: UploadFile = File(...),
    question: str = Form(...)
):
    state, thread_id, doc_id = await prepare_initial_state(pdf, question)

    # as above when streamin is done and message is append as single sting we need to store the question and answer in database
    # so we define on_complete function to do that
    async def on_complete(answer: str):
        supabase_client.table("threads").upsert({
            "thread_id": thread_id,
            "doc_id": doc_id,
            "messages": [
                {"role": "human", "content": question},
                {"role": "ai", "content": answer}
            ]
        }).execute()

    config = {"configurable": {"thread_id": thread_id}}

    return stream_graph(graph, state, config, on_complete)



# ===================== Follow-up Question Endpoint =====================

@app.post("/follow_up")
async def follow_up(
    thread_id: str = Form(...),
    question: str = Form(...)
):
    # first we will load previous message for the seelcted thread id that user had previously used
    previous_messages, doc_id = await load_thread_messages(thread_id)

    # then we will fetch document info to get collection name
    # as our langgraph vectorstore is used collection name to fetch relevant chunks from vectorstore
    # this enusre that retriver fetches from correct document
    response = (
        supabase_client
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
        "doc_id": doc_id,  # which doc_id we are using
        "collection_name": collection_name,  # which vectorstore collection to use
        "messages": messages # list of all previous messages + new question(to provide context to the model)
    }

    # after streaming is done we need to append the new question and answer to the previous messages and update the database
    async def on_complete(answer: str):
        previous_messages.append({"role": "human", "content": question})
        previous_messages.append({"role": "ai", "content": answer})

        # here we will use update insted of upsert as the thread already exist we just need to update the messages field
        supabase_client.table("threads").update(
            {"messages": previous_messages}
        ).eq("thread_id", thread_id).execute()

    config = {"configurable": {"thread_id": thread_id}}

    return stream_graph(graph, state, config, on_complete)



@app.get("/all_threads")
async def get_all_threads():
    """Get all threads with previews"""
    try:
        response = (
            supabase_client
            .table("threads")
            .select("thread_id, doc_id, messages")
            .execute()
        )
        
        threads = []
        if response.data:
            for thread in response.data:
                messages = thread.get("messages", [])
                preview = "New Chat"
                if messages and len(messages) > 0:
                    preview = messages[0].get("content", "New Chat")[:50] + "..."
                
                threads.append({
                    "thread_id": thread["thread_id"],
                    "doc_id": thread["doc_id"],
                    "preview": preview
                })
        
        return threads
    except Exception as e:
        print(f"❌ Error fetching threads: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    


@app.get("/get_threads/{thread_id}")
async def get_threads(thread_id: str):
    """Get a specific thread's data"""
    try:
        response = (
            supabase_client
            .table("threads")
            .select("*")
            .eq("thread_id", thread_id)
            .single()
            .execute()
        )
        
        if response.data:
            return {
                "thread_id": response.data["thread_id"],
                "doc_id": response.data["doc_id"],
                "messages": response.data["messages"]
            }
        else:
            raise HTTPException(status_code=404, detail="Thread not found")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Thread not found: {str(e)}")







# filename = "Legal Case.pdf"
# parts = filename.rsplit(".", 1)
# print(parts)
# ['Legal Case', 'pdf']

# multiple dots file
# filename = "my.important.document.pdf"
# parts = filename.rsplit(".", 1)
# print(parts)
# ['my.important.document', 'pdf']