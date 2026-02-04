from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from src.graph.builder import GraphBuilder
from src.db_connection.connection import CONNECTION_STRING
from fastapi import FastAPI


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
    async with AsyncPostgresSaver.from_conn_string(CONNECTION_STRING) as cp:
        await cp.setup()
        # wehave to checkpointer and graph instance in app state so that we can access it in route handlers
        app.state.checkpointer = cp
        app.state.graph = GraphBuilder(checkpointer=cp).build_graph()
        print("Graph + Checkpointer ready")
        yield



app = FastAPI(title="QanoonAI",lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from backend.routes import threads,chat,auth
# Binds Router To the Fastapi object
app.include_router(threads.router)
app.include_router(chat.router)
app.include_router(auth.router)



#Important
#Backend inserts MUST use:
# SUPABASE_SERVICE_ROLE_KEY
# If you’re using:
# SUPABASE_ANON_KEY
# inserts will fail or silently no-op.


# No response received. Please try again. ===>  This mean graph is None
# NEVER IMPORT RUNTIME FORM APP.PY TO OTHER FILES AS IT WILL CREATE CIRCULAR IMPORT ISSUE