import json
import os
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, "..", "data", "products.json")
    output_dir = os.path.join(base_dir, "index_store")
    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading products from {data_path}...")
    with open(data_path, "r", encoding="utf-8") as f:
        products = json.load(f)

    print(f"Loaded {len(products)} products.")

    # Convert products to searchable text strings
    product_texts = []
    metadata = []
    for prod in products:
        title = prod.get("title", "")
        category = prod.get("category", "")
        description = prod.get("description", "")
        attributes = ", ".join(prod.get("attributes", []))
        
        text_repr = f"Title: {title} | Category: {category} | Description: {description} | Attributes: {attributes}"
        product_texts.append(text_repr)
        metadata.append(prod)

    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    print(f"Loading model: {model_name}...")
    model = SentenceTransformer(model_name)

    print("Generating embeddings...")
    embeddings = model.encode(product_texts, convert_to_numpy=True, show_progress_bar=False)
    embeddings = embeddings.astype(np.float32)

    # Normalize L2 for Cosine Similarity via Inner Product (IP)
    faiss.normalize_L2(embeddings)
    dimension = embeddings.shape[1]

    print(f"Building FAISS IndexFlatIP with dimension={dimension}...")
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    index_file = os.path.join(output_dir, "faiss_index.bin")
    meta_file = os.path.join(output_dir, "products_meta.json")

    faiss.write_index(index, index_file)
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Successfully built index with {index.ntotal} products, dimension={dimension}")
    print(f"Index saved to: {index_file}")
    print(f"Metadata saved to: {meta_file}")

if __name__ == "__main__":
    main()
