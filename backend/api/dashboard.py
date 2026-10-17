"""Build the catalog summary shown on the dashboard."""

from datetime import datetime, timezone
from math import isfinite
from src.data.catalog import load_products, COLLECTION


def stock_value(value):
    """Normalize numeric stock while retaining unknown and invalid values."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if isfinite(number) and number >= 0 else None
    except (ValueError, TypeError):
        return None


def dashboard_data():
    products = load_products()
    if not isinstance(products, list):
        raise FileNotFoundError(
            "catalog could not be loaded from MongoDB."
        )

    categories = sorted({item.get("category") for item in products if item.get("category")})
    rated_products = [item for item in products if isinstance(item.get("rating"), (int, float))]
    average_rating = (
        sum(item["rating"] for item in rated_products) / len(rated_products)
        if rated_products else None
    )
    stocks = [stock_value(item.get("stock")) for item in products]
    return {
        "products": products[:100],
        "displayedProductCount": min(100, len(products)),
        "categories": categories,
        "productCount": len(products),
        "averageRating": average_rating,
        "ratedProductCount": len(rated_products),
        "totalStock": sum(stocks) if stocks and all(value is not None for value in stocks) else None,
        "sources": {
            "catalog": f"MongoDB/{COLLECTION}",
        },
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }

