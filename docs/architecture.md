# Architecture and folder responsibilities

```mermaid
flowchart LR
    U[Next.js website] --> A[Python HTTP API]
    M[(MongoDB Amazon catalog)] --> A
    A --> S[Spelling and query expansion]
    S --> R[Keyword and semantic retrieval]
    R --> C[Cross-encoder reranker]
    C --> B[75% reranker / 25% retrieval rank blend]
    B --> U
```

## Ownership

- `backend/api/` handles HTTP requests and engine initialization.
- `backend/src/data/amazon_mongo.py` loads catalog records and their import version.
- `backend/src/search/amazon.py` implements the serving search pipeline.
- `backend/src/semantic/` owns model training, embedding generation, and evaluation tools.
- `backend/scripts/` provides operator commands; `backend/notebooks/` contains cloud experiments.
- Root `frontend/` owns the user interface. Its illustrative landing-page fixtures are
  separate from the live MongoDB search catalog.
- `backend/models/`, `backend/indexes/`, `backend/reports/`, and `backend/colab/` contain generated local artifacts.

## Storage

The MongoDB collection `amazon_products` stores the prepared Amazon products.
`catalog_manifests` records the successful import version. The importer upserts
records without deleting other collections. Serving does not fall back to JSON.
The serving cache under `backend/indexes/amazon` contains vectors and product IDs;
serving loads product records from MongoDB. Offline FAISS caches also serialize
product metadata. Publish serving catalog changes through the importer to update
the cache version.

## Configuration

Copy `backend/.env.example` to `backend/.env` and set your values.
Backend commands load `backend/.env` without overriding shell exports. Model paths are relative to
`backend/` unless absolute paths are provided. Model downloads and
training belong in preparation workflows, not HTTP requests.

The frontend reads `NEXT_PUBLIC_API_URL`; see its API client for the default.
