from sqlalchemy.pool import NullPool  
import os
from pathlib import Path  
from dotenv import load_dotenv
from supabase import create_client
# from sqlalchemy import create_engine


# Absolute path to .env (project root)
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)


CONNECTION_STRING = os.environ.get("CONNECTION_STRING","")
SUPERBASE_SERVICE_ROLE_KEY = os.environ.get("SUPERBASE_SERVICE_ROLE_KEY","")
SUPABASE_URL = os.environ.get("SUPABASE_URL","")



# engine has no attribute table
#  To check if connected to supbase or not 
# DB_ENGINE = create_engine(
#     CONNECTION_STRING,
#     poolclass = NullPool,
#     pool_pre_ping = True  # avoid using stale connections  
#     )
# with DB_ENGINE.connect() as conn:
#     print("Connected to Supabase Postgres")



supabase_client = create_client(SUPABASE_URL,SUPERBASE_SERVICE_ROLE_KEY)
print("Succefully coonectd to Supabase client")
    