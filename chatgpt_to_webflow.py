#!/usr/bin/env python3
"""
chatgpt_to_webflow.py
Generate marketing dashboard entries with OpenAI and push them to Webflow.
Now split into two commands so generation and publishing can be tested independently.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import re
import unicodedata

import requests
from openai import OpenAI


ITEM_SCHEMA = {
    "name": "WebflowDashboardBatch",
    "description": "Batch of CMS-ready marketing dashboard entries for Webflow.",
    "schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "minItems": 1,
                "maxItems": 15,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "title",
                        "subtitle",
                        "source",
                        "author",
                        "link",
                        "thumbnail",
                        "tags",
                        "category",
                        "description",
                        "access",
                        "source_type",
                        "last_checked",
                        "language",
                    ],
                    "properties": {
                        "slug": {"type": "string", "pattern": "^[a-z0-9-]+$"},
                        "title": {"type": "string", "minLength": 5},
                        "subtitle": {"type": "string", "minLength": 10},
                        "source": {"type": "string", "minLength": 3},
                        "author": {"type": "string", "minLength": 3},
                        "link": {"type": "string", "format": "uri"},
                        "thumbnail": {"type": "string", "format": "uri"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 0,
                            "maxItems": 10,
                            "uniqueItems": True,
                        },
                        "category": {"type": "string"},
                        "description": {"type": "string", "minLength": 20},
                        "access": {"type": "string"},
                        "source_type": {"type": "string"},
                        "license": {"type": ["string", "null"]},
                        "last_checked": {"type": "string", "format": "date"},
                        "language": {"type": "string", "minLength": 2, "maxLength": 10},
                    },
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    },
}

DEFAULT_FIELD_MAP = {
    "title": "name",
    "slug": "slug",
    "subtitle": "subtitle",
    "source": "source-name",
    "author": "author",
    "link": "source-url",
    "thumbnail": "thumbnail",
    "tags": "tags",
    "category": "category",
    "description": "description",
    "access": "access-level",
    "source_type": "source-type",
    "license": "license",
    "last_checked": "last-checked",
    "language": "language",
}


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return cleaned or "dashboard-entry"


@dataclass
class DashboardItem:
    slug: str
    title: str
    subtitle: str
    source: str
    author: str
    link: str
    thumbnail: str
    tags: List[str]
    category: str
    description: str
    access: str
    source_type: str
    last_checked: str
    language: str
    license: str | None = None

    def as_dict(self) -> Dict[str, Any]:
        """Canonical dictionary used before mapping to Webflow field slugs."""
        return {
            "title": self.title,
            "slug": self.slug,
            "subtitle": self.subtitle,
            "source": self.source,
            "author": self.author,
            "link": self.link,
            "thumbnail": self.thumbnail,
            "tags": self.tags,
            "category": self.category,
            "description": self.description,
            "access": self.access,
            "source_type": self.source_type,
            "license": self.license,
            "last_checked": self.last_checked,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DashboardItem":
        copy = {**data}
        copy.setdefault("tags", [])
        copy["slug"] = copy.get("slug") or slugify(copy["title"])
        return cls(**copy)


class DashboardGenerator:
    def __init__(self, openai_key: str) -> None:
        self.client = OpenAI(api_key=openai_key)

    def generate_items(self, topic: str, count: int) -> List[DashboardItem]:
        logging.info("Requesting %d dashboard entries for '%s' from OpenAI", count, topic)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a marketing analytics expert with knowledge of real public dashboards from sites like "
                    "Tableau Public, Looker Studio Gallery, Power BI Community, and blogs like Windsor.ai or Search "
                    "Engine Journal. ALWAYS use ONLY real, existing examples with valid thumbnail and source URLs from "
                    "your training data. Do not invent, guess, or modify URLs - use only ones you know are accurate. If "
                    "you do not know a valid URL for a dashboard, skip it or use a placeholder such as "
                    "'https://example.com/placeholder.jpg' for thumbnails. Prioritize popular, recent marketing dashboards.\n\n"
                    "Every item must include: slug, title, subtitle, source, author, link, thumbnail, tags, category, "
                    "description, access, source_type, license (nullable), last_checked (YYYY-MM-DD), language."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate {count} diverse, high-quality real public marketing dashboard examples for: {topic}. "
                    "Stick strictly to real galleries or known sites. For each record: "
                    "slug (kebab-case, derived from title), "
                    "title (official dashboard name), subtitle (what it monitors), "
                    "source (organization), author (team or department), "
                    "link (direct dashboard URL), thumbnail (valid image URL), "
                    "tags (2-5 lowercase keywords), category (top-level classification), "
                    "description (under 320 letters), access (e.g., public, gated), source_type (gov_open_data, vendor, community, etc.), "
                    "license (if unknown use null), last_checked (ISO date for today), language (ISO 639-1 code).\n"
                    "Only include entries where both the dashboard link and thumbnail are known to exist.and give me as json type"
                ),
            },
        ]

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.5,
            response_format={"type": "json_schema", "json_schema": ITEM_SCHEMA},
        )
        content = response.choices[0].message.content
        payload = json.loads(content)
        items = [DashboardItem.from_dict(item) for item in payload["items"]]
        logging.info("Got %d dashboard entries", len(items))
        return items

    def save_items(
        self,
        items: List[DashboardItem],
        *,
        output_path: Path | None,
        staging_dir: Path,
    ) -> Path:
        if output_path:
            path = output_path
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            staging_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            path = staging_dir / f"dashboards_{timestamp}.json"

        with path.open("w", encoding="utf-8") as handle:
            json.dump([asdict(item) for item in items], handle, indent=2)
        logging.info("Saved %d items to %s", len(items), path)
        return path


class WebflowPublisher:
    def __init__(
        self,
        webflow_token: str,
        collection_id: str,
        *,
        field_map: Dict[str, str],
        tag_map: Dict[str, str] | None = None,
        site_id: str | None = None,
    ) -> None:
        self.collection_id = collection_id
        self.field_map = field_map
        self.tag_map = tag_map or {}
        self.site_id = site_id
        self.session = requests.Session()
        self.headers = {
            "Authorization": f"Bearer {webflow_token}",
            "Content-Type": "application/json",
            "accept-version": "2.0.0",
        }
        self.collection_fields = self._fetch_collection_fields()

    def _fetch_collection_fields(self) -> Dict[str, Dict[str, Any]]:
        url = f"https://api.webflow.com/v2/collections/{self.collection_id}"
        try:
            response = self.session.get(url, headers=self.headers, timeout=30)
        except requests.RequestException as err:
            logging.warning("Could not load Webflow collection schema: %s", err)
            return {}

        if response.status_code >= 400:
            logging.warning(
                "Could not fetch Webflow collection schema (%s): %s",
                response.status_code,
                response.text,
            )
            return {}

        data = response.json()
        fields = {field["slug"]: field for field in data.get("fields", [])}
        logging.debug("Webflow collection exposes fields: %s", ", ".join(fields.keys()))
        return fields

    def _map_tags(self, tags: List[str]) -> List[str]:
        if not tags:
            return []
        if not self.tag_map:
            logging.debug("No tag map provided; skipping tags data")
            return []
        resolved = []
        missing = []
        for tag in tags:
            tag_id = self.tag_map.get(tag)
            if tag_id:
                resolved.append(tag_id)
            else:
                missing.append(tag)
        if missing:
            logging.warning(
                "Missing Webflow tag IDs for: %s (skipping these tags)",
                ", ".join(missing),
            )
        return resolved

    def _build_field_data(self, item: DashboardItem) -> Dict[str, Any]:
        canonical = item.as_dict()
        prepared: Dict[str, Any] = {}

        for logical_key, slug in self.field_map.items():
            if not slug:
                continue
            value = canonical.get(logical_key)
            if value in (None, "", []):
                continue
            if logical_key == "thumbnail":
                prepared[slug] = {"url": value}
            elif logical_key == "tags":
                tag_refs = self._map_tags(value)
                if tag_refs:
                    prepared[slug] = tag_refs
            else:
                prepared[slug] = value

        if not self.collection_fields:
            return prepared

        filtered: Dict[str, Any] = {}
        for slug, value in prepared.items():
            field_def = self.collection_fields.get(slug)
            if not field_def:
                logging.debug("Skipping field '%s'; not present in Webflow collection", slug)
                continue

            field_type = field_def.get("type")
            if field_type == "MultiReference":
                if isinstance(value, list) and all(isinstance(v, str) for v in value):
                    filtered[slug] = value
                else:
                    logging.debug("Skipping field '%s'; expected reference IDs list", slug)
            elif field_type == "Reference":
                if isinstance(value, str):
                    filtered[slug] = value
                else:
                    logging.debug("Skipping field '%s'; expected single reference ID", slug)
            else:
                filtered[slug] = value

        return filtered

    def push_to_webflow(self, items: List[DashboardItem], *, live: bool, limit: int | None = None) -> None:
        url = f"https://api.webflow.com/v2/collections/{self.collection_id}/items"
        created = 0
        created_ids: List[str] = []

        for item in items:
            if limit is not None and created >= limit:
                logging.info("Creation limit %d reached; stopping", limit)
                break

            field_data = self._build_field_data(item)
            if not field_data:
                logging.warning("Skipping item '%s'; no mapped fields matched the Webflow schema", item.slug)
                continue

            item_payload = {
                "isArchived": False,
                "isDraft": not live,
                "fieldData": field_data,
            }
            payload = {"items": [item_payload]}
            params = {"live": str(live).lower()}
            logging.info("Creating item '%s' (live=%s)", item.slug, live)
            response = self.session.post(url, headers=self.headers, params=params, json=payload, timeout=30)
            if response.status_code >= 400:
                logging.error("Webflow error (%s): %s", response.status_code, response.text)
                raise RuntimeError(f"Failed to create '{item.slug}': {response.text}")
            created += 1
            response_data = response.json()
            items_data = response_data.get("items", [])
            if items_data and len(items_data) > 0:
                created_id = items_data[0].get("id")
                if created_id:
                    created_ids.append(created_id)
                    logging.info("Created Webflow item ID %s", created_id)
                else:
                    logging.warning("No ID returned for item '%s'", item.slug)
            else:
                logging.warning("Empty items array in response for '%s'", item.slug)

        logging.info("Created %d Webflow items", created)
        logging.info("Collected %d item IDs for publishing: %s", len(created_ids), created_ids)
        if live and created_ids:
            self._publish_items(created_ids)
        elif live and not created_ids:
            logging.warning("No item IDs collected - items will remain in 'queued to publish' status")

    def _publish_items(self, item_ids: List[str]) -> None:
        if not self.site_id:
            logging.info(
                "Skipping publish API call because WEBFLOW_SITE_ID/--site-id not provided. "
                "Items may remain queued until the site is published manually."
            )
            return

        publish_url = f"https://api.webflow.com/v2/collections/{self.collection_id}/items/publish"
        payload = {"itemIds": item_ids}
        logging.info("Publishing %d items from collection %s", len(item_ids), self.collection_id)
        response = self.session.post(publish_url, headers=self.headers, json=payload, timeout=30)
        if response.status_code >= 400:
            logging.error(
                "Failed to publish items via Webflow publish endpoint (%s): %s",
                response.status_code,
                response.text,
            )
            raise RuntimeError(f"Publish failed with status {response.status_code}: {response.text}")
        
        result = response.json()
        logging.info("Publish API call succeeded: %s", result)
        
        site_publish_url = f"https://api.webflow.com/v2/sites/{self.site_id}/publish"
        site_payload = {"publishToWebflowSubdomain": True}
        logging.info("Publishing site %s to make items live", self.site_id)
        site_response = self.session.post(site_publish_url, headers=self.headers, json=site_payload, timeout=60)
        if site_response.status_code >= 400:
            logging.error(
                "Failed to publish site (%s): %s",
                site_response.status_code,
                site_response.text,
            )
            raise RuntimeError(f"Site publish failed with status {site_response.status_code}: {site_response.text}")
        
        site_result = site_response.json()
        logging.info("Site publish initiated: %s", site_result)


def load_items(path: Path) -> List[DashboardItem]:
    with path.open("r", encoding="utf-8") as handle:
        raw_items = json.load(handle)
    items = [DashboardItem.from_dict(item) for item in raw_items]
    logging.info("Loaded %d items from %s", len(items), path)
    return items


def load_mapping_file(path: str | None) -> Dict[str, Any]:
    if not path:
        return {}
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Mapping file {path} must contain a JSON object")
    return data


def build_field_map(overrides: Dict[str, Any] | None) -> Dict[str, str]:
    field_map = DEFAULT_FIELD_MAP.copy()
    if overrides:
        for key, value in overrides.items():
            field_map[key] = value
    return field_map


def require_env(var: str) -> str:
    value = os.getenv(var)
    if not value:
        raise RuntimeError(f"Set {var} env var")
    return value


def optional_env(var: str) -> str | None:
    return os.getenv(var)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate dashboard JSON with ChatGPT and/or push it to Webflow."
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, etc.).")

    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Only generate dashboard JSON via OpenAI.")
    generate.add_argument("topic", help="High-level topic or brief for ChatGPT.")
    generate.add_argument("--count", type=int, default=3, help="How many dashboards to request (max 15).")
    generate.add_argument(
        "--staging-dir",
        default="staging_payloads",
        help="Directory for timestamped payload JSON (ignored if --output supplied).",
    )
    generate.add_argument(
        "--output",
        default=None,
        help="Explicit output JSON file path. If omitted, a timestamped file is created in --staging-dir.",
    )
    generate.add_argument(
        "--print-json",
        action="store_true",
        help="Echo the generated JSON to stdout in addition to writing the file.",
    )

    publish = subparsers.add_parser("publish", help="Load dashboard JSON and push it to Webflow.")
    publish.add_argument("input_file", help="Path to JSON exported by the generate command.")
    publish_group = publish.add_mutually_exclusive_group()
    publish_group.add_argument(
        "--live",
        dest="live",
        action="store_true",
        help="Publish items live (default behavior).",
    )
    publish_group.add_argument(
        "--draft",
        dest="live",
        action="store_false",
        help="Create items as drafts instead of publishing.",
    )
    publish.set_defaults(live=True)
    publish.add_argument("--limit", type=int, default=None, help="Max items to push in this run.")
    publish.add_argument(
        "--field-map",
        default=None,
        help="Optional JSON file that maps canonical field names (title, subtitle, etc.) to Webflow field slugs.",
    )
    publish.add_argument(
        "--tag-map",
        default=None,
        help="Optional JSON file mapping tag labels to Webflow item IDs for multi-reference tag fields.",
    )
    publish.add_argument(
        "--site-id",
        default=None,
        help="Webflow site ID for triggering publish after item creation. "
        "If omitted, falls back to WEBFLOW_SITE_ID env var and items may remain queued.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s: %(message)s")

    if args.command == "generate":
        openai_key = require_env("OPENAI_API_KEY")
        generator = DashboardGenerator(openai_key)
        items = generator.generate_items(args.topic, args.count)
        output = Path(args.output) if args.output else None
        staging_dir = Path(args.staging_dir)
        saved_path = generator.save_items(items, output_path=output, staging_dir=staging_dir)
        if args.print_json:
            print(json.dumps([asdict(item) for item in items], indent=2))
        logging.info("Generation complete. File ready at %s", saved_path)
        return

    if args.command == "publish":
        webflow_token = require_env("WEBFLOW_TOKEN")
        collection_id = require_env("WEBFLOW_COLLECTION_ID")
        items = load_items(Path(args.input_file))
        field_map_overrides = load_mapping_file(args.field_map)
        tag_map = load_mapping_file(args.tag_map)
        field_map = build_field_map(field_map_overrides)
        site_id = args.site_id or optional_env("WEBFLOW_SITE_ID")
        publisher = WebflowPublisher(
            webflow_token,
            collection_id,
            field_map=field_map,
            tag_map=tag_map,
            site_id=site_id,
        )
        publisher.push_to_webflow(items, live=args.live, limit=args.limit)
        logging.info("Publish complete.")
        return


if __name__ == "__main__":
    main()
