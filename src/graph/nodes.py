import os
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage
)
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres import PGVector
from tqdm import tqdm
from langchain.messages import RemoveMessage
from langchain_community.document_loaders import DirectoryLoader
from sqlalchemy.pool import NullPool

# import from other custom modules
from src.graph import state
from src.prompts.rag_prompt import PROMPT_TEMPLATE
from src.db_connection.connection import CONNECTION_STRING
from src.utils.file_hash import get_file_hash
from src.graph.state import AgentState

# SUPABASE CLIENT (SYNC)
from src.db_connection.connection import supabase_client


class GraphNodes:
    def __init__(self, embedding_model, llm, supbase_client):
        self.embedding_model = embedding_model
        self.llm = llm
        self.supabase_client = supbase_client

    def set_doc_id(self, state: AgentState):
        if state.get("doc_id"):
            return state

        path = os.path.abspath(state["documents_path"])

        if not os.path.isfile(path):
            raise ValueError("Directoy uploaded not supported with hashing yet")

        state["doc_id"] = get_file_hash(path)
        return state

    def check_pdf_already_uploaded(self, state: AgentState):
        if state.get("vectorstore_uploaded"):
            return state

        response = (
            self.supabase_client
            .table("documents")
            .select("doc_id")
            .eq("doc_id", state["doc_id"])
            .eq("user_id", state["user_id"])
            .limit(1)
            .execute()
        )

        if response.data:
            print("Pdf already exist in supbase skipping documnet ingesion...")
            state["vectorstore_uploaded"] = True
        else:
            state["vectorstore_uploaded"] = False

        return state

    def document_ingestion(self, state: AgentState):
        if state.get("vectorstore_uploaded"):
            print("Skipping vectoingestion - PDF already exist")
            state["vectorstore_uploaded"] = True
            return state

        path = os.path.abspath(state["documents_path"])

        if not os.path.isfile(path):
            raise ValueError(f"Invalid documents_path: {path}")

        loader = PyPDFLoader(path)
        documents = loader.load()

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = splitter.split_documents(documents)

        for i, chunk in enumerate(chunks):
            source_path = chunk.metadata.get("source", "")
            file_name = os.path.basename(source_path) if source_path else "unknow.pdf"

            metadata = {
                "user_id": state["user_id"],
                "doc_id": state["doc_id"],
                "chunk_index": i,
                "file_name": file_name,
                "page": chunk.metadata.get("page")
            }
            chunk.metadata.update(metadata)

        vectorstore = PGVector(
            connection=CONNECTION_STRING,
            collection_name=state["collection_name"],
            embeddings=self.embedding_model,
            use_jsonb=True,
            engine_args={"poolclass": NullPool}
        )

        batch_size = 50
        for i in tqdm(range(0, len(chunks), batch_size), desc="Uploading chunks"):
            batch = chunks[i:i + batch_size]
            vectorstore.add_documents(batch)

        rows = [{
            "user_id": state["user_id"],
            "doc_id": state["doc_id"],
            "chunk_index": i,
            "file_name": chunk.metadata["file_name"],
            "page": chunk.metadata.get("page"),
            "content": chunk.page_content,
        } for i, chunk in enumerate(chunks)]

        if rows:
            try:
                self.supabase_client.table("documents").insert(rows).execute()
            except Exception:
                print("Chunks already exist — skipping insert")

        print(f"Uploaded {len(chunks)} chunks")

        state["vectorstore_uploaded"] = True
        return state

    def query_rewriter(self, state: AgentState):
        human_messages = [m for m in state.get("messages", []) if isinstance(m, HumanMessage)]
        current_query = human_messages[-1].content

        if len(state.get("messages", [])) > 1:
            memory_text = state.get("summary") or ""
            if not memory_text:
                conversation_history = []
                for m in state.get("messages", [])[:-1]:
                    role = "User" if isinstance(m, HumanMessage) else "Assistant"
                    conversation_history.append(f"{role}: {m.content}")
                memory_text = "\n".join(conversation_history)

            rewrite_prompt = f"""Given this conversation history:
{memory_text}

Rewrite the following question to be standalone (include necessary context from history):
Question: {current_query}

Standalone question:"""

            response = self.llm.invoke([HumanMessage(content=rewrite_prompt)])
            rewritten_query = response.content.strip()

            print(f"Original: {current_query}")
            print(f"Rewritten: {rewritten_query}")

            state["rewritten_query"] = rewritten_query
        else:
            state["rewritten_query"] = current_query

        return state

    def retriever(self, state: AgentState):
        vectorstore = PGVector(
            connection=CONNECTION_STRING,
            collection_name=state["collection_name"],
            embeddings=self.embedding_model,
            use_jsonb=True,
            engine_args={"poolclass": NullPool}
        )

        retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": 5,
                "filter": {
                    "doc_id": state["doc_id"],
                    "user_id": state["user_id"]
                }
            }
        )

        query = state.get("rewritten_query", state["messages"][-1].content)
        retrieved_docs = retriever.invoke(query)

        state["retrieved_docs"] = retrieved_docs
        return state

    def context_builder(self, state: AgentState):
        retrieved_docs = state.get("retrieved_docs", [])

        if not retrieved_docs:
            state["context"] = ""
            state["answer"] = "I could not find relevant information in the provided document."
        else:
            context = "\n\n".join(
                f"[Source: {doc.metadata.get('file_name', 'Unknown')} "
                f"- Page {doc.metadata.get('page', 'N/A')}]\n"
                f"{doc.page_content}"
                for doc in retrieved_docs
            )
            state["context"] = context

        return state

    def summary_creation(self, state: AgentState):
        existing_summary = state["summary"]

        if existing_summary:
            prompt = (
                f"Existing summary:\n{existing_summary}\n\n"
                "Extend the summary using new conversation above"
            )
        else:
            prompt = "summarize the conversation above"

        message_for_summary = state["messages"] + [HumanMessage(content=prompt)]

        response = self.llm.invoke(message_for_summary)

        message_to_delete = state["messages"][:-2] if len(state["messages"]) > 2 else []

        return {
            "summary": response.content,
            "messages": [RemoveMessage(id=m.id) for m in message_to_delete]
        }

    def should_summzarizer(self, state: AgentState):
        print("summarize node triggered")
        # Trigger summarization after 3 human turns.
        human_count = sum(1 for m in state.get("messages", []) if isinstance(m, HumanMessage))
        return human_count >= 3

    def agent_response(self, state: AgentState):
        context = state.get("context", "")

        human_messages = [m for m in state.get("messages", []) if isinstance(m, HumanMessage)]
        if not human_messages:
            raise ValueError("No human message found in state for retrieval")

        query = human_messages[-1].content

        prompt_messages = []

        memory_text = state.get("summary", "")
        if not memory_text:
            conversation_history = []
            for m in state.get("messages", []):
                role = "User" if isinstance(m, HumanMessage) else "Assistant"
                conversation_history.append(f"{role}: {m.content}")
            memory_text = "\n".join(conversation_history) if conversation_history else "No previous conversation."

        prompt_messages.append(SystemMessage(content=f"Conversation Memory:\n{memory_text}"))

        formatted_prompt = PROMPT_TEMPLATE.format(
            context=context,
            question=query
        )
        prompt_messages.append(HumanMessage(content=formatted_prompt))

        response = self.llm.invoke(prompt_messages)

        token_usage = response.response_metadata.get("token_usage", {})
        total_tokens = token_usage.get("total_tokens", 0)

        supabase_client.table("usage").insert({
            "user_id": state["user_id"],
            "doc_id": state["doc_id"],
            "tokens_used": total_tokens,
            "query": state["messages"][-1].content,
            "answer": response.content
        }).execute()

        state["messages"].append(AIMessage(content=response.content))
        state["answer"] = response.content

        return state

    def conditional(self, state: AgentState):
        if state.get("vectorstore_uploaded", False):
            return "query_rewriter"
        else:
            return "document_ingestion"
