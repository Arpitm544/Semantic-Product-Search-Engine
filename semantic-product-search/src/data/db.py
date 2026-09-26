"""
MongoDB database connection and CRUD helpers for Semantic Product Search Engine.
"""
import logging
from typing import Any, Dict, List, Optional
from pymongo import MongoClient, ReplaceOne
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from src.config import (
    MONGO_URI,
    MONGO_DB_NAME,
    MONGO_COLLECTION_RAW,
    MONGO_COLLECTION_PROCESSED,
)

logger = logging.getLogger(__name__)


def get_mongo_client(
    uri: Optional[str] = None,
    server_selection_timeout_ms: int = 3000
) -> MongoClient:
    """Creates and returns a MongoClient instance with configured timeout."""
    connection_uri = uri or MONGO_URI
    return MongoClient(
        connection_uri,
        serverSelectionTimeoutMS=server_selection_timeout_ms
    )


def get_database(
    db_name: Optional[str] = None,
    uri: Optional[str] = None
) -> Database:
    """Returns the target MongoDB database."""
    client = get_mongo_client(uri)
    name = db_name or MONGO_DB_NAME
    return client[name]


def is_mongo_available(uri: Optional[str] = None, timeout_ms: int = 2000) -> bool:
    """Checks if MongoDB server is reachable."""
    try:
        client = get_mongo_client(uri, server_selection_timeout_ms=timeout_ms)
        client.admin.command("ping")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
        logger.warning(f"MongoDB not reachable at {uri or MONGO_URI}: {e}")
        return False


def get_raw_collection(db: Optional[Database] = None) -> Collection:
    """Returns collection for raw products."""
    database = db if db is not None else get_database()
    col = database[MONGO_COLLECTION_RAW]
    col.create_index("id", unique=True)
    return col


def get_processed_collection(db: Optional[Database] = None) -> Collection:
    """Returns collection for processed/cleaned products."""
    database = db if db is not None else get_database()
    col = database[MONGO_COLLECTION_PROCESSED]
    col.create_index("id", unique=True)
    return col


def save_raw_products(
    products: List[Dict[str, Any]],
    db: Optional[Database] = None
) -> int:
    """
    Saves raw products into MongoDB collection with upsert on 'id'.
    Returns count of processed operations.
    """
    if not products:
        return 0
    collection = get_raw_collection(db)
    operations = [
        ReplaceOne({"id": item["id"]}, item, upsert=True)
        for item in products
        if "id" in item
    ]
    if operations:
        result = collection.bulk_write(operations, ordered=False)
        total_upserted = (result.upserted_count or 0) + (result.modified_count or 0) + (result.matched_count or 0)
        return total_upserted
    return 0


def load_raw_products(db: Optional[Database] = None) -> List[Dict[str, Any]]:
    """Loads all raw products from MongoDB, omitting the BSON _id field."""
    collection = get_raw_collection(db)
    return list(collection.find({}, {"_id": 0}))


def save_processed_products(
    products: List[Dict[str, Any]],
    db: Optional[Database] = None
) -> int:
    """
    Saves cleaned/processed products into MongoDB collection with upsert on 'id'.
    Returns count of processed operations.
    """
    if not products:
        return 0
    collection = get_processed_collection(db)
    operations = [
        ReplaceOne({"id": item["id"]}, item, upsert=True)
        for item in products
        if "id" in item
    ]
    if operations:
        result = collection.bulk_write(operations, ordered=False)
        total_upserted = (result.upserted_count or 0) + (result.modified_count or 0) + (result.matched_count or 0)
        return total_upserted
    return 0


def load_processed_products(db: Optional[Database] = None) -> List[Dict[str, Any]]:
    """Loads all processed products from MongoDB, omitting the BSON _id field."""
    collection = get_processed_collection(db)
    return list(collection.find({}, {"_id": 0}))


def get_products_by_ids(
    ids: List[int],
    processed: bool = True,
    db: Optional[Database] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves a list of product documents by their IDs, preserving order if possible.
    """
    if not ids:
        return []
    collection = get_processed_collection(db) if processed else get_raw_collection(db)
    docs = list(collection.find({"id": {"$in": ids}}, {"_id": 0}))
    doc_map = {doc["id"]: doc for doc in docs if "id" in doc}
    return [doc_map[pid] for pid in ids if pid in doc_map]
