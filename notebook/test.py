from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
)

response = llm.invoke("Explain transformers in one sentence")

print(response.content)
print("*"*100)
print(response.response_metadata["token_usage"]["total_tokens"])
