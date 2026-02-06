from fastapi import HTTPException,Depends
from src.db_connection.connection import supabase_client
from fastapi import APIRouter
from backend.routes.auth import get_current_user

router = APIRouter()

# ============================= Load Thread Messages =============================

async def load_thread_messages(thread_id: str,user_id:str):
    response = (
        supabase_client
        .table("threads")
        .select("messages, doc_id,summary")
        .eq("thread_id", thread_id)
        .eq("user_id",user_id)   # filter by login user id
        .single()
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Thread not found")

    return response.data["messages"], response.data["doc_id"],response.data.get("summary","")



# ============================= Get All Threads with Previews =============================
# sidebar chats threads
@router.get("/all_threads")
async def get_all_threads(user=Depends(get_current_user)):
    """Get all threads with previews"""
    try:
        response = (
            supabase_client
            .table("threads")
            .select("thread_id, doc_id, messages")
            .eq("user_id",user.id)  # filter by login user
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
        print(f"Error fetching threads: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    


    
# ============================= Get Specific Thread Data =============================

@router.get("/get_threads/{thread_id}")
async def get_threads(thread_id: str,user=Depends(get_current_user)):
    """Get a specific thread's data"""
    messages, doc_id,summary = await load_thread_messages(thread_id,user.id)
    return {
        "thread_id": thread_id,
        "doc_id": doc_id,
        "messages": messages
    }
