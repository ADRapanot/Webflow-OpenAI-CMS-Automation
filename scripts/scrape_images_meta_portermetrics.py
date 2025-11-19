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


def extract_image_metadata(img_tag, base_url: str) -> dict:
    """Derive contextual metadata for an image tag."""
    metadata = {}
    
    src = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")
    if src:
        metadata["thumbnail"] = urljoin(base_url, src.strip())
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


def _normalize_spaces(text: str) -> str:
    """Collapse all runs of whitespace into single spaces and trim."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_elementor_posts(soup: BeautifulSoup, base_url: str) -> list:
    """
    Extract metadata from Elementor post cards like:
    <article class="elementor-post elementor-grid-item ...">
      - thumbnail: img[src]
      - source_link: a[href] around thumbnail/title
      - title: h2.elementor-post__title a text
      - extra_text: div.elementor-post__excerpt p text
    """
    results = []
    for article in soup.select("article.elementor-post.elementor-grid-item"):
        # Source link from thumbnail or title
        link_tag = article.select_one("a.elementor-post__thumbnail__link[href]") or article.select_one("h2.elementor-post__title a[href]")
        source_link = urljoin(base_url, link_tag["href"].strip()) if link_tag and link_tag.has_attr("href") else ""

        # Thumbnail - extract from img tag, never use source_link if img tag exists
        img_tag = article.select_one(".elementor-post__thumbnail img")
        thumbnail = ""
        img_tag_found = img_tag is not None
        
        if img_tag:
            # Handle srcset first - extract the largest image URL if srcset exists
            srcset = img_tag.get("srcset") or img_tag.get("data-srcset")
            if srcset:
                # Extract URLs from srcset (format: "url1 size1, url2 size2")
                srcset_urls = re.findall(r'([^\s,]+(?:\.jpg|\.jpeg|\.png|\.gif|\.webp)[^\s,]*)', srcset, re.IGNORECASE)
                if srcset_urls:
                    # Use the largest image (usually the last one in srcset)
                    thumbnail = urljoin(base_url, srcset_urls[-1].strip())
            
            # If no thumbnail from srcset, try src attribute and other data attributes
            if not thumbnail:
                src = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src") or img_tag.get("data-original")
                if src and src.strip() and not src.startswith('data:'):
                    thumbnail = urljoin(base_url, src.strip())
        
        # Only use source_link as fallback if no img tag was found at all
        # Never overwrite a valid image URL with source_link, and never use source_link if img tag exists
        if not thumbnail and source_link and not img_tag_found:
            thumbnail = source_link

        # Title
        title_tag = article.select_one("h2.elementor-post__title a")
        raw_title = title_tag.get_text(" ", strip=True) if title_tag else ""
        title = _normalize_spaces(raw_title)

        # Excerpt
        excerpt_tag = article.select_one(".elementor-post__excerpt")
        raw_excerpt = excerpt_tag.get_text(" ", strip=True) if excerpt_tag else ""
        extra_text = _normalize_spaces(raw_excerpt)

        if thumbnail or source_link or title or extra_text:
            results.append({
                "thumbnail": thumbnail,
                "source_link": source_link,
                "title": title,
                "author": "",
                "extra_text": extra_text,
            })
    return results


def extract_elementor_text_blocks(soup: BeautifulSoup, base_url: str) -> list:
    """
    Fallback extraction for cases where only the inner text block exists:
    <div class="elementor-post__text">
      <h2 class="elementor-post__title"><a href="...">Title</a></h2>
      <div class="elementor-post__excerpt"><p>Excerpt ...</p></div>
    </div>
    Uses the link as both source_link and thumbnail placeholder.
    """
    results = []
    for text_block in soup.select("div.elementor-post__text"):
        title_tag = text_block.select_one("h2.elementor-post__title a[href]")
        source_link = urljoin(base_url, title_tag["href"].strip()) if title_tag and title_tag.has_attr("href") else ""

        raw_title = title_tag.get_text(" ", strip=True) if title_tag else ""
        title = _normalize_spaces(raw_title)

        excerpt_tag = text_block.select_one(".elementor-post__excerpt")
        raw_excerpt = excerpt_tag.get_text(" ", strip=True) if excerpt_tag else ""
        extra_text = _normalize_spaces(raw_excerpt)

        if source_link or title or extra_text:
            results.append({
                "thumbnail": source_link or "",
                "source_link": source_link,
                "title": title,
                "author": "",
                "extra_text": extra_text,
            })
    return results


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
        elementor_entries_list = []

        # Special handling: Elementor post cards (Porter Metrics templates/blog)
        try:
            elementor_entries = extract_elementor_posts(soup, url)
            for entry in elementor_entries:
                thumb = entry.get("thumbnail", "")
                if thumb:
                    metadata_map[thumb] = entry
                    image_urls.append(thumb)
            elementor_entries_list = elementor_entries
        except Exception as e:
            logging.debug(f"Elementor parsing skipped due to error: {e}")

        # Fallback: handle cards that only include the text block (no outer article)
        try:
            text_block_entries = extract_elementor_text_blocks(soup, url)
            for entry in text_block_entries:
                thumb = entry.get("thumbnail", "")
                if thumb:
                    # Do not enforce image extension; include as metadata-only entry later
                    if thumb not in metadata_map:
                        metadata_map[thumb] = entry
                    # Also add to image_urls so we attempt to keep it through the flow;
                    # if filtered out later by extension/dimension steps, we will still merge it after.
                    image_urls.append(thumb)
            elementor_entries_list.extend(text_block_entries)
        except Exception as e:
            logging.debug(f"Elementor text-block parsing skipped due to error: {e}")
        
        # Get images from <img> tags
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            srcset = img.get('srcset') or img.get('data-srcset')
            
            if src and not src.startswith('data:'):
                image_urls.append(src)
                meta = extract_image_metadata(img, url)
                if meta.get("thumbnail"):
                    metadata_map[meta["thumbnail"]] = meta
            
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
        
        # Convert to full URLs, filter by image extension, and remove duplicates
        full_urls = []
        for img_url in image_urls:
            if img_url.startswith('data:'):
                continue
            stripped_url = img_url.strip().split()[0]
            full_url = urljoin(url, stripped_url)
            
            # Filter: only include URLs with image extensions
            if not has_image_extension(full_url):
                logging.debug(f"Skipping URL without image extension: {full_url}")
                continue
            
            full_urls.append(full_url)
            if full_url not in metadata_map and img_url in metadata_map:
                metadata_map[full_url] = metadata_map[img_url]
        
        # Remove duplicates while preserving order
        image_urls = list(dict.fromkeys(full_urls))
        logging.info("Found %d total images", len(image_urls))
        
        # Filter images by dimensions (width and height must be > 200px)
        filtered_urls = []
        min_size = 200
        logging.info("Filtering images by dimensions (min %dpx x %dpx)...", min_size, min_size)
        
        for idx, img_url in enumerate(image_urls, 1):
            logging.info("Checking dimensions for %d/%d: %s", idx, len(image_urls), img_url)
            width, height = check_image_dimensions(driver, img_url, min_size)
            
            if (width > min_size and height > min_size) or (width == 0 and height == 0):
                logging.info("  ✓ Image accepted: %dx%d", width, height)
                filtered_urls.append(img_url)
            else:
                logging.info("  ✗ Image skipped: dimensions too small %dx%d", width, height)
        
        image_urls = filtered_urls
        logging.info("Filtered to %d images with dimensions > %dpx x %dpx", len(image_urls), min_size, min_size)
        
    finally:
        driver.quit()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    collected_metadata = []
    
    for idx, img_url in enumerate(image_urls, 1):
        logging.info("Collecting metadata for %d/%d: %s", idx, len(image_urls), img_url)
        meta = metadata_map.get(img_url, {})
        if "thumbnail" not in meta or not meta["thumbnail"]:
            meta = dict(meta)
            meta["thumbnail"] = img_url
        meta.setdefault("source_link", "")
        meta.setdefault("title", "")
        meta.setdefault("author", "")
        meta.setdefault("extra_text", "")
        collected_metadata.append(meta)

    # Include Elementor entries that may not have image extensions (thus filtered out)
    try:
        existing_thumbs = {m.get("thumbnail") for m in collected_metadata}
        for entry in elementor_entries_list:
            thumb = entry.get("thumbnail")
            if not thumb or thumb in existing_thumbs:
                continue
            collected_metadata.append(entry)
    except Exception as e:
        logging.debug(f"Failed to merge Elementor-only entries: {e}")
    
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
