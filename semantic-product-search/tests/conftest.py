"""
conftest.py — Shared pytest fixtures for Semantic Product Search Engine tests.

Fixtures defined here are auto-discovered by pytest and available to ALL test
files without any explicit import.
"""
import pytest


# ---------------------------------------------------------------------------
# Shared product catalog fixtures
# ---------------------------------------------------------------------------

SAMPLE_PRODUCTS = [
    {
        "id": 1,
        "title": "Wireless Noise Cancelling Headphones",
        "description": "Over-ear Bluetooth headphones with active noise cancellation.",
        "category": "electronics",
        "brand": "AudioTech",
        "price": 79.99,
        "rating": 4.5,
        "stock": 25,
        "tags": ["audio", "bluetooth", "electronics"],
        "thumbnail": "",
        "images": [],
        "representation_text": (
            "[Category] electronics | [Brand] AudioTech | "
            "[Title] Wireless Noise Cancelling Headphones | "
            "[Details] Over-ear Bluetooth headphones with active noise cancellation. | "
            "[Tags] audio, bluetooth, electronics"
        ),
    },
    {
        "id": 2,
        "title": "Leather Running Shoes",
        "description": "Comfortable sneakers for athletics and jogging.",
        "category": "footwear",
        "brand": "Speedy",
        "price": 59.99,
        "rating": 4.2,
        "stock": 60,
        "tags": ["shoes", "sports", "running"],
        "thumbnail": "",
        "images": [],
        "representation_text": (
            "[Category] footwear | [Brand] Speedy | "
            "[Title] Leather Running Shoes | "
            "[Details] Comfortable sneakers for athletics and jogging. | "
            "[Tags] shoes, sports, running"
        ),
    },
    {
        "id": 3,
        "title": "Smart Watch Fitness Tracker",
        "description": "Heart rate monitor, step counter, waterproof smartwatch.",
        "category": "electronics",
        "brand": "FitTech",
        "price": 129.99,
        "rating": 4.7,
        "stock": 15,
        "tags": ["smartwatch", "fitness", "electronics"],
        "thumbnail": "",
        "images": [],
        "representation_text": (
            "[Category] electronics | [Brand] FitTech | "
            "[Title] Smart Watch Fitness Tracker | "
            "[Details] Heart rate monitor, step counter, waterproof smartwatch. | "
            "[Tags] smartwatch, fitness, electronics"
        ),
    },
    {
        "id": 4,
        "title": "Winter Parka Jacket",
        "description": "Heavy insulated coat for extreme cold weather.",
        "category": "clothing",
        "brand": "NorthTrail",
        "price": 199.99,
        "rating": 4.8,
        "stock": 10,
        "tags": ["winter", "jacket", "warm"],
        "thumbnail": "",
        "images": [],
        "representation_text": (
            "[Category] clothing | [Brand] NorthTrail | "
            "[Title] Winter Parka Jacket | "
            "[Details] Heavy insulated coat for extreme cold weather. | "
            "[Tags] winter, jacket, warm"
        ),
    },
    {
        "id": 5,
        "title": "Stainless Steel Water Bottle",
        "description": "Vacuum insulated bottle keeps drinks cold for 24 hours.",
        "category": "kitchen",
        "brand": "HydroMax",
        "price": 29.99,
        "rating": 4.6,
        "stock": 100,
        "tags": ["bottle", "kitchen", "hydration"],
        "thumbnail": "",
        "images": [],
        "representation_text": (
            "[Category] kitchen | [Brand] HydroMax | "
            "[Title] Stainless Steel Water Bottle | "
            "[Details] Vacuum insulated bottle keeps drinks cold for 24 hours. | "
            "[Tags] bottle, kitchen, hydration"
        ),
    },
]


@pytest.fixture(scope="session")
def sample_products():
    """
    A small, self-contained product catalog used across all test modules.
    Session-scoped so it is created once per test run.
    """
    return SAMPLE_PRODUCTS


@pytest.fixture(scope="session")
def electronics_products(sample_products):
    """Subset of sample_products filtered to electronics category."""
    return [p for p in sample_products if p["category"] == "electronics"]


# ---------------------------------------------------------------------------
# BM25 fixture — fitted on sample catalog
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def fitted_bm25(sample_products):
    """
    A BM25Okapi index pre-fitted on the sample product catalog.
    Session-scoped so the model is built once and reused across tests.
    """
    from src.baseline.bm25 import BM25Okapi
    return BM25Okapi().fit(sample_products)


# ---------------------------------------------------------------------------
# Semantic search fixture — fitted on sample catalog
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def fitted_semantic(sample_products):
    """
    A SemanticVectorSearch engine pre-fitted on the sample product catalog.
    Session-scoped so the heavy embedding model is loaded only once.
    """
    from src.semantic.vector_search import SemanticVectorSearch
    engine = SemanticVectorSearch()
    engine.fit(sample_products)
    return engine


# ---------------------------------------------------------------------------
# IR evaluation helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def ir_metrics():
    """
    Returns a namespace of IR metric functions for use in metric unit tests.
    """
    from src.baseline.evaluate_baseline import (
        precision_at_k,
        recall_at_k,
        recall_at_k,
        ndcg_at_k,
        reciprocal_rank,
        average_precision,
    )
    return {
        "precision_at_k": precision_at_k,
        "recall_at_k": recall_at_k,
        "ndcg_at_k": ndcg_at_k,
        "reciprocal_rank": reciprocal_rank,
        "average_precision": average_precision,
    }
