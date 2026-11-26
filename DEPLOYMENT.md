# Production deployment

The code is prepared for authenticated deployment. Production hosting and Clerk
activation are pending because no production domain has been chosen.

## Runtime and build

Use Node.js 20.9+ for the frontend and Python 3.10+ for the backend. Install the
frontend with `npm ci`, then run `npm run build` and `npm run start` in `frontend/`.
Install backend dependencies with `python -m pip install -r requirements.txt`
from `backend/`. Run `uvicorn api.main:app --host 0.0.0.0 --port 8000` behind an
HTTPS reverse proxy or managed host. The local Python launcher binds only to
127.0.0.1; use the Uvicorn command for container hosting.

Provision MongoDB, import the catalog, and install the search/reranking models
using the backend README. Keep API health checks public so hosting can monitor
`/api/health`; 503 indicates initialization or failure, not an auth error.

## Clerk and domain

1. Choose a production domain you control and a frontend/API hosting service.
2. From the frontend folder, run `npx -y clerk@latest deploy` in your terminal.
   Complete Clerk's domain, DNS, and production instance setup. Verify with
   `npx -y clerk@latest deploy status --mode agent`.
3. Configure production Google/GitHub OAuth credentials and callback URLs in
   Clerk if using those login methods. Keep phone signup/sign-in disabled.
4. Set production environment values in the hosting provider's secret settings.
   Never place development keys, secret keys, or `.env.local` in Git.

Frontend environment (set before build):

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`: production publishable key.
- `CLERK_SECRET_KEY`: production secret key, server-only.
- `NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in` and
  `NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up`.
- Both `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` and
  `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL`: `/dashboard`.
- `NEXT_PUBLIC_API_URL`: HTTPS origin of your Python API.

Backend environment:

- `CLERK_ISSUER_URL`: exact Clerk session issuer from the production OpenID
  configuration. With the Vercel Clerk proxy, use the production app URL followed
  by `/__clerk`. With direct access, use the Clerk Frontend API URL.
- `CLERK_JWKS_URL`: optional trusted HTTPS signing-key endpoint for the same
  Clerk instance. By default the backend appends `/.well-known/jwks.json` to
  the configured issuer.
- `FRONTEND_ORIGINS`: comma-separated exact frontend origins, e.g.
  `https://example.com,https://www.example.com`. These control CORS and JWT `azp`
  verification. Do not use `*`.
- Configure database, model, and optional SerpApi values from `backend/.env.example`.
  The Python API only needs Clerk's public JWKS; it does not need a secret key.

## Release checks

- Run `npm audit`, `npm test`, and `npm run build` in `frontend/`.
- Run `python -m pytest tests/test_auth.py tests/test_search_api.py
  tests/test_shopping_api.py tests/test_candidate_ranking.py
  tests/test_review_followups.py` in `backend/` (one command).
- Signed-out requests must not reveal dashboard/search pages. API requests
  without bearer tokens must return 401; health checks remain public.
- Sign in with a real test account and confirm catalog and shopping searches,
  account management, and sign-out work against the production API.
- Production users are separate from development users. Create a production
  test account after enabling the production instance.

## Scheduled price checks

The normal FastAPI lifespan starts a single local alert worker by default. It
runs only for alerts users explicitly enable and uses persisted due-time leases,
so multiple backend processes do not immediately check the same alert. Keep a
backend process running for automatic checks. A suspended laptop or sleeping
host will check overdue alerts after it resumes.

- `PRICE_ALERTS_ENABLED=1` enables the lifespan worker; set `0` to use only an
  external scheduler. It defaults to `1`.
- `PRICE_ALERT_INTERVAL_SECONDS=21600` sets the per-alert interval (six hours).
  Values below 3600 are clamped to one hour.
- For cron or a managed host scheduler, run
  `python scripts/check_price_alerts.py` from `backend/` every few minutes with
  the backend environment. It processes at most 100 due alerts per invocation.
  There is no public unauthenticated worker-trigger endpoint.
- Google Shopping checks need the existing backend-only `SERPAPI_API_KEY` and
  stable region/language/location settings. Changing the market makes old alerts
  unavailable until recreated. Calls use provider quota and normal request
  timeouts; unsupported offers never silently match by title alone.
- Google Shopping alert checks have their own daily SerpApi budgets, separate
  from the per-minute search limits: `PRICE_ALERT_SHOPPING_CHECKS_PER_USER_PER_DAY=10`
  per user and `PRICE_ALERT_SHOPPING_CHECKS_PER_DAY=200` across all users (UTC
  days, shared through MongoDB). When a budget is used up, the alert shows as
  unavailable and retries at its next scheduled check. `0` pauses these checks.
  Catalog alerts do not use SerpApi and are not limited.
- Notifications are in-app only. This implementation does not send emails or SMS.
- Include `python -m pytest tests/test_account_features.py tests/test_price_alerts.py`
  in release checks. Tests use mocks and never consume real provider quota.

## Search throttling and alert capacity

Search API calls use shared MongoDB fixed-window counters per Clerk user and
source: 30 catalog searches and 5 Google Shopping searches per minute by default.
Set `CATALOG_SEARCHES_PER_MINUTE` and `SHOPPING_SEARCHES_PER_MINUTE` to positive
integers to adjust them. Rejected calls return HTTP 429 with `Retry-After`.
Unavailable counter storage returns 503 without running the expensive search.
The `search_rate_limits` collection requires permission to create a TTL index;
expired records are removed automatically. Concurrent workers share the counters.

The 50-active-alert limit is enforced by a unique partial index on
`price_alerts(user_id, active_slot)`. Existing enabled alerts without slots count
against capacity; new and resumed alerts reserve unique slots. Pausing/deleting
an alert frees its slot. If legacy data already exceeds 50 active alerts, pause
or remove enough alerts before creating or resuming another.

Internal failure details stay in server logs. Public health and search responses
return safe retryable messages. Vector caches with mismatched row counts,
nonfinite/unnormalized values, or a wrong model dimension are rebuilt.

## Vultr automatic backend releases

The Vultr timer checks `main` every three minutes. It uses the public GitHub API
to require a successful push run of `python-app.yml` for the exact commit, then
switches the existing checkout and restarts `product-search-api.service`.
The local `/api/health` endpoint must report ready within 120 seconds after
the restart. The updater restores the previous revision on failure, checks its
health, and holds the failed revision until `main` advances. Its recovery state
also survives an interrupted deployment.

The updater retains the existing environment, models and Python runtime.
A requirements change needs a manual release with a compatible runtime to set
a new rollback baseline. The timer keeps the checkout pinned to a tested
commit and runs Git as `productsearch`.

Install the deployment files from a CI-tested checkout as root:

```sh
install -D -m 0755 backend/scripts/deploy_vultr.py /usr/local/libexec/product-search-deploy.py
install -m 0644 deploy/vultr/product-search-deploy.service deploy/vultr/product-search-deploy.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now product-search-deploy.timer
systemctl start product-search-deploy.service
```

Use `journalctl -u product-search-deploy.service` to review releases and
rollbacks, and `systemctl list-timers product-search-deploy.timer` to check
the next run.
