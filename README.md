# Semantic Product Search Engine

Product search over a prepared Amazon ESCI catalog stored in MongoDB. The backend
combines a fine-tuned MiniLM encoder, full-text keyword retrieval, spelling
correction, query expansion, and a blended cross-encoder reranker.

## Repository layout

```text
.
├── frontend/                   Next.js website
├── docs/                       Setup, architecture, training, and study guides
│   └── archive/                Historical documentation
├── .github/                    GitHub Actions workflows
├── backend/                    Python application workspace
│   ├── api/                    HTTP API
│   ├── src/                    Shared Python modules
│   │   ├── data/               MongoDB access and data preparation
│   │   ├── search/             Correction, expansion, and ranking
│   │   ├── semantic/           Embeddings, training, and evaluation
│   │   └── baseline/           Keyword baseline
│   ├── scripts/                Import, packaging, and startup commands
│   ├── notebooks/              Colab experiments
│   ├── tests/                  Existing automated checks
│   ├── data/                   Offline import and evaluation artifacts
│   ├── models/                 Local model weights (Git ignored)
│   ├── indexes/                Derived vector caches (Git ignored)
│   ├── reports/                Evaluation outputs (Git ignored)
│   └── colab/                  Generated upload bundles (Git ignored)
├── requirements.txt            Repository dependency entry point
└── pytest.ini                  Existing test discovery configuration
```

## Local startup

From the repository root, with MongoDB running and the project virtual environment
and model weights prepared using [the backend setup guide](docs/amazon-backend.md),
and the prepared Amazon catalog imported into MongoDB:

```sh
cd backend
.venv/bin/python scripts/import_amazon_mongo.py
sh scripts/start_amazon_backend.sh
```

In another terminal, from the repository root:

```sh
cd frontend
npm run dev:frontend
```

Backend: `http://127.0.0.1:8000`. The frontend prints its URL when it starts. Alternatively, `npm run dev` from
`frontend/` starts both services; use it instead of the two separate commands.
First backend startup builds product vectors; later startups reuse the index.

## Documentation

- [MongoDB backend and model setup](docs/amazon-backend.md)
- [Architecture and configuration](docs/architecture.md)
- [Google Colab training](docs/colab-training.md)
- [Command reference](docs/commands.md)
- [Spelling and fine-tuning experiments](docs/typo-search.md)
- [Study notes](docs/study-notes.md)

## Data and evaluation

MongoDB is the serving source of truth for all 42,617 Amazon product records.
Offline JSON files are import/evaluation artifacts; the API has no JSON fallback.
Local weights and vector caches are separate from the product database.

The latest reported Colab validation top-5 success was 79.88% for generated typo
queries and 86.50% for clean queries. These are experiment results, not a fresh
benchmark of the integrated backend. Amazon ESCI source attribution and license
are included with the prepared dataset. Original project notes are preserved
under `docs/archive`.
