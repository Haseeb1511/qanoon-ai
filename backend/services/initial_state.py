from src.utils.file_hash import get_file_hash
import uuid
import aiofiles
from pathlib import Path
from langchain_core.messages import HumanMessage
from src.db_connection.connection import supabase_client
from fastapi import Request, HTTPException

UPLOAD_DIR = Path("uploaded_docs")
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)




# -----------------------------
# helper: extract JWT from request
# -----------------------------
def get_access_token_from_request(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return auth_header.split(" ")[1]






# Initail state for the graph
async def prepare_initial_state(pdf, question: str, request: Request):
    """ 
    Prepares the state for RAG graph.
    - Saves PDF
    - Generates doc_id
    - Gets user_id from Supabase access token
    """
    pdf_path = UPLOAD_DIR / pdf.filename


    async with aiofiles.open(pdf_path, "wb") as f:
        while chunk := await pdf.read(1024 * 1024):
            await f.write(chunk)


    doc_id = get_file_hash(str(pdf_path))  # generate unique doc id based on file content using get_file_hash funciton
    collection_name = pdf_path.stem.lower().replace(" ", "_")  # "law.pdf".stem -> "law"
    thread_id = str(uuid.uuid4())  # genearate thread id for the conversation


    # Extract access token from request headers
    access_token = get_access_token_from_request(request)


    # Get user info from Supabase
    user_response = supabase_client.auth.get_user(access_token)
    state = {
        "user_id": user_response.user.id,   # unique user id from supbase
        "documents_path": str(pdf_path),
        "doc_id": doc_id,
        "collection_name": collection_name,
        "messages": [HumanMessage(content=question)],
        "summary": ""
    }

    return state, thread_id, doc_id





# filename = "Legal Case.pdf"
# parts = filename.rsplit(".", 1)
# print(parts)
# ['Legal Case', 'pdf']

# multiple dots file
# filename = "my.important.document.pdf"
# parts = filename.rsplit(".", 1)
# print(parts)
# ['my.important.document', 'pdf']