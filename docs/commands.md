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

A fresh checkout contains no dataset. From `backend/`, install
`requirements.txt`, then run the following preparation commands before importing.
The downloader obtains the official Amazon ESCI files and attribution metadata
in `data/dataset/raw/`; preparation creates `prepared/products.json`.
Source information and file hashes are recorded in `raw/source.json`.
The downloader also writes `raw/LICENSE` and `raw/NOTICE`. These attribution
and provenance files are allowed by Git; the large dataset files stay ignored.

```sh
python -m src.semantic.download_esci
python -m src.semantic.prepare_esci --pairs 20000
```

See [Colab preparation](colab-training.md#prepare-the-bundle-from-a-fresh-checkout)
for environment setup, download size, and complete preparation options.

## Import the catalog into MongoDB

~~~sh
python scripts/import_catalog.py
~~~

The default input is data/dataset/prepared/products.json.
Serving reads the imported MongoDB catalog.

## Training

Use `scripts/create_colab_bundle.py` to package `src/semantic/train_esci.py`
and the prepared data. Follow [Colab training](colab-training.md) to generate
and run the matching training ZIP and notebook.

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
