from typing import Any, Dict, List, Tuple

REQUIRED_FIELDS = ["id", "title", "description", "category", "price"]

def validate_catalog(products: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
    """
    Validates catalog integrity:
    - Checks for required fields
    - Detects duplicate IDs
    - Analyzes missing or empty critical fields
    - Verifies numeric fields (e.g. price >= 0)
    """
    total_count = len(products)
    if total_count == 0:
        return False, {"error": "Catalog is empty"}

    seen_ids = set()
    duplicate_ids = []
    missing_fields_summary = {field: 0 for field in REQUIRED_FIELDS}
    invalid_price_count = 0

    for item in products:
        item_id = item.get("id")
        if item_id in seen_ids:
            duplicate_ids.append(item_id)
        seen_ids.add(item_id)

        for field in REQUIRED_FIELDS:
            val = item.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing_fields_summary[field] += 1

        price = item.get("price")
        if price is None or not isinstance(price, (int, float)) or price < 0:
            invalid_price_count += 1

    is_valid = (
        len(duplicate_ids) == 0
        and missing_fields_summary["title"] == 0
        and missing_fields_summary["category"] == 0
        and invalid_price_count == 0
    )

    report = {
        "total_records": total_count,
        "unique_ids": len(seen_ids),
        "duplicate_ids": duplicate_ids,
        "missing_fields": missing_fields_summary,
        "invalid_prices": invalid_price_count,
        "is_valid": is_valid,
    }

    return is_valid, report


if __name__ == "__main__":
    from src.data.load_data import load_raw_products
    raw = load_raw_products()
    valid, report = validate_catalog(raw)
    print(f"Validation passed: {valid}")
    print("Catalog report:", report)
