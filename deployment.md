Simple frontend → GitHub → Vercel (auto-deploy)

Backend only → Docker → AWS (ECR + EC2)
They are independent pipelines, which is the correct architecture.

## Fronend
Frontend (GitHub → Vercel)

Vercel connected to GitHub

On every push:

Vercel builds

Vercel deploys


## Backend
Backend (GitHub Actions → AWS)

Trigger: push to main

GitHub Actions:

Build Docker image

Push to ECR

SSH into EC2

Pull image

Restart container


```bash

docker pull <aws_account>.dkr.ecr.<region>.amazonaws.com/imdb-backend:latest

docker run -d \
  --name imdb-backend \
  -p 8000:8000 \
  --restart always \
  <aws_account>.dkr.ecr.<region>.amazonaws.com/imdb-backend:latest


```



```bash


Git Push
│
├── Frontend → Vercel (auto)
│
└── Backend → GitHub Actions
               → Docker build
               → ECR push
               → EC2 pull & restart


```