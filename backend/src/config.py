"""
Configuration constants and directory paths for Semantic Product Search Engine.
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)
DATA_DIR = PROJECT_ROOT / "data"
DATASET_DIR = DATA_DIR / "dataset"

INDEXES_DIR = PROJECT_ROOT / "indexes"
BM25_INDEX_PATH = INDEXES_DIR / "bm25_index.pkl"
FAISS_INDEX_PATH = INDEXES_DIR / "faiss_index.bin"
FAISS_ID_MAP_PATH = INDEXES_DIR / "faiss_id_map.pkl"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "semantic_product_search")

