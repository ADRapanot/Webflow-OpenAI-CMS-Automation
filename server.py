#!/usr/bin/env python3
"""
server.py
Webhook handler for Webflow CMS automation with image scraping and selection.
"""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from scrape_images_js import scrape_images_with_js
# from select_best_image import analyze_image
from upload_mock_image import upload_to_webflow
from chatgpt_to_webflow import WebflowPublisher, DashboardItem, DashboardGenerator, slugify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def fetch_and_save_collection_schema(collection_id: str, webflow_token: str) -> Dict[str, Any]:
    """
    Fetch collection schema from Webflow and save it to file.
    Returns the collection schema.
    """
    url = f"https://api.webflow.com/v2/collections/{collection_id}"
    headers = {
        "Authorization": f"Bearer {webflow_token}",
        "Content-Type": "application/json",
        "accept-version": "2.0.0",
    }
    
    logging.info(f"Fetching collection schema for: {collection_id}")
    response = requests.get(url, headers=headers, timeout=30)
    
    if response.status_code >= 400:
        logging.error(f"Failed to fetch collection schema ({response.status_code}): {response.text}")
        raise RuntimeError(f"Failed to fetch collection schema: {response.text}")
    
    schema = response.json()
    
    # Save schema to file
    schema_file = Path(f"collection_schema_{collection_id}.json")
    with schema_file.open("w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    
    logging.info(f"Saved collection schema to: {schema_file}")
    return schema


def download_thumbnail(url, output_dir="downloaded_thumbnails"):
    """Download an image from the given URL and return its local file path."""
    import uuid
    
    os.makedirs(output_dir, exist_ok=True)
    # Use the last segment as filename, with fallback to a unique name
    filename = url.split("/")[-1].split("?")[0]
    if not filename:
        filename = str(uuid.uuid4())
    
    try:
        resp = requests.get(url, timeout=30, stream=True)
        resp.raise_for_status()
        # Skip SVGs or non-image responses
        content_type = resp.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            return None
        if "svg" in content_type.lower():
            return None
        
        # Ensure filename has proper extension based on content-type
        if not Path(filename).suffix:
            # Map content-type to file extension
            ext_map = {
                'image/jpeg': '.jpg',
                'image/jpg': '.jpg',
                'image/png': '.png',
                'image/gif': '.gif',
                'image/webp': '.webp',
                'image/bmp': '.bmp',
            }
            ext = ext_map.get(content_type.split(';')[0].strip().lower(), '.jpg')
            filename = filename + ext
        
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        # Ensure file isn't empty/tiny
        if os.stat(filepath).st_size < 500:
            os.remove(filepath)
            return None
        return filepath
    except Exception:
        return None

def process_webhook_item(
    collection_id: str,
    site_id: str,
    field_data: Dict[Any, Any],
    webflow_token: str,
) -> Dict[str, Any]:
    """
    Process a single item from webhook data:
    1. Fetch and save collection schema
    2. Extract keywords from slug/category
    3. Scrape images from the link URL
    4. Select best image using AI (or skip if only 1 image)
    5. Upload image to Webflow
    6. Return updated field data with thumbnail URL
    
    Image Selection Logic:
    - If 0 images scraped: Returns error with skip_item=True (item will not be created)
    - If 1 image scraped: Skip AI selection, use that image directly
    - If 2+ images scraped: Use AI to select best, always use highest scoring image
    """
    
    # Step 1: Fetch collection schema
    try:
        schema = fetch_and_save_collection_schema(collection_id, webflow_token)
    except Exception as e:
        logging.error(f"Failed to fetch collection schema: {e}")
        return {"error": f"Failed to fetch collection schema: {str(e)}"}
    
    # Step 2: Extract keywords and link from field_data
    # keywords = field_data.get('title', '') + ' ' + field_data.get('slug', '') + ' ' + field_data.get('category', '') + ' ' + field_data.get('description', '')
    tags = field_data.get('tags', '')
    
    # Convert tags to string if it's a list
    if isinstance(tags, list):
        keywords = ' '.join(tags) if tags else ''
    else:
        keywords = tags if tags else ''
    
    # link = field_data.get('link') or field_data.get('source-url', '')
    
    # if not link:
    #     logging.error("No link found in field_data")
    #     return {"error": "No link field found in fieldData"}
    
    # if not keywords:
    #     logging.warning("No keywords found, using 'dashboard' as default")
    #     keywords = "dashboard"
    
    # logging.info(f"Processing item with keywords: '{keywords}' and link: {link}")
    
    # # Create directories for this processing run
    # datetime_str = datetime.now().strftime("%Y%m%d_%H-%M-%S")
    # slug_safe = slugify(keywords)
    
    # images_dir = Path("images") / f"{datetime_str}_{slug_safe}"
    # best_match_dir = Path("best_match") / f"{datetime_str}_{slug_safe}"
    
    # try:
    #     # Step 3: Scrape images using Selenium
    #     logging.info(f"Scraping images from: {link}")
        
    #     saved_images = scrape_images_with_js(
    #         url=link,
    #         output_dir=images_dir,
    #         keywords=None,  # Scrape ALL images, not just matching keywords
    #         headless=True,
    #         wait_time=5,
    #         scroll=True,
    #     )
        
    #     if not saved_images:
    #         logging.warning(f"No images scraped from {link}")
    #         return {"error": "No images found at the provided link", "skip_item": True}
        
    #     logging.info(f"Scraped {len(saved_images)} images")
        
    #     # Step 4: Select best image
    #     # If only one image, skip AI selection and use it directly
    #     if len(saved_images) == 1:
    #         logging.info("Only one image found, skipping AI selection")
    #         best = {
    #             'path': saved_images[0],
    #             'score': 100,
    #             'reasoning': 'Only one image available, using it by default'
    #         }
    #     else:
    #         # Multiple images: Use AI to select best
    #         logging.info(f"Selecting best image from {len(saved_images)} using AI with keywords: {keywords}")
            
    #         api_key = os.getenv("OPENAI_API_KEY")
    #         if not api_key:
    #             logging.error("OPENAI_API_KEY not set")
    #             return {"error": "OPENAI_API_KEY not configured"}
            
    #         best = None
    #         threshold_score = 90.0
            
    #         for idx, image_path in enumerate(saved_images, 1):
    #             try:
    #                 logging.info(f"[{idx}/{len(saved_images)}] Analyzing {Path(image_path).name}")
    #                 result = analyze_image(image_path, keywords, api_key)
                    
    #                 score = result['score']
    #                 logging.info(f"Score: {score}/100 - {result['reasoning']}")
                    
    #                 if best is None or score > best['score']:
    #                     best = {
    #                         'path': image_path,
    #                         'score': score,
    #                         'reasoning': result['reasoning']
    #                     }
                    
    #                 if score >= threshold_score:
    #                     logging.info(f"Found match with score {score} >= {threshold_score}. Stopping.")
    #                     break
                    
    #                 if idx % 10 == 0:
    #                     logging.info(f"Batch complete. Best so far: {best['score']}/100")
                        
    #             except Exception as e:
    #                 logging.error(f"Failed to analyze {Path(image_path).name}: {e}")
            
    #         # If no images could be analyzed, return error
    #         if not best:
    #             logging.warning(f"Failed to analyze any images")
    #             return {"error": "Failed to analyze images", "skip_item": True}
            
    #         # Always use the best image found, even if score is low
    #         logging.info(f"Selected image with highest score: {best['score']}/100")
        
    #     # Save best match
    #     best_match_dir.mkdir(parents=True, exist_ok=True)
    #     best_image_path = Path(best['path'])
    #     dest_path = best_match_dir / best_image_path.name
        
    #     counter = 1
    #     while dest_path.exists():
    #         stem = best_image_path.stem
    #         ext = best_image_path.suffix
    #         dest_path = best_match_dir / f"{stem}_{counter}{ext}"
    #         counter += 1
        
    #     shutil.copy2(best['path'], dest_path)
    #     logging.info(f"Saved best match to: {dest_path}")
        
        # Step 5: Upload image to Webflow
    logging.info("Uploading image to Webflow...")
    imageData = download_thumbnail(field_data['thumbnail'])
    print(field_data)
    print(imageData)
    # INSERT_YOUR_CODE
    if not imageData or not os.path.isfile(imageData):
        logging.error("Downloaded thumbnail is missing or not a valid file.")
        return {
            "error": "Downloaded thumbnail image is missing or invalid.",
            "skip_item": True
        }
    with open(imageData, 'rb') as f:
        image_data = f.read()
    
    
    upload_result = upload_to_webflow(
        site_id=site_id,
        webflow_token=webflow_token,
        file_name=Path(imageData).name,
        file_data=image_data
    )
    
    thumbnail_url = upload_result['hostedUrl']
    logging.info(f"Uploaded to Webflow: {thumbnail_url}")
    
    # Step 6: Update field_data with thumbnail URL
    # Find the correct thumbnail field from schema
    thumbnail_field = None
    for field in schema.get('fields', []):
        if field['type'] == 'Image':
            thumbnail_field = field['slug']
            break
    
    if not thumbnail_field:
        logging.warning("No Image field found in collection schema, using 'thumbnail'")
        thumbnail_field = 'thumbnail'
    
    # Update field_data to match collection schema
    schema_fields = {field['slug']: field for field in schema.get('fields', [])}
    slug_remap = {
        "thumbnail": thumbnail_field,
        "tags": "tags-2",
        "description": "post-summary",
        "link": "source-url",
    }
    
    updated_field_data = {}
    for key, value in field_data.items():
        slug = slug_remap.get(key, key)
        if slug not in schema_fields:
            logging.debug(f"Ignoring field '{key}' (not in schema)")
            continue
        
        if slug == "tags-2" and isinstance(value, list):
            value = ", ".join(value)
        
        updated_field_data[slug] = value
    
    updated_field_data[thumbnail_field] = {"url": thumbnail_url}
    
    # Ensure required system fields exist
    updated_field_data.setdefault("_archived", False)
    updated_field_data.setdefault("_draft", False)
    
    return {
        "success": True,
        "thumbnail_url": thumbnail_url,
        "thumbnail_field": thumbnail_field,
        "field_data": updated_field_data,
    }
        
    # except Exception as e:
    #     logging.error(f"Error processing item: {e}", exc_info=True)
    #     return {"error": str(e)}
    
    # finally:
    #     # Cleanup temporary images
    #     if images_dir.exists():
    #         shutil.rmtree(images_dir, ignore_errors=True)
    #         logging.info(f"Cleaned up temporary images: {images_dir}")


@app.route('/webhook', methods=['POST'])
def webhook_endpoint():
    """
    Webhook endpoint that receives:
    {
      "collection_id": "...",
      "site_id": "...",
      "fieldData": {
        "slug": "marketing-analytics",  // Used as topic for GPT generation
        "category": "Marketing",
        ...other fields (optional)
      },
      "count": 5  // optional, number of items to generate (default: 5)
    }
    
    Extracts slug/category from fieldData, generates items using GPT, processes each, and posts to Webflow.
    """
    try:
        data = request.get_json(silent=True)
        
        # Handle Make.com formFields format (array of objects)
        if data and isinstance(data.get('formFields'), list):
            form_fields = data.get('formFields', [])
            data = {}
            for field in form_fields:
                if isinstance(field, dict) and 'name' in field and 'value' in field:
                    field_name = field['name']
                    field_value = field['value']
                    # Try to parse JSON values
                    if isinstance(field_value, str):
                        try:
                            field_value = json.loads(field_value)
                        except (json.JSONDecodeError, TypeError):
                            pass
                    data[field_name] = field_value
        
        if data is None:
            # Fallback: handle application/x-www-form-urlencoded (or other form submissions)
            if request.form:
                form_dict = {}
                for key in request.form.keys():
                    values = request.form.getlist(key)
                    parsed_values = []
                    for value in values:
                        value = value.strip()
                        if not value:
                            parsed_values.append(value)
                            continue
                        try:
                            parsed_values.append(json.loads(value))
                        except json.JSONDecodeError:
                            parsed_values.append(value)
                    form_dict[key] = parsed_values[0] if len(parsed_values) == 1 else parsed_values
                data = form_dict or None
            elif request.data:
                # Attempt to parse raw payload as JSON string
                raw_payload = request.data.decode("utf-8").strip()
                if raw_payload:
                    try:
                        data = json.loads(raw_payload)
                        # Check if it's Make.com formFields format
                        if isinstance(data.get('formFields'), list):
                            form_fields = data.get('formFields', [])
                            converted_data = {}
                            for field in form_fields:
                                if isinstance(field, dict) and 'name' in field and 'value' in field:
                                    field_name = field['name']
                                    field_value = field['value']
                                    if isinstance(field_value, str):
                                        try:
                                            field_value = json.loads(field_value)
                                        except (json.JSONDecodeError, TypeError):
                                            pass
                                    converted_data[field_name] = field_value
                            data = converted_data
                    except json.JSONDecodeError:
                        data = None
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        collection_id = data.get('collection_id')
        site_id = data.get('site_id')
        field_data = data.get('fieldData', {})
        if isinstance(field_data, str):
            try:
                field_data = json.loads(field_data)
            except json.JSONDecodeError:
                return jsonify({'error': 'fieldData must be valid JSON'}), 400
        elif not isinstance(field_data, dict):
            return jsonify({'error': 'fieldData must be an object'}), 400
        
        raw_count = data.get('count', 15)
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            return jsonify({'error': 'count must be an integer'}), 400
        
        # Extract topic from fieldData (slug or category)
        topic = field_data.get('title', '') + ' ' + field_data.get('slug', '') + ' ' + field_data.get('description', '')
        Slug = field_data.get('slug', '')
        if not collection_id:
            return jsonify({'error': 'collection_id is required'}), 400
        
        if not site_id:
            return jsonify({'error': 'site_id is required'}), 400
        
        if not topic:
            return jsonify({'error': 'slug or category in fieldData is required'}), 400
        
        
        # Get API tokens
        webflow_token = os.getenv("WEBFLOW_TOKEN")
        if not webflow_token:
            return jsonify({'error': 'WEBFLOW_TOKEN not configured'}), 500
        
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            return jsonify({'error': 'OPENAI_API_KEY not configured'}), 500
        
        logging.info(f"Processing webhook for collection: {collection_id}, topic: {topic}, count: {count}")
        
        # Step 1: Generate items using GPT
        logging.info(f"Generating {count} items for topic: {topic}")
        generator = DashboardGenerator(openai_key=openai_key)
        
        try:
            generated_items = generator.generate_items(topic=topic, count=count)
        except Exception as e:
            logging.error(f"Failed to generate items: {e}")
            return jsonify({'error': f'Failed to generate items: {str(e)}'}), 500
        
        # Step 2: Save generated items to content folder
        datetime_str = datetime.now().strftime("%Y%m%d_%H-%M-%S")
        content_dir = Path("content") / f"{datetime_str}"
        content_dir.mkdir(parents=True, exist_ok=True)
        
        generated_file = content_dir / "generated.json"
        with open(generated_file, 'w', encoding='utf-8') as f:
            json.dump([item.as_dict() for item in generated_items], f, indent=2, ensure_ascii=False)
        
        logging.info(f"Saved {len(generated_items)} generated items to {generated_file}")
        
        # Step 3: Process each generated item
        results = []
        created_count = 0
        skipped_count = 0
        failed_count = 0
        
        for idx, item in enumerate(generated_items, 1):
            logging.info(f"\n{'='*60}")
            logging.info(f"Processing item {idx}/{len(generated_items)}: {item.title}")
            logging.info(f"{'='*60}")
            print(item)
            # Convert DashboardItem to field_data dict
            field_data = {
                "name": item.title,
                "slug": item.slug,
                "category": Slug,
                "thumbnail": item.thumbnail,  # Use link from generated item
                "source-url": item.link,
                "source": item.source,
                "tags": item.tags,
                "author": item.author,
                "description": item.description,
                "access": item.access,
                "source-type": item.source_type,
                "language": item.language,
                "last-checked": item.last_checked,
            }
            
            # Process the item (scrape, select, upload)
            result = process_webhook_item(
                collection_id=collection_id,
                site_id=site_id,
                field_data=field_data,
                webflow_token=webflow_token
            )
            
            if 'error' in result:
                # If skip_item flag is set, don't create the item (no images found)
                if result.get('skip_item'):
                    logging.warning(f"Skipping item {idx}: {result['error']}")
                    results.append({
                        'item': item.title,
                        'status': 'skipped',
                        'reason': result['error']
                    })
                    skipped_count += 1
                    continue
                else:
                    logging.error(f"Failed to process item {idx}: {result['error']}")
                    results.append({
                        'item': item.title,
                        'status': 'failed',
                        'error': result['error']
                    })
                    failed_count += 1
                    continue
            
            # Post to Webflow using the updated field_data
            logging.info(f"Posting item {idx} to Webflow CMS...")
            
            headers = {
                "Authorization": f"Bearer {webflow_token}",
                "Content-Type": "application/json",
                "accept-version": "2.0.0",
            }
            
            item_payload = {
                "isArchived": False,
                "isDraft": False,
                "fieldData": result['field_data'],
            }
            
            url = f"https://api.webflow.com/v2/collections/{collection_id}/items"
            params = {"live": "true"}
            
            try:
                response = requests.post(url, headers=headers, params=params, json={"items": [item_payload]}, timeout=30)
                
                if response.status_code >= 400:
                    logging.error(f"Webflow API error ({response.status_code}): {response.text}")
                    results.append({
                        'item': item.title,
                        'status': 'failed',
                        'error': f'Webflow API error: {response.status_code}'
                    })
                    failed_count += 1
                    continue
                
                webflow_response = response.json()
                created_items_response = webflow_response.get('items', [])
                
                if created_items_response:
                    item_id = created_items_response[0].get('id')
                    logging.info(f"✓ Created item {idx} with ID: {item_id}")
                    
                    results.append({
                        'item': item.title,
                        'status': 'created',
                        'item_id': item_id,
                        'thumbnail_url': result['thumbnail_url'],
                    })
                    created_count += 1
                else:
                    logging.warning(f"Item {idx} created but no ID returned")
                    results.append({
                        'item': item.title,
                        'status': 'created',
                        'item_id': None
                    })
                    created_count += 1
                    
            except Exception as e:
                logging.error(f"Failed to post item {idx}: {e}")
                results.append({
                    'item': item.title,
                    'status': 'failed',
                    'error': str(e)
                })
                failed_count += 1
        
        # Two-step publish process for all created items
        all_item_ids = [r.get('item_id') for r in results if r.get('status') == 'created' and r.get('item_id')]
        
        if all_item_ids:
            logging.info(f"\n{'='*60}")
            logging.info(f"Publishing {len(all_item_ids)} items...")
            logging.info(f"{'='*60}")
            
            headers = {
                "Authorization": f"Bearer {webflow_token}",
                "Content-Type": "application/json",
                "accept-version": "2.0.0",
            }
            
            # Step 1: Publish items in collection
            publish_url = f"https://api.webflow.com/v2/collections/{collection_id}/items/publish"
            publish_payload = {"itemIds": all_item_ids}
            publish_response = requests.post(publish_url, headers=headers, json=publish_payload, timeout=30)
            
            if publish_response.status_code >= 400:
                logging.error(f"Failed to publish items ({publish_response.status_code}): {publish_response.text}")
            else:
                logging.info(f"✓ Items published to collection: {publish_response.json()}")
            
            # Step 2: Publish site to make items live
            logging.info(f"Publishing site {site_id}...")
            site_publish_url = f"https://api.webflow.com/v2/sites/{site_id}/publish"
            site_payload = {"publishToWebflowSubdomain": True}
            site_response = requests.post(site_publish_url, headers=headers, json=site_payload, timeout=60)
            
            if site_response.status_code >= 400:
                logging.error(f"Failed to publish site ({site_response.status_code}): {site_response.text}")
            else:
                logging.info(f"✓ Site published: {site_response.json()}")
        
        # Return summary
        logging.info(f"\n{'='*60}")
        logging.info(f"SUMMARY: {created_count} created, {skipped_count} skipped, {failed_count} failed")
        logging.info(f"{'='*60}")
        
        return jsonify({
            'success': True,
            'message': f'Generated and processed {len(generated_items)} items',
            'topic': topic,
            'content_dir': str(content_dir),
            'summary': {
                'total': len(generated_items),
                'created': created_count,
                'skipped': skipped_count,
                'failed': failed_count
            },
            'results': results
        })
        
    except Exception as e:
        logging.error(f"Error in webhook endpoint: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})


@app.route('/debug/env', methods=['GET'])
def debug_env():
    """Debug endpoint to check if environment variables are loaded (for troubleshooting)."""
    openai_key = os.getenv("OPENAI_API_KEY")
    webflow_token = os.getenv("WEBFLOW_TOKEN")
    
    return jsonify({
        'openai_key_set': bool(openai_key),
        'openai_key_prefix': openai_key[:7] if openai_key else None,
        'webflow_token_set': bool(webflow_token),
        'webflow_token_length': len(webflow_token) if webflow_token else 0,
        'all_env_vars': list(os.environ.keys())  # List all available env vars
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
