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
        workflow.add_edge("retriever", "context_builder")
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
