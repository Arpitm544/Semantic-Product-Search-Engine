"""
Data loading utilities for Semantic Product Search Engine.
Supports loading from MongoDB document store or local JSON files.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.config import RAW_DATA_PATH, PROCESSED_DATA_PATH
from src.data.db import (
    is_mongo_available,
    load_raw_products as load_raw_mongo,
    load_processed_products as load_processed_mongo,
)

logger = logging.getLogger(__name__)


def load_raw_products(
    path: Optional[Path] = None,
    prefer_mongo: bool = True
) -> List[Dict[str, Any]]:
    """
    Load raw products.
    If prefer_mongo is True and MongoDB is reachable, loads from database.
    Otherwise falls back to the JSON file at path.
    """
    if prefer_mongo and path is None and is_mongo_available():
        try:
            docs = load_raw_mongo()
            if docs:
                logger.info(f"Loaded {len(docs)} raw products from MongoDB.")
                return docs
        except Exception as e:
            logger.warning(f"Error loading from MongoDB, falling back to file: {e}")

    target_path = path or RAW_DATA_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"Raw data not found at {target_path}")
    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "products" in data:
        return data["products"]
    elif isinstance(data, list):
        return data
    else:
        raise ValueError(f"Unexpected data format in {target_path}")


def load_cleaned_products(
    path: Optional[Path] = None,
    prefer_mongo: bool = True
) -> List[Dict[str, Any]]:
    """
    Load cleaned/preprocessed products.
    If prefer_mongo is True and MongoDB is reachable, loads from database.
    Otherwise falls back to the JSON file at path.
    """
    if prefer_mongo and path is None and is_mongo_available():
        try:
            docs = load_processed_mongo()
            if docs:
                logger.info(f"Loaded {len(docs)} cleaned products from MongoDB.")
                return docs
        except Exception as e:
            logger.warning(f"Error loading from MongoDB, falling back to file: {e}")

    target_path = path or PROCESSED_DATA_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"Processed data not found at {target_path}")
    with open(target_path, "r", encoding="utf-8") as f:
        return json.load(f)

