# QanoonAI Deployment Guide

Frontend → GitHub → Vercel (auto-deploy)
Backend  → Docker → AWS (ECR + EC2)

They are independent pipelines, which is the correct architecture.

---

## Frontend (GitHub → Vercel)

- Vercel is connected to GitHub
- On every push to `main`, Vercel **auto-builds and deploys** the frontend
- No CI/CD file needed — Vercel handles it natively

---

## Backend (GitHub Actions → AWS)

**Trigger:** Push to `main` (only when backend files change)

**Pipeline:**
```
Git Push (main)
  │
  └── GitHub Actions (.github/workflows/deploy.yml)
        ├── Build Docker image (backend/Dockerfile.fastapi)
        ├── Push to Amazon ECR (qanoonai-backend:latest)
        └── SSH into EC2
              ├── Pull latest image from ECR
              ├── Stop old container
              └── Start new container on port 8000
```

---

## AWS Setup Checklist

### 1. IAM User (for GitHub Actions)
- Create user: `qanoon-ai`
- Attach policy: `AmazonEC2ContainerRegistryFullAccess`
- Create **Access Key** (Third-party service) → save Key ID & Secret

 you do NOT need to log in as the IAM user. Here's how it works:

* The IAM user is only for GitHub Actions (programmatic access)
* You stay logged into AWS Console with your root/admin account to do all the setup steps (create ECR repo, launch EC2, etc.)
* The IAM user's Access Key & Secret are only used by GitHub Actions behind the scenes — you just paste them into GitHub Secrets
* Think of it as: you manage AWS, the IAM user is a "robot account" for CI/CD




Step	Logged in as	Where
Create IAM user qanoon-ai	✅ Your root/admin account	AWS Console
Create ECR repo qanoonai-backend	✅ Your root/admin account	AWS Console
Launch EC2 instance	✅ Your root/admin account	AWS Console
SSH into EC2 & install Docker	✅ SSH with .pem key	Terminal
Add secrets to GitHub	N/A	GitHub Settings


### 2. ECR Repository
- Create **private** repository: `qanoonai-backend`
- Note the registry URI: `<account_id>.dkr.ecr.<region>.amazonaws.com`

### 3. EC2 Instance
- **AMI:** Ubuntu 22.04 LTS
- **Instance type:** `t2.micro` (free tier) or `t2.small` / `t3.small`
- **Key Pair:** Create `.pem` key and save it
- **Security Group inbound rules:**

| Type       | Port | Source      |
|------------|------|-------------|
| SSH        | 22   | Your IP     |
| Custom TCP | 8000 | 0.0.0.0/0   |
| source      |   | 0.0.0.0/0   |

### 4. EC2 Instance Setup (SSH in)
Go to EC2 → Instances → select your instance → click **Connect**

```bash
# --- Step 1: Install Docker (official script, works on all Ubuntu versions) ---
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Allow ubuntu user to run docker without sudo
sudo usermod -aG docker ubuntu

# Apply docker group instantly (no need to logout/login)
newgrp docker



# --- Step 2: Install AWS CLI v2 (apt version is broken on Ubuntu 24.04) ---
sudo apt-get install -y unzip
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify both installed correctly
docker --version
aws --version



# --- Step 3: Configure AWS CLI (so EC2 can pull images from ECR) ---
aws configure
# Enter: Access Key ID, Secret Access Key, region (eu-north-1), output format (json) (Ec2 secrets)



# --- Step 4: Create .env file with your app secrets ---
nano /home/ubuntu/.env
# Paste all your env vars (SUPABASE_URL, OPENAI_API_KEY, etc.)
# OPENAI_API_KEY=sk-5mECuwLsT...
# SUPABASE_URL=https://vhcpucdg...
# SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
# CONNECTION_STRING=postgresql://postgres...
# GOOGLE_CLIENT_ID=271064791200-...
# GOOGLE_CLIENT_SECRET=GOCSPX-Q76x3y...
# GOOGLE_API_KEY=AIzaSyBZzQ...
# JWT_SECRET=08abce0923df...

```

### 5. GitHub Repository Secrets
Go to **GitHub Repo → Settings → Secrets → Actions** and add:

| Secret Name              | Value                                                     |
|--------------------------|-----------------------------------------------------------|
| `AWS_ACCESS_KEY_ID`      | IAM user access key                                       |
| `AWS_SECRET_ACCESS_KEY`  | IAM user secret key                                       |
| `AWS_DEFAULT_REGION`     | e.g. `us-east-1` or `ap-south-1`                         |
| `EC2_HOST`               | EC2 public IP or DNS                                      |
| `EC2_SSH_KEY`            | Full contents of your `.pem` file                         |
| `ECR_REGISTRY`           | `<account_id>.dkr.ecr.<region>.amazonaws.com`             |

---

## Manual Deploy (first time or emergency)

```bash
# SSH into EC2
ssh -i your-key.pem ubuntu@<ec2-public-ip>

# Login to ECR
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account_id>.dkr.ecr.<region>.amazonaws.com

# Pull and run
docker pull <account_id>.dkr.ecr.<region>.amazonaws.com/qanoonai-backend:latest

docker run -d \
  --name qanoonai-backend \
  -p 8000:8000 \
  --restart always \
  --env-file /home/ubuntu/.env \
  <account_id>.dkr.ecr.<region>.amazonaws.com/qanoonai-backend:latest
```