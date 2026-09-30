"""
Text cleaning and preprocessing pipeline.
Addresses TR-002: Minimal, leakage-safe cleaning and canonical text representation.
"""
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.config import RAW_DATA_PATH, PROCESSED_DATA_PATH, PROCESSED_DATA_DIR
from src.data.db import is_mongo_available, save_processed_products
from src.data.load_data import load_raw_products
from src.data.validation import validate_catalog

logger = logging.getLogger(__name__)


def clean_text(text: Optional[str]) -> str:
    """Minimal text cleaner that preserves semantic casing and punctuation."""
    if not text:
        return ""
    # Strip HTML tags if any
    cleaned = re.sub(r"<[^>]+>", " ", text)
    # Normalize excessive whitespaces and newlines
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_representation_text(item: Dict[str, Any]) -> str:
    """
    Constructs a rich templated string representation suitable for both
    Sentence-Transformers embedding generation and BM25 indexing.
    Format: [Category] ... | [Brand] ... | [Title] ... | [Details] ... | [Tags] ...
    """
    title = clean_text(item.get("title", ""))
    category = clean_text(item.get("category", ""))
    brand = clean_text(item.get("brand", ""))
    description = clean_text(item.get("description", ""))

    tags = item.get("tags", [])
    tags_str = ", ".join([clean_text(t) for t in tags if t])

    parts = []
    if category:
        parts.append(f"[Category] {category}")
    if brand:
        parts.append(f"[Brand] {brand}")
    if title:
        parts.append(f"[Title] {title}")
    if description:
        parts.append(f"[Details] {description}")
    if tags_str:
        parts.append(f"[Tags] {tags_str}")

    return " | ".join(parts)


def preprocess_catalog(
    products: List[Dict[str, Any]],
    output_path: Optional[Path] = None,
    save_to_mongo: bool = True,
    save_json_backup: bool = False,
) -> List[Dict[str, Any]]:
    """
    Cleans raw catalog items and generates standardized fields.

    Primary store: MongoDB `products_processed` collection.
    Fallback/backup: local JSON file at output_path (default: PROCESSED_DATA_PATH).
    """
    cleaned_products = []

    for item in products:
        cleaned_item = {
            "id": item.get("id"),
            "title": clean_text(item.get("title")),
            "description": clean_text(item.get("description")),
            "category": clean_text(item.get("category")),
            "brand": clean_text(item.get("brand")) or "Generic",
            "price": float(item.get("price", 0.0)),
            "rating": float(item.get("rating", 0.0)),
            "stock": int(item.get("stock", 0)),
            "tags": [clean_text(t) for t in item.get("tags", []) if t],
            "thumbnail": item.get("thumbnail", ""),
            "images": item.get("images", []),
            "representation_text": build_representation_text(item),
        }
        cleaned_products.append(cleaned_item)

    # 1️⃣  Primary store: MongoDB
    if save_to_mongo:
        if is_mongo_available():
            try:
                count = save_processed_products(cleaned_products)
                logger.info(f"Saved/Upserted {count} cleaned products to MongoDB.")
                print(f"  ✅ MongoDB  → {count} products upserted into 'products_processed'.")
            except Exception as e:
                logger.warning(f"Could not persist processed products to MongoDB: {e}")
                print(f"  ⚠️  MongoDB  → save failed: {e}")
        else:
            logger.warning("MongoDB not reachable; skipping MongoDB save.")
            print("  ⚠️  MongoDB  → not reachable, skipped.")

    # 2️⃣  Backup: local JSON file
    if save_json_backup:
        dest = output_path or PROCESSED_DATA_PATH
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(cleaned_products, f, indent=2, ensure_ascii=False)
        logger.info(f"JSON backup written to {dest}.")
        print(f"  📄 JSON backup → {dest}")

    print(f"  Total preprocessed: {len(cleaned_products)} products.")
    return cleaned_products


def main():
    print("=" * 55)
    print("  Preprocessing Pipeline")
    print("=" * 55)
    print("Loading raw products from MongoDB...")
    raw = load_raw_products()
    is_valid, report = validate_catalog(raw)
    print(f"Validation: {'✅ PASSED' if is_valid else '❌ FAILED'}")
    if not is_valid:
        print("Validation report:", report)

    print(f"\nCleaning {len(raw)} products and saving to stores...")
    cleaned = preprocess_catalog(raw)
    print(f"\nSample representation_text:\n  {cleaned[0]['representation_text']}")
    print("=" * 55)
    print("  ✅ Preprocessing complete.")
    print("=" * 55)


if __name__ == "__main__":
    main()
