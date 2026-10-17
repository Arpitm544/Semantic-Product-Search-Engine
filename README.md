# Semantic Product Search Engine

Product search over a prepared Amazon ESCI catalog stored in MongoDB. The backend
combines a fine-tuned MiniLM encoder, full-text keyword retrieval, spelling
correction, query expansion, and a blended cross-encoder reranker.

## Repository layout

```text
.
├── frontend/                   Next.js website
├── docs/                       Setup, architecture, training, and study guides
├── .github/                    GitHub Actions workflows
├── backend/                    Python application workspace
│   ├── api/                    HTTP API
│   ├── src/                    Shared Python modules
│   │   ├── data/               MongoDB catalog access
│   │   ├── search/             Correction, expansion, and ranking
│   │   ├── semantic/           Embeddings, training, and evaluation
│   │   └── keyword_search/     Keyword search (BM25)
│   ├── scripts/                Import, packaging, and startup commands
│   ├── notebooks/              Colab experiments
│   ├── tests/                  Automated checks
│   ├── data/                   dataset/ source, training, and evaluation data
│   ├── models/                 Local model weights (Git ignored)
│   ├── indexes/                Derived vector caches (Git ignored)
│   ├── reports/                Evaluation outputs (Git ignored)
│   └── colab/                  Generated upload bundles (Git ignored)
├── requirements.txt            Repository dependency entry point
└── pytest.ini                  Existing test discovery configuration
```

## Local startup

From the repository root, with MongoDB running and the project virtual environment
and model weights prepared using [the backend setup guide](docs/backend.md),
and the prepared Amazon catalog imported into MongoDB:

```sh
cd backend
.venv/bin/python scripts/import_catalog.py
sh scripts/start_backend.sh
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

- [MongoDB backend and model setup](docs/backend.md)
- [Architecture and configuration](docs/architecture.md)
- [Google Colab training](docs/colab-training.md)
- [Command reference](docs/commands.md)
- [Spelling and fine-tuning experiments](docs/typo-search.md)
- [Study notes](docs/study-notes.md)

## Data and evaluation

MongoDB is the serving source of truth for all 42,617 Amazon product records.
Offline JSON files are import/evaluation artifacts; the API has no JSON fallback.
Local weights and vector caches are separate from the product database.
All local dataset files are under backend/data/dataset/, with raw/ and prepared/ subfolders.

The latest reported Colab validation top-5 success was 79.88% for generated typo
queries and 86.50% for clean queries. These are experiment results, not a fresh
benchmark of the integrated backend. Amazon ESCI source attribution and license
are included with the prepared dataset.
