"""
CVE Scraper module to fetch CVEs from cve.org API
"""
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import requests

logger = logging.getLogger(__name__)


class CVEScraper:
    """
    Scraper for CVE.org API (NVD/CVE API 2.0)
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize CVE scraper

        Args:
            api_key: Optional NVD API key for higher rate limits
        """
        self.base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        self.api_key = api_key
        self.session = requests.Session()

        # Set headers
        headers = {
            'User-Agent': 'AWS-Lambda-CVE-Scraper/1.0'
        }
        if self.api_key:
            headers['apiKey'] = self.api_key

        self.session.headers.update(headers)

        # Rate limiting (without API key: 5 requests per 30 seconds, with key: 50 per 30 seconds)
        self.rate_limit_delay = 6 if not api_key else 0.6

    def fetch_cves(
        self,
        limit: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch CVEs from NVD API

        Args:
            limit: Maximum number of CVEs to fetch (None = all available)
            start_date: Start date for CVE publication (YYYY-MM-DD format)
            end_date: End date for CVE publication (YYYY-MM-DD format)

        Returns:
            List of CVE dictionaries
        """
        all_cves = []

        # Default to last 30 days if no start date specified
        if not start_date:
            start_dt = datetime.utcnow() - timedelta(days=30)
            start_date = start_dt.strftime('%Y-%m-%d')

        if not end_date:
            end_date = datetime.utcnow().strftime('%Y-%m-%d')

        logger.info(f"Fetching CVEs from {start_date} to {end_date}")

        # Convert dates to ISO format for API
        pub_start_date = f"{start_date}T00:00:00.000"
        pub_end_date = f"{end_date}T23:59:59.999"

        start_index = 0
        results_per_page = 2000  # NVD API max

        while True:
            try:
                params = {
                    'pubStartDate': pub_start_date,
                    'pubEndDate': pub_end_date,
                    'startIndex': start_index,
                    'resultsPerPage': results_per_page
                }

                logger.info(f"Fetching CVEs: startIndex={start_index}")

                response = self.session.get(self.base_url, params=params, timeout=30)
                response.raise_for_status()

                data = response.json()

                vulnerabilities = data.get('vulnerabilities', [])

                if not vulnerabilities:
                    logger.info("No more CVEs to fetch")
                    break

                # Process and normalize CVE data
                for vuln in vulnerabilities:
                    cve_data = self._normalize_cve(vuln)
                    all_cves.append(cve_data)

                logger.info(f"Fetched {len(vulnerabilities)} CVEs (total: {len(all_cves)})")

                # Check if we've reached the limit
                if limit and len(all_cves) >= limit:
                    all_cves = all_cves[:limit]
                    logger.info(f"Reached specified limit of {limit} CVEs")
                    break

                # Check if there are more results
                total_results = data.get('totalResults', 0)
                if start_index + len(vulnerabilities) >= total_results:
                    logger.info(f"Fetched all available CVEs: {len(all_cves)}")
                    break

                start_index += len(vulnerabilities)

                # Rate limiting
                time.sleep(self.rate_limit_delay)

            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching CVEs: {str(e)}")
                if response.status_code == 403:
                    logger.error("API access forbidden. Check API key or rate limits.")
                break

            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}", exc_info=True)
                break

        logger.info(f"Total CVEs fetched: {len(all_cves)}")
        return all_cves

    def _normalize_cve(self, vuln: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize CVE data into a consistent format for RAG

        Args:
            vuln: Raw vulnerability data from NVD API

        Returns:
            Normalized CVE dictionary
        """
        cve = vuln.get('cve', {})
        cve_id = cve.get('id', 'UNKNOWN')

        # Extract descriptions
        descriptions = cve.get('descriptions', [])
        description = next(
            (desc.get('value', '') for desc in descriptions if desc.get('lang') == 'en'),
            ''
        )

        # Extract CVSS metrics
        metrics = cve.get('metrics', {})
        cvss_data = self._extract_cvss_metrics(metrics)

        # Extract references
        references = [
            {
                'url': ref.get('url', ''),
                'source': ref.get('source', ''),
                'tags': ref.get('tags', [])
            }
            for ref in cve.get('references', [])
        ]

        # Extract weaknesses (CWE)
        weaknesses = []
        for weakness in cve.get('weaknesses', []):
            for desc in weakness.get('description', []):
                if desc.get('lang') == 'en':
                    weaknesses.append(desc.get('value', ''))

        # Extract CPE configurations
        configurations = cve.get('configurations', [])
        affected_products = self._extract_affected_products(configurations)

        # Publication dates
        published = cve.get('published', '')
        last_modified = cve.get('lastModified', '')

        return {
            'id': cve_id,
            'type': 'CVE',
            'source': 'NVD',
            'description': description,
            'published': published,
            'lastModified': last_modified,
            'cvss': cvss_data,
            'weaknesses': weaknesses,
            'references': references,
            'affectedProducts': affected_products,
            'raw_data': cve  # Keep raw data for completeness
        }

    def _extract_cvss_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract CVSS metrics from various versions

        Args:
            metrics: Metrics dictionary from CVE data

        Returns:
            Consolidated CVSS metrics
        """
        cvss_data = {}

        # CVSS v3.1
        cvss_v31 = metrics.get('cvssMetricV31', [])
        if cvss_v31:
            primary = next((m for m in cvss_v31 if m.get('type') == 'Primary'), cvss_v31[0])
            cvss_data['v31'] = {
                'baseScore': primary.get('cvssData', {}).get('baseScore'),
                'baseSeverity': primary.get('cvssData', {}).get('baseSeverity'),
                'vectorString': primary.get('cvssData', {}).get('vectorString'),
                'exploitabilityScore': primary.get('exploitabilityScore'),
                'impactScore': primary.get('impactScore')
            }

        # CVSS v3.0
        cvss_v30 = metrics.get('cvssMetricV30', [])
        if cvss_v30:
            primary = next((m for m in cvss_v30 if m.get('type') == 'Primary'), cvss_v30[0])
            cvss_data['v30'] = {
                'baseScore': primary.get('cvssData', {}).get('baseScore'),
                'baseSeverity': primary.get('cvssData', {}).get('baseSeverity'),
                'vectorString': primary.get('cvssData', {}).get('vectorString')
            }

        # CVSS v2.0
        cvss_v2 = metrics.get('cvssMetricV2', [])
        if cvss_v2:
            primary = next((m for m in cvss_v2 if m.get('type') == 'Primary'), cvss_v2[0])
            cvss_data['v2'] = {
                'baseScore': primary.get('cvssData', {}).get('baseScore'),
                'vectorString': primary.get('cvssData', {}).get('vectorString')
            }

        return cvss_data

    def _extract_affected_products(self, configurations: List[Dict[str, Any]]) -> List[str]:
        """
        Extract affected products from CPE configurations

        Args:
            configurations: Configuration list from CVE data

        Returns:
            List of affected product strings
        """
        products = []

        def extract_cpes(node: Dict[str, Any]):
            if 'cpeMatch' in node:
                for cpe_match in node.get('cpeMatch', []):
                    if cpe_match.get('vulnerable', True):
                        criteria = cpe_match.get('criteria', '')
                        if criteria and criteria not in products:
                            products.append(criteria)

            # Recursively process child nodes
            for child in node.get('nodes', []):
                extract_cpes(child)

        for config in configurations:
            for node in config.get('nodes', []):
                extract_cpes(node)

        return products
