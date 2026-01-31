from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from dotenv import load_dotenv
load_dotenv()
from langchain_openai import ChatOpenAI



# chatting llm
llm = ChatOpenAI(model="gpt-4o-mini",temperature=0,streaming=True)
#embedding llm
EMBEDDING = OpenAIEmbeddings(model="text-embedding-3-small")

