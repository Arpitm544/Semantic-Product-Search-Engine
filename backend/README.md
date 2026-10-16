# Backend

FastAPI serves product search using MongoDB, keyword matching, spelling correction,
semantic matching, and a reranker. Start with the [reading guide](READING_GUIDE.md)
for a file-by-file explanation and request flow.

## Start the backend

From this `backend` directory, with MongoDB running, the catalog imported, and
local model weights available:

```sh
sh scripts/start_backend.sh
```

The script uses `.venv/bin/python` to run `api/main.py`. Uvicorn serves the API on
port 8000 by default. Initial vector creation can take several minutes; later
starts reuse saved vectors.

| URL | Purpose |
|---|---|
| `http://127.0.0.1:8000/api/health` | Search readiness and startup errors |
| `http://127.0.0.1:8000/api/search?q=headphones` | Product search |
| `http://127.0.0.1:8000/api/search?q=headphones&fuzzy=0` | Search with spelling correction disabled |
| `http://127.0.0.1:8000/api/search?q=headphones&source=serpapi` | Google Shopping through SerpApi |
| `http://127.0.0.1:8000/api/dashboard` | Catalog summary and preview |
| `http://127.0.0.1:8000/docs` | Interactive API documentation |

See [backend setup](../docs/backend.md) for dependency installation, MongoDB import,
model paths, and index details. Configuration names are in [.env.example](.env.example).
The API loads `.env`; exported shell settings take precedence.

## Google Shopping search (optional)

Get an API key from your [SerpApi dashboard](https://serpapi.com/manage-api-key).
Add these settings to `backend/.env`, then restart the backend:

```dotenv
SERPAPI_API_KEY=your_private_key
SERPAPI_COUNTRY=in
SERPAPI_LANGUAGE=en
```

`SERPAPI_LOCATION` optionally selects a city, such as `Mumbai, Maharashtra, India`.
Keep the key on the backend; never use a `NEXT_PUBLIC_` variable for it.
The frontend `/search` page lets visitors choose **MongoDB catalog** or
**Google Shopping · SerpApi**. MongoDB is the default when `source` is omitted.
Other source values and queries longer than 512 characters return HTTP 400.

Shopping fetches candidates from SerpApi, then ranks those candidates with our
fine-tuned MiniLM encoder and cross-encoder reranker. It combines semantic rank
(25%) and reranker rank (75%) using reciprocal rank fusion, as MongoDB search does.
Both sources reuse the same local model instances and inference lock. Shopping
does not query or modify the MongoDB index and works without MongoDB. It uses
the original query; MongoDB spelling correction and expansion are not applied
to external candidates. `/api/health` reports MongoDB model readiness.
The response contains up to 20 organic products, including image URLs, the
provider's displayed prices, merchants, and links when available. `total` is the
number of normalized products returned, not an estimate of all Google matches.
Unavailable fields stay empty. No separate request is made for each product.
Successful model ranking returns `searchMode=google-shopping-semantic-reranked`,
`semanticModel=fine-tuned`, and `rankingStatus=ranked`. Each product includes
`semanticScore`, `rerankerScore`, the fused `score`, and its original `providerRank`.
These scores are ranking signals, not probabilities of relevance. The candidate
set is limited to products returned by Google Shopping, so local ranking cannot
recover products that the provider omitted.

If local weights are missing or inference fails, the response retains Google's
order, `semanticModel=null`, and `rankingStatus=unavailable`, with a visible warning
and `warningCode=shopping_ranking_unavailable`. Empty results skip model loading.

Successful identical queries are cached in memory for five minutes (up to 128
entries per backend process). Only provider candidates are cached; our models
rank them on each search without modifying the cached records. Concurrent identical queries share one upstream
request. Errors are not cached and no automatic retries consume extra quota.
HTTP 503 reports missing/rejected credentials or a connection failure, 429 reports
a quota/throughput limit, 504 reports a timeout, and 502 reports provider or response
errors. Error bodies include a stable `code` and a readable `error`; provider
response bodies and credential-bearing URLs are never sent to the frontend.
See [SerpApi's documentation](https://serpapi.com/google-shopping-api) for product
fields and [error codes](https://serpapi.com/api-status-and-error-codes).

## Start the frontend separately

In another terminal:

```sh
cd frontend
npm run dev:frontend
```

Run these commands from the repository root. Alternatively, `npm run dev` from
`frontend` starts both services.

## Offline tools

From `backend`, use:

```sh
python scripts/import_catalog.py
python -m src.semantic.evaluate_typos --lexical-only
```

Activate `.venv` before running these Python commands. Imports and evaluation use the existing prepared dataset.

The local dataset downloader, preparation script, training script, and notebook
have been removed.
Previously uploaded Colab ZIPs retain their own code. Restore the training script
before using the retained bundle generator to build another training package.

More information: [root README](../README.md), [commands](../docs/commands.md), and
[search evaluation](../docs/typo-search.md).
