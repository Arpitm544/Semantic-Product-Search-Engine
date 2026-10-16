"""MongoDB connection helpers for the product catalog."""

from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database

from src.config import MONGO_URI, MONGO_DB_NAME


def get_mongo_client(uri: Optional[str] = None, server_selection_timeout_ms: int = 3000) -> MongoClient:
    """Creates and returns a MongoClient instance with configured timeout."""
    connection_uri = uri or MONGO_URI
    return MongoClient(
        connection_uri,
        serverSelectionTimeoutMS=server_selection_timeout_ms
    )


def get_database(db_name: Optional[str] = None, uri: Optional[str] = None) -> Database:
    """Returns the target MongoDB database."""
    client = get_mongo_client(uri)
    name = db_name or MONGO_DB_NAME
    return client[name]
