"""
KEV Scraper module to fetch Known Exploited Vulnerabilities from CISA
"""
import logging
from typing import List, Dict, Any
import requests

logger = logging.getLogger(__name__)


class KEVScraper:
    """
    Scraper for CISA Known Exploited Vulnerabilities Catalog
    """

    def __init__(self):
        """
        Initialize KEV scraper
        """
        self.catalog_url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AWS-Lambda-KEV-Scraper/1.0'
        })

    def fetch_kevs(self) -> List[Dict[str, Any]]:
        """
        Fetch all Known Exploited Vulnerabilities from CISA catalog

        Returns:
            List of KEV dictionaries
        """
        try:
            logger.info(f"Fetching KEV catalog from {self.catalog_url}")

            response = self.session.get(self.catalog_url, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract catalog metadata
            catalog_version = data.get('catalogVersion', 'unknown')
            date_released = data.get('dateReleased', '')
            count = data.get('count', 0)

            logger.info(f"KEV Catalog version: {catalog_version}, released: {date_released}, count: {count}")

            # Get vulnerabilities
            vulnerabilities = data.get('vulnerabilities', [])

            # Normalize KEV data
            normalized_kevs = [self._normalize_kev(vuln) for vuln in vulnerabilities]

            logger.info(f"Total KEVs fetched: {len(normalized_kevs)}")

            return normalized_kevs

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching KEV catalog: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise

    def _normalize_kev(self, vuln: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize KEV data into a consistent format for RAG

        Args:
            vuln: Raw vulnerability data from CISA KEV catalog

        Returns:
            Normalized KEV dictionary
        """
        cve_id = vuln.get('cveID', 'UNKNOWN')
        vendor_project = vuln.get('vendorProject', '')
        product = vuln.get('product', '')
        vulnerability_name = vuln.get('vulnerabilityName', '')
        date_added = vuln.get('dateAdded', '')
        short_description = vuln.get('shortDescription', '')
        required_action = vuln.get('requiredAction', '')
        due_date = vuln.get('dueDate', '')
        known_ransomware = vuln.get('knownRansomwareCampaignUse', 'Unknown')
        notes = vuln.get('notes', '')

        # Create a comprehensive description for RAG
        comprehensive_description = f"""
{vulnerability_name}

CVE ID: {cve_id}
Vendor/Project: {vendor_project}
Product: {product}

Description: {short_description}

Known Ransomware Campaign Use: {known_ransomware}

Required Action: {required_action}
Due Date: {due_date}

Date Added to KEV Catalog: {date_added}
""".strip()

        if notes:
            comprehensive_description += f"\n\nNotes: {notes}"

        return {
            'id': cve_id,
            'type': 'KEV',
            'source': 'CISA',
            'vulnerabilityName': vulnerability_name,
            'vendorProject': vendor_project,
            'product': product,
            'description': comprehensive_description,
            'shortDescription': short_description,
            'dateAdded': date_added,
            'requiredAction': required_action,
            'dueDate': due_date,
            'knownRansomwareCampaignUse': known_ransomware,
            'notes': notes,
            'raw_data': vuln  # Keep raw data for completeness
        }

    def get_kev_by_cve_id(self, cve_id: str) -> Dict[str, Any]:
        """
        Fetch a specific KEV by CVE ID

        Args:
            cve_id: CVE identifier (e.g., 'CVE-2021-44228')

        Returns:
            KEV dictionary or None if not found
        """
        kevs = self.fetch_kevs()

        for kev in kevs:
            if kev['id'] == cve_id:
                return kev

        logger.warning(f"KEV not found for CVE ID: {cve_id}")
        return None

    def get_kevs_by_vendor(self, vendor: str) -> List[Dict[str, Any]]:
        """
        Filter KEVs by vendor/project

        Args:
            vendor: Vendor name to filter by

        Returns:
            List of matching KEV dictionaries
        """
        kevs = self.fetch_kevs()

        matching_kevs = [
            kev for kev in kevs
            if vendor.lower() in kev.get('vendorProject', '').lower()
        ]

        logger.info(f"Found {len(matching_kevs)} KEVs for vendor: {vendor}")
        return matching_kevs

    def get_ransomware_kevs(self) -> List[Dict[str, Any]]:
        """
        Get all KEVs known to be used in ransomware campaigns

        Returns:
            List of KEV dictionaries with known ransomware use
        """
        kevs = self.fetch_kevs()

        ransomware_kevs = [
            kev for kev in kevs
            if kev.get('knownRansomwareCampaignUse', '').lower() == 'known'
        ]

        logger.info(f"Found {len(ransomware_kevs)} KEVs with known ransomware use")
        return ransomware_kevs
