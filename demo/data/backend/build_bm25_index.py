import json
import os
from app.bm25 import BM25Okapi

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, "..", "data", "products.json")
    output_dir = os.path.join(base_dir, "index_store")
    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading products for BM25 indexing from {data_path}...")
    with open(data_path, "r", encoding="utf-8") as f:
        products = json.load(f)

    bm25 = BM25Okapi()
    bm25.fit(products)

    index_file = os.path.join(output_dir, "bm25_index.pkl")
    bm25.save(index_file)

    print(f"Successfully built BM25 index for {len(products)} products.")
    print(f"BM25 index saved to: {index_file}")

if __name__ == "__main__":
    main()
