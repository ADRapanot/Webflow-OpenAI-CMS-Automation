#!/usr/bin/env python3
"""
scrape_images_js.py
Scrape images from JavaScript-rendered pages using Selenium.
"""

import argparse
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup


def sanitize_filename(url: str, index: int) -> str:
    """Generate a safe filename from URL."""
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    
    if not filename or '.' not in filename:
        ext = '.jpg'
        if 'png' in url.lower():
            ext = '.png'
        elif 'gif' in url.lower():
            ext = '.gif'
        elif 'webp' in url.lower():
            ext = '.webp'
        filename = f"image_{index}{ext}"
    
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    return filename


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
        
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Collect all image URLs (no keyword filtering - scoring happens later)
        image_urls = []
        
        # Get images from <img> tags
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            srcset = img.get('srcset') or img.get('data-srcset')
            
            if src and not src.startswith('data:'):
                image_urls.append(src)
            
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
            full_url = urljoin(url, img_url.strip().split()[0])
            full_urls.append(full_url)
        
        # Remove duplicates while preserving order
        image_urls = list(dict.fromkeys(full_urls))
        logging.info("Found %d total images", len(image_urls))
        
    finally:
        driver.quit()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_files = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for idx, img_url in enumerate(image_urls, 1):
        try:
            logging.info("Downloading %d/%d: %s", idx, len(image_urls), img_url)
            
            img_response = requests.get(img_url, headers=headers, timeout=30, stream=True)
            img_response.raise_for_status()
            
            content_type = img_response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                logging.warning("Skipping non-image: %s (type: %s)", img_url, content_type)
                continue
            
            filename = sanitize_filename(img_url, idx)
            filepath = output_dir / filename
            
            counter = 1
            while filepath.exists():
                name, ext = os.path.splitext(filename)
                filepath = output_dir / f"{name}_{counter}{ext}"
                counter += 1
            
            with open(filepath, 'wb') as f:
                for chunk in img_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = filepath.stat().st_size
            if file_size < 1024:
                logging.warning("Image too small (%d bytes), deleting: %s", file_size, filepath)
                filepath.unlink()
                continue
            
            logging.info("Saved: %s (%d KB)", filepath, file_size // 1024)
            saved_files.append(str(filepath))
            
        except Exception as e:
            logging.error("Failed to download %s: %s", img_url, e)
            continue
    
    logging.info("Successfully saved %d images to %s", len(saved_files), output_dir)
    return saved_files


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
        default=5,
        help="Seconds to wait for JavaScript to load (default: 5)"
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
    
    saved_files = scrape_images_with_js(
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
    print(f"Scraped all images from page")
    print(f"Total images saved: {len(saved_files)}")
    print(f"Output directory: {output_path.absolute()}")
    print(f"{'='*60}")
    
    if saved_files:
        print("\nSaved files:")
        for filepath in saved_files[:10]:
            print(f"  - {filepath}")
        if len(saved_files) > 10:
            print(f"  ... and {len(saved_files) - 10} more")


if __name__ == "__main__":
    main()
