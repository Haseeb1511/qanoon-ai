
from src.db_connection.connection import supabase_client
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

# ============================ Token limit check ============================

TOKEN_LIMIT = 10000

async def check_token_limit(user_id:str):
    # fetch the usage table from database and select its total_tokens attribute
    response = await run_in_threadpool(
        lambda: supabase_client
        .table("usage")
        .select("total_tokens")
        .eq("user_id", user_id)
        .execute()
    )
    if not response.data:
        return False

    # we sum the total_tokens(attribute) of all rows of that user to get how many token he has used till not
    total_tokens = sum(row["total_tokens"] for row in response.data)
    if total_tokens >= TOKEN_LIMIT:
        raise HTTPException(status_code=429, detail="You have reached your maximum API limit (100,000 tokens)")
    return True