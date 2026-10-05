# Run Commands — Semantic Product Search

Keep this guide beside the [Study Notes](STUDY_NOTES.md). Each command below tells you which file it runs, what it does, and where its results go.

## Start in the right folder

From the repository root, enter the Python project:

```bash
cd semantic-product-search
```

All module, notebook, and test commands below run from this folder. Use `python -m src...` so Python can find the project's imports.

## Set up Python once

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On later visits, activate the environment with `source .venv/bin/activate` before running the modules. On Windows, the activation command is `.venv\Scripts\activate`.

The embedding library may download the MiniLM model the first time you use dense search. An internet connection is needed for API ingestion and for an uncached model download.

## Commands for each executable module

### 1. Fetch products — `src/ingestion.py`

```bash
python -m src.ingestion
```

Fetches the DummyJSON catalog and attempts to upsert records into MongoDB's `products_raw` collection. It does not update `data/raw/products.json`. With MongoDB unavailable, it logs that persistence was skipped.

The default MongoDB server is `mongodb://localhost:27017/`. The `MONGO_URI` and `MONGO_DB_NAME` environment variables can change the connection settings. If you are learning from the saved local catalog, you can skip API ingestion.

### 2. Check the catalog — `src/data/validation.py`

```bash
python -m src.data.validation
```

Loads raw records from MongoDB or the saved JSON file, then prints a validation result and a report of missing fields, duplicate IDs, and invalid prices. It does not create an index.

### 3. Prepare searchable text — `src/data/preprocess.py`

```bash
python -m src.data.preprocess
```

Loads raw products, prints their validation status, prepares `representation_text`, and attempts to save processed records to MongoDB's `products_processed` collection. The default command does not update `data/processed/products_cleaned.json` because `save_json_backup` defaults to `False`. Validation failure is printed but does not stop this command.

To read the saved raw JSON and write a fresh cleaned JSON file, use this alternative:

```bash
python - <<'PY'
from src.data.load_data import load_raw_products
from src.data.preprocess import preprocess_catalog
from src.data.validation import validate_catalog

raw = load_raw_products(prefer_mongo=False)
valid, report = validate_catalog(raw)
if not valid:
    raise ValueError(report)

preprocess_catalog(raw, save_to_mongo=False, save_json_backup=True)
PY
```

This version explicitly stops on failed validation and writes `data/processed/products_cleaned.json`. It is a shell example for macOS/Linux.

### 4. Explore the catalog — `src/eda/eda_analysis.py`

```bash
python -m src.eda.eda_analysis
```

Loads processed products and summarizes categories, prices, ratings, vocabulary, and text lengths. Writes `reports/eda_summary.md`.

### 5. Build keyword search — `src/baseline/bm25.py`

```bash
python -m src.baseline.bm25
```

Builds a BM25 index from processed products, writes `indexes/bm25_index.pkl`, then searches the example query `warm winter jacket` and prints up to three results. Running it again rebuilds the saved index.

### 6. Evaluate keyword search — `src/baseline/evaluate_baseline.py`

```bash
python -m src.baseline.evaluate_baseline
```

Loads the saved BM25 index, or builds one if absent, and searches the queries in `data/eval/eval_set.json`. Prints retrieval metrics and query timing, then writes `reports/baseline_metrics.json`.

### 7. Build semantic search — `src/dense/vector_search.py`

```bash
python -m src.dense.vector_search
```

Loads processed products, generates MiniLM embeddings, normalizes them, and builds a FAISS `IndexFlatIP` index. Writes both `indexes/faiss_index.bin` and `indexes/faiss_id_map.pkl`.

It then searches the example query `wireless Bluetooth headphones` and prints up to three results. Running it again rebuilds both index artifacts.

### 8. Evaluate semantic search — `src/dense/evaluate_dense.py`

```bash
python -m src.dense.evaluate_dense
```

Loads the saved FAISS index and metadata, or builds them if either is missing, and evaluates the same labeled queries. Prints metrics and timing, then writes `reports/dense_metrics.json`.

### 9. Compare both methods — `src/compare_models.py`

```bash
python -m src.compare_models
```

Runs both evaluators and prints a comparison. Refreshes the two metrics JSON files and writes `reports/comparison_report.md`.

Evaluation reuses existing indexes. After changing searchable product text or the embedding model, run the two index-building commands before comparing the methods.

## A simple learning sequence

With dependencies installed and the saved raw catalog available, you can use the local JSON preprocessing example above, then run:

```bash
python -m src.eda.eda_analysis
python -m src.baseline.bm25
python -m src.dense.vector_search
python -m src.compare_models
```

Loaders normally prefer nonempty MongoDB collections when available. For an explicitly local-only experiment in Python, call `load_raw_products(prefer_mongo=False)` or `load_cleaned_products(prefer_mongo=False)`. The existing module commands do not expose a local-only command-line flag.

## Search with your own query

After building the indexes, this example loads both and prints their results without rebuilding:

```bash
python - <<'PY'
from src.baseline.bm25 import BM25Okapi
from src.dense.vector_search import DenseVectorSearch

query = "eyewear for sunny days"
engines = [
    ("Keyword", BM25Okapi.load()),
    ("Semantic", DenseVectorSearch.load()),
]
for name, engine in engines:
    print(f"\n{name}: {query}")
    for product, score in engine.search(query, top_k=3):
        print(product["id"], product["title"], score)
PY
```

Edit `query` to try other searches. Scores from the two methods have different scales.

## Run existing tests

Run all existing tests:

```bash
python -m pytest tests/
```

Or select one file:

| Test file | Command |
| --- | --- |
| `tests/test_data_pipeline.py` | `python -m pytest tests/test_data_pipeline.py` |
| `tests/test_db.py` | `python -m pytest tests/test_db.py` |
| `tests/test_baseline.py` | `python -m pytest tests/test_baseline.py` |
| `tests/test_dense_search.py` | `python -m pytest tests/test_dense_search.py` |

Dense search tests use a real encoder and may need the model download. `tests/conftest.py` supplies fixtures to pytest; it is not a standalone test command.

## Open the notebook

The notebook is `notebooks/01_eda.ipynb`. Jupyter is an optional extra for reading it interactively:

```bash
python -m pip install notebook
python -m notebook notebooks/01_eda.ipynb
```

Choose the Python environment where you installed this project's dependencies.

## Files without a standalone pipeline command

| File or folder | How it is used |
| --- | --- |
| `src/config.py` | Imported for paths and settings |
| `src/data/db.py` | Imported for MongoDB operations |
| `src/data/load_data.py` | Imported for loading records |
| `__init__.py` | Package marker used by Python imports |
| `tests/conftest.py` | Automatically loaded by pytest |
| `data/` | Input records and evaluation labels |
| `indexes/` | Artifacts loaded by the search engines |
| `reports/` | Outputs to read after running the pipeline |

This guide documents the current entry points. The commands were checked against the source code, but the pipeline and test suite were not executed while adding this documentation.
