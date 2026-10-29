"""Signed webhook ingress and session-protected status."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from api.auth import require_session
from api.shopify_service import context, status
from src.integrations.shopify.webhooks import verify, TOPICS
from src.integrations.shopify.hydration import invalidate

router = APIRouter()


@router.get('/api/shopify/status', dependencies=[Depends(require_session)])
def shopify_status():
    try:
        return status()
    except PyMongoError:
        return JSONResponse(status_code=503, content={'error': 'Shopify storage is unavailable.'})


@router.post('/api/shopify/webhooks')
async def webhook(request: Request):
    try:
        settings, repository = context()
    except ValueError:
        return JSONResponse(status_code=503, content={'error': 'Shopify is not configured.'})
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 2_000_000:
            return JSONResponse(status_code=413, content={'error': 'Webhook is too large.'})
    if request.headers.get('x-shopify-shop-domain') != settings.shop or not verify(
            bytes(body), request.headers.get('x-shopify-hmac-sha256'), settings.secret):
        return JSONResponse(status_code=401, content={'error': 'Invalid Shopify signature.'})
    delivery = request.headers.get('x-shopify-webhook-id', '')
    if not delivery or len(delivery) > 200:
        return JSONResponse(status_code=400, content={'error': 'Missing delivery ID.'})
    if request.headers.get('x-shopify-topic') not in TOPICS:
        return {'accepted': True, 'ignored': True}
    try:
        repository.enqueue(delivery)
    except PyMongoError:
        return JSONResponse(status_code=503, content={'error': 'Webhook could not be persisted.'})
    invalidate(settings.shop)
    return {'accepted': True}
