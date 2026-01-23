import os
from typing import TypedDict, Annotated
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

class AgentState(TypedDict):
    documents_path:str
    documents:list[Document]
    chunks:list[Document] 
    collection_name:str
    retrieved_docs:list[Document]
    context: str 
    answer:str
    messages: Annotated[list[BaseMessage], add_messages]
    doc_id:str
    summary:str
    vectorstore_uploaded:bool
    rewritten_query:str