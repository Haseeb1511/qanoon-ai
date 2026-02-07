import os
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage
)
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_community.vectorstores.pgvector import PGVector
from langchain_postgres import PGVector
from tqdm import tqdm
from langchain.messages import RemoveMessage # to delete something from state permenantly
from langchain_community.document_loaders import DirectoryLoader
from sqlalchemy.pool import NullPool

import asyncio

# import from other custom modules
from src.graph import state
from src.prompts.rag_prompt import PROMPT_TEMPLATE
from src.db_connection.connection import CONNECTION_STRING 
from src.utils.file_hash import get_file_hash
from src.graph.state import AgentState
from fastapi.concurrency import run_in_threadpool

# SUPBAE CLIENT IS SYNCHRONOUS SO WE USE run_in_threadpool TO AVOID BLOCKING THE MAIN THREAD
from src.db_connection.connection import supabase_client
from langchain_community.retrievers import BM25Retriever
# from langchain.schema import Document
from langchain_core.documents import Document


#for streaming token count 
from langchain_community.callbacks import get_openai_callback


def rrf_merge(bm25_docs, dense_docs, k=60, top_n=5):
    """
    Reciprocal Rank Fusion to merge BM25 and dense retrieval results.
    Uses page_content as unique identifier since LangChain Documents don't have IDs.
    Returns the actual Document objects, not just IDs.
    Dense retrieval gets 2x weight since semantic matching is more accurate for legal queries.
    """
    scores = {}
    doc_map = {}  # Map content hash to document for retrieval

    # BM25 results with standard weight (1x)
    for rank, doc in enumerate(bm25_docs or []):
        # Use content hash as unique identifier
        doc_key = hash(doc.page_content)
        doc_map[doc_key] = doc
        scores[doc_key] = scores.get(doc_key, 0.0) + 1 / (k + rank + 1)

    # Dense results with 2x weight (semantic is more reliable for legal)
    for rank, doc in enumerate(dense_docs or []):
        doc_key = hash(doc.page_content)
        doc_map[doc_key] = doc
        scores[doc_key] = scores.get(doc_key, 0.0) + 2 * (1 / (k + rank + 1))  # 2x weight

    if not scores:
        return []

    # Sort by score and return actual Document objects
    sorted_keys = sorted(scores, key=scores.get, reverse=True)[:top_n]
    return [doc_map[key] for key in sorted_keys]




class GraphNodes:
    def __init__(self,embedding_model,llm,supbase_client):
        self.embedding_model = embedding_model
        self.llm = llm
        self.supabase_client = supbase_client
            
    
    
    def set_doc_id(self,state:AgentState):
        # Skip if doc_id already exists 
        if state.get("doc_id"):
            return state
            
        path = os.path.abspath(state["documents_path"])
        
        if not os.path.isfile(path):
            raise ValueError("Directoy uploaded not supported with hashing yet")
        state["doc_id"] = get_file_hash(path)
        return state


    # as uspbase = network call  so we make async function to avoid blocking the main thread and also we can do other task while waiting for response from supbase
    async def check_pdf_already_uploaded(self,state:AgentState):
        """Checkif PDF already exist in SUpbase
        Same PDF:    
        - Different user
        - Will embed again (correct behavior)
        """
        # first check if vectostore already exist
        if state.get("vectorstore_uploaded"):
            return state
        # we check id documnet exist already or not and also check for user  if for sepcific user it exist or not (sometime one user might have already uploaded the same document )
        
        # as supbase client does not suppor async we use run in threadpool
        # run_in_threadpool expects a callable (lambda), not the result of the call
        response = await run_in_threadpool(
            lambda: self.supabase_client.table("documents")
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



    async def document_ingestion(self,state: AgentState):

        if state.get("vectorstore_uploaded"):
            print("Skipping vectoingestion - PDF already exist")
            state["vectorstore_uploaded"] = True
            return state
        
        path = os.path.abspath(state["documents_path"])  # ensure absolute

        if not os.path.isfile(path):
            raise ValueError(f"Invalid documents_path: {path}")
        

        loader = PyPDFLoader(path)
        documents = loader.load()

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000,chunk_overlap=200)
        chunks = splitter.split_documents(documents)

        # langchain chunk metadata is first updated
        # langchain chunk metadata (each chunk of document will have this metadata (it will not have page content - only metadata))
        for i,chunk in enumerate(chunks):
            source_path = chunk.metadata.get("source","")
            file_name = os.path.basename(source_path) if source_path else "unknow.pdf"

            metadata = {
                "user_id":state["user_id"],
                "doc_id":state["doc_id"],
                "chunk_index":i,
                "file_name":file_name,
                "page":chunk.metadata.get("page")  
            }
            # update langchian chunk metadata usd by pgvector
            chunk.metadata.update(metadata)

        vectorstore = PGVector(
            connection=CONNECTION_STRING,
            collection_name=state["collection_name"],
            embeddings=self.embedding_model,
            use_jsonb=True,
            engine_args={"poolclass": NullPool}  # disable pooling
        )
        batch_size=50
        # upload embedding 
        for i in tqdm(range(0, len(chunks), batch_size), desc="Uploading chunks"):
            batch = chunks[i:i + batch_size]
            # async 
            await run_in_threadpool(vectorstore.add_documents, batch)
            # vectorstore.add_documents(batch)
        

        # Insert metadata to supbase table
        rows = [{   
                "user_id":state["user_id"],
                "doc_id": state["doc_id"],
                "chunk_index": i,
                "file_name": chunk.metadata["file_name"],
                "page": chunk.metadata.get("page"),
                "content": chunk.page_content,
        } for i,chunk in enumerate(chunks)
        ]
        if rows:
            try:
                await run_in_threadpool(
                    lambda: self.supabase_client.table("documents").insert(rows).execute()
                )
            except Exception:
                print("Chunks already exist — skipping insert")
    
        print(f"Uploaded {len(chunks)} chunks")

        state["vectorstore_uploaded"] = True
        return state




    async def query_rewriter(self,state: AgentState):
        """Rewrite follow-up questions to be standalone using conversation context"""
        
        human_messages = [m for m in state.get("messages", []) if isinstance(m, HumanMessage)]
        current_query = human_messages[-1].content
        
        # If there's conversation history, rewrite the query
        if len(state.get("messages", [])) > 1:
            
            # Build conversation context
            memory_text = state.get("summary") or ""
            if not memory_text:
                conversation_history = []
                for m in state.get("messages", [])[:-1]:  # Exclude current question
                    role = "User" if isinstance(m, HumanMessage) else "Assistant"
                    conversation_history.append(f"{role}: {m.content}")
                memory_text = "\n".join(conversation_history)
            
            # Rewrite query to be standalone
            rewrite_prompt = f"""Given this conversation history:
                {memory_text}

                Rewrite the following question to be standalone (include necessary context from history):
                Question: {current_query}

                Standalone question:"""
            
            response = await self.llm.ainvoke([HumanMessage(content=rewrite_prompt)])
            rewritten_query = response.content.strip()
            
            print(f"Original: {current_query}")
            print(f"Rewritten: {rewritten_query}")
            
            
            # Store rewritten query for retrieval
            state["rewritten_query"] = rewritten_query
            print("Debugging(in state) Rewritten query for follow-up:", state.get("rewritten_query"))
        else:
            state["rewritten_query"] = current_query
        
        return state


    # Hybrid Retrieval: BM25 (keyword) + Dense (semantic) using EnsembleRetriever
    async def retriever(self, state: AgentState):
        # 1. Load document chunks from Supabase for BM25
        response = await run_in_threadpool(
            lambda: self.supabase_client
            .table("documents")
            .select("content, chunk_index, page, file_name")
            .eq("doc_id", state["doc_id"])
            .eq("user_id", state["user_id"])
            .execute()
        )
        
        if not response.data:
            state["retrieved_docs"] = []
            return state
        
        # Convert to LangChain Document objects for BM25
        bm25_docs = [
            Document(
                page_content=row["content"],
                metadata={
                    "doc_id": state["doc_id"],
                    "user_id": state["user_id"],
                    "chunk_index": row["chunk_index"],
                    "page": row["page"],
                    "file_name": row["file_name"]
                }
            )
            for row in response.data
        ]
        
        # BM25 Retriever key word base it search directly from documnets
        bm25_retriever = BM25Retriever.from_documents(bm25_docs, k=3)
        
        # Dense Retriever semantic base it search from vector store
        vectorstore = PGVector(
            connection=CONNECTION_STRING,
            collection_name=state["collection_name"],
            embeddings=self.embedding_model,
            use_jsonb=True,
            engine_args={"poolclass": NullPool}
        )
        dense_retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": 4,
                "filter": {"doc_id": state["doc_id"], "user_id": state["user_id"]}
            }
        )
        
        # Use rewritten query if available (from query_rewriter node), else fall back to raw message
        query = state.get("rewritten_query") or state["messages"][-1].content
        
        # Get results from both retrievers IN PARALLEL (faster than sequential)
        bm25_results, dense_results = await asyncio.gather(
            run_in_threadpool(bm25_retriever.invoke, query),
            run_in_threadpool(dense_retriever.invoke, query)
        )
        
        # Merge using RRF (Reciprocal Rank Fusion)
        retrieved_docs = rrf_merge(bm25_results, dense_results, k=60, top_n=4)
        
        state["retrieved_docs"] = retrieved_docs
        return state


    # file_name is added during text splitting
    # page exists → PyPDFLoader adds this automatically
    # as it is in the middile of our graph which is async we have to make it async also
    async def context_builder(self,state:AgentState):
            retrieved_docs = state.get("retrieved_docs",[])
            if not state["retrieved_docs"]:
                state["context"] = ""
                state["answer"] = ("I could not find relevant information in the provided document.")
            else:

                context = "\n\n".join(
                    f"[Source: {doc.metadata.get('file_name', 'Unknown')} "
                    f"- Page {doc.metadata.get('page', 'N/A')}]\n"    # page no
                    f"{doc.page_content}"
                    for doc in retrieved_docs
                )
                state["context"] = context
            
            # Yield control back to event loop to avoid blocking
            await asyncio.sleep(0)
            return state



    async def summary_creation(self,state:AgentState):
        existing_summary = state["summary"] # we first load existing summary

        # We have two scenrio:
        # 1. We might already have summary
        # 2. or We are Genrating summary fir the first time
        if existing_summary:
            prompt = (
                f"Existing summary:\n{existing_summary}\n\n"
                "Extend the summary using new conversation above"
            )
        else:
            prompt = "summarize the conversation above"

        message_for_summary = state["messages"] + [HumanMessage(content=prompt)]

        print("Callin summary LLM") # debugging
        # generate summary
        response = await self.llm.ainvoke(message_for_summary)

        # now delete the orignal messages that have been summarized
        message_to_delete = state["messages"][:-2] if len(state["messages"]) > 2 else []

        return {
            "summary":response.content,
            "messages":[RemoveMessage(id=m.id) for m in message_to_delete]
        }


    def should_summzarizer(self,state:AgentState):
        return len(state["messages"]) > 6



    # cat node with memory
    async def agent_response(self,state: AgentState):
        """
        Generates the LLM response for the current query, injecting memory (summary or previous messages)
        and RAG context into the prompt.
        """
        context = state.get("context", "")

        # Get all human messages
        human_messages = [m for m in state.get("messages", []) if isinstance(m, HumanMessage)]
        if not human_messages:
            raise ValueError("No human message found in state for retrieval")

        query = human_messages[-1].content

        prompt_messages = []

        # Memory injection 
        # Use summary if it exists, otherwise include all previous messages
        memory_text = state.get("summary", "")
        if not memory_text:
            conversation_history = []
            for m in state.get("messages", []):
                role = "User" if isinstance(m, HumanMessage) else "Assistant"
                conversation_history.append(f"{role}: {m.content}")
            memory_text = "\n".join(conversation_history) if conversation_history else "No previous conversation."

        # Inject memory as system message
        prompt_messages.append(SystemMessage(content=f"Conversation Memory:\n{memory_text}"))

        # RAG context + current query 
        formatted_prompt = PROMPT_TEMPLATE.format(
            context=context,
            question=query
        )
        prompt_messages.append(HumanMessage(content=formatted_prompt))

        print("Calling Agent Response LLM")  # debugging

        # response = self.llm.invoke(prompt_messages)
        with get_openai_callback() as cb:
            response = await self.llm.ainvoke(prompt_messages)
            print("Total tokens:", cb.total_tokens)   #Total tokens = question + answer (plus some extras)
            print("Prompt tokens:", cb.prompt_tokens)  # user query + system prompt + conversation history ==> everything before the model starts answering
            print("Completion tokens:", cb.completion_tokens)  # anser token generated by model(AI response)

        # THIS WORK WHEN WE USE STREAMING
        total_tokens = cb.total_tokens
        prompt_tokens = cb.prompt_tokens
        completion_tokens = cb.completion_tokens

        #THIS WORK WITH OUT STREAMING BUT NOT WITH STREAMING
        # token_usage = response.response_metadata.get("token_usage", {})
        # total_tokens = token_usage.get("total_tokens", 0)
        # print(f"Response metadata: {response.response_metadata}")
        # print(f"Total tokens: {total_tokens}")
        
        # print("pushing tokens usage to supabase")
        # await run_in_threadpool(
        #     lambda: supabase_client.table("usage").insert({
        #             "user_id": state["user_id"],
        #             "doc_id": state["doc_id"],
        #             "total_tokens": total_tokens,
        #             "prompt_tokens":prompt_tokens,
        #             "completion_tokens":completion_tokens,
        #             "query": state["messages"][-1].content,
        #             "answer": response.content
        #             }).execute()
        #     )

        # store token in state 
        state["token_usage"] = {
            "total_tokens": cb.total_tokens,
            "prompt_tokens": cb.prompt_tokens,
            "completion_tokens": cb.completion_tokens,
            "query": query,
            "answer": response.content
            }
        # Save AI response in state
        state["messages"].append(AIMessage(content=response.content))
        state["answer"] = response.content

        return state



    def conditional(self, state: AgentState):
        if state.get("vectorstore_uploaded", False):
            return "query_rewriter"   # already exists → query
        else:
            return "document_ingestion"  # new → ingest






# Network calls (Supabase, OpenAI) → async 
# File I/O operations → async with run_in_threadpool 
# LLM invocations → using ainvoke 

# ASYNC HELP WHERN THIER ARE MULTIPLE USER SO IT DOES  NOT BLOCK THE SERVER WHICH CAUSE ISSUE FOR OTHER USER




# DATABASE CALL USALLY ASYNC


#Waiting on something (timeouts, retries, backoff)



# ===> When you should NOT use asyn
# CPU-bound work (keep sync)
# PDF parsing
# Text splitting
# Hashing files
# Regex
# JSON manipulation
# Prompt formatting






# NullPool means no connection reuse. With 100 concurrent users,
# you'd create 100+ simultaneous database connections.



# from sqlalchemy import create_engine
# from sqlalchemy.pool import QueuePool

# # Create a shared engine with connection pooling
# shared_engine = create_engine(
#     CONNECTION_STRING,
#     poolclass=QueuePool,
#     pool_size=10,          # Max connections to keep open
#     max_overflow=20,       # Additional connections when pool is full
#     pool_pre_ping=True,    # Verify connections before using
#     pool_recycle=3600      # Recycle connections after 1 hour
# )

# # Then in nodes.py - retriever method
# async def retriever(self, state: AgentState):     
#     vectorstore = PGVector(
#         connection=CONNECTION_STRING,
#         collection_name=state["collection_name"],
#         embeddings=self.embedding_model,
#         use_jsonb=True,
#         create_engine_kwargs={
#             "poolclass": QueuePool,
#             "pool_size": 10,
#             "max_overflow": 20,
#             "pool_pre_ping": True
#         }
#     )
  