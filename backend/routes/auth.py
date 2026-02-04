from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import RedirectResponse,JSONResponse
from src.db_connection.connection import supabase_client
import os
import jwt
import httpx
from dotenv import load_dotenv
load_dotenv()


# router = APIRouter(prefix="/auth")

router = APIRouter()


# authentication middleware --> dependency
# -------------------- JWT verification dependency --------------------
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing auth")

    token = auth_header.replace("Bearer ", "")

    user = supabase_client.auth.get_user(token)

    if not user or not user.user:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user.user


#JWT from supbase contain 
# {
#   "sub": "user_id",
#   "email": "...",
#   "role": "authenticated",
#   "exp": ...
# }








