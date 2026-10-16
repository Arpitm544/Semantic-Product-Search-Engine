# Understanding the backend

Start with `api/main.py`. A route connects a URL to an ordinary Python function:

```python
@app.get("/api/search")
def search_products(q: str = "", fuzzy: str = "1"):
```

FastAPI puts the URL's `q` value into the function's `q` argument. The function
gets the search engine, calls `engine.search(...)`, and returns JSON.

## Follow a search request

1. `api/main.py` receives `/api/search?q=headphones`.
2. `api/search_service.py` returns an existing engine or builds one.
3. `src/data/catalog.py` loads products from MongoDB.
4. `src/search/product_search.py` finds candidates and ranks them.
5. FastAPI sends the results back to the frontend.

The engine has two main ranking steps:

- `find_candidates()` combines keyword and meaning-based matches across query variations.
- `rank_candidates()` uses the reranker model, then combines its ranking with retrieval ranking.

A **vector** is a list of numbers representing text's meaning. A **reranker** is a
model that scores how well a query matches each candidate product. A **cache**
saves previously calculated vectors to avoid calculating them again.

## What each folder does

| Folder | Purpose | Start reading here |
|---|---|---|
| `api/` | URLs, startup, search-engine loading, dashboard summaries | `main.py` |
| `src/data/` | MongoDB connection and catalog loading | `catalog.py` |
| `src/keyword_search/` | Match words using BM25 | `bm25.py` |
| `src/search/` | Spelling, combined retrieval, final ranking | `product_search.py` |
| `src/semantic/` | Meaning-based search, data preparation, training, evaluation | `vector_search.py` |
| `scripts/` | Startup, catalog import, and Colab packaging commands | `start_backend.sh` |
| `tests/` | Checks using small test inputs and mocked services | `test_search_api.py` |
| `data/dataset/raw/` | Original downloaded dataset and license | `source.json` |
| `data/dataset/prepared/` | Catalog plus separate training and evaluation examples | `manifest.json` |
| `models/` | Downloaded and trained model files | Configured by `.env` |
| `indexes/` | Saved product vectors | Created automatically |
| `notebooks/` | Instructions to run training in Colab | The Colab notebook |
| `colab/` | Generated ZIP to upload to Colab | Rebuilt by the bundle script |
| `.venv/` | Installed Python dependencies | Managed by pip |

`src/config.py` defines shared paths and database defaults. `.env` supplies local
settings. `requirements.txt` lists the Python packages to install.

## Follow the training workflow

The command modules use the same pattern: `main()` reads command arguments,
then calls the function that performs the task.

1. `download_esci.py` → `download_dataset()` downloads and verifies source files.
2. `prepare_esci.py` → `prepare_dataset()` builds the catalog and separate query splits.
3. `train_esci.py` → `train_model()` trains the model; `train_batch()` updates it for one batch.
4. `evaluate_typos.py` → `evaluate_models()` compares search methods and saves scores.

A **query family** groups queries with the same normalized wording. Keeping
families in separate splits prevents training on evaluation questions.
A **checkpoint** saves model and optimizer state so interrupted training can resume.
A **manifest** records counts, source information, and hashes used to validate files.

ESCI is the source dataset's name. Its labels mean Exact match, Substitute,
Complement, and Irrelevant. These names remain in training code to match the data.

## Functions and classes

API routes and command steps use ordinary functions. Search classes keep related
state together: products, models, spelling vocabulary, and indexes. Read their
`search()` methods first, then follow the helper calls as needed.

The startup shell script sets CPU limits and runs `api/main.py`. Model loading
happens in a background thread; `/api/health` reports readiness while it runs.
