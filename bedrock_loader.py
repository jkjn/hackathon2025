"""
Bedrock Knowledge Base Loader module to upload vulnerability data to AWS Bedrock
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class BedrockKnowledgeBaseLoader:
    """
    Loader for uploading vulnerability data to AWS Bedrock Knowledge Base
    """

    def __init__(
        self,
        knowledge_base_id: str,
        data_source_id: str,
        s3_bucket: str,
        s3_prefix: str = 'vulnerability-data'
    ):
        """
        Initialize Bedrock Knowledge Base loader

        Args:
            knowledge_base_id: ID of the Bedrock Knowledge Base
            data_source_id: ID of the data source within the Knowledge Base
            s3_bucket: S3 bucket for storing vulnerability documents
            s3_prefix: S3 prefix/folder for organizing documents
        """
        self.knowledge_base_id = knowledge_base_id
        self.data_source_id = data_source_id
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix

        # Initialize AWS clients
        self.s3_client = boto3.client('s3')
        self.bedrock_agent_client = boto3.client('bedrock-agent')

    def upload_vulnerabilities(
        self,
        vulnerabilities: List[Dict[str, Any]],
        vulnerability_type: str = 'cve'
    ) -> str:
        """
        Upload vulnerability data to S3 for Knowledge Base ingestion

        Args:
            vulnerabilities: List of vulnerability dictionaries
            vulnerability_type: Type of vulnerability ('cve' or 'kev')

        Returns:
            S3 key of the uploaded file
        """
        if not vulnerabilities:
            logger.warning("No vulnerabilities to upload")
            return None

        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        s3_key = f"{self.s3_prefix}/{vulnerability_type}/vulnerabilities_{timestamp}.json"

        try:
            # Convert to JSONL format (one JSON object per line) for better RAG performance
            jsonl_content = self._create_jsonl_documents(vulnerabilities, vulnerability_type)

            # Upload to S3
            logger.info(f"Uploading {len(vulnerabilities)} {vulnerability_type.upper()}s to s3://{self.s3_bucket}/{s3_key}")

            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=jsonl_content.encode('utf-8'),
                ContentType='application/jsonlines',
                Metadata={
                    'vulnerability_type': vulnerability_type,
                    'count': str(len(vulnerabilities)),
                    'timestamp': timestamp
                }
            )

            logger.info(f"Successfully uploaded to S3: {s3_key}")
            return s3_key

        except ClientError as e:
            logger.error(f"Error uploading to S3: {str(e)}")
            raise

    def _create_jsonl_documents(
        self,
        vulnerabilities: List[Dict[str, Any]],
        vulnerability_type: str
    ) -> str:
        """
        Create JSONL formatted documents optimized for RAG

        Args:
            vulnerabilities: List of vulnerability dictionaries
            vulnerability_type: Type of vulnerability

        Returns:
            JSONL formatted string
        """
        jsonl_lines = []

        for vuln in vulnerabilities:
            # Create a document optimized for RAG retrieval
            document = self._create_rag_document(vuln, vulnerability_type)
            jsonl_lines.append(json.dumps(document))

        return '\n'.join(jsonl_lines)

    def _create_rag_document(
        self,
        vuln: Dict[str, Any],
        vulnerability_type: str
    ) -> Dict[str, Any]:
        """
        Create a document structure optimized for RAG

        Args:
            vuln: Vulnerability dictionary
            vulnerability_type: Type of vulnerability

        Returns:
            Document dictionary optimized for RAG
        """
        vuln_id = vuln.get('id', 'UNKNOWN')

        # Build a comprehensive text content for embedding
        text_parts = []

        # Title/Header
        if vulnerability_type == 'kev':
            text_parts.append(f"# {vuln.get('vulnerabilityName', vuln_id)}")
        else:
            text_parts.append(f"# {vuln_id}")

        # Description
        description = vuln.get('description', '')
        if description:
            text_parts.append(f"\n## Description\n{description}")

        # For KEVs, add specific information
        if vulnerability_type == 'kev':
            vendor = vuln.get('vendorProject', '')
            product = vuln.get('product', '')
            if vendor or product:
                text_parts.append(f"\n## Affected Product\nVendor: {vendor}\nProduct: {product}")

            required_action = vuln.get('requiredAction', '')
            if required_action:
                text_parts.append(f"\n## Required Action\n{required_action}")

            ransomware = vuln.get('knownRansomwareCampaignUse', '')
            if ransomware:
                text_parts.append(f"\n## Ransomware Campaign Use\n{ransomware}")

        # For CVEs, add CVSS information
        if vulnerability_type == 'cve':
            cvss = vuln.get('cvss', {})
            if cvss:
                text_parts.append("\n## CVSS Scores")
                for version, data in cvss.items():
                    if data:
                        score = data.get('baseScore', 'N/A')
                        severity = data.get('baseSeverity', 'N/A')
                        vector = data.get('vectorString', 'N/A')
                        text_parts.append(f"\n{version.upper()}: {score} ({severity})\nVector: {vector}")

            weaknesses = vuln.get('weaknesses', [])
            if weaknesses:
                text_parts.append(f"\n## Weaknesses\n{', '.join(weaknesses)}")

            affected = vuln.get('affectedProducts', [])
            if affected:
                # Limit to first 10 products to avoid too long text
                products_display = affected[:10]
                text_parts.append(f"\n## Affected Products (sample)\n" + '\n'.join(f"- {p}" for p in products_display))

        # References
        references = vuln.get('references', [])
        if references:
            text_parts.append("\n## References")
            for ref in references[:5]:  # Limit to first 5 references
                url = ref.get('url', '') if isinstance(ref, dict) else ref
                if url:
                    text_parts.append(f"- {url}")

        # Metadata
        published = vuln.get('published') or vuln.get('dateAdded', '')
        if published:
            text_parts.append(f"\n## Published\n{published}")

        # Combine all text parts
        full_text = '\n'.join(text_parts)

        # Create document with metadata
        document = {
            'id': vuln_id,
            'type': vulnerability_type.upper(),
            'text': full_text,
            'metadata': {
                'vulnerability_id': vuln_id,
                'vulnerability_type': vulnerability_type,
                'source': vuln.get('source', ''),
                'timestamp': datetime.utcnow().isoformat()
            }
        }

        # Add type-specific metadata
        if vulnerability_type == 'kev':
            document['metadata'].update({
                'vendor': vuln.get('vendorProject', ''),
                'product': vuln.get('product', ''),
                'ransomware_use': vuln.get('knownRansomwareCampaignUse', ''),
                'date_added': vuln.get('dateAdded', '')
            })
        elif vulnerability_type == 'cve':
            cvss = vuln.get('cvss', {})
            if cvss.get('v31'):
                document['metadata']['cvss_score'] = str(cvss['v31'].get('baseScore', ''))
                document['metadata']['cvss_severity'] = cvss['v31'].get('baseSeverity', '')

        return document

    def start_ingestion_job(self) -> str:
        """
        Start an ingestion job to sync data source with Knowledge Base

        Returns:
            Ingestion job ID
        """
        try:
            logger.info(f"Starting ingestion job for Knowledge Base: {self.knowledge_base_id}")

            response = self.bedrock_agent_client.start_ingestion_job(
                knowledgeBaseId=self.knowledge_base_id,
                dataSourceId=self.data_source_id,
                description=f"Vulnerability data ingestion - {datetime.utcnow().isoformat()}"
            )

            ingestion_job = response.get('ingestionJob', {})
            job_id = ingestion_job.get('ingestionJobId')

            logger.info(f"Started ingestion job: {job_id}")
            return job_id

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConflictException':
                logger.warning("Ingestion job already in progress")
                raise
            else:
                logger.error(f"Error starting ingestion job: {str(e)}")
                raise

    def get_ingestion_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of an ingestion job

        Args:
            job_id: Ingestion job ID

        Returns:
            Job status dictionary
        """
        try:
            response = self.bedrock_agent_client.get_ingestion_job(
                knowledgeBaseId=self.knowledge_base_id,
                dataSourceId=self.data_source_id,
                ingestionJobId=job_id
            )

            job = response.get('ingestionJob', {})
            status = {
                'jobId': job.get('ingestionJobId'),
                'status': job.get('status'),
                'startedAt': job.get('startedAt'),
                'updatedAt': job.get('updatedAt'),
                'statistics': job.get('statistics', {})
            }

            logger.info(f"Ingestion job {job_id} status: {status['status']}")
            return status

        except ClientError as e:
            logger.error(f"Error getting ingestion job status: {str(e)}")
            raise

    def upload_individual_document(
        self,
        vuln: Dict[str, Any],
        vulnerability_type: str
    ) -> str:
        """
        Upload a single vulnerability as an individual document

        Args:
            vuln: Vulnerability dictionary
            vulnerability_type: Type of vulnerability

        Returns:
            S3 key of the uploaded document
        """
        vuln_id = vuln.get('id', 'UNKNOWN')
        s3_key = f"{self.s3_prefix}/{vulnerability_type}/{vuln_id}.json"

        try:
            document = self._create_rag_document(vuln, vulnerability_type)

            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=json.dumps(document, indent=2).encode('utf-8'),
                ContentType='application/json',
                Metadata={
                    'vulnerability_id': vuln_id,
                    'vulnerability_type': vulnerability_type
                }
            )

            logger.info(f"Uploaded individual document: {s3_key}")
            return s3_key

        except ClientError as e:
            logger.error(f"Error uploading individual document: {str(e)}")
            raise
