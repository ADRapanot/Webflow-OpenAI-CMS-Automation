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
WINDSOR_TEMPLATE_PAGES: Sequence[str] = [
    "https://supermetrics.com/template-gallery",
    "https://supermetrics.com/template-gallery?page=2",
    "https://supermetrics.com/template-gallery/reporting-tools/google-sheets",
    "https://supermetrics.com/template-gallery/channels/google-analytics",
    "https://supermetrics.com/template-gallery/looker-studio-linkedin-ads-overview",
    "https://supermetrics.com/blog/facebook-ads-report-template"
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
                count += 1
            if q in description:
                count += 1
            if q in source_url:
                count += 2
            # Also count keywords overlap if query is multi-word.
            qwords = set(q.split())
            for part in (title, extra):
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