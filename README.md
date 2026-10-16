# Semantic Product Search Engine

Product search over a prepared Amazon ESCI catalog stored in MongoDB. The backend
combines a fine-tuned MiniLM encoder, brand/title keyword retrieval, spelling
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
│   │   ├── semantic/           Meaning-based search and evaluation
│   │   └── keyword_search/     Keyword search (BM25)
│   ├── scripts/                Import, packaging, and startup commands
│   ├── tests/                  Automated checks
│   ├── data/                   dataset/ source, training, and evaluation data
│   ├── models/                 Local model weights (Git ignored)
│   ├── indexes/                Derived vector caches (Git ignored)
│   ├── reports/                Created when evaluation saves reports (Git ignored)
│   └── colab/                  Generated upload bundles (Git ignored)
├── requirements.txt            Repository dependency entry point
└── pytest.ini                  Existing test discovery configuration
```

## Local startup

From the repository root, with MongoDB running and the project virtual environment
and model weights prepared:

```sh
cd backend
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

## Search flow

FastAPI routes in `backend/api/main.py` call the reusable search engine from
`api/search_service.py`. `src/search/product_search.py` prepares the query, finds
hybrid matches, and reranks them. Spelling rules live in `typos.py`; `hybrid.py`
combines keyword and semantic rankings.

Interactive API documentation: `http://127.0.0.1:8000/docs`.

## Colab files

The local downloader, preparation script, training script, and notebook have been
removed. Existing
uploaded Colab ZIPs keep their own code. The bundle generator remains, but requires
`backend/src/semantic/train_data.py` to be restored before rebuilding a training
package. Recreate the notebook when needed. Evaluation tools remain available locally; rebuilding prepared data requires
restoring the preparation script.

## Documentation

- [Backend reading guide](backend/READING_GUIDE.md)
- [Backend commands and endpoints](backend/README.md)
- [MongoDB backend and model setup](docs/backend.md)
- [Architecture and configuration](docs/architecture.md)
- [Google Colab training](docs/colab-training.md)
- [Command reference](docs/commands.md)
- [Spelling and fine-tuning experiments](docs/typo-search.md)
- [Study notes](docs/study-notes.md)

## Data and evaluation

MongoDB is the serving source of truth for all 42,617 Amazon product records.
Offline JSON files are import/evaluation artifacts; the API has no JSON fallback.
The search page also offers optional Google Shopping results through SerpApi.
Set `SERPAPI_API_KEY` in `backend/.env` and restart the backend; see the
[shopping setup](backend/README.md#google-shopping-search-optional). Shopping
results come from the external provider and do not use the MongoDB search index.
Local weights and vector caches are separate from the product database.
All local dataset files are under backend/data/dataset/, with raw/ and prepared/ subfolders.

The latest reported Colab validation top-5 success was 79.88% for generated typo
queries and 86.50% for clean queries. These are experiment results, not a fresh
benchmark of the integrated backend. Amazon ESCI source attribution and license
are included with the prepared dataset.
