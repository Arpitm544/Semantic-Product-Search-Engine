# Shopify search setup and operations

The integration is disabled by default. It adds `source=shopify` without changing
Amazon or SerpApi. The current implementation is for one bounded collection,
one store, and the Storefront's default market/currency.

## Configure the store

1. Create/install an app using Shopify's current supported app setup. Grant the
   Admin product/collection read permissions required by the catalog query.
2. Configure private Storefront API access through the Headless channel. Publish
   the collection's products to that channel and your online store. Products
   without an online-store URL are excluded.
3. Fill the `SHOPIFY_*` settings in `backend/.env` from `.env.example`. Never
   commit real credentials. The webhook secret is the app client secret.
4. Choose a collection with at most `SHOPIFY_SYNC_MAX_PRODUCTS` items. An import
   exceeding this cap fails without deleting the current catalog. Set
   `SHOPIFY_ENABLED=true` only once credentials and collection are configured.
5. Provision persistent MongoDB and a shared persistent `backend/indexes/shopify`
   volume for API and worker. Local model weights must already be installed.

Storefront prices use the store's default context. Multiple markets, currencies,
customer-specific prices, and OAuth onboarding of other stores are outside this
single-store integration. Supply valid Admin tokens and rotate/renew them using
how your app issues credentials; automatic token renewal is not implemented.

## First import

From `backend/`, using the same environment as the API:

```sh
.venv/bin/python scripts/sync_shopify.py
.venv/bin/python scripts/run_shopify_worker.py
```

Keep the worker running as a supervised process. It handles durable jobs and
hourly complete reconciliation, including publication/collection drift and
missed events. Its first run reconciles immediately. No additional scheduler is
required. Use a small collection for the first import, then test real queries.

Select **Shopify store** on the search page. The authenticated status endpoint is
`GET /api/shopify/status`. Initial search before import returns a controlled 503.

## Webhooks

After the first import has created database indexes, register HTTPS subscriptions
for `products/create`, `products/update`, and `products/delete` at:

```text
https://YOUR-BACKEND/api/shopify/webhooks
```

Collection and product-listing event topics are also accepted where supported by
your app. Subscribe before the production baseline import and reconcile again
after registration to cover setup races. The endpoint verifies the raw-body HMAC,
configured shop domain, and delivery ID; it acknowledges only durable enqueue.
No user session token is required for this signed server-to-server endpoint.

Events trigger a complete bounded collection reconciliation, rather than trusting
partial or out-of-order payloads. Jobs queued before a successful scan are
coalesced. New deliveries arriving during a scan remain queued for another scan.
Expired running-job leases allow recovery after worker restarts. Five failed
attempts mark a job failed; hourly reconciliation continues independently.

## Failure recovery

- Inspect worker logs and `shopify_sync_state` for sync failures. Search can use
  the previous published generation while a new one builds.
- Inspect `shopify_jobs` by store/status. To replay a failed job after fixing its
  cause, set `status=pending`, `attempts=0`, and `next_attempt` to the current UTC
  BSON date. Never edit signed webhook ingress to bypass verification.
- Rerun `sync_shopify.py` to recover catalog drift or rebuild an index. Unchanged
  text reuses cached embeddings. Model fingerprint changes generate fresh ones.
- Restart supervised API workers if a published index file becomes corrupt.
  Restore a previous complete generation by atomically replacing `current.json`
  with its generation/count/model metadata, then reconcile product state. Keep
  API and worker on identical model weights; changes require resynchronization.
- Disable Shopify via `SHOPIFY_ENABLED=false` and restart the API/worker to stop
  serving this source. Existing Amazon/SerpApi sources remain available.

The pipeline builds immutable product/vector snapshots before replacing database
records, then publishes the pointer. MongoDB document updates are idempotent but
are not a multi-document transaction: a crash during replacement can temporarily
hide results. Rerunning a complete sync repairs the state. Current eligibility is
checked against MongoDB and Storefront before returning products. Price details
have a configurable cache of at most 300 seconds (60 by default). Cache invalidation
is local to the receiving API process; other processes expire entries by TTL.

## Capacity and limits

The production app's Amazon source now uses Atlas. Shopify uses a separate local
NumPy cosine matrix plus the existing keyword engine/reranker, so installing FAISS
is unnecessary. Text vectors are cached individually; keyword and cosine indexes
are assembled per generation. This remains O(N) in memory and retrieval work.

This implementation intentionally uses cursor pagination and a strict product cap.
Streaming Admin bulk exports are a future optimization for large catalogs; do not
raise the cap to a large catalog without measuring memory, sync duration, API
throttling, and latency. Initial pilots should stay at 100–500 products.

Generated snapshots and embeddings are gitignored. Old generations and cached
vectors accumulate for rollback. An operator can prune them during maintenance
with API/worker stopped; retain `current.json`'s target and any rollback target.
Automatic garbage collection and an approximate/vector-service migration remain
future capacity work. Do not delete snapshots while API workers load them.

Measure MongoDB storage, embedding cache size, queue age, failed jobs, last sync,
worker/model RAM, and search latency before expanding scope. No store validation
has occurred until real credentials and live product smoke tests are run.

## Validation

```sh
# from repository root
backend/.venv/bin/python -m pytest backend/tests/test_shopify.py -q
# from frontend
npx tsc --noEmit
```

With a development store, verify create/edit/delete/unpublish and collection
membership changes; duplicate webhook delivery; worker restart; upstream timeout;
and semantic results for your own terminology. The encoder was trained on Amazon
ESCI and needs store-specific relevance assessment.

Official references: [Storefront setup](https://shopify.dev/docs/storefronts/headless/building-with-the-storefront-api),
[webhook verification](https://shopify.dev/docs/apps/build/events/verify-deliveries),
[reconciliation](https://shopify.dev/docs/apps/build/webhooks).
