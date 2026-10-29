"""Private product snapshots, owned exclusively by the verified session subject."""
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from typing import Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from pymongo.errors import PyMongoError

from api.account_store import clean_saved_links, iso
from api.auth import require_session
from src.data.db import get_database

router = APIRouter(prefix="/api/saved-products", tags=["Saved products"])


class ProductSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=500)
    category: Optional[str] = Field(default=None, max_length=200)
    brand: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=10000)
    price: Optional[Union[float, str]] = None
    rating: Optional[Union[float, str]] = None
    reviews: Optional[Union[float, str]] = None
    stock: Optional[Union[float, str]] = None
    attributes: list[str] = Field(default_factory=list, max_length=40)

    @field_validator('price', 'rating', 'reviews', 'stock', mode='before')
    @classmethod
    def bounded_values(cls, value):
        import math
        if isinstance(value, bool):
            raise ValueError('Numeric details cannot be booleans.')
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('Numeric details must be finite.')
        if isinstance(value, str) and len(value) > 200:
            raise ValueError('Product details are too long.')
        return value

    @field_validator('attributes')
    @classmethod
    def bounded_attributes(cls, value):
        if any(len(item) > 500 for item in value):
            raise ValueError('Product attribute is too long.')
        return value

    priceLabel: Optional[str] = Field(default=None, max_length=200)
    currency: Optional[str] = Field(default=None, max_length=10)
    imageUrl: Optional[HttpUrl] = None
    url: Optional[HttpUrl] = None
    merchant: Optional[str] = Field(default=None, max_length=200)


class SaveProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["mongo", "serpapi"]
    identity: str = Field(min_length=1, max_length=2048)
    product: ProductSnapshot


@lru_cache(maxsize=1)
def collection():
    result = get_database()["saved_products"]
    result.create_index([("user_id", 1), ("saved_at", -1), ("_id", 1)])
    return result


def saved_id(user_id, source, identity):
    import json
    return sha256(json.dumps([user_id, source, identity]).encode()).hexdigest()


def public_item(item):
    return {"id": item["_id"], "source": item["source"], "identity": item["identity"],
            "product": item["product"], "savedAt": iso(item["saved_at"])}


def unavailable():
    return HTTPException(503, "Saved products are temporarily unavailable. Please try again.")


@router.get("")
def list_saved(offset: int = Query(0, ge=0, le=100000), session=Depends(require_session)):
    try:
        items = list(collection().find({"user_id": session["sub"]}).sort(
            [("saved_at", -1), ("_id", 1)]).skip(offset).limit(51))
        return {"items": [public_item(item) for item in items[:50]], "hasMore": len(items) > 50}
    except PyMongoError:
        raise unavailable() from None


@router.get("/status")
def saved_status(source: Literal["mongo", "serpapi"], identity: str = Query(min_length=1, max_length=2048),
                 session=Depends(require_session)):
    key = saved_id(session["sub"], source, identity)
    try:
        exists = collection().find_one({"_id": key, "user_id": session["sub"]}, {"_id": 1})
        return {"saved": exists is not None, "id": key}
    except PyMongoError:
        raise unavailable() from None


@router.put("")
def save_product(body: SaveProduct, session=Depends(require_session)):
    key = saved_id(session["sub"], body.source, body.identity)
    try:
        collection().update_one({"_id": key, "user_id": session["sub"]}, {"$setOnInsert": {
            "source": body.source, "identity": body.identity, "user_id": session["sub"],
            "product": body.product.model_dump(mode="json"), "saved_at": datetime.now(timezone.utc),
        }}, upsert=True)
        return {"saved": True, "id": key}
    except PyMongoError:
        raise unavailable() from None


@router.delete("/{item_id}")
def remove_product(item_id: str, session=Depends(require_session)):
    try:
        collection().delete_one({"_id": item_id, "user_id": session["sub"]})
        clean_saved_links(session['sub'], item_id)
        return {"saved": False}
    except PyMongoError:
        raise unavailable() from None
