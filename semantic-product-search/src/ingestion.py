"""
Catalog Ingestion Pipeline.
Fetches product catalog from DummyJSON API and persists to MongoDB and local JSON backup.
"""
import json
import logging
import requests
from typing import Any, Dict, List
from src.config import API_URL, RAW_DATA_PATH
from src.data.db import is_mongo_available, save_raw_products

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def fetch_products(api_url: str = API_URL) -> List[Dict[str, Any]]:
    """Fetches product records from target API."""
    logger.info(f"Fetching products from API: {api_url}")
    response = requests.get(api_url, timeout=30)
    response.raise_for_status()
    data = response.json()
    products = data.get("products", [])
    logger.info(f"Successfully fetched {len(products)} products from API.")
    return products


def save_to_file(products: List[Dict[str, Any]], path=RAW_DATA_PATH) -> None:
    """Persists products to local JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(products, file, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(products)} products to file -> {path}")


def save_to_mongo(products: List[Dict[str, Any]]) -> bool:
    """Saves products to MongoDB raw collection if server is reachable."""
    if is_mongo_available():
        try:
            count = save_raw_products(products)
            logger.info(f"Saved/Upserted {count} products to MongoDB collection.")
            return True
        except Exception as e:
            logger.warning(f"Failed writing to MongoDB: {e}")
            return False
    else:
        logger.warning("MongoDB is offline/unreachable. Skipped MongoDB persistence.")
        return False


def ingest():
    """Main ingestion runner."""
    products = fetch_products()
    # Save to MongoDB
    save_to_mongo(products)
    # Save to file backup
    save_to_file(products)
    return products


if __name__ == "__main__":
    ingest()