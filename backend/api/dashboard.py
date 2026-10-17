"""Build the catalog summary shown on the dashboard."""

from datetime import datetime, timezone
from src.data.catalog import load_products, COLLECTION


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
    return {
        "products": products[:100],
        "displayedProductCount": min(100, len(products)),
        "categories": categories,
        "productCount": len(products),
        "averageRating": average_rating,
        "ratedProductCount": len(rated_products),
        "totalStock": (sum(item["stock"] for item in products)
                       if products and all(isinstance(item.get("stock"), (int, float))
                                           for item in products) else None),
        "sources": {
            "catalog": f"MongoDB/{COLLECTION}",
        },
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }

