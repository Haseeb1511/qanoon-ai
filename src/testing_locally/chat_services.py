import os
# # Add project root (parent of 'src') to Python path
# sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import HumanMessage

from src.utils.file_hash import get_file_hash
from src.graph.builder import GraphBuilder
from src.db_connection.connection import CONNECTION_STRING


if __name__ == "__main__":
    # Project root
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    file_path = os.path.join(PROJECT_ROOT,"data","Constitution and law","PAKISTAN PENAL CODE.pdf")
    if not os.path.exists(file_path):
        raise FileNotFoundError("File is not found")
    
    # Generate unique doc_id for PDF
    doc_id = get_file_hash(file_path)

    # Create a collection name based on file name
    collection_name = (os.path.splitext(os.path.basename(file_path))[0].lower().replace(" ", "_"))

    # Thread ID for chat persistence
    thread_id = "user-123"

    # Connect to Supabase Postgres for checkpointing
    with PostgresSaver.from_conn_string(CONNECTION_STRING) as checkpointer:
        checkpointer.setup()

        # Build the workflow graph
        graph = GraphBuilder(checkpointer=checkpointer)()  # use as function

        config = {"configurable": {"thread_id": thread_id}}

        # ===== FIRST MESSAGE =====
        result = graph.invoke(
            {
                "documents_path": file_path,
                "doc_id": doc_id,
                "collection_name": collection_name,
                "messages": [HumanMessage(content="What is punishment for making false claim in court?")],
                "summary": ""},
            config=config
        ) 
        print("Answer 1:", result["answer"])


        # ===== SECOND MESSAGE =====

        initial_state = {
        "doc_id": doc_id,
        "collection_name": collection_name,  # Use existing vectorstore
        "messages": [HumanMessage(content="What is the penalty for that?")],  # Follow-up question
    }
        result = graph.invoke(initial_state,config=config)
        print("Answer 2:", result["answer"])
