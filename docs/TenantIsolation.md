## What “tenant isolation” actually means in RAG

Tenant isolation = **no user can ever retrieve another user’s vectors**, even by accident.

This must be enforced in **3 places**:

1️⃣ **Ingestion (embedding time)**  
```python
    def check_pdf_already_uploaded(self,state:AgentState):
        """Checkif PDF already exist in SUpbase
        Same PDF:    
        - Different user
        - Will embed again (correct behavior)
        """
        # first check if vectostore already exist
        if state.get("vectorstore_uploaded"):
            return state
        # we check id documnet exist already or not and also check for user  if for sepcific user it exist or not (sometime one user might have already uploaded the same document )
        
        response = (
                        self.supabase_client.table("documents")
                        .select("doc_id")
                        .eq("doc_id",state["doc_id"])  # do id
                        .eq("user_id",state["user_id"])   # user id 
                        .limit(1)
                        .execute()
        )
        if response.data:
            print("Pdf already exist in supbase skipping documnet ingesion...")
            state["vectorstore_uploaded"] = True
        else:
            state["vectorstore_uploaded"] = False
        return state

        ```


2️⃣ **Storage (vectorstore structure)**  
```python


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
            self.supabase_client.table("documents").insert(rows).execute()
```



3️⃣ **Retrieval (query-time filtering)**  
```python
retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": 5,
                "filter": {"doc_id": state["doc_id"],"user_id":state["user_id"] } # only search this pdf  and for this user
            }
        )

If you miss **any one**, isolation breaks.

```



## Backend part

user = supabase_client.auth.get_user(access_token)

initial_state = {
    "user_id": user.user.id,   # 👈 REQUIRED
    "documents_path": pdf_path,
    "collection_name": "rag_docs",
    "messages": [HumanMessage(content=query)],
    "summary": "",
    "vectorstore_uploaded": False,
}

## Where to make changes (this is the core answer)

