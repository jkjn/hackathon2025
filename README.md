# CVE and KEV Scraper for AWS Bedrock Knowledge Base

This Lambda function automatically scrapes Common Vulnerabilities and Exposures (CVEs) from cve.org and Known Exploited Vulnerabilities (KEVs) from CISA, then loads them into an AWS Bedrock Knowledge Base for use with Retrieval Augmented Generation (RAG).

## Features

- **CVE Scraping**: Fetches CVEs from the National Vulnerability Database (NVD) API
- **KEV Scraping**: Retrieves Known Exploited Vulnerabilities from CISA's catalog
- **Automated Loading**: Uploads vulnerability data to S3 and syncs with Bedrock Knowledge Base
- **Scheduled Execution**: Runs on a configurable schedule (daily by default)
- **Optimized for RAG**: Formats data specifically for retrieval and question-answering tasks
- **Comprehensive Metadata**: Includes CVSS scores, affected products, remediation actions, and more

## Architecture

```
┌─────────────────┐
│  EventBridge    │  (Scheduled trigger)
│   Schedule      │
└────────┬────────┘
         │
         v
┌─────────────────┐
│     Lambda      │
│   Function      │
├─────────────────┤
│ • CVE Scraper   │──┐
│ • KEV Scraper   │  │
│ • Bedrock Loader│  │
└─────────────────┘  │
         │           │
         v           v
┌─────────────────┐ ┌──────────────┐
│   S3 Bucket     │ │  cve.org     │
│ (Vulnerability  │ │  CISA.gov    │
│     Data)       │ └──────────────┘
└────────┬────────┘
         │
         v
┌─────────────────┐
│    Bedrock      │
│ Knowledge Base  │
│     (RAG)       │
└─────────────────┘
```

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** configured
3. **AWS SAM CLI** installed ([Installation Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
4. **Python 3.11** or later
5. **Bedrock Knowledge Base** already created
6. **NVD API Key** (optional, for higher rate limits) - Get one at [NVD API](https://nvd.nist.gov/developers/request-an-api-key)

## Setup

### 1. Create Bedrock Knowledge Base

First, create a Bedrock Knowledge Base in the AWS Console:

1. Go to **Amazon Bedrock** > **Knowledge bases**
2. Click **Create knowledge base**
3. Configure:
   - Name: `vulnerability-rag-kb`
   - IAM permissions: Create new role or use existing
   - Choose embedding model (e.g., `amazon.titan-embed-text-v1`)
4. Add a data source:
   - Type: **S3**
   - S3 URI: `s3://your-bucket-name/vulnerability-data/`
   - Chunking strategy: **Default** or **Fixed-size** (recommended)
5. Note the **Knowledge Base ID** and **Data Source ID**

### 2. Clone and Configure

```bash
# Clone the repository
git clone <repository-url>
cd hackathon2025

# Install dependencies locally for testing (optional)
pip install -r requirements.txt
```

### 3. Deploy with SAM

```bash
# Build the SAM application
sam build

# Deploy with guided prompts
sam deploy --guided
```

During deployment, provide:
- **Stack Name**: e.g., `cve-kev-scraper`
- **AWS Region**: Your preferred region
- **KnowledgeBaseId**: From step 1
- **DataSourceId**: From step 1
- **S3BucketName**: Bucket for storing vulnerability data (will be created if not exists)
- **S3Prefix**: Prefix for organizing data (default: `vulnerability-data`)
- **ScheduleExpression**: How often to run (default: `rate(1 day)`)
- **NVDApiKey**: Your NVD API key (optional but recommended)

Example:
```
Parameter KnowledgeBaseId: KB123EXAMPLE
Parameter DataSourceId: DS456EXAMPLE
Parameter S3BucketName: my-vulnerability-data-bucket
Parameter S3Prefix: vulnerability-data
Parameter ScheduleExpression: rate(1 day)
Parameter NVDApiKey: ********
```

### 4. Verify Deployment

```bash
# Check Lambda function
aws lambda list-functions --query "Functions[?starts_with(FunctionName, 'cve-kev-scraper')].FunctionName"

# Check CloudWatch Events rule
aws events list-rules --name-prefix cve-kev-scraper
```

## Usage

### Manual Invocation

Invoke the Lambda function manually:

```bash
# Scrape both CVEs and KEVs (default)
aws lambda invoke \
  --function-name cve-kev-scraper-CVEKEVScraperFunction-XXXXX \
  --payload '{}' \
  response.json

# Scrape only CVEs
aws lambda invoke \
  --function-name cve-kev-scraper-CVEKEVScraperFunction-XXXXX \
  --payload '{"scrape_kevs": false}' \
  response.json

# Scrape only KEVs
aws lambda invoke \
  --function-name cve-kev-scraper-CVEKEVScraperFunction-XXXXX \
  --payload '{"scrape_cves": false}' \
  response.json

# Limit CVE results and specify date range
aws lambda invoke \
  --function-name cve-kev-scraper-CVEKEVScraperFunction-XXXXX \
  --payload '{"cve_limit": 100, "cve_start_date": "2024-01-01"}' \
  response.json

# View response
cat response.json
```

### Event Payload Options

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `scrape_cves` | boolean | Whether to scrape CVEs | `true` |
| `scrape_kevs` | boolean | Whether to scrape KEVs | `true` |
| `cve_limit` | integer | Max CVEs to fetch | All available |
| `cve_start_date` | string | CVE start date (YYYY-MM-DD) | 30 days ago |
| `cve_end_date` | string | CVE end date (YYYY-MM-DD) | Today |

### Automated Schedule

The function runs automatically based on the `ScheduleExpression` parameter:

- **Daily**: `rate(1 day)`
- **Every 12 hours**: `rate(12 hours)`
- **Daily at 2 AM UTC**: `cron(0 2 * * ? *)`
- **Weekly on Monday**: `cron(0 0 ? * MON *)`

Update the schedule:
```bash
sam deploy --parameter-overrides ScheduleExpression="rate(12 hours)"
```

## Monitoring

### CloudWatch Logs

View logs:
```bash
aws logs tail /aws/lambda/cve-kev-scraper-CVEKEVScraperFunction-XXXXX --follow
```

### CloudWatch Metrics

Key metrics to monitor:
- **Invocations**: Number of times function is invoked
- **Errors**: Number of errors
- **Duration**: Execution time
- **Throttles**: Rate limiting issues

### CloudWatch Alarms

The deployment includes an alarm for Lambda errors. Configure SNS notifications:

```bash
# Create SNS topic
aws sns create-topic --name cve-kev-scraper-alerts

# Subscribe email
aws sns subscribe \
  --topic-arn arn:aws:sns:REGION:ACCOUNT:cve-kev-scraper-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com
```

## Querying the Knowledge Base

Once data is ingested, query the Knowledge Base using Bedrock:

### Python Example

```python
import boto3
import json

bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

response = bedrock_agent_runtime.retrieve_and_generate(
    input={
        'text': 'What are the critical CVEs related to Apache Log4j?'
    },
    retrieveAndGenerateConfiguration={
        'type': 'KNOWLEDGE_BASE',
        'knowledgeBaseConfiguration': {
            'knowledgeBaseId': 'KB123EXAMPLE',
            'modelArn': 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-v2'
        }
    }
)

print(response['output']['text'])
```

### AWS CLI Example

```bash
aws bedrock-agent-runtime retrieve-and-generate \
  --input '{"text": "What are the known exploited vulnerabilities for Microsoft products?"}' \
  --retrieve-and-generate-configuration '{
    "type": "KNOWLEDGE_BASE",
    "knowledgeBaseConfiguration": {
      "knowledgeBaseId": "KB123EXAMPLE",
      "modelArn": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-v2"
    }
  }'
```

## Data Format

### CVE Document Structure

```json
{
  "id": "CVE-2024-1234",
  "type": "CVE",
  "source": "NVD",
  "text": "# CVE-2024-1234\n\n## Description\n...",
  "metadata": {
    "vulnerability_id": "CVE-2024-1234",
    "vulnerability_type": "cve",
    "source": "NVD",
    "cvss_score": "9.8",
    "cvss_severity": "CRITICAL"
  }
}
```

### KEV Document Structure

```json
{
  "id": "CVE-2024-5678",
  "type": "KEV",
  "source": "CISA",
  "text": "# Vulnerability Name\n\n## Description\n...",
  "metadata": {
    "vulnerability_id": "CVE-2024-5678",
    "vulnerability_type": "kev",
    "vendor": "Microsoft",
    "product": "Windows",
    "ransomware_use": "Known"
  }
}
```

## Cost Considerations

- **Lambda**: Free tier includes 1M requests/month and 400,000 GB-seconds
- **S3**: Storage costs for vulnerability data (typically < 1 GB)
- **Bedrock**: Costs for embeddings and queries
  - Embedding: ~$0.0001 per 1000 tokens
  - Queries: Varies by model
- **CloudWatch**: Log storage (30-day retention)

Estimated monthly cost for daily runs: **$5-20** (depending on usage)

## Troubleshooting

### Issue: Rate Limiting from NVD

**Solution**: Add NVD API key to increase rate limits from 5 to 50 requests per 30 seconds.

```bash
sam deploy --parameter-overrides NVDApiKey="your-api-key-here"
```

### Issue: Timeout Errors

**Solution**: Increase Lambda timeout or reduce data fetch range.

```yaml
# In template.yaml, increase timeout
Timeout: 900  # 15 minutes
```

### Issue: Ingestion Job Conflicts

**Error**: "ConflictException: Ingestion job already in progress"

**Solution**: Wait for the current ingestion job to complete, or check job status:

```python
from bedrock_loader import BedrockKnowledgeBaseLoader

loader = BedrockKnowledgeBaseLoader(
    knowledge_base_id='KB123EXAMPLE',
    data_source_id='DS456EXAMPLE',
    s3_bucket='my-bucket',
    s3_prefix='vulnerability-data'
)

status = loader.get_ingestion_job_status('JOB_ID')
print(status)
```

## Development

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export KNOWLEDGE_BASE_ID="KB123EXAMPLE"
export DATA_SOURCE_ID="DS456EXAMPLE"
export S3_BUCKET="my-bucket"
export S3_PREFIX="vulnerability-data"
export NVD_API_KEY="your-api-key"

# Run locally
python -c "
from lambda_function import lambda_handler
result = lambda_handler({'scrape_cves': True, 'scrape_kevs': True, 'cve_limit': 10}, None)
print(result)
"
```

### Testing Individual Modules

```python
# Test CVE scraper
from cve_scraper import CVEScraper

scraper = CVEScraper()
cves = scraper.fetch_cves(limit=5)
print(f"Fetched {len(cves)} CVEs")

# Test KEV scraper
from kev_scraper import KEVScraper

kev_scraper = KEVScraper()
kevs = kev_scraper.fetch_kevs()
print(f"Fetched {len(kevs)} KEVs")
```

## Security

- Lambda function uses least-privilege IAM permissions
- S3 bucket has encryption enabled and public access blocked
- API keys stored as encrypted environment variables
- CloudWatch logs retained for 30 days

## License

MIT License

## Contributing

Contributions are welcome! Please submit pull requests or open issues for bugs and feature requests.

## Support

For issues or questions:
1. Check CloudWatch logs for error details
2. Review the troubleshooting section
3. Open an issue on GitHub

## References

- [NVD API Documentation](https://nvd.nist.gov/developers/vulnerabilities)
- [CISA KEV Catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
- [AWS Bedrock Knowledge Base](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
