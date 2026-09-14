"""Export PCA-reduced 3D coordinates from FAISS embeddings for Three.js visualization."""
import json
import os
import numpy as np
import faiss
from sklearn.decomposition import PCA

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    index_file = os.path.join(base_dir, "index_store", "faiss_index.bin")
    meta_file = os.path.join(base_dir, "index_store", "products_meta.json")
    output_file = os.path.join(base_dir, "..", "data", "pca_embeddings.json")

    index = faiss.read_index(index_file)
    n = index.ntotal
    d = index.d

    # Reconstruct all vectors from the FAISS index
    embeddings = np.zeros((n, d), dtype=np.float32)
    for i in range(n):
        embeddings[i] = index.reconstruct(i)

    with open(meta_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    # PCA reduce to 3 dimensions
    pca = PCA(n_components=3)
    coords_3d = pca.fit_transform(embeddings)

    # Normalize to [-5, 5] range for Three.js scene
    for dim in range(3):
        min_val = coords_3d[:, dim].min()
        max_val = coords_3d[:, dim].max()
        rng = max_val - min_val if max_val != min_val else 1.0
        coords_3d[:, dim] = (coords_3d[:, dim] - min_val) / rng * 10.0 - 5.0

    result = []
    for i in range(n):
        result.append({
            "id": metadata[i]["id"],
            "title": metadata[i]["title"],
            "category": metadata[i]["category"],
            "price": metadata[i]["price"],
            "x": round(float(coords_3d[i][0]), 4),
            "y": round(float(coords_3d[i][1]), 4),
            "z": round(float(coords_3d[i][2]), 4)
        })

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Exported PCA 3D coordinates for {n} products to {output_file}")
    print(f"PCA explained variance ratio: {pca.explained_variance_ratio_}")

if __name__ == "__main__":
    main()
