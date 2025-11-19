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
import requests
from io import BytesIO
from PIL import Image


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


def check_image_dimensions(img_url: str, min_size: int = 200) -> tuple:
    """
    Check if an image has width and height greater than min_size.
    
    Args:
        img_url: URL of the image to check
        min_size: Minimum width and height in pixels (default: 200)
    
    Returns:
        Tuple of (width, height) if image is valid, (0, 0) otherwise
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(img_url, headers=headers, timeout=10, stream=True)
        response.raise_for_status()
        
        # Read image into memory
        img_data = BytesIO(response.content)
        img = Image.open(img_data)
        width, height = img.size
        
        if width > min_size and height > min_size:
            return (width, height)
        else:
            logging.debug(f"Image {img_url} dimensions ({width}x{height}) are too small (min: {min_size}x{min_size})")
            return (0, 0)
    except Exception as e:
        logging.debug(f"Failed to check dimensions for {img_url}: {e}")
        return (0, 0)


def extract_bymarketers_product_metadata(product_tag, base_url: str) -> dict:
    """
    Extract metadata from a ByMarketers product element.
    
    Structure:
    - <li class="product type-product ...">
      - <a href="source_link" class="product-text-name">title</a>
      - <div class="product-short-description long-description">extra_text</div>
      - <div class="product-img" style="background: url(thumbnail_url)"></div>
    """
    metadata = {
        "thumbnail": "",
        "source_link": "",
        "title": "",
        "author": "",
        "extra_text": ""
    }
    
    # Extract title and source_link from product-text-name link
    # There may be multiple links with this class, prioritize the one with text content
    title_links = product_tag.find_all("a", class_="product-text-name", href=True)
    for title_link in title_links:
        title_text = title_link.get_text(strip=True)
        if title_text:
            metadata["title"] = title_text
            href = title_link.get("href", "")
            if href:
                metadata["source_link"] = urljoin(base_url, href.strip())
            break
    
    # If title not found, try alternative: button alt link with data-product-title
    if not metadata["title"]:
        button_link = product_tag.find("a", class_="button alt", href=True)
        if button_link:
            href = button_link.get("href", "")
            if href and not metadata["source_link"]:
                metadata["source_link"] = urljoin(base_url, href.strip())
            # Try to get title from data-product-title attribute
            title_attr = button_link.get("data-product-title", "")
            if title_attr:
                metadata["title"] = title_attr.strip()
    
    # If source_link still not found, use any product-text-name link
    if not metadata["source_link"] and title_links:
        href = title_links[0].get("href", "")
        if href:
            metadata["source_link"] = urljoin(base_url, href.strip())
    
    # Extract extra_text from product-short-description
    description_div = product_tag.find("div", class_="product-short-description")
    if description_div:
        metadata["extra_text"] = description_div.get_text(strip=True)
    
    # Extract thumbnail from product-img div's style attribute
    # Style format: "background: url(https://...)" or "background: url('https://...')"
    product_img = product_tag.find("div", class_="product-img")
    if product_img:
        style_attr = product_img.get("style", "")
        if style_attr:
            # Extract URL from style attribute: background: url(...) or url('...') or url("...")
            # Match: url( followed by optional quote, then URL content, then optional quote and )
            url_match = re.search(r'url\s*\(\s*["\']?([^"\'()]+)["\']?\s*\)', style_attr)
            if url_match:
                img_url = url_match.group(1).strip()
                if img_url:
                    # Convert relative URLs to absolute
                    if img_url.startswith("/"):
                        metadata["thumbnail"] = urljoin(base_url, img_url)
                    elif img_url.startswith("http"):
                        metadata["thumbnail"] = img_url
                    else:
                        metadata["thumbnail"] = urljoin(base_url, img_url)
    
    return metadata


def extract_catchr_card_metadata(card_tag, base_url: str) -> dict:
    """
    Extract metadata from a Catchr card element.
    
    Structure:
    - <div class="cards">
      - <div class="cards-image"><img src="thumbnail_url" ...></div>
      - <div class="cards-info">
        - <div class="template-info">
          - <div class="templatename">title</div>
          - <div class="div-block-452">
            - <div class="text-block-52">extra_text</div>
            - <a href="source_link" class="button-23">...</a>
    """
    metadata = {
        "thumbnail": "",
        "source_link": "",
        "title": "",
        "author": "",
        "extra_text": ""
    }
    
    # Extract thumbnail from cards-image > img
    cards_image = card_tag.find("div", class_="cards-image")
    if cards_image:
        img_tag = cards_image.find("img")
        if img_tag:
            # Use src attribute (the main image URL)
            img_src = img_tag.get("src", "")
            if img_src:
                img_src = img_src.strip()
                # Convert relative URLs to absolute
                if img_src.startswith("/"):
                    metadata["thumbnail"] = urljoin(base_url, img_src)
                elif img_src.startswith("http"):
                    metadata["thumbnail"] = img_src
                else:
                    metadata["thumbnail"] = urljoin(base_url, img_src)
    
    # Extract title from templatename
    templatename = card_tag.find("div", class_="templatename")
    if templatename:
        metadata["title"] = templatename.get_text(strip=True)
    
    # Extract extra_text from text-block-52
    text_block = card_tag.find("div", class_="text-block-52")
    if text_block:
        metadata["extra_text"] = text_block.get_text(strip=True)
    
    # Extract source_link from button-23 link
    button_link = card_tag.find("a", class_="button-23", href=True)
    if button_link:
        href = button_link.get("href", "")
        if href:
            metadata["source_link"] = urljoin(base_url, href.strip())
    
    return metadata


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
    Scrape template metadata from ByMarketers product pages.
    
    Specifically extracts:
    - Title from <a class="product-text-name"> elements
    - Source link from <a class="product-text-name"> or <a class="button alt"> href attributes
    - Thumbnail images from <div class="product-img"> style="background: url(...)" attributes
    - Extra text from <div class="product-short-description"> elements
    
    Args:
        url: ByMarketers URL to scrape
        output_dir: Directory to save metadata
        keywords: (Unused - kept for backwards compatibility)
        headless: Run browser in headless mode
        wait_time: Seconds to wait for JavaScript to load
        scroll: Whether to scroll page for lazy-loaded images
    
    Returns:
        List of metadata dictionaries with title, source_link, thumbnail, and extra_text
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
        
        # ByMarketers-specific: Find all product li elements
        collected_metadata = []
        products = soup.find_all('li', class_=lambda x: x and 'product' in x.split() if x else False)
        logging.info("Found %d product elements", len(products))
        
        for idx, product in enumerate(products, 1):
            logging.info("Processing product %d/%d", idx, len(products))
            meta = extract_bymarketers_product_metadata(product, url)
            
            # Only process if we have at least a thumbnail or title
            if not (meta.get("thumbnail") or meta.get("title")):
                logging.warning("Skipping product %d - no thumbnail or title found", idx)
                continue
            
            # Check image dimensions - skip if width or height <= 200px
            thumbnail_url = meta.get("thumbnail", "")
            if thumbnail_url:
                logging.info("Checking dimensions for thumbnail: %s", thumbnail_url)
                width, height = check_image_dimensions(thumbnail_url, min_size=200)
                if width == 0 or height == 0:
                    logging.warning(
                        "Skipping product %d - image dimensions too small (thumbnail: %s)",
                        idx, thumbnail_url
                    )
                    continue
                logging.info(
                    "Image dimensions OK: %dx%d (thumbnail: %s)",
                    width, height, thumbnail_url
                )
            
            # Add to collected metadata if it passed all checks
            collected_metadata.append(meta)
            logging.debug(
                "Extracted: title='%s', source_link='%s', thumbnail='%s', extra_text='%s'",
                meta.get("title", ""),
                meta.get("source_link", ""),
                meta.get("thumbnail", ""),
                meta.get("extra_text", "")
            )
        
        logging.info("Collected metadata for %d products", len(collected_metadata))
        
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
        description="Scrape template metadata from ByMarketers product pages (titles, source links, thumbnails, extra text)"
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
        print("\nNew template entries:")
        for entry in new_metadata[:10]:
            title = entry.get('title', 'No title')
            thumbnail = entry.get('thumbnail', 'No thumbnail')
            source = entry.get('source_link', 'No source')
            extra_text = entry.get('extra_text', 'No description')
            print(f"  - {title}")
            print(f"    Thumbnail: {thumbnail}")
            print(f"    Source: {source}")
            print(f"    Description: {extra_text}")
        if len(new_metadata) > 10:
            print(f"  ... and {len(new_metadata) - 10} more")


if __name__ == "__main__":
    main()
