#!/usr/bin/env python3
"""
Clean image_metadata.json by removing entries where:
1. thumbnail is the same as source_link
2. Both title and extra_text are missing (empty strings or None)
"""

import json
from pathlib import Path


def is_empty(value):
    """Check if a value is empty (None, empty string, or whitespace only)"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def should_remove_entry(entry):
    """Determine if an entry should be removed"""
    thumbnail = entry.get("thumbnail", "")
    source_link = entry.get("source_link", "")
    title = entry.get("title", "")
    extra_text = entry.get("extra_text", "")
    
    # Remove if thumbnail equals source_link
    if thumbnail and source_link and thumbnail == source_link:
        return True
    
    # Remove if both title and extra_text are missing
    if is_empty(title) and is_empty(extra_text):
        return True
    
    return False


def main():
    metadata_path = Path(__file__).parent.parent / "images" / "image_metadata.json"
    
    print(f"Loading {metadata_path}...")
    with open(metadata_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    original_count = len(data)
    print(f"Original entries: {original_count}")
    
    # Filter out entries that should be removed
    cleaned_data = [entry for entry in data if not should_remove_entry(entry)]
    
    removed_count = original_count - len(cleaned_data)
    print(f"Removed entries: {removed_count}")
    print(f"Remaining entries: {len(cleaned_data)}")
    
    # Save cleaned data
    print(f"Saving cleaned data to {metadata_path}...")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
    
    print("Done!")


if __name__ == "__main__":
    main()

