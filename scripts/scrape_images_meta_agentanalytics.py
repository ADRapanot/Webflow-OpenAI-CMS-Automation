#!/usr/bin/env python3
"""
scrape_images_js.py
Scrape images from JavaScript-rendered pages using Selenium.
"""

import argparse
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup


def setup_driver(headless: bool = True) -> webdriver.Chrome:
    """Setup Chrome WebDriver with options."""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver


def scroll_page(driver, scroll_pause: float = 2.0, max_scrolls: int = 10):
    """Scroll page to trigger lazy loading."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    scrolls = 0
    
    while scrolls < max_scrolls:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause)
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
        scrolls += 1
        logging.info("Scrolled %d times, page height: %d", scrolls, new_height)


def _get_nearby_text(element, max_chars: int = 240) -> str:
    """Extract nearby text content around an element."""
    texts = []
    for sibling in element.find_all_next(string=True, limit=6):
        stripped = sibling.strip()
        if stripped:
            texts.append(stripped)
        if sum(len(t) for t in texts) >= max_chars:
            break
    snippet = " ".join(texts).strip()
    return snippet[:max_chars] if snippet else ""


def _find_author(element):
    """Search ancestor tree for an author/byline-like element."""
    author_patterns = re.compile(r"(author|byline|writer|posted-by)", re.IGNORECASE)
    for ancestor in element.parents:
        if ancestor is None:
            break
        if ancestor.name in ("body", "html"):
            break
        for candidate in ancestor.find_all(True, class_=author_patterns):
            text = candidate.get_text(strip=True)
            if text:
                return text
        # Look for explicit data-author or itemprop
        if ancestor.has_attr("data-author"):
            return ancestor["data-author"].strip()
        if ancestor.has_attr("itemprop") and "author" in ancestor["itemprop"]:
            text = ancestor.get_text(strip=True)
            if text:
                return text
    return ""


def has_image_extension(url: str) -> bool:
    """Check if URL contains an image file extension."""
    if not url:
        return False
    
    # Common image extensions
    image_extensions = [
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp',
        '.tiff', '.tif', '.heic', '.heif', '.avif', '.jfif', 'thumbnail'
    ]
    
    # Parse URL and check path
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    # Check if path ends with image extension
    for ext in image_extensions:
        if path.endswith(ext):
            return True
    
    # Also check query parameters for image extensions (some CDNs use this)
    query = parsed.query.lower()
    for ext in image_extensions:
        if ext in query:
            return True
    
    return False


def check_image_dimensions(driver: webdriver.Chrome, img_url: str, min_size: int = 200) -> tuple:
    """
    Check if an image has width and height greater than min_size.
    
    Args:
        driver: Selenium WebDriver instance
        img_url: URL of the image to check
        min_size: Minimum width and height in pixels (default: 200)
    
    Returns:
        Tuple of (width, height) if image is valid, (0, 0) otherwise
    """
    try:
        # Use JavaScript to load and check image dimensions
        # execute_async_script requires callback as last argument
        script = """
        const img = new Image();
        img.crossOrigin = 'anonymous';
        const url = arguments[0];
        const callback = arguments[arguments.length - 1];
        
        img.onload = function() {
            callback({width: this.naturalWidth, height: this.naturalHeight});
        };
        img.onerror = function() {
            callback({width: 0, height: 0});
        };
        
        img.src = url;
        
        // Timeout after 5 seconds
        setTimeout(function() {
            callback({width: 0, height: 0});
        }, 5000);
        """
        dimensions = driver.execute_async_script(script, img_url)
        width = dimensions.get('width', 0)
        height = dimensions.get('height', 0)
        
        return (width, height)
    except Exception as e:
        logging.debug(f"Failed to check dimensions for {img_url}: {e}")
        return (0, 0)


def extract_dashboard_metadata(dashboard_card, base_url: str) -> dict:
    """Extract metadata from AgencyAnalytics dashboard card."""
    metadata = {
        "title": "",
        "extra_text": "",
        "thumbnail": "",
        "source_link": "",
        "author": ""
    }
    
    # Find the anchor tag that wraps the card (contains href)
    # The anchor is typically inside the card wrapper
    anchor = dashboard_card.find("a", href=True)
    if anchor and anchor.get("href"):
        href = anchor["href"].strip()
        if href:
            metadata["source_link"] = urljoin(base_url, href)
    
    # Find the image thumbnail
    img = dashboard_card.find("img", class_=lambda x: x and "DashboardReportCard_thumbnail" in x)
    if img:
        # Try src first, then srcset, then data-src
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src:
            # Try to extract from srcset
            srcset = img.get("srcset")
            if srcset:
                # Extract first URL from srcset
                srcset_urls = re.findall(r'([^\s,]+)', srcset)
                if srcset_urls:
                    src = srcset_urls[0]
        
        if src:
            metadata["thumbnail"] = urljoin(base_url, src.strip())
    
    # Find the title in h2 with Text_text class
    title_elem = dashboard_card.find("h2", class_=lambda x: x and "Text_text" in x)
    if title_elem:
        metadata["title"] = title_elem.get_text(strip=True)
    
    # Find extra_text in div with line-clamp-2 class
    text_container = dashboard_card.find("div", class_=lambda x: x and "line-clamp-2" in x)
    if text_container:
        text_elem = text_container.find("div", class_=lambda x: x and "Text_text" in x)
        if text_elem:
            metadata["extra_text"] = text_elem.get_text(" ", strip=True)
    
    return metadata


def extract_image_metadata(img_tag, base_url: str) -> dict:
    """Derive contextual metadata for an image tag."""
    metadata = {}
    
    src = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")
    if src:
        metadata["thumbnail"] = urljoin(base_url, src.strip())
    else:
        metadata["thumbnail"] = ""
    
    # For AgencyAnalytics dashboard cards, look for parent DashboardReportCard container
    dashboard_card = img_tag.find_parent("div", class_=lambda x: x and "DashboardReportCard_cardWrap" in x)
    
    if dashboard_card:
        return extract_dashboard_metadata(dashboard_card, base_url)
    
    # Fallback to original logic for non-dashboard structures
    anchor = img_tag.find_parent("a", href=True)
    if anchor:
        metadata["source_link"] = urljoin(base_url, anchor["href"])
    else:
        metadata["source_link"] = ""
    
    title = img_tag.get("alt") or img_tag.get("title")
    if not title:
        # Check parent figure or caption
        figure = img_tag.find_parent("figure")
        if figure:
            caption = figure.find("figcaption")
            if caption:
                title = caption.get_text(strip=True)
    metadata["title"] = title or ""
    
    metadata["author"] = _find_author(img_tag)
    
    # Only set extra_text if it wasn't already set
    if "extra_text" not in metadata or not metadata.get("extra_text"):
        figure = img_tag.find_parent("figure")
        caption_text = ""
        if figure:
            caption = figure.find("figcaption")
            if caption:
                caption_text = caption.get_text(" ", strip=True)
        nearby_text = _get_nearby_text(img_tag)
        
        metadata["extra_text"] = caption_text or nearby_text
    
    return metadata


def find_pagination_buttons(driver):
    """Find pagination buttons/links on the page."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    pagination_buttons = []
    
    try:
        # Try to find pagination buttons by various selectors
        # Common patterns: button with page number, link with page number, etc.
        wait = WebDriverWait(driver, 10)
        
        # Try finding buttons or links that contain page numbers
        # Look for elements that might be pagination controls
        page_elements = driver.find_elements(By.CSS_SELECTOR, "button, a")
        
        for elem in page_elements:
            try:
                text = elem.text.strip()
                # Check if it's a page number (1-9)
                if text.isdigit() and 1 <= int(text) <= 9:
                    # Check if it's clickable and not disabled
                    if elem.is_displayed() and elem.is_enabled():
                        page_num = int(text)
                        pagination_buttons.append((page_num, elem))
            except:
                continue
        
        # Also try finding by aria-label or data attributes
        for page_num in range(1, 10):
            try:
                # Try various selectors (note: :contains() is not valid CSS, use XPath instead)
                selectors = [
                    f"button[aria-label*='{page_num}']",
                    f"a[aria-label*='{page_num}']",
                ]
                for selector in selectors:
                    try:
                        elem = driver.find_element(By.CSS_SELECTOR, selector)
                        if elem.is_displayed() and elem.is_enabled():
                            pagination_buttons.append((page_num, elem))
                            break
                    except:
                        continue
            except:
                continue
        
        # Remove duplicates and sort by page number
        seen = set()
        unique_buttons = []
        for page_num, elem in sorted(pagination_buttons, key=lambda x: x[0]):
            if page_num not in seen:
                seen.add(page_num)
                unique_buttons.append((page_num, elem))
        
        return unique_buttons
    except Exception as e:
        logging.warning(f"Error finding pagination buttons: {e}")
        return []


def extract_dashboard_items_from_page(soup, base_url):
    """Extract dashboard items from the current page."""
    dashboard_items = []
    
    # Find all dashboard card containers
    dashboard_cards = soup.find_all("div", class_=lambda x: x and "DashboardReportCard_cardWrap" in x)
    
    logging.info("Found %d dashboard cards on this page", len(dashboard_cards))
    
    for card in dashboard_cards:
        metadata = extract_dashboard_metadata(card, base_url)
        if metadata.get("thumbnail") or metadata.get("title"):
            dashboard_items.append(metadata)
            logging.debug(f"Extracted: {metadata.get('title', 'No title')}")
    
    return dashboard_items


def scrape_images_with_js(
    url: str,
    output_dir: Path,
    keywords: list = None,
    headless: bool = True,
    wait_time: int = 5,
    scroll: bool = True,
    total_pages: int = 9,
) -> list:
    """
    Scrape dashboard items from AgencyAnalytics pages with pagination.
    
    Args:
        url: URL to scrape
        output_dir: Directory to save metadata
        keywords: (Unused - kept for backwards compatibility)
        headless: Run browser in headless mode
        wait_time: Seconds to wait for JavaScript to load
        scroll: Whether to scroll page for lazy-loaded images
        total_pages: Total number of pages to scrape (default: 9)
    
    Returns:
        List of new metadata entries
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    
    logging.info("Starting browser and loading: %s", url)
    
    driver = setup_driver(headless)
    all_collected_metadata = []
    
    try:
        driver.get(url)
        
        logging.info("Waiting %d seconds for JavaScript to load...", wait_time)
        time.sleep(wait_time)
        
        # Process all pages
        for page_num in range(1, total_pages + 1):
            logging.info("=" * 60)
            logging.info("Processing page %d of %d", page_num, total_pages)
            logging.info("=" * 60)
            
            # If not on first page, try to click pagination button
            if page_num > 1:
                try:
                    # Try to find and click the page number button
                    # The pagination buttons have structure: <button><span class="Button_text__ChhxV">2</span></button>
                    wait = WebDriverWait(driver, 10)
                    
                    # Try multiple strategies to find pagination button
                    page_button = None
                    
                    # Strategy 1: Find button containing span with page number text
                    # XPath: //button[.//span[contains(@class, 'Button_text') and text()='2']]
                    try:
                        page_button = driver.find_element(
                            By.XPATH, 
                            f"//button[.//span[contains(@class, 'Button_text') and text()='{page_num}']]"
                        )
                    except NoSuchElementException:
                        # Strategy 2: Find button with class containing "Button_button" that contains span with page number
                        try:
                            # Use partial class match since class names might vary
                            buttons = driver.find_elements(By.CSS_SELECTOR, "button[class*='Button_button']")
                            for btn in buttons:
                                try:
                                    # Find span with Button_text class
                                    span = btn.find_element(By.CSS_SELECTOR, "span[class*='Button_text']")
                                    if span.text.strip() == str(page_num):
                                        page_button = btn
                                        break
                                except:
                                    continue
                        except NoSuchElementException:
                            # Strategy 3: Find any button containing the page number text (fallback)
                            try:
                                page_button = driver.find_element(By.XPATH, f"//button[contains(text(), '{page_num}')]")
                            except NoSuchElementException:
                                # Strategy 4: Find by looking for span with page number and get parent button
                                try:
                                    span = driver.find_element(By.XPATH, f"//span[contains(@class, 'Button_text') and text()='{page_num}']")
                                    page_button = span.find_element(By.XPATH, "./parent::button")
                                except:
                                    pass
                    
                    if page_button:
                        # Check if button is visible and enabled
                        if not page_button.is_displayed():
                            # Scroll to button to ensure it's visible
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", page_button)
                            time.sleep(0.5)
                        
                        # Check if button is disabled
                        disabled = page_button.get_attribute("disabled")
                        if disabled is not None and disabled != "false":
                            logging.warning("Pagination button for page %d is disabled, skipping", page_num)
                            continue
                        
                        # Click the button using JavaScript to avoid interception issues
                        driver.execute_script("arguments[0].click();", page_button)
                        logging.info("Clicked pagination button for page %d", page_num)
                        
                        # Wait for page to load and content to update
                        time.sleep(wait_time)
                        
                        # Additional wait for dynamic content to load
                        try:
                            wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "div.DashboardReportCard_cardWrap__GpuLE")) > 0)
                        except:
                            pass
                    else:
                        logging.warning("Could not find pagination button for page %d, skipping", page_num)
                        continue
                        
                except Exception as e:
                    logging.error(f"Error clicking pagination for page {page_num}: {e}")
                    continue
            
            # Scroll page to ensure all content is loaded
            if scroll:
                logging.info("Scrolling page to load lazy content...")
                scroll_page(driver, scroll_pause=1.0, max_scrolls=3)
            
            # Get page source and parse
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract dashboard items from this page
            page_items = extract_dashboard_items_from_page(soup, url)
            all_collected_metadata.extend(page_items)
            
            logging.info("Extracted %d items from page %d (total so far: %d)", 
                       len(page_items), page_num, len(all_collected_metadata))
        
        logging.info("Finished processing all pages. Total items collected: %d", len(all_collected_metadata))
        
    finally:
        driver.quit()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process and save metadata
    new_metadata_entries = []
    
    if all_collected_metadata:
        metadata_path = output_dir / "image_metadata.json"
        existing_metadata = []
        existing_urls = set()
        
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    existing_metadata = json.load(f)
                for item in existing_metadata:
                    if isinstance(item, dict):
                        url = item.get("thumbnail") or item.get("source_link")
                        if url:
                            existing_urls.add(url)
                logging.info("Loaded %d existing metadata entries", len(existing_metadata))
            except Exception as exc:
                logging.warning("Failed to read existing metadata JSON: %s", exc)
                existing_metadata = []
                existing_urls = set()
        
        combined_metadata = list(existing_metadata)
        for meta in all_collected_metadata:
            # Use thumbnail or source_link as unique identifier
            url = meta.get("thumbnail") or meta.get("source_link")
            if url and url in existing_urls:
                continue
            combined_metadata.append(meta)
            if url:
                existing_urls.add(url)
            new_metadata_entries.append(meta)
        
        try:
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(combined_metadata, f, ensure_ascii=False, indent=2)
            logging.info(
                "Saved metadata for %d new items (total %d) to %s",
                len(new_metadata_entries),
                len(combined_metadata),
                metadata_path,
            )
        except Exception as exc:
            logging.warning("Failed to save metadata JSON: %s", exc)
    else:
        logging.info("No metadata collected.")
    
    return new_metadata_entries


def main():
    parser = argparse.ArgumentParser(
        description="Scrape images from JavaScript-rendered webpages"
    )
    parser.add_argument("url", help="URL to scrape images from")
    parser.add_argument(
        "--output-dir",
        "-o",
        default="images",
        help="Output directory for saved images (default: images/)"
    )
    parser.add_argument(
        "--keywords",
        "-k",
        nargs="+",
        default=None,
        help="(Unused) Keywords parameter kept for compatibility. All images are scraped."
    )
    parser.add_argument(
        "--wait-time",
        type=int,
        default=10,
        help="Seconds to wait for JavaScript to load (default: 10)"
    )
    parser.add_argument(
        "--no-scroll",
        action="store_true",
        help="Disable automatic scrolling for lazy-loaded images"
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Show browser window (not headless)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    parser.add_argument(
        "--total-pages",
        type=int,
        default=9,
        help="Total number of pages to scrape (default: 9)"
    )
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(levelname)s: %(message)s"
    )
    
    output_path = Path(args.output_dir)
    
    new_metadata = scrape_images_with_js(
        args.url,
        output_path,
        keywords=args.keywords,
        headless=not args.show_browser,
        wait_time=args.wait_time,
        scroll=not args.no_scroll,
        total_pages=args.total_pages,
    )
    
    print(f"\n{'='*60}")
    print(f"SCRAPING COMPLETE")
    print(f"{'='*60}")
    print(f"Collected dashboard metadata from pages")
    print(f"New metadata entries saved: {len(new_metadata)}")
    print(f"Metadata file: {(output_path / 'image_metadata.json').absolute()}")
    print(f"{'='*60}")
    
    if new_metadata:
        print("\nNew dashboard items:")
        for entry in new_metadata[:10]:
            title = entry.get('title', 'No title')
            source = entry.get('source_link', 'No link')
            print(f"  - {title}: {source}")
        if len(new_metadata) > 10:
            print(f"  ... and {len(new_metadata) - 10} more")


if __name__ == "__main__":
    main()
