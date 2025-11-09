#!/usr/bin/env python3
import base64
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')


def analyze_image(image_path: str, keywords: str, api_key: str) -> Dict:
    try:
        base64_image = encode_image(image_path)
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "model": "gpt-5",
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""Rate how well this image matches these keywords: "{keywords}"

Respond with JSON only:
{{
  "score": <0-100>,
  "reasoning": "<brief explanation>"
}}"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "low"
                            }
                        }
                    ]
                }],
                "max_tokens": 300
            },
            timeout=60
        )
        response.raise_for_status()
        
        content = response.json()['choices'][0]['message']['content']
        
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()
        
        parsed = json.loads(content)
        
        return {
            'score': parsed.get('score', 0),
            'reasoning': parsed.get('reasoning', 'No reasoning provided')
        }
        
    except json.JSONDecodeError as e:
        logging.error(f"JSON parse error: {e}")
        return {'score': 0, 'reasoning': f'JSON error: {str(e)}'}
    except requests.RequestException as e:
        logging.error(f"API request error: {e}")
        return {'score': 0, 'reasoning': f'API error: {str(e)}'}
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return {'score': 0, 'reasoning': f'Error: {str(e)}'}


def select_best_image(keywords: str, image_dir: str = "images", 
                     batch_size: int = 10, threshold: float = 0.91) -> Dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    image_paths = []
    image_dir_path = Path(image_dir)
    
    for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        image_paths.extend(image_dir_path.glob(f'*{ext}'))
        image_paths.extend(image_dir_path.glob(f'*{ext.upper()}'))
    
    if not image_paths:
        raise ValueError(f"No images found in {image_dir}")
    
    logging.info(f"Found {len(image_paths)} images")
    
    best = None
    threshold_score = threshold * 100
    
    for idx, image_path in enumerate(image_paths, 1):
        try:
            logging.info(f"[{idx}/{len(image_paths)}] Analyzing {image_path.name}")
            result = analyze_image(str(image_path), keywords, api_key)
            
            score = result['score']
            logging.info(f"Score: {score}/100")
            
            if best is None or score > best['score']:
                best = {
                    'path': str(image_path),
                    'score': score,
                    'reasoning': result['reasoning']
                }
            
            if score >= threshold_score:
                logging.info(f"Found match with score {score} >= {threshold_score}. Stopping.")
                break
            
            if idx % batch_size == 0:
                logging.info(f"Batch complete. Best so far: {best['score']}/100")
                
        except Exception as e:
            logging.error(f"Failed to analyze {image_path.name}: {e}")
    
    if best and best['score'] > 0:
        date_str = datetime.now().strftime("%Y%m%d")
        save_path = Path("best_match") / date_str
        save_path.mkdir(parents=True, exist_ok=True)
        
        dest = save_path / Path(best['path']).name
        counter = 1
        while dest.exists():
            stem = Path(best['path']).stem
            ext = Path(best['path']).suffix
            dest = save_path / f"{stem}_{counter}{ext}"
            counter += 1
        
        shutil.copy2(best['path'], dest)
        best['saved_path'] = str(dest)
        logging.info(f"Saved to: {dest}")
    
    return best


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python select_best_image.py <keywords>")
        sys.exit(1)
    
    keywords = " ".join(sys.argv[1:])
    result = select_best_image(keywords)
    
    print(f"\nBest Match:")
    print(f"  File: {result['path']}")
    print(f"  Score: {result['score']}/100")
    print(f"  Saved: {result.get('saved_path', 'N/A')}")
