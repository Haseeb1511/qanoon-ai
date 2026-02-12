import os,sys
from dotenv import load_dotenv
from src.graph.nodes import GraphNodes,AgentState
load_dotenv()


from src.agent.model_loader import llm,EMBEDDING
from src.db_connection.connection import supabase_client
from langgraph.graph import START,END,StateGraph


nodes = GraphNodes(embedding_model=EMBEDDING,
                   llm=llm,
                   supbase_client=supabase_client)



class GraphBuilder:
    def __init__(self,checkpointer):
        self.app = None
        self.checkpointer = checkpointer

    
    def build_graph(self):
        workflow = StateGraph(AgentState)
        # nodes
        workflow.add_node("document_ingestion",nodes.document_ingestion)
        workflow.add_node("query_rewriter", nodes.query_rewriter)
        workflow.add_node("retriever", nodes.retriever)

        workflow.add_node("retrieval_grader", nodes.retrieval_grader)  # CRAG: grade docs
        workflow.add_node("query_transformer", nodes.query_transformer)  # CRAG: rewrite query on retry
        
        workflow.add_node("context_builder", nodes.context_builder)
        workflow.add_node("agent_response", nodes.agent_response)
        workflow.add_node("summarize", nodes.summary_creation)
        workflow.add_node("check_pdf", nodes.check_pdf_already_uploaded)
        workflow.add_node("set_doc_id", nodes.set_doc_id)

        # edges
        workflow.add_edge(START, "set_doc_id")
        workflow.add_edge("set_doc_id", "check_pdf")
        workflow.add_conditional_edges(
            "check_pdf",
            nodes.conditional,
            {
                "document_ingestion": "document_ingestion",
                "query_rewriter": "query_rewriter"
            }
        )

        # if new vector store path
        workflow.add_edge("document_ingestion","query_rewriter")

        workflow.add_edge("query_rewriter", "retriever")

        # CRAG: retriever → grade docs → decide (generate or retry)
        workflow.add_edge("retriever", "retrieval_grader")
        workflow.add_conditional_edges(
            "retrieval_grader",
            nodes.decide_to_generate,
            {
                "context_builder": "context_builder",
                "query_transformer": "query_transformer"
            }
        )
        workflow.add_edge("query_transformer", "retriever")  # CRAG retry loop

        workflow.add_edge("context_builder", "agent_response")

        workflow.add_conditional_edges(
            "agent_response",
            nodes.should_summzarizer,
            {
                True: "summarize",
                False: END
            }
        )
        workflow.add_edge("summarize", END)

        self.app = workflow.compile(checkpointer=self.checkpointer)
        return self.app
    


    def __call__(self):
        return self.build_graph()




# For langsmith Studio 
# Default export for LangGraph Studio
from langgraph.checkpoint.memory import MemorySaver
graph = GraphBuilder(checkpointer=MemorySaver()).build_graph()


# or using cli
# pip install langgraph-cli
# pip install -U "langgraph-cli[inmem]"
# langgraph dev
# python -m pip install -e .   # it install our project folder as a package (module)
# LangGraph API already manages persistence automatically.
# So it does NOT allow custom checkpointer.