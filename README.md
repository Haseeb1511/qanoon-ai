# Currently in progress  -- Not yet completed

# How to run Backend
```bash

uv run uvicorn backend.app:app --reload  # to run fast api
uv run python -m backend.app # same as above but(not recomeneded with fastAPI)

```

# FronEnd
```bash
npm install
# how to run froned
npm run frontend

```

---
# TOOl used
```bash
React v19
vite 
tailwand css v4
javascript

# Backend 
Fastpai

langchain
langgraph


```



# From:
response = self.llm.invoke(prompt_messages)

# To:
response = self.llm.with_config(tags=["response"]).invoke(prompt_messages)




# upload
fix issue of rewritten query being printed 111
imporve ui    2222 
jwt authenticaiton   6666
docker trest  3333
urdu translation   5555
modulat fastapi   4444
docker fast api ---> aws
frontend  ---> vercel
