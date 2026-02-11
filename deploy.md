# Pipeline (Self-hosted runner on EC2 — no SSH needed):
```
Git Push (main)
  │
  └── GitHub Actions (.github/workflows/deploy.yml)
        │  (runs directly on EC2 via self-hosted runner)
        ├── Build Docker image (backend/Dockerfile.fastapi)
        ├── Push to Amazon ECR (qanoonai-backend:latest)
        ├── Pull latest image from ECR
        ├── Stop old container
        └── Start new container on port 8000
```



  
  
  




# AWS Setup Checklist

## 1. IAM User (for GitHub Actions)
- Create user: `qanoon-ai`
- Attach policy: `AmazonEC2ContainerRegistryFullAccess`
- Create **Access Key** (Third-party service) → save Key ID & Secret
- For cloud Front:
- CloudFrontFullAccess (this allow full access not recomended for production) or we can use the below custom one
```bash
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "cloudfront:CreateInvalidation",
      "Resource": "arn:aws:cloudfront::<ACCOUNT_ID>:distribution/<DISTRIBUTION_ID>"
    }
  ]
}
```

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

| Type       | Port | Source      | Purpose                              |
|------------|------|-------------|--------------------------------------|
| SSH        | 22   | 0.0.0.0/0  | GitHub Actions runners (dynamic IPs) |
| Custom TCP | 8000 | 0.0.0.0/0  | Backend API access                   |





---

## How to update the Security Group in AWS Console:
1. Go to **EC2 → Instances** → select your instance
2. Click the **Security** tab → click the **Security Group link**
3. Click **Edit inbound rules**
4. Set the **SSH (port 22)** rule source to **`0.0.0.0/0`** (select "Anywhere-IPv4")
5. Ensure **Custom TCP (port 8000)** source is **`0.0.0.0/0`**
6. Click **Save rules**
7. Go back to GitHub → **Actions** tab → re-run the failed workflow




---


# Step 1: EC2 Instance Setup (SSH in)
Go to EC2 → Instances → select your instance → click **Connect**

```bash
# Step 1: Install Docker 
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Allow ubuntu user to run docker without sudo
sudo usermod -aG docker ubuntu

# Apply docker group instantly (no need to logout/login)
newgrp docker
```




---


# Step 2: Self-Hosted GitHub Actions Runner (on EC2)
This lets GitHub Actions run directly on EC2 — no SSH needed.
go to   
``SETTING ==> ACTION ==> RUNNER ==> new self hosted runner ==> linux ==> run the given command in EC2 terminal``

``Install all the commandas``  
then install the below
```bash

## Keep action runner running in Background
cd actions-runner
# Install the runner as a service
sudo ./svc.sh install
# Start the runner service
sudo ./svc.sh start


cd ..  # move out of action runner for next commands

```




# Step 3: Install AWS CLI 
```bash
sudo apt-get install -y unzip
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify both installed correctly
docker --version
aws --version

```




# Step 4: Configure AWS CLI
```bash
# --- Step 3: Configure AWS CLI (so EC2 can pull images from ECR) ---
# This sets up credentials so your EC2 can pull images from ECR when a workflow runs.
# Must happen after AWS CLI is installed, otherwise aws configure won’t work.
aws configure
# Enter: Access Key ID, Secret Access Key, region (eu-north-1), output format (json) (Ec2 secrets)


# Step 4: Create .env file with your app secrets 
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
| `CLOUDFRONT_DISTRIBUTION_ID` | cloudfront distribution id                                |

---

# How to verify on github
1. Check Deployment Status (GitHub)
Go to your GitHub Actions tab.

* click on the latest run "Fix requirements and trigger deploy"
* If it's Green ✅, your backend is live on EC2!
* If it's Red ❌, click it → click build-and-deploy → see the error.



# How to test after Deployed on AWS

```bash
# Get your public IP
curl http://checkip.amazonaws.com  #13.60.87.193



# Replace <PUBLIC_IP> with the IP from above

# 1. Check docs page (open in browser)
http://<PUBLIC_IP>:8000/docs

# 2. Health check from terminal
curl http://<PUBLIC_IP>:8000/docs

# 3. Check the OpenAPI spec
curl http://<PUBLIC_IP>:8000/openapi.json

```



# Final step url must be HTTP
Your frontend is on HTTPS (https://qanoon-ai.vercel.app), but your backend is on HTTP (http://13.60.87.193:8000). Browsers block secure sites (HTTPS) from talking to insecure APIs (HTTP) for security reasons.


The Solution
You must make your backend HTTPS.

Since you are using a raw EC2 IP address, you can't easily get an SSL certificate for it directly.

```bash
Vercel (HTTPS)
   ↓
CloudFront (HTTPS)
   ↓
EC2 Backend (HTTP :8000)
```

## Option A: Use AWS CloudFront

CloudFront acts as a secure "mask" in front of your EC2. It gives you an HTTPS URL (e.g., https://d12345.cloudfront.net) that forwards requests to your HTTP EC2.


1. Go to AWS Console -> CloudFront -> Create Distribution.

2. Origin Domain: Enter your EC2 Public DNS (e.g., ec2-13-60-87-193.eu-north-1.compute.amazonaws.com).

  * Tip: Do not just paste the IP. Use the Public DNS name from EC2 console.
  * Chose origin type ===> other
  * in origin--> s3  --> add this public dns url
  * after creation of distribution 
  * Go to that distribution click origin ==> select origin ===> select Edit
  * In origin protocol ===> HTTP only


3. Cache Policy: Go to your Distribution==> Behaviour===>  CachingDisabled (Crucial for APIs).
 * Allowed HTTP Methods: GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE.
 * Origin Request Policy: AllViewer (Crucial to pass headers like Auth).
 * Redirect HTTP to HTTPS.


4. Wait for deploy, then copy the new CloudFront URL (https://d123...cloudfront.net).

5. Update your frontend environment variable VITE_API_URL to this new URL.

6.  important if you get forbidden cors error on cloudfront (using swagger UI)
 * got to SECURITY ===> MANAGE PROTEXTION ===> SELECT THE USE MONITOR MODE