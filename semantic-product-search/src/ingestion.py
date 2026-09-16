import requests
import json
from pathlib import Path


API_URL = "https://dummyjson.com/products?limit=0"

OUTPUT_PATH = Path("data/raw/products.json")


def fetch_products():
    print("Fetching products from API...")

    response = requests.get(API_URL)

    response.raise_for_status()

    data = response.json()

    return data["products"]


def save_products(products):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(products, file, indent=2, ensure_ascii=False)

    print(f"Saved {len(products)} products")
    print(f"Location: {OUTPUT_PATH}")


def main():
    products = fetch_products()

    save_products(products)


if __name__ == "__main__":
    main()