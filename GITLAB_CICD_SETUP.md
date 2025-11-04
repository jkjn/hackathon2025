# GitLab CI/CD Setup Guide

This guide explains how to set up and use the GitLab CI/CD pipeline for automated deployment of the CVE/KEV scraper Lambda function.

## Pipeline Overview

The pipeline consists of 5 stages:

```
┌──────────┐   ┌──────┐   ┌───────┐   ┌────────┐   ┌────────┐
│ Validate │ → │ Test │ → │ Build │ → │ Deploy │ → │ Verify │
└──────────┘   └──────┘   └───────┘   └────────┘   └────────┘
```

### Stages Explained

1. **Validate**: Validates SAM template and Python syntax
2. **Test**: Runs local tests to verify scraper functionality
3. **Build**: Builds the SAM application with dependencies
4. **Deploy**: Deploys to AWS (dev or prod environment)
5. **Verify**: Verifies the deployment and tests the Lambda function

## Prerequisites

- GitLab project with this repository
- AWS account with appropriate permissions
- IAM user credentials for GitLab CI/CD

## Initial Setup

### Step 1: Configure GitLab CI/CD Variables

Navigate to your GitLab project:
**Settings → CI/CD → Variables**

Add the following variables:

| Variable Name | Value | Protected | Masked | Description |
|--------------|-------|-----------|---------|-------------|
| `AWS_ACCESS_KEY_ID` | `AKIAXXXXXXXXXXXXXXXX` | ✓ | ✓ | AWS Access Key ID |
| `AWS_SECRET_ACCESS_KEY` | `xxxxxxxxxxxxxxxxxxxxx` | ✓ | ✓ | AWS Secret Access Key |
| `NVD_API_KEY` | `your-nvd-api-key` | ✗ | ✓ | Optional NVD API key |

#### Creating AWS IAM User for CI/CD

1. **Create IAM User:**
   ```bash
   aws iam create-user --user-name gitlab-cicd-deployer
   ```

2. **Attach Required Policies:**
   ```bash
   # Create custom policy for deployment
   cat > cicd-policy.json <<EOF
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "cloudformation:*",
           "lambda:*",
           "iam:CreateRole",
           "iam:DeleteRole",
           "iam:GetRole",
           "iam:PassRole",
           "iam:AttachRolePolicy",
           "iam:DetachRolePolicy",
           "iam:DeleteRolePolicy",
           "iam:PutRolePolicy",
           "iam:GetRolePolicy",
           "s3:*",
           "logs:*",
           "events:*",
           "bedrock:*",
           "bedrock-agent:*"
         ],
         "Resource": "*"
       }
     ]
   }
   EOF

   aws iam put-user-policy \
     --user-name gitlab-cicd-deployer \
     --policy-name GitLabCICDPolicy \
     --policy-document file://cicd-policy.json
   ```

3. **Create Access Keys:**
   ```bash
   aws iam create-access-key --user-name gitlab-cicd-deployer
   ```

   Save the output - you'll need:
   - `AccessKeyId`
   - `SecretAccessKey`

### Step 2: Configure Pipeline Settings (Optional)

In **Settings → CI/CD → General pipelines**:

- **Timeout**: Set to 30 minutes (default 60 is fine)
- **Custom CI/CD configuration path**: `.gitlab-ci.yml` (default)
- **Public pipelines**: Disable for security
- **Auto-cancel redundant pipelines**: Enable

### Step 3: Enable Auto DevOps (Optional)

If you want automatic deployments:

**Settings → CI/CD → Auto DevOps**
- Uncheck "Default to Auto DevOps pipeline" (we have custom pipeline)

## Configuration Details

### Deployment Parameters

The pipeline is pre-configured with:

| Parameter | Value |
|-----------|-------|
| **Region** | `us-east-2` |
| **S3 Bucket** | `eahackathon2025-team2-rag` |
| **Knowledge Base ID** | `4FGDLF4WDO` |
| **Data Source ID** | `KM5BQWXYTQ` |
| **Stack Name (Dev)** | `cve-kev-scraper-team2-dev` |
| **Stack Name (Prod)** | `cve-kev-scraper-team2-prod` |
| **Schedule** | `rate(1 day)` |

### Environment-Specific Configuration

**Development (`dev`):**
- Triggers: All branches except `main`/`master`
- S3 Prefix: `vulnerability-data/dev`
- Auto-deploys on push
- Can be cleaned up manually

**Production (`prod`):**
- Triggers: Only `main`/`master` branches
- S3 Prefix: `vulnerability-data/prod`
- **Requires manual approval** before deployment
- Persistent deployment

## Using the Pipeline

### Automatic Deployment to Dev

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/my-update
   ```

2. **Make changes and commit:**
   ```bash
   git add .
   git commit -m "Update scraper logic"
   git push origin feature/my-update
   ```

3. **Pipeline automatically runs:**
   - Validates code
   - Runs tests
   - Builds application
   - Deploys to `dev` environment
   - Verifies deployment

4. **Monitor pipeline:**
   - Go to **CI/CD → Pipelines**
   - Click on the running pipeline
   - View each stage's progress

### Manual Deployment to Production

1. **Merge to main branch:**
   ```bash
   git checkout main
   git merge feature/my-update
   git push origin main
   ```

2. **Pipeline starts but pauses at deploy:**
   - Validate, test, and build stages run automatically
   - Deploy stage shows "manual action required"

3. **Approve production deployment:**
   - Go to **CI/CD → Pipelines**
   - Click on the pipeline
   - Click the **play button** (▶) on `deploy:prod` job
   - Confirm the deployment

4. **Verify deployment:**
   - `verify:prod` job runs automatically after deployment
   - Check logs to ensure Lambda function is working

### Running Pipeline Manually

You can trigger a pipeline manually:

1. Go to **CI/CD → Pipelines**
2. Click **Run pipeline**
3. Select branch
4. Add variables if needed (optional)
5. Click **Run pipeline**

## Pipeline Jobs Reference

### Job: `validate`

**Purpose**: Validate SAM template and Python code syntax

**Runs on**: All branches and merge requests

**Commands**:
```bash
sam validate --lint
python -m py_compile *.py
```

**Failure means**: Template errors or Python syntax errors

### Job: `test`

**Purpose**: Run local tests of scrapers

**Runs on**: All branches and merge requests

**Commands**:
```bash
pip install -r requirements.txt
python test_local.py
```

**Note**: Allowed to fail (warnings won't block pipeline)

### Job: `build`

**Purpose**: Build SAM application with dependencies

**Runs on**: All branches and merge requests

**Commands**:
```bash
sam build --use-container
```

**Artifacts**: `.aws-sam/` directory (1 hour expiration)

### Job: `deploy:dev`

**Purpose**: Deploy to development environment

**Runs on**: All branches except `main`/`master`

**Environment**: `development`

**Parameters**:
- Stack: `cve-kev-scraper-team2-dev`
- S3 Prefix: `vulnerability-data/dev`

### Job: `deploy:prod`

**Purpose**: Deploy to production environment

**Runs on**: `main`/`master` branches only

**Trigger**: **Manual approval required**

**Environment**: `production`

**Parameters**:
- Stack: `cve-kev-scraper-team2-prod`
- S3 Prefix: `vulnerability-data/prod`

### Job: `verify:dev` / `verify:prod`

**Purpose**: Verify deployment and test Lambda

**Runs on**: After successful deployment

**Actions**:
- Gets Lambda function details
- Tests function invocation with small payload
- Checks S3 bucket access
- Validates EventBridge schedule

**Note**: Allowed to fail (won't block pipeline)

### Job: `cleanup:dev` / `cleanup:prod`

**Purpose**: Delete CloudFormation stack

**Trigger**: **Manual only**

**Location**: Environment page → Stop environment

**Warning**: This deletes all resources!

## Monitoring Deployments

### View Pipeline Status

**CI/CD → Pipelines**
- Green checkmark: Success
- Red X: Failed
- Orange pause: Manual action needed
- Blue circle: Running

### View Job Logs

1. Click on pipeline
2. Click on specific job
3. View real-time logs
4. Download logs if needed

### View Environments

**Deployments → Environments**
- Shows active environments (`development`, `production`)
- Click environment to see deployment history
- Stop environment to trigger cleanup job

### Check Deployment Artifacts

After deployment, check:

1. **CloudFormation Stack:**
   ```bash
   aws cloudformation describe-stacks \
     --stack-name cve-kev-scraper-team2-prod \
     --region us-east-2
   ```

2. **Lambda Function:**
   ```bash
   aws lambda list-functions \
     --region us-east-2 \
     --query "Functions[?contains(FunctionName, 'cve-kev-scraper')]"
   ```

3. **S3 Bucket Contents:**
   ```bash
   aws s3 ls s3://eahackathon2025-team2-rag/vulnerability-data/prod/ \
     --region us-east-2
   ```

## Troubleshooting

### Issue: Pipeline Fails at Validate Stage

**Error**: `sam validate` fails

**Solution**:
- Check `template.yaml` syntax
- Ensure all required fields are present
- Run `sam validate --lint` locally

### Issue: AWS Credentials Not Found

**Error**: `ERROR: AWS credentials not found`

**Solution**:
1. Check GitLab CI/CD variables are set correctly
2. Verify variable names: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
3. Ensure variables are not marked as "protected" if deploying from non-protected branches
4. Check IAM user has necessary permissions

### Issue: S3 Bucket Access Denied

**Error**: `Access Denied` when uploading to S3

**Solution**:
1. Verify S3 bucket exists: `eahackathon2025-team2-rag`
2. Check IAM user has S3 permissions
3. Verify bucket is in correct region (`us-east-2`)
4. Check bucket policy allows the IAM user

### Issue: CloudFormation Stack Already Exists

**Error**: `Stack already exists`

**Solution**:
Option 1 - Use existing stack (updates it):
- Pipeline should handle this automatically with `--no-fail-on-empty-changeset`

Option 2 - Delete and recreate:
```bash
aws cloudformation delete-stack \
  --stack-name cve-kev-scraper-team2-dev \
  --region us-east-2
```

### Issue: Lambda Deployment Package Too Large

**Error**: `Unzipped size must be smaller than...`

**Solution**:
- Use `sam build --use-container` (already configured)
- Remove unnecessary dependencies from `requirements.txt`
- Consider using Lambda Layers for large libraries

### Issue: Bedrock Knowledge Base Not Found

**Error**: Resource not found for Knowledge Base

**Solution**:
1. Verify Knowledge Base ID: `4FGDLF4WDO`
2. Check Knowledge Base is in `us-east-2` region
3. Verify IAM permissions for Bedrock
4. Ensure Data Source ID is correct: `KM5BQWXYTQ`

### Issue: Pipeline Stuck on Manual Job

**Not an error** - Production deployment requires manual approval

**Action**:
1. Review the changes
2. Click the play button on `deploy:prod` job
3. Confirm deployment

## Advanced Configuration

### Changing Deployment Schedule

Edit `.gitlab-ci.yml` or `samconfig.toml`:

```yaml
# Daily at 2 AM UTC
ScheduleExpression=\"cron(0 2 * * ? *)\"

# Every 12 hours
ScheduleExpression=\"rate(12 hours)\"

# Weekly on Monday
ScheduleExpression=\"cron(0 0 ? * MON *)\"
```

### Adding Staging Environment

1. **Create staging configuration in `.gitlab-ci.yml`:**

```yaml
deploy:staging:
  stage: deploy
  script:
    - sam deploy --config-env staging
  environment:
    name: staging
  only:
    - develop
  when: manual
```

2. **Add staging config to `samconfig.toml`:**

```toml
[staging]
[staging.deploy.parameters]
stack_name = "cve-kev-scraper-team2-staging"
s3_prefix = "sam-deployments/staging"
parameter_overrides = [
    "S3Prefix=vulnerability-data/staging"
]
```

### Running Specific Jobs

Use GitLab's job filtering:

**Run only validate and test:**
```bash
# In .gitlab-ci.yml, use rules or only/except
```

**Skip jobs:**
Add `[ci skip]` to commit message:
```bash
git commit -m "Update README [ci skip]"
```

### Notifications

Set up pipeline notifications:

**Settings → Integrations → Slack notifications**
- Enable Pipeline events
- Add webhook URL
- Customize messages

## Security Best Practices

1. **Protect sensitive branches:**
   - Settings → Repository → Protected branches
   - Protect `main` and `master`
   - Require merge request approval

2. **Mask sensitive variables:**
   - Always mask API keys and credentials
   - Use "Protected" flag for production variables

3. **Limit IAM permissions:**
   - Use principle of least privilege
   - Create separate IAM users for dev/prod if needed
   - Rotate access keys regularly

4. **Enable MFA:**
   - Require MFA for manual production deployments
   - Use GitLab's approval features

5. **Audit pipeline runs:**
   - Review pipeline history regularly
   - Check for unauthorized deployments
   - Monitor CloudWatch logs

## Cost Optimization

- **Limit pipeline runs**: Use `only`/`except` rules
- **Clean up dev environments**: Use cleanup jobs
- **Optimize container caching**: Already enabled
- **Use spot instances**: Not applicable for GitLab CI
- **Schedule deployments**: Deploy during off-peak hours

## Resources

- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)
- [AWS SAM CLI Reference](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-command-reference.html)
- [GitLab Environments](https://docs.gitlab.com/ee/ci/environments/)
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)

## Support

For issues with the pipeline:
1. Check job logs in GitLab CI/CD
2. Verify AWS credentials and permissions
3. Review CloudFormation events
4. Check this troubleshooting guide
5. Contact team lead or open an issue
