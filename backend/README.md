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
| `http://127.0.0.1:8000/api/search?q=headphones&source=shops` | Free online shops (eBay, independent stores) |
| `http://127.0.0.1:8000/api/dashboard` | Catalog summary and preview |
| `http://127.0.0.1:8000/docs` | Interactive API documentation |

See [backend setup](../docs/backend.md) for dependency installation, MongoDB import,
model paths, and index details. Configuration names are in [.env.example](.env.example).
The API loads `.env`; exported shell settings take precedence.

## Google Shopping search (optional)

MongoDB search returns `candidateCount`: the bounded candidate pool considered
for ranking, not an exhaustive catalog match count. `results` contains at most
20 of those candidates.

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
errors. Shopping provider and configuration errors include a stable `code` and
a readable `error`. HTTP 400 validation errors contain only `error`; provider
response bodies and credential-bearing URLs are never sent to the frontend.
See [SerpApi's documentation](https://serpapi.com/google-shopping-api) for product
fields and [error codes](https://serpapi.com/api-status-and-error-codes).

## Online shops search (free, optional)

`source=shops` searches several shops' own product APIs at once, without paid
search quota, then ranks the merged results with the same encoder and reranker
as Google Shopping. On the search page it is **Online shops · eBay, stores**.
Each shop turns on once its keys (or, for independent stores, its entry in
`SHOP_STORES`) are in `backend/.env`; restart the backend after changing them.
With no shop configured, the source returns HTTP 503 with `code=shops_not_configured`.

| Shop | Free account | Settings |
|---|---|---|
| eBay | [eBay Developers Program](https://developer.ebay.com/) production keyset (Browse API) | `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, optional `EBAY_MARKETPLACE_ID` (default `EBAY_US`) |

```dotenv
EBAY_CLIENT_ID=your_client_id
EBAY_CLIENT_SECRET=your_client_secret
```

How it behaves:

- Shops are searched in parallel with a 15-second shared deadline. A shop that
  fails or times out is listed in `providers` with its `status` and `message`,
  and a `warning` names it; results from the other shops are still returned. If
  every configured shop fails, the API returns HTTP 503 with `code=shops_unavailable`.
- Each shop contributes up to 10 results, merged round-robin
  so no shop crowds out the others, then ranked by our models. If the models are
  unavailable, the shops' own order is kept with `rankingStatus=unavailable`.
- Results are cached per shop and query for five minutes. eBay application
  tokens last two hours and are reused; eBay allows 1,000 token requests a day.
- `EBAY_DAILY_CALLS` (default 4,000) caps eBay search calls per backend process
  per UTC day, to stay inside the free quota.
  Per-user searches are limited by `SHOPS_SEARCHES_PER_MINUTE` (default 10).
- Results can be saved, collected, and compared. Price alerts are not available
  yet for shop results. Saved preferences apply only the budget filter, because
  not every shop reports brand, category, or stock.
- Each result has an `id` of `<shop>:<shop product id>`, `merchant` (`eBay` or
  the store's domain), `price` and `currency`, and, where the shop
  provides them, `brand`, `category`, `inStock`, an image, and a link to the
  product on the shop's site.

### Independent stores (no keys)

Many independent stores built on Shopify or WooCommerce publish their product
data openly. List the stores to include in `SHOP_STORES`, as comma-separated
`platform:host[:CURRENCY]` entries:

```dotenv
SHOP_STORES=shopify:www.example-store.in:INR,woocommerce:shop.example.com
```

- `platform` is `shopify` or `woocommerce`. `host` is the store's final public
  domain, with no `https://`, path, or port; IP addresses and `localhost` are
  rejected. `CURRENCY` defaults to `INR`. Up to 20 stores; invalid entries are
  skipped with a warning in the backend log.
- **Shopify:** the public `/products.json` catalog is downloaded (up to
  `SHOP_STORE_MAX_PRODUCTS`, default 1,000) and refreshed every six hours, then
  searched by keyword before our models rank the results. Shopify's default
  robots.txt disallows `/search`, so storefront search pages are never used.
  Shopify catalogs have no currency, so it comes from the entry. The first search
  after a refresh can exceed the 15-second deadline for a large catalog; the
  download still finishes, and that store answers from the next search.
- **WooCommerce:** searched live through the public Store API
  (`/wp-json/wc/store/v1/products?search=`), which reports its own currency.
- Every store's robots.txt is read first (cached for a day) and respected: a
  store that disallows access is skipped, with `status=blocked` and a warning.
  Requests use the generic user agent `SemanticProductSearch/1.0` and never
  include user data. Redirects are not followed; a store that redirects is
  reported with `status=redirect`, so you can list its final domain instead.
- `SHOP_STORE_DAILY_CALLS` (default 2,000) caps requests to each store per
  backend process per UTC day.

Only list stores whose terms allow this use. Product data comes from each shop's
official API or the store's own public product data; protected pages and
storefront search pages are never fetched.

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

The dataset downloader, preparation script, training script, and Colab notebook
are available for reproducible training. See [Colab training](../docs/colab-training.md)
to prepare the data and regenerate a matching notebook and bundle.

More information: [root README](../README.md), [commands](../docs/commands.md), and
[search evaluation](../docs/typo-search.md).
