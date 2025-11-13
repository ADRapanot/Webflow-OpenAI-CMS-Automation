from __future__ import annotations

import json
import logging
import os
from pprint import pprint

from chatgpt_to_webflow import DashboardGenerator


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    api_key = "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"
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY in your environment before running this script.")

    topic = os.getenv("DASHBOARD_TOPIC", "crm analytics")
    count = int(os.getenv("DASHBOARD_COUNT", "8"))

    generator = DashboardGenerator(api_key)
    items = generator.generate_items(topic, count)

    print(f"Generated {len(items)} dashboard items for topic '{topic}':")
    for item in items:
        pprint(item.as_dict())

    with open("latest_dashboards.json", "w", encoding="utf-8") as handle:
        json.dump([item.as_dict() for item in items], handle, indent=2)
    print("Saved items to latest_dashboards.json")


if __name__ == "__main__":
    main()
