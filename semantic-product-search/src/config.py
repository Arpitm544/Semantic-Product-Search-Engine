"""
Configuration constants and directory paths for Semantic Product Search Engine.
"""
import os
from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_PATH = DATA_DIR / "raw" / "products.json"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
PROCESSED_DATA_PATH = PROCESSED_DATA_DIR / "products_cleaned.json"

EVAL_DIR = DATA_DIR / "eval"
EVAL_SET_PATH = EVAL_DIR / "eval_set.json"

INDEXES_DIR = PROJECT_ROOT / "indexes"
BM25_INDEX_PATH = INDEXES_DIR / "bm25_index.pkl"
FAISS_INDEX_PATH = INDEXES_DIR / "faiss_index.bin"
FAISS_ID_MAP_PATH = INDEXES_DIR / "faiss_id_map.pkl"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

REPORTS_DIR = PROJECT_ROOT / "reports"
EDA_REPORT_PATH = REPORTS_DIR / "eda_summary.md"
BASELINE_METRICS_PATH = REPORTS_DIR / "baseline_metrics.json"
DENSE_METRICS_PATH = REPORTS_DIR / "dense_metrics.json"
COMPARISON_REPORT_PATH = REPORTS_DIR / "comparison_report.md"

# Ingestion API URL
API_URL = "https://dummyjson.com/products?limit=0"

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "semantic_product_search")
MONGO_COLLECTION_RAW = "products_raw"
MONGO_COLLECTION_PROCESSED = "products_processed"

# IR Metrics Configuration
DEFAULT_TOP_K = [5, 10]

