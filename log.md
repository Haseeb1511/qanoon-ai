# How to View Backend Logs on AWS EC2

Since your backend is running inside a Docker container on the EC2 instance, you have two main options to view logs.

## Method 1: The Quickest Way (SSH + Docker)

This is the best method for immediate debugging.

1.  **SSH into your EC2 instance**:
    ```bash
    ssh -i "path/to/your-key.pem" ubuntu@<your-ec2-public-ip>
    ```

    *Replace `path/to/your-key.pem` with your actual key file path and `<your-ec2-public-ip>` with your instance's IP address.*

2.  **View the logs**:
    Once inside the server, run the following command to see the logs in real-time:
    ```bash
    # View logs and follow new output
    docker logs -f qanoonai-backend
    ```

    *Press `Ctrl+C` to exit the log view.*

---

## Method 2: The Professional Way (AWS CloudWatch)

If you want to view logs directly in the AWS Console (without SSH), you can configure your Docker container to send logs to CloudWatch.

### 1. Create a CloudWatch Log Group
1.  Go to the **AWS Console** > **CloudWatch**.
2.  Click **Log groups** > **Create log group**.
3.  Name it: `/aws/ec2/qanoonai-backend`.

### 2. Update Deployment Configuration
Update your `docker run` command (in `.github/workflows/deploy.yml` or your manual script) to use the `awslogs` driver:

```bash
docker run -d \
  --name qanoonai-backend \
  -p 8000:8000 \
  --restart always \
  --env-file /home/ubuntu/.env \
  --log-driver=awslogs \
  --log-opt awslogs-region=us-east-1 \
  --log-opt awslogs-group=/aws/ec2/qanoonai-backend \
  --log-opt awslogs-create-group=true \
  $ECR_REGISTRY/qanoonai-backend:latest
```

*Note: Change `us-east-1` to your actual AWS region if different.*

### 3. Usage
Once deployed with these changes, you can view logs at:
**AWS Console > CloudWatch > Log groups > /aws/ec2/qanoonai-backend**

> **Important**: Ensure your EC2 Instance Profile (IAM Role) has the `CloudWatchLogsFullAccess` policy or specific permissions (`logs:CreateLogStream`, `logs:PutLogEvents`).
