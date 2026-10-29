# Shopify semantic search implementation plan

Status: implemented bounded single-store integration; see [setup and implementation limits](shopify-setup.md). The original target design below used FAISS; the working tree now uses Atlas for Amazon, so Shopify uses a separate NumPy cosine index. Bulk exports, automatic token renewal, and automatic index garbage collection remain deferred capacity work.

## 1. Goal and initial scope

Use one connected Shopify store as a product source while retaining the existing
MiniLM + keyword retrieval + reranker pipeline. Start with one selected collection
of 100–500 products. Keep the existing Amazon and SerpApi sources working.

Shopify owns the product catalog. MongoDB stores a compact search copy. FAISS
stores derived vectors on disk. Current selling details come from Shopify for
the products displayed to a customer.

Initial scope: product-level search, listing cards, and links to the Shopify
online store. Cart, checkout, multi-store onboarding, and variant-level search
are later features. The initial store must have a working online storefront.

## 2. Proposed folder structure

Paths below are relative to the repository root. [new] means proposed;
[edit] means an existing file requires changes. Unmarked files already exist.

```text
Semantic-Product-Search-Engine/
├── docs/
│   ├── shopify-implementation-plan.md       [new] this plan
│   └── shopify-setup.md                     [new] setup and operating guide
├── backend/
│   ├── .env.example                        [edit/create] configuration names only
│   ├── api/
│   │   ├── main.py                         [edit] source routing and router registration
│   │   ├── search_service.py               [edit] source-specific engine lifecycle
│   │   ├── shopify_routes.py               [new] webhook and source status routes
│   │   └── shopify_service.py              [new] rank, hydrate, and format results
│   ├── src/
│   │   ├── integrations/
│   │   │   ├── __init__.py                  [new]
│   │   │   └── shopify/
│   │   │       ├── __init__.py              [new]
│   │   │       ├── config.py                [new] validated settings
│   │   │       ├── client.py                [new] GraphQL transport, auth, retries
│   │   │       ├── queries.py               [new] Admin and Storefront queries
│   │   │       ├── mapper.py                [new] Shopify → search record
│   │   │       ├── sync.py                  [new] initial and reconciliation imports
│   │   │       ├── webhooks.py              [new] signature and delivery validation
│   │   │       └── hydration.py             [new] batched selling details and TTL cache
│   │   ├── data/
│   │   │   ├── db.py
│   │   │   ├── catalog.py                  [edit] source-aware catalog access
│   │   │   └── shopify_repository.py        [new] products, sync state, durable jobs
│   │   ├── search/
│   │   │   ├── product_search.py            [edit if needed] source-neutral IDs/metadata
│   │   │   └── index_manager.py             [new] build and publish index generations
│   │   └── semantic/
│   │       ├── vector_search.py             [edit] assemble index from cached vectors
│   │       └── embedding_cache.py           [new] reuse unchanged product vectors
│   ├── scripts/
│   │   ├── sync_shopify.py                  [new] initial/reconcile sync CLI
│   │   └── run_shopify_worker.py            [new] durable jobs and index rebuilds
│   ├── indexes/
│   │   └── shopify/                         [generated, gitignored]
│   │       └── <store-key>/
│   │           ├── embeddings/             reusable vectors, keyed by text/model hash
│   │           ├── generations/<version>/  complete index and ID mapping
│   │           └── current.json            published generation pointer
│   └── tests/
│       ├── test_shopify_mapping.py          [new]
│       ├── test_shopify_sync.py             [new]
│       ├── test_shopify_webhooks.py         [new]
│       ├── test_shopify_index.py            [new]
│       └── test_shopify_search.py           [new]
└── frontend/src/
    ├── lib/
    │   ├── api.ts                          [edit] Shopify source and response handling
    │   └── types.ts                        [edit] source, availability, freshness
    └── app/search/page.tsx                  [edit] source selector and product cards
```

Do not create empty placeholder files ahead of their implementation phase. Reuse
the existing HTTP and MongoDB libraries; Redis/Celery are unnecessary initially.
Read frontend/AGENTS.md before implementing frontend changes.

## 3. Storage design and size control

### shopify_products

One document per product, uniquely indexed by (shop_domain, product_gid).
Use a stable string search ID that includes both store and product identity.

```json
{
  "id": "shopify:example.myshopify.com:123",
  "shop_domain": "example.myshopify.com",
  "product_gid": "gid://shopify/Product/123",
  "title": "Blue running shoes",
  "description": "Plain-text description used for search",
  "category": "Shoes",
  "brand": "Example",
  "tags": ["running", "blue"],
  "options": {"Size": ["7", "8"], "Color": ["Blue"]},
  "representation_text": "Canonical searchable text",
  "text_hash": "sha256 of canonical searchable text",
  "eligible": true,
  "shopify_updated_at": "ISO timestamp",
  "synced_at": "ISO timestamp",
  "sync_generation": "import identifier"
}
```

Store bounded, cleaned text and relevant options, not raw Shopify responses,
image binaries, complete variant trees, orders, or customer data. Hydrate image
and product URLs with the selling details. Set deterministic text-length limits
and record truncation so unusually large descriptions do not inflate storage.

Additional collections:

| Collection | Responsibility | Retention/indexes |
| --- | --- | --- |
| shopify_sync_state | Cursor, scope, last success, reconciliation generation | Unique store key |
| shopify_jobs | Durable webhook/reconcile work and retries | Unique delivery key; status/next-attempt index; TTL on completed jobs |
| catalog_manifests | Ready search generation, count, source, model fingerprint | Separate Shopify manifest; retain Amazon compatibility |

Vector storage is separate from MongoDB. Approximate raw float32 vector size is
product count × embedding dimension × 4 bytes. At 384 dimensions, 100,000 vectors
need about 154 MB before index, metadata, and process overhead. Measure actual
MongoDB BSON/index size, RAM, and disk after the pilot rather than promise a fixed
capacity. Background publication temporarily needs room for old and new indexes.

## 4. Shopify connection and configuration

Configure a single-store app with only the catalog read permissions required by
the chosen queries. Configure Storefront access and publish the selected products
to its channel. Active Admin products are not automatically customer-visible.
Confirm Storefront visibility during synchronization and again during hydration.

Proposed settings (backend only):

```dotenv
SHOPIFY_ENABLED=false
SHOPIFY_SHOP_DOMAIN=example.myshopify.com
SHOPIFY_API_VERSION=<supported-pinned-version>
SHOPIFY_ADMIN_ACCESS_TOKEN=<secret>
SHOPIFY_STOREFRONT_PRIVATE_TOKEN=<secret>
SHOPIFY_WEBHOOK_SECRET=<app-client-secret>
SHOPIFY_COLLECTION_GID=<selected-collection>
SHOPIFY_SYNC_MAX_PRODUCTS=500
SHOPIFY_HYDRATION_TTL_SECONDS=60
```

Choose the supported authentication/token issuance method for the store's app
setup; handle token refresh if that method issues expiring credentials. Never put
Admin or private Storefront tokens in NEXT_PUBLIC variables. Validate the store
domain against configuration, use explicit timeouts, inspect GraphQL errors even
on HTTP 200, and back off on throttling. Use bounded retries and log no secrets.

## 5. Data flows

### Initial import and reconciliation

1. Validate credentials, collection scope, channel access, and configured cap.
2. Fetch scoped products with cursor pagination for the pilot. Stream GraphQL
   bulk output for a large catalog instead of loading the entire export in RAM.
3. Map and upsert compact documents; repeated imports must be idempotent.
4. Record a generation and checkpoint only successfully persisted work.
5. Remove products no longer in scope only after a complete authoritative scan.
   A failed, partial, or capped scan must never trigger blanket deletion.
6. Queue one coalesced index rebuild for changed searchable data.

Subscribe before the first full scan and reconcile afterward to close the
scan/webhook race. Check collection membership changes and channel publication in
periodic reconciliation, not only product-update events.

### Search request

1. Frontend requests GET /api/search?q=...&source=shopify under existing session auth.
2. Search the published Shopify FAISS and keyword indexes and rerank candidates.
3. Batch-fetch Storefront details for a bounded candidate set, retaining rank order.
4. Suppress null/unpublished products; refill from a bounded candidate pool.
5. Return current price range, currency, availability, image, and online-store URL.

Use a short-lived, bounded cache keyed by store, product, and market/language
context. Version one uses one configured market/currency. Return a price range
or clearly labelled starting price; do not present one variant's price as the
price of every variant. Cache freshness must be explicit. On upstream failure,
show unavailable selling details or a controlled error, not fabricated values.
Do not offer local price/stock filters until their accuracy strategy is defined:
hydrating only the top results cannot implement complete catalog-wide filtering.

### Updates and deletions

POST /api/shopify/webhooks verifies HMAC against raw bytes and the configured
shop, then durably stores the job before acknowledging. It uses webhook auth,
not the customer session dependency. Duplicate delivery IDs are harmless.
Return a retryable failure if durable enqueue fails.

A separate worker claims jobs using expiring leases, refetches the authoritative
product state, checks scope/visibility, and updates or removes records. Treat
out-of-order events as hints to reconcile current state. Retry transient failures
with bounded exponential backoff; retain failed jobs for diagnosis and replay.
Product deletion/unpublication invalidates detail caches and prevents old index
entries from appearing by checking current eligibility for candidate IDs.

## 6. Search index lifecycle: required backend change

Current api/search_service.py keys its entire engine and vector cache to the
catalog manifest hash. src/data/catalog.py also assumes a single Amazon catalog.
Simply inserting Shopify records would not safely support continuous updates.

Introduce source/store-specific engine state and manifests. Cache each vector by
product identity, canonical text hash, and model fingerprint. A changed title or
description generates a new vector; unchanged text reuses the existing vector.
Price-only changes do not require embeddings.

For the first implementation, rebuild the FAISS layout and keyword index in
batches using cached vectors. This is incremental embedding generation, not a
fully incremental FAISS index. Rebuilding layout still costs O(catalog size).

Build against a consistent product snapshot: stage records and vectors, validate
the ID order/count/hash and source revision, write a complete generation, then
atomically publish its pointer. If source data changes during the build, queue
another generation. Keep the previous ready engine serving during the build.
The worker writes index files; each API process detects and loads the published
generation. All processes need the same persistent index volume. Failed builds
retain the previous pointer. Garbage-collect unused generations and vectors only
after readers no longer need them; preserve a rollback generation.

Share model instances and serialize model work with the existing model lock
where necessary. Benchmark contention and memory before running builds beside
live traffic. A worker process has its own model memory; budget for that too.

## 7. API and frontend contract

| Interface | Planned behavior |
| --- | --- |
| GET /api/search?source=shopify | Existing search envelope plus Shopify results |
| GET /api/shopify/status | Session-protected readiness, count, last successful sync, sanitized failure |
| POST /api/shopify/webhooks | Signed Shopify event ingress; no browser dependency |
| sync_shopify.py | Operator-only initial/reconcile command; no public import endpoint |

Maintain source=mongo and source=serpapi. Shopify readiness must not make the
existing source unhealthy. Report Shopify disabled, initial sync, ready, and
degraded states distinctly. No request should build an index synchronously.

Extend SearchProduct with optional source, availableForSale, detailsUpdatedAt,
and detailsStatus fields. Reuse existing imageUrl, url, currency, and priceLabel.
Show a Shopify option, genuine images, currency-aware prices, stock availability,
and a product link. Avoid deriving inventory quantity from a boolean availability.
Treat links as validated external HTTPS URLs. Empty, unavailable, and syncing
states need clear UI messages. The initial dashboard stays on its current source.

## 8. Implementation order and completion gates

| Phase | Deliverable | Completion gate |
| --- | --- | --- |
| 1. Foundation | Config, clients, queries, mapper, repository indexes | One published product maps correctly; secrets stay backend-only |
| 2. Pilot import | Scoped CLI sync, checkpoints, compact documents | 100–500 products import; rerun adds no duplicates; failed scan deletes nothing |
| 3. Search index | Source isolation, embedding reuse, generation publication | Restart reuses vectors; one text edit re-encodes only that product; searches survive builds |
| 4. Search API | Shopify source, batched hydration, TTL cache | Natural-language queries return valid product links and correct currency/price labels |
| 5. Frontend | Source selector and result/status states | Product cards work on mobile and desktop; existing sources still work |
| 6. Continuous sync | Signed ingress, durable worker, retries, reconciliation | Create/edit/delete/unpublish reflected; duplicate and reordered deliveries safe |
| 7. Rollout | Setup guide, scheduling, metrics, controlled scope increase | Pilot relevance and resource measurements justify the next product cap |

The first reviewable milestone is phases 1–5 with manual sync. Automatic syncing
is complete only after phase 6; label the manual-sync pilot accordingly.

## 9. Verification and operations

- Unit tests: mapping missing fields, HTML cleanup, deterministic hashes, stable
  IDs, and option bounds.
- Sync tests: pagination, throttling, GraphQL partial errors, retry checkpoints,
  duplicate imports, scope changes, and failed/capped scan deletion protection.
- Webhook tests: correct/incorrect raw-body signatures, wrong shop, duplicates,
  out-of-order events, durable enqueue failure, and worker restart recovery.
- Index tests: embedding reuse, model fingerprint invalidation, corrupt/failed
  generation, stable ID mapping, concurrent updates, deletion filtering, rollback.
- Search tests: batched hydration, missing products, stale/failed cache entries,
  starting-price/range labels, bounded refills, and source isolation.
- Store smoke test: create, rename, unpublish, and delete a test product; verify
  results after sync. Compare representative semantic queries against expected
  matches because the existing encoder was fine-tuned on Amazon ESCI data.

Track sync lag, queue depth/oldest job age, failed jobs, embedding time, index
build duration, Shopify errors, cache hits, search p95, and process memory.
Proposed pilot goals: edits visible within five minutes with a healthy worker;
no full re-encoding for metadata-only edits; no downtime during publication.
Measure baseline latency before choosing a numeric latency target.

Run the API and worker as separate supervised processes. Schedule reconciliation
hourly initially, with a periodic complete scope scan for deletion/publication
drift. Persist MongoDB and index files, configure a public HTTPS webhook endpoint,
and document credential renewal, failed-job replay, rebuild, and rollback commands.
Disable Shopify through its feature flag if needed without interrupting Amazon.

## 10. Decisions needed before implementation

Store domain and app access; selected collection; initial product cap; storefront
publication channel; default market/currency; hosting for webhook ingress and the
worker. Credentials should be entered into backend configuration, not this plan.
For a much larger catalog, benchmark the current in-memory FAISS/BM25 approach
before choosing a database/vector service migration.

## Official references

- [GraphQL bulk imports](https://shopify.dev/docs/apps/build/apis/graphql-admin/bulk-operations/queries)
- [Headless channel and Storefront access](https://shopify.dev/docs/storefronts/headless/building-with-the-storefront-api)
- [Storefront product fields](https://shopify.dev/docs/api/storefront/latest/objects/product)
- [Webhooks, duplicate deliveries, and reconciliation](https://shopify.dev/docs/apps/build/webhooks)
- [Webhook signature verification](https://shopify.dev/docs/apps/build/events/verify-deliveries)
