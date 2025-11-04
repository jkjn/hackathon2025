# Deployment Guide

This guide provides step-by-step instructions for deploying the CVE/KEV scraper Lambda function.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Test locally (optional)
python test_local.py

# 3. Build SAM application
sam build

# 4. Deploy
sam deploy --guided
```

## Detailed Deployment Steps

### Step 1: Prerequisites

Ensure you have:

- [x] AWS CLI installed and configured
- [x] AWS SAM CLI installed
- [x] Python 3.11+ installed
- [x] Appropriate AWS permissions

#### Install AWS SAM CLI

**macOS:**
```bash
brew install aws-sam-cli
```

**Linux:**
```bash
# Download the installer
wget https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip

# Unzip and install
unzip aws-sam-cli-linux-x86_64.zip -d sam-installation
sudo ./sam-installation/install
```

**Windows:**
Download from [AWS SAM CLI releases](https://github.com/aws/aws-sam-cli/releases/latest)

#### Verify Installation

```bash
sam --version
aws --version
python --version
```

### Step 2: Create Bedrock Knowledge Base

1. **Open AWS Console** → Navigate to Amazon Bedrock

2. **Create Knowledge Base:**
   - Click "Knowledge bases" in left menu
   - Click "Create knowledge base"
   - Name: `vulnerability-rag-kb`
   - Description: `CVE and KEV vulnerability database for RAG`
   - IAM Role: Create new service role

3. **Configure Data Source:**
   - Click "Next"
   - Data source name: `vulnerability-data-source`
   - S3 URI: `s3://YOUR-BUCKET-NAME/vulnerability-data/`
   - Click "Next"

4. **Select Embedding Model:**
   - Choose: `Titan Embeddings G1 - Text` (recommended)
   - Or: `Cohere Embed English` or `Cohere Embed Multilingual`
   - Click "Next"

5. **Configure Vector Database:**
   - Option 1: Quick create (managed OpenSearch Serverless)
   - Option 2: Use existing OpenSearch or other vector DB
   - Click "Next" and "Create"

6. **Save IDs:**
   ```
   Knowledge Base ID: KB1234567890EXAMPLE
   Data Source ID: DS0987654321EXAMPLE
   ```

### Step 3: Create S3 Bucket (Optional)

If you don't have an S3 bucket yet:

```bash
# Create bucket
aws s3 mb s3://my-vulnerability-data-bucket

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket my-vulnerability-data-bucket \
  --versioning-configuration Status=Enabled

# Block public access
aws s3api put-public-access-block \
  --bucket my-vulnerability-data-bucket \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

### Step 4: Get NVD API Key (Recommended)

1. Visit [NVD API Request Page](https://nvd.nist.gov/developers/request-an-api-key)
2. Enter your email address
3. Check your email for the API key
4. Save the key securely

**Benefits of API Key:**
- Without key: 5 requests per 30 seconds
- With key: 50 requests per 30 seconds (10x faster)

### Step 5: Local Testing (Optional)

Test the scrapers before deploying:

```bash
# Install dependencies
pip install -r requirements.txt

# Run test script
python test_local.py

# Check output
cat sample_cves.json
cat sample_kevs.json
```

### Step 6: Build SAM Application

```bash
# Navigate to project directory
cd hackathon2025

# Build the application
sam build

# Verify build
ls -la .aws-sam/build/
```

### Step 7: Deploy with SAM

#### First-Time Deployment (Guided)

```bash
sam deploy --guided
```

You'll be prompted for:

```
Setting default arguments for 'sam deploy'
=========================================
Stack Name [sam-app]: cve-kev-scraper
AWS Region [us-east-1]: us-east-1
Parameter KnowledgeBaseId []: KB1234567890EXAMPLE
Parameter DataSourceId []: DS0987654321EXAMPLE
Parameter S3BucketName []: my-vulnerability-data-bucket
Parameter S3Prefix [vulnerability-data]: vulnerability-data
Parameter ScheduleExpression [rate(1 day)]: rate(1 day)
Parameter NVDApiKey []: your-nvd-api-key-here
#Shows you resources changes to be deployed and require a 'Y' to initiate deploy
Confirm changes before deploy [y/N]: y
#SAM needs permission to be able to create roles to connect to the resources in your template
Allow SAM CLI IAM role creation [Y/n]: Y
#Preserves the state of previously provisioned resources when an operation fails
Disable rollback [y/N]: N
CVEKEVScraperFunction may not have authorization defined, Is this okay? [y/N]: y
Save arguments to configuration file [Y/n]: Y
SAM configuration file [samconfig.toml]: samconfig.toml
SAM configuration environment [default]: default
```

This will create `samconfig.toml` for subsequent deployments.

#### Subsequent Deployments

After the first deployment, simply run:

```bash
sam deploy
```

### Step 8: Verify Deployment

```bash
# List Lambda functions
aws lambda list-functions \
  --query "Functions[?contains(FunctionName, 'cve-kev-scraper')].FunctionName"

# Get function details
aws lambda get-function \
  --function-name cve-kev-scraper-CVEKEVScraperFunction-XXXXX

# Check EventBridge rule
aws events list-rules \
  --name-prefix cve-kev-scraper
```

### Step 9: Test Lambda Function

```bash
# Get exact function name
FUNCTION_NAME=$(aws lambda list-functions \
  --query "Functions[?contains(FunctionName, 'cve-kev-scraper')].FunctionName" \
  --output text)

# Test with small dataset
aws lambda invoke \
  --function-name $FUNCTION_NAME \
  --payload '{"cve_limit": 10, "scrape_kevs": true}' \
  response.json

# Check response
cat response.json | jq .
```

Expected response:
```json
{
  "statusCode": 200,
  "body": "{\"timestamp\": \"2024-01-15T10:30:00\", \"cves_processed\": 10, \"kevs_processed\": 1234, \"sync_job_id\": \"JOBID123\"}"
}
```

### Step 10: Monitor First Execution

```bash
# Tail CloudWatch logs
sam logs --name CVEKEVScraperFunction --tail

# Or with AWS CLI
aws logs tail /aws/lambda/$FUNCTION_NAME --follow
```

Look for:
- ✓ "Starting CVE and KEV scraping job"
- ✓ "Fetched X CVEs"
- ✓ "Fetched X KEVs"
- ✓ "Uploaded to S3"
- ✓ "Started ingestion job"

### Step 11: Verify Data in S3

```bash
# List uploaded files
aws s3 ls s3://my-vulnerability-data-bucket/vulnerability-data/ --recursive

# Download sample file
aws s3 cp s3://my-vulnerability-data-bucket/vulnerability-data/cve/vulnerabilities_20240115_103000.json ./
```

### Step 12: Check Bedrock Knowledge Base

1. **AWS Console** → Amazon Bedrock → Knowledge bases
2. Select your knowledge base
3. Click on data source
4. Check "Last sync" status
5. Verify document count

Or via CLI:
```bash
aws bedrock-agent list-ingestion-jobs \
  --knowledge-base-id KB1234567890EXAMPLE \
  --data-source-id DS0987654321EXAMPLE \
  --max-results 5
```

## Updating the Deployment

### Update Function Code

```bash
# Make code changes
vim lambda_function.py

# Rebuild and deploy
sam build
sam deploy
```

### Update Parameters

```bash
# Change schedule to twice daily
sam deploy --parameter-overrides ScheduleExpression="rate(12 hours)"

# Update NVD API key
sam deploy --parameter-overrides NVDApiKey="new-api-key"
```

### Update via samconfig.toml

Edit `samconfig.toml`:
```toml
[default.deploy.parameters]
parameter_overrides = "ScheduleExpression=\"rate(12 hours)\" NVDApiKey=\"new-key\""
```

Then deploy:
```bash
sam deploy
```

## Troubleshooting Deployment

### Issue: SAM CLI Not Found

```bash
# Verify installation
which sam

# Reinstall if needed
brew reinstall aws-sam-cli  # macOS
```

### Issue: Insufficient IAM Permissions

Ensure your AWS user/role has:
- `cloudformation:*`
- `lambda:*`
- `iam:CreateRole`
- `iam:AttachRolePolicy`
- `s3:*`
- `bedrock:*`
- `bedrock-agent:*`
- `events:*`
- `logs:*`

### Issue: S3 Bucket Already Exists

If bucket name is taken:
```bash
# Use a unique name
sam deploy --parameter-overrides S3BucketName="my-unique-vuln-data-$(date +%s)"
```

### Issue: Knowledge Base Not Found

Verify IDs:
```bash
# List knowledge bases
aws bedrock-agent list-knowledge-bases

# Get specific KB details
aws bedrock-agent get-knowledge-base --knowledge-base-id KB123...
```

### Issue: Deployment Stuck

Cancel and retry:
```bash
# Delete stack
aws cloudformation delete-stack --stack-name cve-kev-scraper

# Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name cve-kev-scraper

# Redeploy
sam deploy --guided
```

## Cleanup

To remove all resources:

```bash
# Delete SAM stack
sam delete

# Or with CloudFormation
aws cloudformation delete-stack --stack-name cve-kev-scraper

# Delete S3 bucket (if created by stack)
aws s3 rb s3://my-vulnerability-data-bucket --force

# Delete CloudWatch logs
aws logs delete-log-group --log-group-name /aws/lambda/cve-kev-scraper-CVEKEVScraperFunction-XXXXX
```

## Next Steps

After successful deployment:

1. **Set up monitoring**: Configure CloudWatch alarms and SNS notifications
2. **Test queries**: Use Bedrock API to query the knowledge base
3. **Optimize schedule**: Adjust based on your needs (daily, weekly, etc.)
4. **Review costs**: Monitor AWS costs in billing dashboard
5. **Customize filters**: Modify scrapers to focus on specific CVEs/KEVs

## Support

For deployment issues:
- Check CloudWatch logs: `/aws/lambda/[function-name]`
- Review CloudFormation events in AWS Console
- Validate SAM template: `sam validate`
- Open GitHub issue with error details
