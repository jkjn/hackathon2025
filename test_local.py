#!/usr/bin/env python3
"""
Local testing script for CVE and KEV scrapers
Run this script to test the scrapers without deploying to AWS
"""
import json
import logging
import sys
from datetime import datetime, timedelta

from cve_scraper import CVEScraper
from kev_scraper import KEVScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_cve_scraper(limit=5):
    """Test CVE scraper with a small limit"""
    logger.info("=" * 60)
    logger.info("Testing CVE Scraper")
    logger.info("=" * 60)

    try:
        scraper = CVEScraper()

        # Fetch a small number of recent CVEs
        start_date = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        logger.info(f"Fetching {limit} CVEs from the last 7 days...")

        cves = scraper.fetch_cves(limit=limit, start_date=start_date)

        logger.info(f"\nSuccessfully fetched {len(cves)} CVEs\n")

        # Display sample CVE
        if cves:
            sample = cves[0]
            logger.info("Sample CVE:")
            logger.info(f"  ID: {sample.get('id')}")
            logger.info(f"  Published: {sample.get('published')}")
            logger.info(f"  Description: {sample.get('description', '')[:100]}...")

            cvss = sample.get('cvss', {})
            if cvss.get('v31'):
                logger.info(f"  CVSS v3.1 Score: {cvss['v31'].get('baseScore')} ({cvss['v31'].get('baseSeverity')})")

        return True

    except Exception as e:
        logger.error(f"CVE scraper test failed: {str(e)}", exc_info=True)
        return False


def test_kev_scraper():
    """Test KEV scraper"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing KEV Scraper")
    logger.info("=" * 60)

    try:
        scraper = KEVScraper()

        logger.info("Fetching KEVs from CISA...")
        kevs = scraper.fetch_kevs()

        logger.info(f"\nSuccessfully fetched {len(kevs)} KEVs\n")

        # Display sample KEV
        if kevs:
            sample = kevs[0]
            logger.info("Sample KEV:")
            logger.info(f"  ID: {sample.get('id')}")
            logger.info(f"  Name: {sample.get('vulnerabilityName')}")
            logger.info(f"  Vendor: {sample.get('vendorProject')}")
            logger.info(f"  Product: {sample.get('product')}")
            logger.info(f"  Date Added: {sample.get('dateAdded')}")
            logger.info(f"  Ransomware Use: {sample.get('knownRansomwareCampaignUse')}")

        # Get ransomware-related KEVs
        ransomware_kevs = scraper.get_ransomware_kevs()
        logger.info(f"\nKEVs with known ransomware use: {len(ransomware_kevs)}")

        return True

    except Exception as e:
        logger.error(f"KEV scraper test failed: {str(e)}", exc_info=True)
        return False


def save_sample_data(cves, kevs):
    """Save sample data to JSON files for inspection"""
    try:
        if cves:
            with open('sample_cves.json', 'w') as f:
                json.dump(cves[:5], f, indent=2)
            logger.info("\nSaved sample CVEs to: sample_cves.json")

        if kevs:
            with open('sample_kevs.json', 'w') as f:
                json.dump(kevs[:5], f, indent=2)
            logger.info("Saved sample KEVs to: sample_kevs.json")

    except Exception as e:
        logger.error(f"Error saving sample data: {str(e)}")


def main():
    """Main test function"""
    logger.info("\n" + "=" * 60)
    logger.info("CVE/KEV Scraper Local Test")
    logger.info("=" * 60 + "\n")

    results = {
        'cve_test': False,
        'kev_test': False
    }

    # Test CVE scraper
    results['cve_test'] = test_cve_scraper(limit=5)

    # Test KEV scraper
    results['kev_test'] = test_kev_scraper()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    logger.info(f"CVE Scraper: {'PASSED' if results['cve_test'] else 'FAILED'}")
    logger.info(f"KEV Scraper: {'PASSED' if results['kev_test'] else 'FAILED'}")

    # Save sample data if tests passed
    if results['cve_test'] and results['kev_test']:
        logger.info("\nFetching sample data for inspection...")
        cve_scraper = CVEScraper()
        kev_scraper = KEVScraper()

        cves = cve_scraper.fetch_cves(limit=5)
        kevs = kev_scraper.fetch_kevs()

        save_sample_data(cves, kevs)

    # Exit with appropriate code
    if all(results.values()):
        logger.info("\n✓ All tests passed!\n")
        sys.exit(0)
    else:
        logger.error("\n✗ Some tests failed\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
