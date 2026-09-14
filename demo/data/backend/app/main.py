import os
import json
import time
from typing import List, Dict, Any, Optional
import numpy as np
import faiss
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from app.bm25 import BM25Okapi

app = FastAPI(
    title="Semantic & Hybrid Product Search API",
    version="2.1.0",
    description="Vector & BM25 Keyword Search Service with Live Weight Tuning Sandbox"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global memory variables
INDEX = None
BM25_INDEX = None
METADATA = []
MODEL = None
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

class SearchFilter(BaseModel):
    category: Optional[str] = None
    max_price: Optional[float] = None

class SearchRequest(BaseModel):
    query: str
    mode: Optional[str] = "semantic"  # semantic, keyword, hybrid
    semanticWeight: Optional[float] = 0.7  # 0.0 to 1.0 (weight for semantic search in hybrid mode)
    topK: Optional[int] = 10
    filters: Optional[SearchFilter] = None

class SearchResultItem(BaseModel):
    rank: int
    score: float
    semScore: float
    kwScore: float
    semanticWeight: float
    id: str
    title: str
    category: str
    price: float
    description: str
    attributes: List[str]

class SearchResponse(BaseModel):
    query: str
    mode: str
    semanticWeight: float
    latencyMs: float
    totalResults: int
    results: List[SearchResultItem]

def load_resources():
    global INDEX, BM25_INDEX, METADATA, MODEL
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_file = os.path.join(base_dir, "index_store", "faiss_index.bin")
    meta_file = os.path.join(base_dir, "index_store", "products_meta.json")
    bm25_file = os.path.join(base_dir, "index_store", "bm25_index.pkl")

    print("Initializing Search Engine Service (Vector & BM25 Sandbox)...")

    if os.path.exists(meta_file):
        with open(meta_file, "r", encoding="utf-8") as f:
            METADATA = json.load(f)
        print(f"Loaded {len(METADATA)} products metadata.")

    if os.path.exists(index_file):
        print(f"Loading FAISS index from {index_file}...")
        INDEX = faiss.read_index(index_file)

    if os.path.exists(bm25_file):
        print(f"Loading BM25 index from {bm25_file}...")
        BM25_INDEX = BM25Okapi.load(bm25_file)
    else:
        if METADATA:
            print("Building in-memory BM25 index...")
            BM25_INDEX = BM25Okapi()
            BM25_INDEX.fit(METADATA)

    try:
        print(f"Loading Embedding Model ({MODEL_NAME})...")
        MODEL = SentenceTransformer(MODEL_NAME)
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Error loading sentence-transformer model: {e}")

@app.on_event("startup")
def startup_event():
    load_resources()

@app.get("/health")
def health_check():
    faiss_loaded = INDEX is not None and INDEX.ntotal > 0
    bm25_loaded = BM25_INDEX is not None
    model_loaded = MODEL is not None
    status = "ok" if (faiss_loaded and bm25_loaded and model_loaded) else "degraded"
    
    return {
        "status": status,
        "indexLoaded": faiss_loaded,
        "bm25Loaded": bm25_loaded,
        "modelLoaded": model_loaded,
        "totalProductsIndexed": INDEX.ntotal if INDEX else len(METADATA),
        "model": MODEL_NAME
    }

@app.get("/api/v1/eval")
def get_evaluation_results():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results_path = os.path.join(base_dir, "..", "data", "eval_results.json")
    if os.path.exists(results_path):
        with open(results_path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        from evaluate import evaluate_search_engine
        return evaluate_search_engine()

@app.post("/api/v1/search", response_model=SearchResponse)
def search_products(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")
    
    if not METADATA:
        raise HTTPException(status_code=503, detail="Catalog metadata not loaded.")

    start_time = time.time()
    mode = (req.mode or "semantic").lower()
    alpha = float(req.semanticWeight if req.semanticWeight is not None else 0.7)
    alpha = max(0.0, min(1.0, alpha))

    # Vector Semantic Scores
    sem_scores = {}
    if INDEX is not None and MODEL is not None:
        query_vector = MODEL.encode([req.query], convert_to_numpy=True).astype(np.float32)
        faiss.normalize_L2(query_vector)
        k_search = min(INDEX.ntotal, 100)
        scores, indices = INDEX.search(query_vector, k_search)
        for idx, score in zip(indices[0], scores[0]):
            if idx >= 0 and idx < len(METADATA):
                sem_scores[idx] = float(score)

    # BM25 Keyword Scores
    bm25_scores = {}
    if BM25_INDEX is not None:
        ranked_bm25 = BM25_INDEX.search(req.query, top_k=len(METADATA))
        max_b_score = ranked_bm25[0][1] if ranked_bm25 else 1.0
        for idx, b_score in ranked_bm25:
            bm25_scores[idx] = float(b_score / max_b_score) if max_b_score > 0 else 0.0

    candidate_results = []

    for idx, prod in enumerate(METADATA):
        # Apply filters
        if req.filters:
            if req.filters.category and req.filters.category.strip() and req.filters.category != "All":
                if prod.get("category", "").lower() != req.filters.category.strip().lower():
                    continue
            if req.filters.max_price is not None and req.filters.max_price > 0:
                if prod.get("price", 0) > req.filters.max_price:
                    continue

        raw_sem = sem_scores.get(idx, 0.0)
        raw_kw = bm25_scores.get(idx, 0.0)

        if mode == "keyword":
            final_score = raw_kw
        elif mode == "hybrid":
            final_score = (alpha * raw_sem) + ((1.0 - alpha) * raw_kw)
        else:  # semantic
            final_score = raw_sem

        if final_score > 0.0 or mode == "semantic":
            candidate_results.append({
                "product": prod,
                "score": round(max(0.0, min(1.0, float(final_score))), 4),
                "semScore": round(max(0.0, min(1.0, float(raw_sem))), 4),
                "kwScore": round(max(0.0, min(1.0, float(raw_kw))), 4)
            })

    candidate_results.sort(key=lambda x: x["score"], reverse=True)

    top_results = []
    for rank, item in enumerate(candidate_results[:req.topK], start=1):
        prod = item["product"]
        top_results.append(SearchResultItem(
            rank=rank,
            score=item["score"],
            semScore=item["semScore"],
            kwScore=item["kwScore"],
            semanticWeight=round(alpha, 2),
            id=prod["id"],
            title=prod["title"],
            category=prod["category"],
            price=prod["price"],
            description=prod["description"],
            attributes=prod.get("attributes", [])
        ))

    latency_ms = round((time.time() - start_time) * 1000, 2)

    return SearchResponse(
        query=req.query,
        mode=mode,
        semanticWeight=round(alpha, 2),
        latencyMs=latency_ms,
        totalResults=len(top_results),
        results=top_results
    )
