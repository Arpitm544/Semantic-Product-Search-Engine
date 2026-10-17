# Product search backend

> Commands and artifact paths in this guide are relative to `backend/`, unless stated otherwise.

The serving catalog is MongoDB `semantic_product_search.amazon_products`.
There is no JSON fallback in the API. The prepared JSON is only an import artifact.

## Prepare data and models

From a fresh checkout, follow [Colab preparation and training](colab-training.md)
to create `data/dataset/prepared/products.json` and download `esci_minilm_model.zip`.
The model archive is produced by that workflow; it is not included in Git.
With the backend virtual environment activated, extract the archive and prepare
the reranker once (this step downloads weights; serving never does):

```bash
mkdir -p models
unzip /absolute/path/to/esci_minilm_model.zip -d models
python - <<'MODEL'
from sentence_transformers import CrossEncoder
model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2")
model.save_pretrained("models/ms-marco-MiniLM-L6-v2")
MODEL
cp .env.example .env
python scripts/import_catalog.py
```

Replace the archive path with your downloaded file. The encoder must contain
`models/esci-minilm-20k/modules.json` and its weights; the reranker must contain
`models/ms-marco-MiniLM-L6-v2/config.json` and its weights. Both directories are
Git ignored. Configure MongoDB in `.env` before importing; shell exports take
precedence. Start MongoDB before the import.

## Start

Ensure MongoDB is running, then from the Python project directory:

```sh
sh scripts/start_backend.sh
```

The first startup embeds 42,617 products using the fine-tuned MiniLM on CPU.
It can take several minutes. Later startups reuse vectors under `indexes/catalog`.
These caches contain only vectors and product IDs; product documents come from MongoDB.
The API listens at `http://127.0.0.1:8000` by default; set `PORT` to use another port. Start the existing frontend separately.
The dashboard displays the first 100 records and the full product count.
Amazon ESCI has no reliable price, stock, or rating fields; missing values are not invented.

## Search configuration

- Fine-tuned model: `models/esci-minilm-20k`.
- Reranker: `models/ms-marco-MiniLM-L6-v2`, maximum length 256.
- Keyword matching: full `representation_text`, including product details.
- Spelling vocabulary: brand and title.
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

Set `MONGO_URI`, `MONGO_DB_NAME`, and `MONGO_COLLECTION` before starting
or importing when using a different database. Defaults are localhost port 27017,
`semantic_product_search`, and `amazon_products`.

```sh
.venv/bin/python scripts/import_catalog.py
```

The importer upserts by product ID, records a catalog version, and does not delete
existing data. If unrelated IDs exist in the selected collection, it stops.
A partial import marks the catalog unavailable until a successful reimport.
Imports acquire a MongoDB lock in `catalog_import_locks` before modifying the
catalog. A concurrent importer stops without writing. The lock is released on
normal completion or an exception. If a process is killed, first stop or confirm
the old importer is no longer running, then remove only its lock document
(`_id` equal to `MONGO_COLLECTION`) from `catalog_import_locks` in the configured
database and rerun the import. Locks do not expire while an importer may be active.
Each import has a unique manifest ID; readers reject a catalog if the manifest
changes during their scan, including a reimport of identical input.
At startup, the API retries in-progress or changing imports every two seconds
for up to five minutes before reporting an initialization error. Other startup
errors, such as missing model files, are reported immediately.
Catalog changes should be published through this importer so the vector cache
is rebuilt. Direct database edits do not automatically update the search index.
An external application should use the same version-manifest protocol.

Optional model overrides: `SEMANTIC_MODEL_PATH` and `RERANKER_MODEL_PATH`.
Training checkpoints and original models can remain as backups. No retraining
is performed by the backend.

The backend uses FastAPI with function-based routes. Uvicorn starts when you run
`api/main.py`; the startup script sets the local CPU thread limits.
Interactive API documentation is available at http://127.0.0.1:8000/docs.
