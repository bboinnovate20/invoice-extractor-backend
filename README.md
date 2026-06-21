# Invoice Extractor — Backend

The aim of this is to practice and learn Cloud deployment, using Lambda function, AWS S3 storage, AWS IAM for User roles and management, AWS CloudWatch and AWS API gateway

---

**Backend Deployed URL**: `POST https://unk0evcl6k.execute-api.us-east-1.amazonaws.com/prod/`
**Full App Deployment**: `https://ai-invoice-extractor-p0k3vkim8-bboinnovate20s-projects.vercel.app/`

## Core Functionalities

1. Receives invoice text and column names from the client
2. Sends the text to the LLM API for structured field extraction
3. Returns the extracted data as a JSON array

OCR and Excel conversion are handled client-side — this Lambda only does AI extraction.

---

## Architecture

The application was originally designed with an **upload-first** architecture: files would be uploaded to AWS S3 (direct browser-to-S3), and a Lambda function would download them, run OCR, extract invoice fields via AI, and return an Excel file.

However, this architecture had a critical performance problem — with 40+ files, the Lambda was doing everything sequentially: downloading each PDF, running Tesseract OCR page by page, calling the AI API, and converting to Excel. This made processing extremely slow, and cold starts made it worse.

**The decision was made to move OCR to the client side.**

The current architecture works as follows: files never leave the browser until OCR is complete. The user selects PDF files locally, Tesseract.js runs OCR directly in the browser on each file, and only the extracted plain text is sent to Lambda. This means Lambda now only does one thing — calls the DeepSeek AI API to extract structured fields from the text and returns JSON.

The S3 upload pipeline (`s3.ts`, `handleUpload`) remains in the codebase but is bypassed in the current `handleSubmit` flow. Lambda returns only the structured JSON response — the client handles Excel conversion locally using SheetJS (`xlsx`).

The Lambda is exposed via AWS API Gateway HTTP API (`POST /`) rather than a Lambda Function URL, because the Function URL consistently returned 403 Forbidden despite correct IAM permissions — likely due to an account-level public access block.

---

## AWS Services Used

### Amazon ECR (Elastic Container Registry)
Stores the Docker image for the Lambda function. Every time the function is updated, a new image is built and pushed to ECR, then Lambda is pointed to the new image.

### AWS Lambda
Runs the containerized Python function. Configured with:
- **Timeout**: 300 seconds (to handle large batches)
- **Memory**: 1024 MB
- **Package type**: Container image (from ECR)
- **Runtime**: Python via Docker

### AWS API Gateway (HTTP API)
Exposes the Lambda function as a public HTTP endpoint (`POST /`).

API Gateway wraps the request body as a JSON string — the Lambda parses it with `json.loads(event['body'])`.

### AWS IAM (Identity and Access Management)
Two separate permission chains:

- **IAM User** (`ibrahim-one`) — has policies to deploy: `AWSLambda_FullAccess`, `AmazonEC2ContainerRegistryFullAccess`, `IAMFullAccess`
- **IAM Role** (`lambda-basic-role`) — assumed by the Lambda function at runtime, has `AWSLambdaBasicExecutionRole` to write logs to CloudWatch

### Amazon CloudWatch
Automatically receives Lambda logs via the `AWSLambdaBasicExecutionRole` policy. Used for debugging and monitoring invocations.

---

## Containerization

The Lambda runs as a Docker container. This was chosen over a zip deployment because:
- The function has heavy dependencies (`pandas`, `openai`)
- A container gives full control over the environment

### Dockerfile structure
```
Base image  → python lambda base image
Install     → requirements.txt
Copy        → app.py
CMD         → app.lambda_handler
```

### Local testing
```bash
# Run container locally
docker run -p 8080:8080 invoice-extractor

# Test locally
curl -X POST http://localhost:9000/2015-03-31/functions/function/invocations \
  -H "Content-Type: application/json" \
  -d '{"columns": ["supplier_name"], "text": "Invoice from British Gas..."}'
```

---

## Deploying

### First time setup
```bash
# 1. Create ECR repository
aws ecr create-repository --repository-name invoice-extractor --region us-east-1

# 2. Create IAM role
aws iam create-role \
  --role-name lambda-basic-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }]
  }'

aws iam attach-role-policy \
  --role-name lambda-basic-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# 3. Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS \
  --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# 4. Build, tag and push
docker build -t invoice-extractor .
docker tag invoice-extractor:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/invoice-extractor:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/invoice-extractor:latest

# 5. Create Lambda function
aws lambda create-function \
  --function-name invoice-extractor \
  --package-type Image \
  --code ImageUri=<account-id>.dkr.ecr.us-east-1.amazonaws.com/invoice-extractor:latest \
  --role arn:aws:iam::<account-id>:role/lambda-basic-role \
  --region us-east-1 \
  --timeout 300 \
  --memory-size 1024 \
  --environment "Variables={OPENAI_API_KEY=your-key}"

# 6. Create API Gateway
aws apigatewayv2 create-api \
  --name invoice-extractor-api \
  --protocol-type HTTP \
  --region us-east-1

aws apigatewayv2 create-integration \
  --api-id <api-id> \
  --integration-type AWS_PROXY \
  --integration-uri arn:aws:lambda:us-east-1:<account-id>:function:invoice-extractor \
  --payload-format-version 2.0 \
  --region us-east-1

aws apigatewayv2 create-route \
  --api-id <api-id> \
  --route-key "POST /" \
  --target "integrations/<integration-id>" \
  --region us-east-1

aws apigatewayv2 create-stage \
  --api-id <api-id> \
  --stage-name prod \
  --auto-deploy \
  --region us-east-1

aws lambda add-permission \
  --function-name invoice-extractor \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:<account-id>:<api-id>/*/*/" \
  --region us-east-1
```

### Every deploy after first time
```bash
docker build -t invoice-extractor .
docker tag invoice-extractor:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/invoice-extractor:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/invoice-extractor:latest
aws lambda update-function-code \
  --function-name invoice-extractor \
  --image-uri <account-id>.dkr.ecr.us-east-1.amazonaws.com/invoice-extractor:latest \
  --region us-east-1
```

---

## Environment Variables
For security
| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | LLM API key (uses OpenAI-compatible client) |

Set via:
```bash
aws lambda update-function-configuration \
  --function-name invoice-extractor \
  --environment "Variables={OPENAI_API_KEY=your-key}" \
  --region us-east-1
```

---

## API

**Endpoint**: `POST https://<api-id>.execute-api.us-east-1.amazonaws.com/prod/`

**Request**:
```json
{
  "columns": ["supplier_name", "total_amount", "invoice_date"],
  "text": "Invoice text extracted from PDF...",
  "as_json": true
}
```

**Response**:
```json
{
  "message": "Successfully converted",
  "json_content": [
    {
      "supplier_name": "British Gas",
      "total_amount": 340.00,
      "invoice_date": "2025-05-10"
    }
  ]
}
```