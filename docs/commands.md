# Run commands

Run Python commands from backend/. Run website commands from frontend/.

## Start the application

From backend/, with MongoDB and the local models ready:

~~~sh
sh scripts/start_backend.sh
~~~

From frontend/, in another terminal:

~~~sh
npm run dev:frontend
~~~

The website uses port 3001; the API uses port 8000.
See [backend setup](backend.md) for model paths and database settings.

## Dataset

All local source and prepared data live under data/dataset/ inside backend/:

- raw/: original Amazon products, labeled queries, source information, and license.
- prepared/: products.json, train.jsonl, validation.jsonl, test.jsonl, and manifest.json.

The original dataset is already stored in `data/dataset/raw/`.
Source information and file hashes are recorded in `raw/source.json`.

The preparation script has been removed. Use the existing prepared files; restore
the script from Git history before changing the preparation process.

## Import the catalog into MongoDB

~~~sh
python scripts/import_catalog.py
~~~

The default input is data/dataset/prepared/products.json.
Serving reads the imported MongoDB catalog.

## Training

The local training script has been removed. Existing uploaded Colab ZIPs keep
their own copy. Restore `src/semantic/train_data.py` before creating a new
training ZIP or notebook with `scripts/create_colab_bundle.py`.

## Evaluate search

Compare keyword and spelling-aware retrieval on the prepared validation split:

~~~sh
python -m src.semantic.evaluate_typos --lexical-only
~~~

Use --split test for the held-out test split. Model comparisons and metrics are
described in [search evaluation](typo-search.md).

## Tests

From the repository root, with development dependencies installed:

~~~sh
pytest
~~~

The tests use small in-memory fixtures; they do not require the retired sample
catalog or its data folders.
