# Amazon search backend

> Commands and artifact paths in this guide are relative to `backend/`, unless stated otherwise.

The serving catalog is MongoDB `semantic_product_search.amazon_products`.
There is no JSON fallback in the API. The prepared JSON is only an import artifact.
The existing raw and processed collections are preserved.

## Start

Ensure MongoDB is running, then from the Python project directory:

```sh
sh scripts/start_amazon_backend.sh
```

The first startup embeds 42,617 products using the fine-tuned MiniLM on CPU.
It can take several minutes. Later startups reuse vectors under `indexes/amazon`.
These caches contain only vectors and product IDs; product documents come from MongoDB.
The API remains at `http://127.0.0.1:8000`. Start the existing frontend separately.
The dashboard displays the first 100 records and the full product count.
Amazon ESCI has no reliable price, stock, or rating fields; missing values are not invented.

## Search configuration

- Fine-tuned model: `models/colab-export/esci-minilm-20k`.
- Reranker: `models/ms-marco-MiniLM-L6-v2`, maximum length 256.
- Keyword matching: brand and title.
- Spelling: frequency-based tie handling; common known words preserved.
- Query expansion: original query plus up to four alternatives.
- Retrieval: 50 candidates per alternative, reciprocal-rank fusion.
- Final ranking: 75% reranker rank, 25% fused retrieval rank.
- Use `fuzzy=0` to disable spelling correction and query expansion.

Models are loaded locally; serving does not download models.
The backend serializes inference for predictable CPU memory usage.
The Colab validation result of 79.88% applies to the full experimental pipeline;
this backend has not been benchmarked for accuracy or latency yet.

## Database settings and import

Set `MONGO_URI`, `MONGO_DB_NAME`, and `MONGO_AMAZON_COLLECTION` before starting
or importing when using a different database. Defaults are localhost port 27017,
`semantic_product_search`, and `amazon_products`.

```sh
.venv/bin/python scripts/import_amazon_mongo.py
```

The importer upserts by product ID, records a catalog version, and does not delete
existing data. If unrelated IDs exist in the selected collection, it stops.
A partial import marks the catalog unavailable until a successful reimport.
Catalog changes should be published through this importer so the vector cache
is rebuilt. Direct database edits do not automatically update the search index.
An external application should use the same version-manifest protocol.

Optional model overrides: `SEMANTIC_MODEL_PATH` and `RERANKER_MODEL_PATH`.
Training checkpoints and original models can remain as backups. No retraining
is performed by the backend.
