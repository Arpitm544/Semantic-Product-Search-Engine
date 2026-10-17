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

Download the original dataset only when it is missing:

~~~sh
python -m src.semantic.download_esci
~~~

Prepare the dataset only when prepared/ is missing:

~~~sh
python -m src.semantic.prepare_esci
~~~

The preparation command refuses to overwrite an existing manifest.
For a separate experiment, supply another --output-dir.

## Import the catalog into MongoDB

~~~sh
python scripts/import_catalog.py
~~~

The default input is data/dataset/prepared/products.json.
Serving reads the imported MongoDB catalog.

## Training

Use the [Colab guide](colab-training.md) for GPU training.
To regenerate the matching upload ZIP and notebook after code changes:

~~~sh
python scripts/create_colab_bundle.py
~~~

Local training uses the same prepared dataset:

~~~sh
python -m src.semantic.train_esci --output-dir models/new-run
~~~

Training requires the embedding model and training libraries. Use a new output
directory for a new run; --resume continues a compatible checkpoint.

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
