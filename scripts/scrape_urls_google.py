import re
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Iterable, List, Optional, Sequence
from urllib.parse import urljoin
import os
import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

try:
    from scripts.scrape_looker_reports import main as looker_main
except ModuleNotFoundError:  # Allows running as a standalone script
    from scrape_looker_reports import main as looker_main

# --------------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------------

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT = 20

TABLEAU_BASE = "https://public.tableau.com"
# WINDSOR_TEMPLATE_PAGES: Sequence[str] = [
#     "https://www.catchr.io/template"
# ]
DATABOX_TEMPLATE_PAGES: Sequence[str] = [
    "https://databox.com/dashboard-examples/marketing",
    "https://databox.com/dashboard-examples/sales",
    "https://databox.com/dashboard-examples/customer-support",
    "https://databox.com/dashboard-examples/ecommerce",
    "https://databox.com/dashboard-examples/project-management",
    "https://databox.com/dashboard-examples/financial",
    "https://databox.com/dashboard-examples/software-development",
    "https://databox.com/dashboard-examples/saas",
    "https://databox.com/dashboard-examples/google-analytics-4-dashboards",
    "https://databox.com/dashboard-examples/hubspot-dashboards",
    "https://databox.com/dashboard-examples/hubspot-crm-dashboards",
    "https://databox.com/dashboard-examples/hubspot-service-dashboards",
    "https://databox.com/dashboard-examples/facebook-ads-dashboards",
    "https://databox.com/dashboard-examples/facebook-dashboards",
    "https://databox.com/dashboard-examples/google-ads-dashboards",
    "https://databox.com/dashboard-examples/instagram-business-dashboards",
    "https://databox.com/dashboard-examples/google-search-console-dashboards",
    "https://databox.com/dashboard-examples/linkedin-dashboards",
    "https://databox.com/dashboard-examples/twitter-dashboards",
    "https://databox.com/dashboard-examples/shopify-dashboards",
    "https://databox.com/dashboard-examples/youtube-dashboards",
    "https://databox.com/dashboard-examples/google-my-business-dashboards",
    "https://databox.com/dashboard-examples/mailchimp-dashboards",
    "https://databox.com/dashboard-examples/linkedin-ads-dashboards",
    "https://databox.com/dashboard-examples/stripe-dashboards",
    "https://databox.com/dashboard-examples/active-campaign-dashboards",
    "https://databox.com/dashboard-examples/quickbooks-dashboards",
    "https://databox.com/dashboard-examples/semrush-dashboards",
    "https://databox.com/dashboard-examples/pipedrive-dashboards",
    "https://databox.com/dashboard-examples/xero-dashboards",
    "https://databox.com/dashboard-examples/woocommerce-dashboards",
    "https://databox.com/dashboard-examples/github-dashboards",
    "https://databox.com/dashboard-examples/harvest-dashboards",
    "https://databox.com/dashboard-examples/klaviyo-dashboards",
    "https://databox.com/dashboard-examples/callrail-dashboards",
    "https://databox.com/dashboard-examples/microsoft-advertising-dashboards",
    "https://databox.com/dashboard-examples/intercom-dashboards",
    "https://databox.com/dashboard-examples/mixpanel-dashboards",
    "https://databox.com/dashboard-examples/adsense-dashboards",
    "https://databox.com/dashboard-examples/accuranker-dashboards",
    "https://databox.com/dashboard-examples/google-play-dashboards",
    "https://databox.com/dashboard-examples/twitter-ads-dashboards",
    "https://databox.com/dashboard-examples/tiktok-ads-dashboards",
    "https://databox.com/dashboard-examples/paypal-dashboards",
    "https://databox.com/dashboard-examples/eventbrite-dashboards",
    "https://databox.com/dashboard-examples/helpscout-dashboards",
    "https://databox.com/dashboard-examples/moz-dashboards",
    "https://databox.com/dashboard-examples/vimeo-dashboards",
    "https://databox.com/dashboard-examples/wistia-dashboards",
    "https://databox.com/dashboard-examples/jira-dashboards",
    "https://databox.com/dashboard-examples/bitbucket-dashboards",
    "https://databox.com/dashboard-examples/sharpspring-dashboards",
    "https://databox.com/dashboard-examples/drift-dashboards",
    "https://databox.com/dashboard-examples/admob-dashboards",
    "https://databox.com/dashboard-examples/adobe-analytics-dashboards",
    "https://databox.com/dashboard-examples/sendgrid-dashboards",
    "https://databox.com/dashboard-examples/stackadapt-dashboards",
    "https://databox.com/dashboard-examples/help-scout-docs-dashboards",
    "https://databox.com/dashboard-examples/infusionsoft-by-keap-dashboards",
    "https://databox.com/dashboard-examples/surveymonkey-dashboards",
    "https://databox.com/dashboard-examples/copper-dashboards",
    "https://databox.com/dashboard-examples/free-vimeo-ott-dashboard-examples-and-templates",
    "https://databox.com/dashboard-examples/appfigures-dashboards",
    "https://databox.com/dashboard-examples/bigcommerce-dashboards",
    "https://databox.com/dashboard-examples/freshdesk-dashboards",
    "https://databox.com/dashboard-examples/freshbooks-dashboards",
    "https://databox.com/dashboard-examples/chartmogul-dashboards",
    "https://databox.com/dashboard-examples/ahrefs-dashboards",
]

PORTERMETRICS_TEMPLATE_PAGES: Sequence[str] = [
    "https://portermetrics.com/en/templates/",
    "https://portermetrics.com/en/templates/2",
    "https://portermetrics.com/en/templates/3",
    "https://portermetrics.com/en/templates/4",
    "https://portermetrics.com/en/templates/5",
    "https://portermetrics.com/en/dashboard-templates/",
    "https://portermetrics.com/en/report-templates/",
    "https://portermetrics.com/en/report-templates/2",
    "https://portermetrics.com/en/report-templates/3",
    "https://portermetrics.com/en/report-templates/4",
    "https://portermetrics.com/en/templates/digital-marketing/",
    "https://portermetrics.com/en/templates/e-commerce/",
    "https://portermetrics.com/en/templates/ppc/",
    "https://portermetrics.com/en/templates/social-media/",
    "https://portermetrics.com/en/templates/lead-generation/",
    "https://portermetrics.com/en/templates/facebook-ads/",
    "https://portermetrics.com/en/templates/google-sheets/",
    "https://portermetrics.com/en/templates/google-sheets/facebook-ads/",
    "https://portermetrics.com/en/templates/google-sheets/ppc/",
    "https://portermetrics.com/en/templates/google-sheets/social-media/",
    "https://portermetrics.com/en/templates/google-sheets/e-commerce/",
    "https://portermetrics.com/en/examples/",
]
AGENCYANALYTICS_TEMPLATE_PAGES: Sequence[str] = [
    "https://agencyanalytics.com/templates"
]
WINDSOR_TEMPLATE_PAGES: Sequence[str] = [
    "https://bymarketers.co/browse/business-processes/",
    "https://bymarketers.co/browse/content-marketing/",
    "https://bymarketers.co/browse/display-advertising/",
    "https://bymarketers.co/browse/ecommerce/",
    "https://bymarketers.co/browse/email-marketing/",
    "https://bymarketers.co/browse/finance/",
    "https://bymarketers.co/browse/graphic-design/",
    "https://bymarketers.co/browse/paid-advertising/",
    "https://bymarketers.co/browse/project-management/",
    "https://bymarketers.co/browse/seo/",
    "https://bymarketers.co/browse/social-media/",
    "https://bymarketers.co/browse/ux/",
    "https://bymarketers.co/platforms/amazon/",
    "https://bymarketers.co/platforms/bing/",
    "https://bymarketers.co/platforms/google-ads/",
    "https://bymarketers.co/platforms/ga4/",
    "https://bymarketers.co/platforms/google-my-business/",
    "https://bymarketers.co/platforms/google-search-console/",
    "https://bymarketers.co/platforms/instagram/",
    "https://bymarketers.co/platforms/linkedin/",
    "https://bymarketers.co/platforms/mailchimp/",
    "https://bymarketers.co/platforms/meta/",
    "https://bymarketers.co/platforms/notion/",
    "https://bymarketers.co/platforms/other/",
    "https://bymarketers.co/platforms/pinterest/",
    "https://bymarketers.co/platforms/salesforce/",
    "https://bymarketers.co/platforms/semrush/",
    "https://bymarketers.co/platforms/shopify/",
    "https://bymarketers.co/platforms/snapchat/",
    "https://bymarketers.co/platforms/tik-tok/",
    "https://bymarketers.co/file-type/clickup/",
    "https://bymarketers.co/file-type/google-docs/",
    "https://bymarketers.co/file-type/google-looker-studio/",
    "https://bymarketers.co/file-type/google-sheets/",
    "https://bymarketers.co/file-type/google-slides/",
    "https://bymarketers.co/file-type/ms-doc/",
    "https://bymarketers.co/file-type/ms-excel/",
    "https://bymarketers.co/file-type/notion/",
    "https://bymarketers.co/file-type/other/",
    "https://bymarketers.co/file-type/powerpoint/",
    "https://bymarketers.co/file-type/powerbi/"
]
LOOKER_JS_URL = "https://lookerstudio.google.com/gallery/static/gallery/report_gallery_js.js"
LOOKER_OUTPUT_PATH = Path(__file__).with_name("reports_looker.json")


# --------------------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------------------

@dataclass
class WindsorTemplate:
    category_url: str
    title: str
    source_url: str
    thumbnail_url: str

    def to_dict(self) -> dict:
        return asdict(self)


def _absolute_url(base: str, candidate: Optional[str]) -> str:
    if not candidate:
        return base
    return urljoin(base, candidate)


# --------------------------------------------------------------------------------------
# Tableau Public scraping
# --------------------------------------------------------------------------------------


def get_tableau_dashboards(query: str, num_results: int = 10, max_pages: int = 5) -> List[dict]:
    """
    Scrape Tableau Public search results for the supplied query using headless
    Selenium so we can capture dynamically rendered gallery cards.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    chrome_binary = os.getenv("CHROME_BIN") or os.getenv("GOOGLE_CHROME_BIN")
    if chrome_binary:
        options.binary_location = chrome_binary

    chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
    if chromedriver_path and Path(chromedriver_path).exists():
        service = Service(executable_path=chromedriver_path)
    else:
        service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)

    encoded_query = query.replace(" ", "%20")
    base_url = f"{TABLEAU_BASE}/app/search/vizzes/{encoded_query}"

    results: List[dict] = []
    page_number = 1

    try:
        while len(results) < num_results and page_number <= max_pages:
            page_url = base_url if page_number == 1 else f"{base_url}?page={page_number}"
            driver.get(page_url)

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div[data-testid="VizCard"]'))
                )
            except TimeoutException:
                print(f"Tableau: no viz cards found on page {page_number} for query '{query}'.")
                break

            soup = BeautifulSoup(driver.page_source, "html.parser")
            viz_cards = soup.select('div[data-testid="VizCard"]')

            for viz_card in viz_cards:
                link_elem = viz_card.find("a", attrs={"href": True})
                if not link_elem:
                    continue

                relative_link = link_elem["href"]
                if "/viz/" not in relative_link:
                    continue

                viz_link = _absolute_url(TABLEAU_BASE, relative_link)

                title_elem = viz_card.find("a", attrs={"class": lambda value: value and "title" in value})
                title = title_elem.text.strip() if title_elem and title_elem.text else "Unknown"

                author_elem = viz_card.find("a", attrs={"class": lambda value: value and "author" in value})
                author = author_elem.text.strip() if author_elem and author_elem.text else "Unknown"

                thumbnail_elem = viz_card.find("img")
                thumbnail_url = ""
                if thumbnail_elem and thumbnail_elem.get("src"):
                    thumbnail_url = _absolute_url(TABLEAU_BASE, thumbnail_elem["src"])

                results.append(
                    {
                        "title": title,
                        "author": author,
                        "sourceUrl": viz_link,
                        "thumbnail": thumbnail_url,
                    }
                )

                if len(results) >= num_results:
                    break

            page_number += 1
    finally:
        driver.quit()

    return results


# --------------------------------------------------------------------------------------
# Looker Studio aggregation via scrape_looker_reports helper
# --------------------------------------------------------------------------------------

def _fetch_looker_reports(query: str = "") -> List[dict]:
    try:
        reports = looker_main(
            js_url=LOOKER_JS_URL,
            output_path=LOOKER_OUTPUT_PATH,
            indent=2,
            timeout=30.0,
            write_output=True,
        )
    except Exception as exc:
        print(f"Looker Studio: scraper execution failed: {exc}")
        return []
    return reports


# --------------------------------------------------------------------------------------
# Convenience helper
# --------------------------------------------------------------------------------------

def get_dashboards_from_sites(query: str = "", limit: Optional[int] = None, include_tableau: bool = True) -> List[dict]:
    """
    Fetch dashboards from Windsor.ai, Looker Studio, and optionally Tableau Public.
    """
    results = []
    # results = get_windsor_dashboards(query=query, limit=limit)
    # results.extend(_fetch_looker_reports(query=query))
    print(len(results))
    # INSERT_YOUR_CODE
    

    reports_dir = Path(__file__).parent / "../reports"
    print(reports_dir)
    if reports_dir.exists() and reports_dir.is_dir():
        for fname in os.listdir(reports_dir):
            if fname.endswith(".json"):
                fpath = reports_dir / fname
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            results.append(data)
                        elif isinstance(data, list):
                            results.extend(data)
                except Exception as exc:
                    print(f"Could not load {fpath}: {exc}")
    results.extend(get_tableau_dashboards(query=query, num_results=limit or 10))
    # INSERT_YOUR_CODE
    # Sort dashboards by simple relevance to query and return up to 100 examples.
    # We'll score by simple substring matches on title/extra_text fields, highest first.

    def relevance_score(item):
        # Lowercased query and fields.
        q = (query or "").strip().lower()
        if not q:
            return 0
        if isinstance(item, dict):
            title = str(item.get("title", "")).lower()
            extra = str(item.get("extra_text", "")).lower()
            description = str(item.get("description", "")).lower()
            source_url = str(item.get("source_url", "")).lower()
            count = 0
            if q in title:
                count += 2  # strong preference if in title
            if q in extra:
                count += 2
            if q in description:
                count += 1
            if q in source_url:
                count += 2
            # Also count keywords overlap if query is multi-word.
            qwords = set(q.split())
            for part in (title, extra,description,source_url):
                for word in qwords:
                    if word and word in part:
                        count += 1
            return count
        return 0

    # Sort by score (descending), preserve original order for ties.
    results = sorted(results, key=relevance_score, reverse=True)
    # Return only top 100 results.
    results = results[:100]
    return results


if __name__ == "__main__":
    dashboards = get_dashboards_from_sites("marketing analytics", limit=20)
    print(len(dashboards))
    # print(dashboards)