#!/usr/bin/env python3
"""
upload_mock_image.py
Upload a mock/placeholder image to Webflow and get the hosted URL.
"""

import argparse
import hashlib
import io
import json
import logging
import os
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont


def create_mock_image(text: str = "Mock Dashboard", size: tuple = (800, 600)) -> bytes:
    """Create a simple mock image with text."""
    img = Image.new('RGB', size, color=(0, 102, 204))
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except:
        font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size[0] - text_width) // 2
    y = (size[1] - text_height) // 2
    
    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def calculate_md5(data: bytes) -> str:
    """Calculate MD5 hash of file data."""
    return hashlib.md5(data).hexdigest()


def upload_to_webflow(
    site_id: str,
    webflow_token: str,
    file_name: str,
    file_data: bytes,
    folder_id: str | None = None,
) -> dict:
    """
    Upload an image to Webflow using the 2-step process.
    Returns dict with assetUrl, hostedUrl, and asset ID.
    """
    headers = {
        "Authorization": f"Bearer {webflow_token}",
        "Content-Type": "application/json",
        "accept-version": "2.0.0",
    }
    
    file_hash = calculate_md5(file_data)
    logging.info("Calculated MD5 hash: %s", file_hash)
    
    prepare_url = f"https://api.webflow.com/v2/sites/{site_id}/assets"
    payload = {
        "fileName": file_name,
        "fileHash": file_hash,
    }
    if folder_id:
        payload["parentFolder"] = folder_id
    
    logging.info("Step 1: Getting upload credentials from Webflow")
    response = requests.post(prepare_url, headers=headers, json=payload, timeout=30)
    
    if response.status_code >= 400:
        logging.error("Failed to prepare upload (%s): %s", response.status_code, response.text)
        raise RuntimeError(f"Prepare upload failed: {response.text}")
    
    upload_info = response.json()
    upload_url = upload_info["uploadUrl"]
    upload_details = upload_info["uploadDetails"]
    
    logging.info("Step 2: Uploading file to S3: %s", upload_url)
    
    files = {'file': (file_name, file_data, 'image/png')}
    s3_response = requests.post(upload_url, data=upload_details, files=files, timeout=60)
    
    if s3_response.status_code not in (200, 201, 204):
        logging.error("S3 upload failed (%s): %s", s3_response.status_code, s3_response.text)
        raise RuntimeError(f"S3 upload failed: {s3_response.text}")
    
    logging.info("Upload successful!")
    
    return {
        "id": upload_info.get("id"),
        "assetUrl": upload_info.get("assetUrl"),
        "hostedUrl": upload_info.get("hostedUrl"),
        "fileName": upload_info.get("originalFileName"),
        "createdOn": upload_info.get("createdOn"),
    }


def main():
    parser = argparse.ArgumentParser(description="Upload a mock image to Webflow")
    parser.add_argument("--site-id", required=True, help="Webflow site ID")
    parser.add_argument("--text", default="Mock Dashboard", help="Text to display on mock image")
    parser.add_argument("--width", type=int, default=800, help="Image width")
    parser.add_argument("--height", type=int, default=600, help="Image height")
    parser.add_argument("--file-name", default="mock-dashboard.png", help="Output file name")
    parser.add_argument("--folder-id", default=None, help="Optional Webflow folder ID")
    parser.add_argument("--save-local", action="store_true", help="Save image locally before upload")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s: %(message)s")
    
    webflow_token = os.getenv("WEBFLOW_TOKEN")
    if not webflow_token:
        raise RuntimeError("Set WEBFLOW_TOKEN environment variable")
    
    logging.info("Creating mock image: %dx%d with text '%s'", args.width, args.height, args.text)
    image_data = create_mock_image(args.text, (args.width, args.height))
    
    if args.save_local:
        local_path = Path(args.file_name)
        local_path.write_bytes(image_data)
        logging.info("Saved local copy to %s", local_path)
    
    result = upload_to_webflow(
        site_id=args.site_id,
        webflow_token=webflow_token,
        file_name=args.file_name,
        file_data=image_data,
        folder_id=args.folder_id,
    )
    
    print("\n" + "="*60)
    print("UPLOAD SUCCESSFUL")
    print("="*60)
    print(json.dumps(result, indent=2))
    print("="*60)
    print(f"\nHosted URL: {result['hostedUrl']}")
    print(f"Asset URL: {result['assetUrl']}")
    print(f"Asset ID: {result['id']}")


if __name__ == "__main__":
    main()
