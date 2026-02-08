from fastapi import HTTPException, UploadFile, Form, File, Request, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage
from src.db_connection.connection import supabase_client
from backend.services.initial_state import prepare_initial_state
from backend.services.streaming import stream_graph
from backend.routes.threads import load_thread_messages

from backend.routes.auth import get_current_user  # for user authentication
from fastapi import APIRouter

from fastapi.concurrency import run_in_threadpool
import time
import os
import tempfile
import asyncio
import json
from backend.services.token_limit import check_token_limit

# audio files
from src.audio.voice import text_to_speech, text_to_speech_bytes
from src.audio.transcription import AudioToText

from backend.services.log_token_usage import log_token_usage


router = APIRouter()

audio_to_text = AudioToText()


# ========================= Transcribe audio file funciotn ================
async def transcribe_audio_file(audio: UploadFile) -> str:
    """
    Save and transcribe an audio file.
    Returns (transcribed_text, temp_file_path)
    """
    suffix = os.path.splitext(audio.filename)[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        content = await audio.read()
        temp_file.write(content)
        audio_path = temp_file.name

    # Transcribe audio to text
    question = await asyncio.to_thread(audio_to_text.transcribe, audio_path)
    
    # Cleanup temp file
    try:
        os.unlink(audio_path)
    except:
        pass
    
    return question



from fastapi import BackgroundTasks
#==================== Initial Question Endpoint (voice based) =====================
@router.post("/ask/audio")
async def ask_question_audio(
    request: Request,
    background_tasks:BackgroundTasks,
    audio: UploadFile = File(...),
    pdf: UploadFile = File(...),
    user=Depends(get_current_user)
):
    """
    Handle initial question via audio input.
    1. Receives audio file and PDF
    2. Transcribes audio to text
    3. Processes the question through the RAG pipeline using stream_graph
    4. Streams the response back
    """


    # check token limits first (raises HTTPException if limit exceeded)
    await check_token_limit(user.id)

    # Transcribe audio to text first (before streaming starts)
    question = await transcribe_audio_file(audio)
    print("Transcribed audio to text:", question)


    # Prepare initial state for our LLM
    state, thread_id, doc_ids = await prepare_initial_state(pdf, question, request)

    start_time = time.time()

    # Callback to store in database after streaming completes
    async def on_complete(answer: str, final_state: dict):
        end_time = time.time()
        duration = end_time - start_time
        print(f"/ask/audio query took {duration:.2f} seconds")

        # supbase .execute is async so we need to await it
        try:
            await run_in_threadpool(
            lambda:supabase_client.table("threads").upsert({
            "thread_id": thread_id,
            "doc_ids": doc_ids,  
            "user_id": user.id,
            "messages": [
                {"role": "human", "content": question},
                {"role": "ai", "content": answer}
                ]
            }).execute()
            )
            print("Thread upserted successfully in ask/audio endpoint.")

        except asyncio.TimeoutError:
            print("Supbase timeout error while upserting thread data")


     # schedule token usage logging in database in background task
        token_usage = final_state.get("token_usage")
        if token_usage:
            background_tasks.add_task(
                log_token_usage,
                user.id,
                doc_ids[0] if doc_ids else "",  # Use first doc_id for logging
                thread_id,
                token_usage
            )
            print("Tokens logged to supbase successfully")


    config = {"configurable": {"thread_id": thread_id}}
    graph = request.app.state.graph

    # we can not store stream_graph in variable as it is streaming response 
    return await stream_graph(graph, state, config, on_complete, thread_id=thread_id,first_message=question)


# ===================== Follow-up Question Endpoint (voice based) =====================

@router.post("/follow_up/audio")
async def follow_up_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    thread_id: str = Form(...),
    user=Depends(get_current_user)
):
    """
    Handle follow-up question via audio input.
    1. Receives audio file and thread_id
    2. Transcribes audio to text
    3. Loads previous conversation context
    4. Processes the question through the RAG pipeline using stream_graph
    5. Streams the response back
    """


    # check token limits first (raises HTTPException if limit exceeded)
    await check_token_limit(user.id)
    
    # Transcribe audio to text first
    question = await transcribe_audio_file(audio)
    print("Transcribed audio to text:", question)


    # Load previous messages for the selected thread
    previous_messages, doc_ids, summary = await load_thread_messages(thread_id, user.id)

    if not doc_ids:
        raise HTTPException(status_code=404, detail="No documents found for this thread")

    # Use user-based collection name for multi-PDF support
    collection_name = f"user_{user.id}"

    # Build messages list with context
    messages = []
    for m in previous_messages:
        if m["role"] == "human":
            messages.append(HumanMessage(content=m["content"]))
        else:
            messages.append(AIMessage(content=m["content"]))

    messages.append(HumanMessage(content=question))

    # Prepare state for the graph
    state = {
        "user_id": user.id,
        "doc_ids": doc_ids,  # Changed to doc_ids array
        "collection_name": collection_name,
        "summary": summary or "",
        "messages": messages,
        "vectorstore_uploaded": True
    }

    start_time = time.time()

    # Callback to update database after streaming completes
    async def on_complete(answer: str, final_state: dict):
        end_time = time.time()
        duration = end_time - start_time
        print(f"/follow_up/audio query took {duration:.2f} seconds")


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

        
        token_usage = final_state.get("token_usage")
        if token_usage:
            background_tasks.add_task(
                log_token_usage,
                user.id,
                doc_ids[0] if doc_ids else "",  # Use first doc_id for logging
                thread_id,
                token_usage
            )
            print(f"token logged to supbase in follow up endpoint")

    config = {"configurable": {"thread_id": thread_id}}
    graph = request.app.state.graph

    # we can not store stream_graph in variable as it is streaming response 
    return await stream_graph(graph, state, config, on_complete, thread_id=thread_id,first_message=question)




# ===================== Text-to-Speech Endpoint =====================
@router.post("/tts")
async def text_to_speech_endpoint(
    text: str = Form(...),
    user=Depends(get_current_user)
):
    """
    Convert text to speech and return audio file.
    """
    try:
        audio_bytes = await asyncio.to_thread(text_to_speech_bytes, text)
        
        return StreamingResponse(
            iter([audio_bytes]),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=response.mp3"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")