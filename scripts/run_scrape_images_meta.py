#!/usr/bin/env python3
"""
Batch runner for `scrape_images_meta.py`.

Executes the metadata scraper across the Windsor template gallery URLs defined
in `scrape_urls_google.py` (lines 39-54) without downloading image files.
"""

import argparse
import logging
from pathlib import Path
from time import sleep

from scrape_images_meta_portermetrics import scrape_images_with_js
from scrape_urls_google import WINDSOR_TEMPLATE_PAGES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run scrape_images_meta.py across Windsor template gallery URLs."
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="images",
        help="Directory containing image_metadata.json (default: images/).",
    )
    parser.add_argument(
        "--wait-time",
        type=int,
        default=8,
        help="Seconds to wait for each page to finish rendering (default: 8).",
    )
    parser.add_argument(
        "--no-scroll",
        action="store_true",
        help="Disable automatic scrolling for lazy-loaded images.",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Show the Chrome window instead of running headless.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay in seconds between requests (default: 2.0).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    output_dir = Path(args.output_dir)
    total_new_entries = 0

    logging.info("Starting batch metadata collection for %d URLs.", len(WINDSOR_TEMPLATE_PAGES))

    for idx, url in enumerate(WINDSOR_TEMPLATE_PAGES, 1):
        logging.info("Processing %d/%d: %s", idx, len(WINDSOR_TEMPLATE_PAGES), url)
        try:
            new_entries = scrape_images_with_js(
                url,
                output_dir,
                keywords=None,
                headless=not args.show_browser,
                wait_time=args.wait_time,
                scroll=not args.no_scroll,
            )
            logging.info("Added %d new metadata entries for %s", len(new_entries), url)
            total_new_entries += len(new_entries)
        except Exception as exc:
            logging.exception("Failed to process %s: %s", url, exc)

        if idx < len(WINDSOR_TEMPLATE_PAGES) and args.delay > 0:
            sleep(args.delay)

    logging.info("Batch complete. Total new metadata entries: %d", total_new_entries)
    logging.info("Metadata stored in: %s", (output_dir / "image_metadata.json").resolve())


if __name__ == "__main__":
    main()


