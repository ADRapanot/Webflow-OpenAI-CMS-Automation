"""
Simple script to create a Webflow webhook via the v2 API.

Usage:
    python scripts/create_webhook.py --site-id <SITE_ID> --token <TOKEN> \
        --trigger-type cms.item.created --url https://example.com/webflow-hook

You can alternatively supply WEBFLOW_SITE_ID and WEBFLOW_TOKEN as environment
variables; CLI arguments take precedence.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

import requests


DEFAULT_TRIGGER = "collection_item_created"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a Webflow webhook.")
    parser.add_argument("--site-id", help="Webflow Site ID.")
    parser.add_argument("--collection-id", help="Webflow Collection ID.")
    parser.add_argument("--token", help="Webflow API token.")
    parser.add_argument(
        "--trigger-type",
        default=DEFAULT_TRIGGER,
        help=f"Webhook trigger type (default: {DEFAULT_TRIGGER}).",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Destination URL for the webhook.",
    )
    parser.add_argument(
        "--description",
        help="Optional human-readable description for the webhook.",
    )
    return parser


def resolve_credentials(args: argparse.Namespace) -> Dict[str, str]:
    site_id = args.site_id or os.getenv("WEBFLOW_SITE_ID")
    token = args.token or os.getenv("WEBFLOW_TOKEN")
    collection_id = args.collection_id or os.getenv("WEBFLOW_COLLECTION_ID")
    missing = [name for name, value in (("site-id", site_id), ("token", token)) if not value]
    if missing:
        raise SystemExit(
            f"Missing required value(s): {', '.join(missing)}. "
            "Provide via CLI arguments or environment variables."
        )
    return {"site_id": site_id, "token": token}


def create_webhook(
    site_id: str,
    token: str,
    trigger_type: str,
    collection_id: str,
    url: str,
    description: str | None = None,
) -> requests.Response:
    endpoint = f"https://api.webflow.com/v2/sites/{site_id}/webhooks"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "triggerType": trigger_type,
        "collectionId": collection_id,
        "url": url,
    }
    if description:
        payload["description"] = description

    response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    return response


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    creds = resolve_credentials(args)

    try:
        response = create_webhook(
            site_id=creds["site_id"],
            token=creds["token"],
            trigger_type=args.trigger_type,
            collection_id=args.collection_id,
            url=args.url,
            description=args.description,
        )
    except requests.RequestException as exc:
        raise SystemExit(f"Request failed: {exc}") from exc

    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print("Response JSON:")
        print(json.dumps(data, indent=2))
    except ValueError:
        print("Response Text:")
        print(response.text)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)

