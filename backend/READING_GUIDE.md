# Understanding the backend

Start with `api/main.py`, then follow the functions it calls. The API receives a
query, gets a prepared search engine, and returns matching products as JSON.

## How a URL calls a function

In `api/main.py`:

```python
@app.get("/api/search")
def search_products(q: str = "", fuzzy: str = "1", source: str = "mongo"):
```

Opening `/api/search?q=headphones` makes FastAPI call
`search_products(q="headphones")`. The decorator connects the URL to the function.
The URL calls a function; folders organize the files that contain the code.

## Follow a search

```text
/api/search?q=headphones
    ↓
api/main.py → search_products()
    ↓
api/search_service.py → get_search_engine()
    ↓
src/search/product_search.py → ProductSearch.search()
    ↓
JSON results returned to the frontend
```

`get_search_engine()` loads products and models when needed and reuses the engine
while the catalog and model settings stay the same. This line creates the engine:

```python
_search_engine = ProductSearch(products, semantic, reranker, model_lock=get_candidate_ranker().lock)
```

`ProductSearch.search()` has three steps:

1. Prepare the query and its spelling variations.
2. `find_candidates()` gets possible matches from hybrid search.
3. `rank_candidates()` puts the best matches first.

## Search files

| File | Job | Functions to read first |
|---|---|---|
| `search/product_search.py` | Manage the complete search | `search()`, `find_candidates()`, `rank_candidates()` |
| `search/typos.py` | Find cautious spelling corrections | `correct()`, `suggestion()`, `alternatives()` |
| `search/hybrid.py` | Combine keyword and meaning-based matches | `search()`, `collect_rankings()`, `combine_rankings()` |
| `keyword_search/bm25.py` | Match query words to product text | `fit_bm25()`, `search_bm25()` |
| `semantic/vector_search.py` | Find products with similar meaning | `fit()`, `search()` |

These paths are inside `src/`. In `typos.py`, `CatalogSpelling` chooses clear
corrections; `FrequencySpelling` also considers how common words are in the catalog.
Use `fuzzy=0` in the search URL to disable spelling correction and query variations.
Keyword search, semantic search, and reranking still run.

A **vector** is a list of numbers representing text's meaning. A **reranker**
scores how well a query matches candidate products. Final ranking combines
retrieval order (25%) with reranker order (75%).

## API and database files

| File | Job |
|---|---|
| `api/main.py` | Define FastAPI routes and start Uvicorn |
| `api/search_service.py` | Load models, restore saved vectors, and reuse the engine |
| `api/dashboard.py` | Build catalog counts, categories, and a product preview |
| `src/data/catalog.py` | Load the MongoDB catalog and check its import status |
| `src/data/db.py` | Create the MongoDB connection |
| `src/config.py` | Define shared paths and database defaults |
| `.env` | Supply local configuration; shell settings take precedence |

The startup script sets CPU limits and runs `api/main.py`. Models load in a
background thread. `/api/health` reports progress until search is ready.

API routes use ordinary functions. Search classes keep products, models,
vocabulary, and indexes together so requests can reuse them.

## Data preparation and evaluation

| File in `src/semantic/` | Job |
|---|---|
| `dataset.py` | Read data, generate typo examples, and group training batches |
| `evaluate_typos.py` | Compare search methods on clean and typo queries |
| `vector_search.py` | Run meaning-based search |

The prepared catalog and query splits already exist in `data/dataset/prepared/`.
Use `src/semantic/prepare_esci.py` to rebuild the prepared files after downloading
the source with `src/semantic/download_esci.py`.

A **query family** groups queries with the same normalized wording. Keeping
families separate prevents training on evaluation questions. A **manifest**
records counts, source information, and hashes used to validate the files.
ESCI is the source dataset's name; its labels mean Exact, Substitute, Complement,
and Irrelevant. Source labels and IDs remain compatible with the existing data.

## Other folders and scripts

| Location | Contents |
|---|---|
| `scripts/start_backend.sh` | Start the API with local CPU limits |
| `scripts/import_catalog.py` | Import the prepared catalog into MongoDB |
| `scripts/create_colab_bundle.py` | Generator retained for future Colab packaging |
| `tests/` | Automated checks, small test inputs, and mocked services |
| `data/dataset/raw/` | Original downloaded files, source information, and license |
| `data/dataset/prepared/` | Catalog, training/validation/test examples, and manifest |
| `models/` | Local embedding model and reranker weights |
| `indexes/` | Saved product vectors that avoid repeated calculation |
| `colab/` | Previously generated upload artifacts |
| `.venv/` | Installed Python packages |

The downloader, preparation script, and `src/semantic/train_esci.py` support
reproducible training. Follow [Colab training](../docs/colab-training.md) to
regenerate the notebook and its matching ZIP with the bundle generator.
