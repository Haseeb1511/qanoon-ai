import json, asyncio
from fastapi.responses import StreamingResponse
import time





# ===================== Streaming Graph =====================
async def stream_graph(graph, state, config, on_complete=None, thread_id=None,first_message=None):
    """
    first_message:it is for transcibed message audio endpoint only
    """


    async def event_generator():

        tokens = []
        final_state = {}  # Capture the final state from the graph

        if first_message:
            yield f"data: {json.dumps({'transcribed_text': first_message})}\n\n"
            
        # Send thread_id first if this is a new thread (from /ask endpoint)
        if thread_id:
            yield f"data: {json.dumps({'type': 'thread_created', 'thread_id': thread_id})}\n\n"


        print("Token streaming started...")


        # IMPORTANT INFORMATION
        # WHEN WE USE LANGGRAPHH WITH STREAMING WE FACE A ISSUE
        ## WE only get STREAMING CHUNKS, not the final state
        # THEN How do WE access token_usage??
        # WITHOUT the capture code:
        # graph.astream_events() yields:
        #   ├─ on_chain_start (node: agent_response)
        #   ├─ on_chat_model_stream (token: "The")      ← You capture these for UI
        #   ├─ on_chat_model_stream (token: " penalty")  ← You capture these for UI
        #   ├─ on_chat_model_stream (token: " is...")    ← You capture these for UI
        #   └─ on_chain_end (node: agent_response)       ← THIS has our token_usage!
        #      └─ output: {token_usage: {...}, answer: "...", messages: [...]}
        # The on_chain_end event contains the complete output from our node, including all the state updates like token_usage and summary.
        # EXAMPLE:
        #    kitchen events:
        # - on_chain_start: "Started cooking"
        # - on_stream: "Smell of cooking burger..."  ← Customer experiences this
        # - on_chain_end: "Burger ready!"
        #     └─ output: {
        #         burger: "🍔",
        #         cost: "$10",           ← You need this for billing!
        #         calories: 500
        #     }
        try:
            async for event in graph.astream_events(state, config=config, version="v2"):
                # the node from which we want streaming
                node = event.get("metadata", {}).get("langgraph_node")
                # event_type = event.get("event", "")


                # Capture token_usage from agent_response node
                if event["event"] == "on_chain_end" and node == "agent_response":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        if "token_usage" in output:
                            final_state["token_usage"] = output["token_usage"]


                # Capture state updates from summarize node
                if event["event"] == "on_chain_end" and node == "summarize":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict) and "summary" in output:
                        final_state["summary"] = output["summary"]
                        # print(f"Captured summary from summarize node: {output['summary'][:100]}...")
                
                # workflow.add_node("agent_response", nodes.agent_response) ==> as we have this node we check that we only stream from this node(agent)
                # Streaming started here (we have to close it also)
                if (
                        event["event"] == "on_chat_model_stream"
                        and node == "agent_response"
                    ):
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and getattr(chunk, "content", None):
                        tokens.append(chunk.content) # we also append token in list as to persist the wole content is databse as otherwise we are genrating token by token so it will save incorrectly in database
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                        await asyncio.sleep(0)
                        
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"
            return
        
        print("Token streaming finished.")

        final_answer = "".join(tokens)  # join all the tokens in single string


        # do this after the entier streaming is finshed(here when all token are streamed and final_answer is joined then we store the the content in the database)
        if on_complete:
            try:
                await on_complete(final_answer, final_state)  # Pass final_state to on_complete
                print("on_complete callback executed successfully.")
            except Exception as e:
                print(f"Error in on_complete callback: {e}")
                # Don't yield error here - the answer was already streamed successfully
                # Just log the error and continue to send the done event


        # In SSE every msg is sent as data: <message>\n\n
        # The double newline \n\n is required by SSE protocol to signal end of the event.
        # our froned can detect this done message to know that the streaming is complete
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        print("sending event to fronend")

    print("Starting event generator...")
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache", # ensures the browser does not cache the streamed response. Each stream should be fresh.
            "X-Accel-Buffering": "no",  # used mainly with Nginx or reverse proxies to disable buffering. Without this, tokens may be delivered in large chunks instead of real-time.
            "Connection": "keep-alive" # keeps the HTTP connection open so multiple messages (tokens) can flow continuously.
        }
    )



#THIS LINE HVAE ISSUE SINCE RE-RWITTEN QUERY ALSO USE LLM IT START STREAMING REWRITTEN QUERY ALONG WIH THE LLM FINAL RESPONESE
# so we need to filter only on_chat_model_stream event for final LLM response not for re-written query
# so we can check the event metadata or tags to differentiate between them
# async for event in graph.astream_events(state, config=config, version="v2"):
#     if event["event"] == "on_chat_model_stream":


# ON_CHAT_MODEL_STREAM EVENT (OUTPUT IS LIKE THIS)
# event = {
#   "event": "on_chat_model_stream",
#   "name": "ChatOpenAI",
#   "data": {
#       "chunk": AIMessageChunk(content="Hel")
#   },
#   "tags": ["llm"],
#   "metadata": {...}
# }


# ON_CHAI_MODEL STREAM EVENT(THE OUTPUT IS LIKE THIS)
# event = {
#     "event": "on_chain_end",
#     "name": "agent_response",
#     "data": {
#         "output": {  # ← "output" key for final results
#             "token_usage": {...},
#             "answer": "The penalty is...",
#             "messages": [...]
#         }
#     },
#     "metadata": {
#         "langgraph_node": "agent_response"
#     }
# }

# # Access it like this:
# output = event.get("data", {}).get("output", {})  
# token_usage = output.get("token_usage")


# langgraph has many kind of event
# Event name	   ===> Meaning
# on_chain_start	===> A chain/node started
# on_chain_end	===> A chain/node finished
# on_chat_model_start ===>	LLM started
# on_chat_model_stream ===>	LLM produced a token
# on_chat_model_end  ===>	LLM finished
# on_tool_start	 ===> Tool execution started
# on_tool_end ===>	Tool execution finished










# User asks first question → /ask called
# Backend streams: {"type": "thread_created", "thread_id": "abc123"} ← first event
# Frontend immediately sets activeThread = { thread_id: "abc123" }
# User asks second question → activeThread exists → /follow_up called 