import os

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage
)
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores.pgvector import PGVector
from tqdm import tqdm

from langchain.messages import RemoveMessage # to delete something from state permenantly


from langchain_community.document_loaders import DirectoryLoader


from sqlalchemy.pool import NullPool

# import from other custom modules
from src.prompts.rag_prompt import PROMPT_TEMPLATE
from src.db_connection.connection import CONNECTION_STRING 
from src.utils.file_hash import get_file_hash
from src.graph.state import AgentState





class GraphNodes:
    def __init__(self,embedding_model,llm,supbase_client):
        self.embedding_model = embedding_model
        self.llm = llm
        self.supabase_client = supbase_client
            
    
    
    def set_doc_id(self,state:AgentState):
        path = os.path.abspath(state["documents_path"])
        
        if not os.path.isfile(path):
            raise ValueError("Directoy uploaded not supported with hashing yet")
        state["doc_id"] = get_file_hash(path)
        return state



    def check_pdf_already_uploaded(self,state:AgentState):
        """Checkif PDF already exist in SUpbase"""
        # first check if vectostore already exist
        if state.get("vectorstore_uploaded"):
            return state
        # it aslo check if vectorstore exist in database
        response = (self.supabase_client.table("documents").select("doc_id").eq("doc_id",state["doc_id"]).limit(1).execute())
        if response.data:
            print("Pdf already exist in supbase skipping documnet ingesion...")
            state["vectorstore_uploaded"] = True
        else:
            state["vectorstore_uploaded"] = False
        return state  


    def document_ingestion(self,state: AgentState):

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
                "doc_id":state["doc_id"],
                "chunk_index":i,
                "file_name":file_name,
                "page":chunk.metadata.get("page")  
            }
            # update langchian chunk metadata usd by pgvector
            chunk.metadata.update(metadata)

        vectorstore = PGVector(
            connection_string=CONNECTION_STRING,
            collection_name=state["collection_name"],
            embedding_function=self.embedding_model,
            use_jsonb=True,
            engine_args={"poolclass": NullPool}  # disable pooling
        )
        batch_size=50
        # upload embedding 
        for i in tqdm(range(0, len(chunks), batch_size), desc="Uploading chunks"):
            batch = chunks[i:i + batch_size]
            vectorstore.add_documents(batch)
        

        # Insert metadata to supbase table
        rows = [{
                "doc_id": state["doc_id"],
                "chunk_index": i,
                "file_name": chunk.metadata["file_name"],
                "page": chunk.metadata.get("page"),
                "content": chunk.page_content,
        } for i,chunk in enumerate(chunks)
        ]
        if rows:
            self.supabase_client.table("documents").insert(rows).execute()
    
        print(f"Uploaded {len(chunks)} chunks")

        state["vectorstore_uploaded"] = True
        return state


    def query_rewriter(self,state: AgentState):
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
                        
            response = self.llm.invoke([HumanMessage(content=rewrite_prompt)])
            rewritten_query = response.content.strip()
            
            print(f"Original: {current_query}")
            print(f"Rewritten: {rewritten_query}")
            
            # Store rewritten query for retrieval
            state["rewritten_query"] = rewritten_query
        else:
            state["rewritten_query"] = current_query
        
        return state



    # We can add Metadata filtering Here
    # We can add Metadata filtering Here
    def retriever(self,state: AgentState):     
        vectorstore = PGVector(
            connection_string=CONNECTION_STRING,
            collection_name=state["collection_name"],
            embedding_function=self.embedding_model,
            use_jsonb=True,
            engine_args={"poolclass": NullPool} # disable pooling
        )

        # Metadata filter for this specific PDF
        retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": 5,
                "filter": {"doc_id": state["doc_id"]} # only search this pdf 
            }
        )
        
        # Use rewritten query instead of original
        query = state.get("rewritten_query", state["messages"][-1].content)
        
        retrieved_docs = retriever.invoke(query)

        state["retrieved_docs"] = retrieved_docs
        return state


    # file_name is added during text splitting
    # page exists → PyPDFLoader adds this automatically
    def context_builder(self,state:AgentState):
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
            return state



    def summary_creation(self,state:AgentState):
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
        response = self.llm.invoke(message_for_summary)

        # now delete the orignal messages that have been summarized
        message_to_delete = state["messages"][:-2] if len(state["messages"]) > 2 else []

        return {
            "summary":response.content,
            "messages":[RemoveMessage(id=m.id) for m in message_to_delete]
        }


    def should_summzarizer(self,state:AgentState):
        return len(state["messages"]) > 6



    # cat node with memory
    def agent_response(self,state: AgentState):
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
        response = self.llm.invoke(prompt_messages)

        # Save AI response in state
        state["messages"].append(AIMessage(content=response.content))
        state["answer"] = response.content

        return state



    def conditional(self, state: AgentState):
        if state.get("vectorstore_uploaded", False):
            return "query_rewriter"   # already exists → query
        else:
            return "document_ingestion"  # new → ingest
