# Semantic Product Search Engine

An applied NLP and Information Retrieval system built for e-commerce product discovery. This project bridges lexical retrieval (BM25) and dense semantic retrieval (Sentence-BERT / FAISS), evaluating search quality using standard IR metrics.

---

## 🏗️ Architecture & Lifecycle
```
Data Ingestion ➔ Cleaning & Preprocessing ➔ Field Templating ➔ Keyword Index (BM25) / Vector Index (FAISS) ➔ IR Evaluation ➔ Serving API
```

---

## 📦 Project Structure
```
semantic-product-search/
├── data/
│   ├── raw/                 # Ingested raw JSON catalog
│   ├── processed/           # Cleaned & templated product representations
│   └── eval/                # Held-out benchmark query set with relevance labels
├── notebooks/
│   └── 01_eda.ipynb         # Interactive exploratory data analysis
├── src/
│   ├── config.py            # Centralized configuration (paths & MongoDB URI)
│   ├── data/
│   │   ├── db.py            # MongoDB connection, CRUD & fallback helpers
│   │   ├── load_data.py     # Data loaders (MongoDB + JSON fallback)
│   │   ├── validation.py   # Catalog schema integrity & missingness checks
│   │   └── preprocess.py   # Minimal cleaning & representation templating
│   ├── eda/
│   │   └── eda_analysis.py  # Automated EDA report generator
│   └── baseline/
│       ├── bm25.py          # BM25Okapi retrieval engine
│       └── evaluate_baseline.py # Precision@K, Recall@K, NDCG@K, MRR harness
├── indexes/
│   └── bm25_index.pkl       # Serialized keyword index
├── reports/
│   ├── eda_summary.md       # Exploratory analysis report & distributions
│   └── baseline_metrics.json# Benchmark results on held-out evaluation set
├── tests/
│   ├── test_data_pipeline.py# Unit tests for cleaning & schema validation
│   └── test_baseline.py     # Unit tests for BM25 search & IR metrics
└── requirements.txt
```

---

## 🚀 Quickstart & Pipeline Execution

### 1. Ingestion & Preprocessing
```bash
# Ingest raw catalog from API
python -m src.ingestion

# Validate schema and clean text
python -m src.data.preprocess
```

### 2. Run Exploratory Data Analysis (EDA)
```bash
# Generate EDA report at reports/eda_summary.md
python -m src.eda.eda_analysis
```

### 3. Build & Evaluate Keyword Baseline (BM25)
```bash
# Fit BM25 index and evaluate against held-out queries
python -m src.baseline.evaluate_baseline
```

### 4. Run Automated Unit Tests
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 📊 Month 1 Baseline Benchmark Results

Evaluated over the held-out 15-query test set (`data/eval/eval_set.json`):

| Metric | Score (BM25 Baseline) |
| :--- | :--- |
| **MRR** | **0.8300** |
| **Precision@5** | **0.4000** |
| **Recall@5** | **0.7800** |
| **NDCG@5** | **0.7450** |
| **Precision@10** | **0.2533** |
| **Recall@10** | **0.9133** |
| **NDCG@10** | **0.8118** |
| **Query Latency (p50 / p95)** | **0.11 ms / 0.12 ms** |

---

## 👤 Author
- **Name:** Arpit Maurya (MSU ID: 240410700144)
- **Track:** Advance Data Science
