from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from dotenv import load_dotenv
load_dotenv()


# chatting llm
llm = ChatOpenAI(model="gpt-4o-mini",
                temperature=0,
                streaming=True,
                stream_usage=True,
                )
#embedding llm
EMBEDDING = OpenAIEmbeddings(model="text-embedding-3-small")

# model_kwargs={"stream_usage": True}