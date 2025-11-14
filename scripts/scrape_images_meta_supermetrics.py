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


def clean_thumbnail_url(url: str) -> str:
    """
    Clean thumbnail URL by extracting the actual CDN URL from wrapper URLs.
    
    Handles URLs like:
    "https://supermetrics.com/template-gallery/reporting-tools/format=avif/https:/cdn.sanity.io/images/...?w=1887&h=1975&fit=max"
    
    Returns:
    "https://cdn.sanity.io/images/..." (without query parameters)
    """
    if not url:
        return url
    
    # Look for cdn.sanity.io in the URL
    sanity_pos = url.find('cdn.sanity.io')
    if sanity_pos > 0:
        # Look backwards to find the protocol (https: or http:)
        # Search in a window before the domain
        search_start = max(0, sanity_pos - 50)
        before_domain = url[search_start:sanity_pos]
        
        # Find https?: or http?: pattern (with one or two slashes)
        protocol_match = re.search(r'(https?:/+)', before_domain)
        if protocol_match:
            # Get the start position relative to full URL
            protocol_start = search_start + protocol_match.start()
            # Find the end (query string or end of URL)
            query_pos = url.find('?', sanity_pos)
            if query_pos == -1:
                query_pos = len(url)
            
            # Extract the URL
            clean_url = url[protocol_start:query_pos]
            # Fix protocol to always have exactly two slashes (https:/ -> https://, https:/// -> https://)
            clean_url = re.sub(r'^(https?):/+', r'\1://', clean_url)
            return clean_url
    
    # Try Cloudflare CDN wrapper pattern
    cloudflare_match = re.search(r'https?://[^/]+/cdn-cgi/image/[^/]+/(https?:/+/[^\s?]+)', url)
    if cloudflare_match:
        clean_url = cloudflare_match.group(1)
        # Fix protocol to always have exactly two slashes
        clean_url = re.sub(r'^(https?):/+', r'\1://', clean_url)
        # Remove query parameters
        if '?' in clean_url:
            clean_url = clean_url.split('?')[0]
        return clean_url
    
    # If no CDN pattern found, just remove query parameters from the original URL
    if '?' in url:
        url = url.split('?')[0]
    
    return url


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


def extract_supermetrics_report_metadata(article_tag, base_url: str) -> dict:
    """
    Extract metadata from a Supermetrics report article.
    
    Structure:
    - <article data-template-type="report">
      - <a href="source_link"><h3>title</h3></a>
      - <picture> with <source> and <img> tags for thumbnail
    """
    metadata = {
        "thumbnail": "",
        "source_link": "",
        "title": "",
        "author": "",
        "extra_text": ""
    }
    
    # Extract title and source_link from <a><h3> structure
    link_tag = article_tag.find("a", href=True)
    if link_tag:
        href = link_tag.get("href", "")
        if href:
            metadata["source_link"] = urljoin(base_url, href.strip())
        
        h3_tag = link_tag.find("h3")
        if h3_tag:
            metadata["title"] = h3_tag.get_text(strip=True)
    
    # Extract thumbnail from <picture> tag
    picture_tag = article_tag.find("picture")
    if picture_tag:
        # First try to get the highest resolution from srcset in <source> tags
        best_url = None
        best_width = 0
        
        # Check all <source> tags for srcset
        for source in picture_tag.find_all("source", srcset=True):
            srcset = source.get("srcset", "")
            # Parse srcset: "url1 320w, url2 480w, ..."
            # Split by comma first, then parse each entry
            for entry in srcset.split(','):
                entry = entry.strip()
                # Match: URL (may contain spaces) followed by space and number+w
                match = re.search(r'(.+?)\s+(\d+)w\s*$', entry)
                if match:
                    url = match.group(1).strip()
                    width_str = match.group(2)
                    try:
                        width = int(width_str)
                        if width > best_width:
                            best_width = width
                            best_url = url
                    except ValueError:
                        continue
        
        # If no srcset found, try the <img> tag
        if not best_url:
            img_tag = picture_tag.find("img")
            if img_tag:
                # Try srcset first
                img_srcset = img_tag.get("srcset", "")
                if img_srcset:
                    # Parse srcset: "url1 320w, url2 480w, ..."
                    # Split by comma first, then parse each entry
                    for entry in img_srcset.split(','):
                        entry = entry.strip()
                        # Match: URL (may contain spaces) followed by space and number+w
                        match = re.search(r'(.+?)\s+(\d+)w\s*$', entry)
                        if match:
                            url = match.group(1).strip()
                            width_str = match.group(2)
                            try:
                                width = int(width_str)
                                if width > best_width:
                                    best_width = width
                                    best_url = url
                            except ValueError:
                                continue
                
                # Fall back to src attribute
                if not best_url:
                    img_src = img_tag.get("src", "")
                    if img_src:
                        best_url = img_src.strip()
        
        if best_url:
            # Clean up the URL - extract actual CDN URL from wrapper URLs
            # This handles URLs like:
            # "https://supermetrics.com/template-gallery/reporting-tools/format=avif/https:/cdn.sanity.io/images/...?w=1887&h=1975&fit=max"
            best_url = clean_thumbnail_url(best_url)
            
            # Convert relative URLs to absolute
            if best_url.startswith("/"):
                metadata["thumbnail"] = urljoin(base_url, best_url)
            elif best_url.startswith("http"):
                metadata["thumbnail"] = best_url
            else:
                metadata["thumbnail"] = urljoin(base_url, best_url)
    
    return metadata


def extract_image_metadata(img_tag, base_url: str) -> dict:
    """Derive contextual metadata for an image tag."""
    metadata = {}
    
    src = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")
    if src:
        cleaned_src = clean_thumbnail_url(src.strip())
        metadata["thumbnail"] = urljoin(base_url, cleaned_src)
    else:
        metadata["thumbnail"] = ""
    
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
    
    figure = img_tag.find_parent("figure")
    caption_text = ""
    if figure:
        caption = figure.find("figcaption")
        if caption:
            caption_text = caption.get_text(" ", strip=True)
    nearby_text = _get_nearby_text(img_tag)
    
    metadata["extra_text"] = caption_text or nearby_text
    
    return metadata


def scrape_images_with_js(
    url: str,
    output_dir: Path,
    keywords: list = None,
    headless: bool = True,
    wait_time: int = 5,
    scroll: bool = True,
) -> list:
    """
    Scrape report metadata from Supermetrics pages.
    
    Specifically extracts:
    - Title from <h3> tags inside <a> tags
    - Source link from <a> href attributes
    - Thumbnail images from <picture> tags (highest resolution from srcset)
    
    Args:
        url: Supermetrics URL to scrape
        output_dir: Directory to save metadata
        keywords: (Unused - kept for backwards compatibility)
        headless: Run browser in headless mode
        wait_time: Seconds to wait for JavaScript to load
        scroll: Whether to scroll page for lazy-loaded images
    
    Returns:
        List of metadata dictionaries with title, source_link, and thumbnail
    """
    logging.info("Starting browser and loading: %s", url)
    
    driver = setup_driver(headless)
    
    try:
        driver.get(url)
        
        logging.info("Waiting %d seconds for JavaScript to load...", wait_time)
        time.sleep(wait_time)
        
        if scroll:
            logging.info("Scrolling page to load lazy images...")
            scroll_page(driver)
        
        page_source = driver.page_source
        
        # Save page source for debugging
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_dir = Path("debug_output")
        debug_dir.mkdir(exist_ok=True)
        page_source_file = debug_dir / f"scrape_page_source_{timestamp}.html"
        
        try:
            with open(page_source_file, 'w', encoding='utf-8') as f:
                f.write(page_source)
            logging.info(f"Saved page source to: {page_source_file}")
        except Exception as e:
            logging.warning(f"Failed to save page source: {e}")
        
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Supermetrics-specific: Find all report articles
        collected_metadata = []
        articles = soup.find_all('article', {'data-template-type': 'report'})
        logging.info("Found %d report articles", len(articles))
        
        for idx, article in enumerate(articles, 1):
            logging.info("Processing article %d/%d", idx, len(articles))
            meta = extract_supermetrics_report_metadata(article, url)
            
            # Only add if we have at least a thumbnail or title
            if meta.get("thumbnail") or meta.get("title"):
                collected_metadata.append(meta)
                logging.debug(
                    "Extracted: title='%s', source_link='%s', thumbnail='%s'",
                    meta.get("title", ""),
                    meta.get("source_link", ""),
                    meta.get("thumbnail", "")
                )
            else:
                logging.warning("Skipping article %d - no thumbnail or title found", idx)
        
        logging.info("Collected metadata for %d reports", len(collected_metadata))
        
    finally:
        driver.quit()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    new_metadata_entries = []
    
    if collected_metadata:
        metadata_path = output_dir / "image_metadata.json"
        existing_metadata = []
        existing_urls = set()
        
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    existing_metadata = json.load(f)
                for item in existing_metadata:
                    if isinstance(item, dict):
                        url = item.get("thumbnail")
                        if url:
                            existing_urls.add(url)
                logging.info("Loaded %d existing metadata entries", len(existing_metadata))
            except Exception as exc:
                logging.warning("Failed to read existing metadata JSON: %s", exc)
                existing_metadata = []
                existing_urls = set()
        
        combined_metadata = list(existing_metadata)
        for meta in collected_metadata:
            url = meta.get("thumbnail")
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
                "Saved metadata for %d new images (total %d) to %s",
                len(new_metadata_entries),
                len(combined_metadata),
                metadata_path,
            )
        except Exception as exc:
            logging.warning("Failed to save metadata JSON: %s", exc)
    else:
        logging.info("No additional metadata collected for images.")
    
    return new_metadata_entries


def main():
    parser = argparse.ArgumentParser(
        description="Scrape report metadata from Supermetrics pages (titles, source links, thumbnails)"
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
    )
    
    print(f"\n{'='*60}")
    print(f"SCRAPING COMPLETE")
    print(f"{'='*60}")
    print(f"Collected image metadata from page")
    print(f"New metadata entries saved: {len(new_metadata)}")
    print(f"Metadata file: {(output_path / 'image_metadata.json').absolute()}")
    print(f"{'='*60}")
    
    if new_metadata:
        print("\nNew report entries:")
        for entry in new_metadata[:10]:
            title = entry.get('title', 'No title')
            thumbnail = entry.get('thumbnail', 'No thumbnail')
            source = entry.get('source_link', 'No source')
            print(f"  - {title}")
            print(f"    Thumbnail: {thumbnail}")
            print(f"    Source: {source}")
        if len(new_metadata) > 10:
            print(f"  ... and {len(new_metadata) - 10} more")


if __name__ == "__main__":
    main()
