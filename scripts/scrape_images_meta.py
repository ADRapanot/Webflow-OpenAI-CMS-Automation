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


def extract_image_metadata(img_tag, base_url: str) -> dict:
    """Derive contextual metadata for an image tag."""
    metadata = {}
    
    src = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")
    if src:
        metadata["image_url"] = urljoin(base_url, src.strip())
    else:
        metadata["image_url"] = ""
    
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
    Scrape ALL images from JavaScript-rendered page.
    
    Args:
        url: URL to scrape
        output_dir: Directory to save images
        keywords: (Unused - kept for backwards compatibility)
        headless: Run browser in headless mode
        wait_time: Seconds to wait for JavaScript to load
        scroll: Whether to scroll page for lazy-loaded images
    
    Returns:
        List of saved file paths
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
        
        # Collect all image URLs (no keyword filtering - scoring happens later)
        image_urls = []
        metadata_map = {}
        
        # Get images from <img> tags
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            srcset = img.get('srcset') or img.get('data-srcset')
            
            if src and not src.startswith('data:'):
                image_urls.append(src)
                meta = extract_image_metadata(img, url)
                if meta.get("image_url"):
                    metadata_map[meta["image_url"]] = meta
            
            if srcset:
                srcset_urls = re.findall(r'([^\s,]+(?:\.jpg|\.jpeg|\.png|\.gif|\.webp)[^\s,]*)', srcset, re.IGNORECASE)
                image_urls.extend(srcset_urls)
        
        # Get images from <source> tags
        for source in soup.find_all('source'):
            srcset = source.get('srcset') or source.get('data-srcset')
            src = source.get('src')
            
            if srcset:
                urls = re.findall(r'(https?://[^\s,]+)', srcset)
                image_urls.extend(urls)
            
            if src:
                image_urls.append(src)
        
        # Get images from meta tags (og:image, twitter:image)
        for tag in soup.find_all(['meta', 'link']):
            if tag.get('property') in ['og:image', 'twitter:image']:
                content = tag.get('content')
                if content:
                    image_urls.append(content)
            elif tag.get('rel') == ['image_src']:
                href = tag.get('href')
                if href:
                    image_urls.append(href)
        
        # Convert to full URLs and remove duplicates
        full_urls = []
        for img_url in image_urls:
            if img_url.startswith('data:'):
                continue
            stripped_url = img_url.strip().split()[0]
            full_url = urljoin(url, stripped_url)
            if urlparse(full_url).path.lower().endswith('.svg'):
                continue
            full_urls.append(full_url)
            if full_url not in metadata_map and img_url in metadata_map:
                metadata_map[full_url] = metadata_map[img_url]
        
        # Remove duplicates while preserving order
        image_urls = list(dict.fromkeys(full_urls))
        logging.info("Found %d total images", len(image_urls))
        
    finally:
        driver.quit()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    collected_metadata = []
    
    for idx, img_url in enumerate(image_urls, 1):
        logging.info("Collecting metadata for %d/%d: %s", idx, len(image_urls), img_url)
        meta = metadata_map.get(img_url, {})
        if "image_url" not in meta or not meta["image_url"]:
            meta = dict(meta)
            meta["image_url"] = img_url
        meta.setdefault("source_link", "")
        meta.setdefault("title", "")
        meta.setdefault("author", "")
        meta.setdefault("extra_text", "")
        collected_metadata.append(meta)
    
    logging.info("Collected metadata for %d images", len(collected_metadata))
    
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
                        url = item.get("image_url")
                        if url:
                            existing_urls.add(url)
                logging.info("Loaded %d existing metadata entries", len(existing_metadata))
            except Exception as exc:
                logging.warning("Failed to read existing metadata JSON: %s", exc)
                existing_metadata = []
                existing_urls = set()
        
        combined_metadata = list(existing_metadata)
        for meta in collected_metadata:
            url = meta.get("image_url")
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
        print("\nNew image URLs:")
        for entry in new_metadata[:10]:
            print(f"  - {entry.get('image_url', '')}")
        if len(new_metadata) > 10:
            print(f"  ... and {len(new_metadata) - 10} more")


if __name__ == "__main__":
    main()
