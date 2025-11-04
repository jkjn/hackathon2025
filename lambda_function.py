"""
AWS Lambda function to scrape CVEs and KEVs and load into Bedrock Knowledge Base
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any

from cve_scraper import CVEScraper
from kev_scraper import KEVScraper
from bedrock_loader import BedrockKnowledgeBaseLoader

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID')
DATA_SOURCE_ID = os.environ.get('DATA_SOURCE_ID')
S3_BUCKET = os.environ.get('S3_BUCKET')
S3_PREFIX = os.environ.get('S3_PREFIX', 'vulnerability-data')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler function

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        Response dictionary with status and message
    """
    try:
        logger.info("Starting CVE and KEV scraping job")

        # Initialize scrapers
        cve_scraper = CVEScraper()
        kev_scraper = KEVScraper()
        bedrock_loader = BedrockKnowledgeBaseLoader(
            knowledge_base_id=KNOWLEDGE_BASE_ID,
            data_source_id=DATA_SOURCE_ID,
            s3_bucket=S3_BUCKET,
            s3_prefix=S3_PREFIX
        )

        # Determine what to scrape based on event
        scrape_cves = event.get('scrape_cves', True)
        scrape_kevs = event.get('scrape_kevs', True)

        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'cves_processed': 0,
            'kevs_processed': 0,
            'errors': []
        }

        # Scrape CVEs
        if scrape_cves:
            try:
                logger.info("Fetching CVEs from cve.org")
                cves = cve_scraper.fetch_cves(
                    limit=event.get('cve_limit'),
                    start_date=event.get('cve_start_date')
                )
                logger.info(f"Fetched {len(cves)} CVEs")

                # Upload CVEs to S3 and sync with Knowledge Base
                cve_s3_key = bedrock_loader.upload_vulnerabilities(
                    vulnerabilities=cves,
                    vulnerability_type='cve'
                )
                logger.info(f"Uploaded CVEs to S3: {cve_s3_key}")

                results['cves_processed'] = len(cves)
                results['cve_s3_key'] = cve_s3_key

            except Exception as e:
                logger.error(f"Error processing CVEs: {str(e)}", exc_info=True)
                results['errors'].append(f"CVE processing error: {str(e)}")

        # Scrape KEVs
        if scrape_kevs:
            try:
                logger.info("Fetching KEVs from CISA")
                kevs = kev_scraper.fetch_kevs()
                logger.info(f"Fetched {len(kevs)} KEVs")

                # Upload KEVs to S3 and sync with Knowledge Base
                kev_s3_key = bedrock_loader.upload_vulnerabilities(
                    vulnerabilities=kevs,
                    vulnerability_type='kev'
                )
                logger.info(f"Uploaded KEVs to S3: {kev_s3_key}")

                results['kevs_processed'] = len(kevs)
                results['kev_s3_key'] = kev_s3_key

            except Exception as e:
                logger.error(f"Error processing KEVs: {str(e)}", exc_info=True)
                results['errors'].append(f"KEV processing error: {str(e)}")

        # Sync data source with Knowledge Base
        if results['cves_processed'] > 0 or results['kevs_processed'] > 0:
            try:
                logger.info("Syncing data source with Bedrock Knowledge Base")
                sync_job_id = bedrock_loader.start_ingestion_job()
                results['sync_job_id'] = sync_job_id
                logger.info(f"Started ingestion job: {sync_job_id}")
            except Exception as e:
                logger.error(f"Error syncing with Knowledge Base: {str(e)}", exc_info=True)
                results['errors'].append(f"Knowledge Base sync error: {str(e)}")

        # Prepare response
        status_code = 200 if not results['errors'] else 207  # 207 = Multi-Status (partial success)

        logger.info(f"Job completed: {json.dumps(results)}")

        return {
            'statusCode': status_code,
            'body': json.dumps(results),
            'headers': {
                'Content-Type': 'application/json'
            }
        }

    except Exception as e:
        logger.error(f"Fatal error in lambda_handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }),
            'headers': {
                'Content-Type': 'application/json'
            }
        }
