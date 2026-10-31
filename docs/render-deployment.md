# Render backend deployment

`GET /healthz` (alias `/api/health/live`) is a public lightweight liveness ping.
It always returns HTTP 200 while the API process responds, even during model
startup. It never calls MongoDB or runs inference. `/api/health` remains the
readiness endpoint and returns 503 until search is available; Render uses that
endpoint to avoid publishing a broken deployment.

## Prerequisites

Export the existing encoder and reranker with
`python scripts/export_deploy_models.py /tmp/search-models.tar.gz` from `backend`.
The artifact contains only inference model files and an Atlas generation binding
verified against a ready vector manifest. It excludes credentials and datasets.
Host this archive at an HTTPS download URL; set `MODEL_ARTIFACT_URL` and its
`MODEL_ARTIFACT_SHA256` in Render. The build verifies the archive checksum.

The binding validates the encoder file contents and catalog hash, so deployment
can reuse the existing Atlas vector generation across paths and timestamps.
If either changes, export a newly indexed generation instead.

## Deploy

Connect the GitHub repository in Render and create a Blueprint using the root
`render.yaml`. Review the selected instance and its cost before creating it;
no paid plan is selected in source. The two PyTorch models need benchmarking;
start with an instance with sufficient RAM (4 GB is an initial estimate).

Set the requested secrets and model artifact variables in Render. Add any
optional SerpApi/Shopify secrets separately if those features are enabled. Allow
Render outbound IPs in Atlas network access. Add the deployed website origin
to `FRONTEND_ORIGINS` and configure Clerk for that domain.

The start command binds to `0.0.0.0:$PORT` with one worker to avoid duplicating
model memory. Readiness must return 200 before considering the service working.

## Eight-minute external ping

Once a public Render URL exists, configure an external HTTP monitor or hosted
scheduler to GET `https://<service>.onrender.com/healthz` every 480 seconds.
Use a 30-second timeout and alert on repeated errors. Run this outside Render:
a timer inside a sleeping service cannot wake it. No external monitor has been
created yet; it needs your deployed URL and monitor account.

Render free services can sleep after 15 minutes without inbound traffic and
are subject to monthly usage limits. Pings do not increase RAM, fix errors, or
guarantee uptime. Render's own readiness checks are separate from this monitor.
