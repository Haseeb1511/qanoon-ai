# Currently in progress  -- Not yet completed


![alt text](graph.png)




# How to run this project
```bash
pip install uv
uv init
uv add -r requirements.txt


```
#
```bash
1. commit "setting and custom prompt feature working" it conitain codebase with sinlg epdf per thread
2. commit  contain multiple pdf per thread

main → single PDF per thread
feature/multi-pdf → multiple PDFs per thread


git checkout -b feature/multi-pdf   # create new branch or swtich to this branch
# then 
git add .
git commit -m "commit message"
git push origin feature/multi-pdf   # push to remote

```



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



# Google OAuth 2.0 login + JWT-based authentication/authorization



# How summary Generation work
```bash

User Q1 → Q2 → Q3 (3rd message triggers summarizer)
                    ↓
              Creates summary
                    ↓
              Saved to Supabase
                    ↓
User Q4 → Loads summary from DB
              ↓
        Query Rewriter uses summary
              ↓
        Agent Response uses summary
              ↓
        Summary extended (if messages ≥3 again)

```



# How to add Rate limit in app

```bash

| File                                   | Change                                                   |
|----------------------------------------|----------------------------------------------------------|
| backend/routes/chat.py                 | Add token limit check before `/ask` and `/follow_up`     |
| backend/routes/audio.py                | Add same check for audio endpoints                       |
| frontend/src/components/ChatWindow.jsx | Handle `429` error and show token limit message          |
| frontend/src/App.jsx                   | Optionally disable input when `userTotalTokens >= 100000`|



```




```powershell
time for update token usage 
const id = setInterval(poll, 5000);
in app.jsx
```