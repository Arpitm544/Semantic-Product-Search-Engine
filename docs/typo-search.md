# Fine tuning and fuzzy product search

> Commands and artifact paths in this guide are relative to `backend/`, unless stated otherwise.

The live API now searches the original query with BM25 and a cached semantic
model. It also searches a suggested spelling when the catalog contains a clear
nearby word. Ranked lists are combined with weighted reciprocal rank fusion:
original keyword 1.0, suggested keyword 0.85, original semantic 1.0, suggested
semantic 0.5. These weights are starting values to assess on validation data.
Raw BM25 and cosine scores are not added together.

For example, `samsng galaxy` can generate the suggestion `samsung galaxy`.
Both queries contribute results. The website displays the suggestion and a
**Use original spelling** button. That button sends `fuzzy=0` and searches the
original query without spelling expansion.

## Run the workflow

Run these commands from `backend/` in your Python environment:

```bash
python -m pip install -r requirements.txt
python -m src.semantic.prepare_training
python -m src.semantic.fine_tune
python -m src.semantic.evaluate_typos --model models/typo-minilm-candidate --split validation
```

The first two model commands may download MiniLM if it is not cached. Add
`--local-files-only` to training and evaluation to use only cached model files.
Training runs on the device selected by Sentence Transformers, or you can pass
`--device cpu`, `--device cuda`, or `--device mps`. The default is two epochs,
batch size 16, learning rate 0.00002, and two CPU threads.

The local starter dataset uses your saved processed catalog:
`data/processed/products_cleaned.json`. To use another saved catalog, supply
`--catalog /path/to/products.json` consistently to all three commands.

After selecting settings on validation data, evaluate the untouched test split:

```bash
python -m src.semantic.evaluate_typos --model models/typo-minilm-candidate --split test
```

This writes `reports/typo_validation_metrics.json` or
`reports/typo_test_metrics.json`. Each report compares:

1. BM25.
2. BM25 with fuzzy expansion.
3. Original MiniLM semantic retrieval.
4. Original MiniLM with BM25 and fuzzy expansion.
5. Fine tuned MiniLM semantic retrieval.
6. Fine tuned MiniLM with BM25 and fuzzy expansion.

The report includes clean and typo results separately, and splits synthetic
title queries from the existing curated evaluation queries. This helps show
whether spelling tolerance improves and whether ordinary search regresses.

* **Hit rate@5:** fraction of queries with at least one relevant product in the
  first five results. Multiply by 100 to express it as a percentage.
* **Recall@5:** fraction of all labeled relevant products recovered in the first
  five results, averaged across queries. It differs from hit rate when a query
  has multiple relevant products.
* **MRR@10:** rewards placing the first relevant product near the top.

Choose the trained model only if its results support the change. A lower
training loss does not establish better search.

## Activate a selected model

The first local experiment used 626 synthetic training pairs and two epochs.
Its test split had 37 clean queries and 148 generated typo queries; the typo
queries combine 88 held-out product-title variants with 60 variants of the
existing curated queries. No test products or queries were used for training.

| System | Typo hit rate@5 | Typo recall@5 | Typo MRR@10 |
| --- | ---: | ---: | ---: |
| BM25 | 89.9% | 0.810 | 0.822 |
| BM25 + fuzzy | 95.9% | 0.874 | 0.865 |
| Original MiniLM semantic | 95.9% | 0.909 | 0.886 |
| Original MiniLM + BM25 + fuzzy | 97.3% | 0.908 | 0.902 |
| Fine tuned MiniLM semantic | 95.3% | 0.880 | 0.871 |
| Fine tuned MiniLM + BM25 + fuzzy | 96.6% | 0.904 | 0.887 |

The candidate improved ranking on the synthetic validation titles but did
not improve the held-out test benchmark. Keep the original MiniLM with fuzzy
matching as the default for this experiment. A more representative training
set should include reviewed natural product queries. These percentages
describe this small generated benchmark and are not estimates of shopper
accuracy. If further experiments are made after inspecting these results,
reserve a fresh independent test set.

Detailed local results are in `reports/typo_test_metrics.json`.
The dataset uses seed 42 and catalog fingerprint
`e8bfb32a72d9990a1db42e2464704c4b54fdd9307fd91ad3c6f91d51b1f831f7`.

Set the trained model directory when starting the API:

```bash
SEMANTIC_MODEL_PATH=models/typo-minilm-candidate python api/main.py
```

Or start both the website and API:

```bash
cd frontend
SEMANTIC_MODEL_PATH=models/typo-minilm-candidate npm run dev
```

Relative model paths are resolved from the Python project directory. Restart
the API after replacing a model. The API rebuilds the FAISS vectors from the
current catalog with the selected model once per catalog version; it never
combines old product embeddings with a new query model. Training also writes
separate `faiss_index.bin` and `faiss_id_map.pkl` artifacts inside the candidate
model directory for standalone use.

Without `SEMANTIC_MODEL_PATH`, the API tries the cached original MiniLM. If its
dependencies or cached weights are unavailable, search uses BM25 with fuzzy
matching and returns `searchMode: "bm25-fuzzy"`. A configured model that fails
to load returns a service error so configuration mistakes are visible. Serving
does not download weights. To deliberately run lexical search, set
`SEARCH_SEMANTIC=0`.

Example API request:

```bash
curl 'http://127.0.0.1:8000/api/search?q=samsng%20galaxy'
```

The response retains `query`, `total`, and `results`, and adds
`correctedQuery`, `corrections`, `searchMode`, and `semanticModel`.
Each result's `score` is a fusion ranking score, not a probability or confidence
percentage. `matchSources` identifies the retrieval branches that found it.
`total` counts the union of retrieved candidates, not every potentially
relevant product in the catalog; semantic branches retrieve at least 50
candidates, bounded by catalog size.

## How the starter training data works

`prepare_training` creates clean product-title queries and variants containing
one deletion, adjacent letter swap, neighboring keyboard substitution, or
repeated letter. Numeric model codes remain intact. The labeled positive is the
product's full searchable text.

Product families with identical normalized titles stay in the same split.
Products referenced by the existing evaluation set are reserved from training.
The remaining families are split approximately 70% training, 15% validation,
and 15% test. Query strings shared with held-out data are excluded from
training. A catalog fingerprint catches changes before training or evaluation.

The trainer uses `MultipleNegativesRankingLoss`: each query should resemble
its positive product more than other products in its batch. A batch contains
at most one example per category to reduce cases where another relevant
product becomes a negative. This also gives relatively easy negatives; a
larger labeled dataset with verified difficult negatives is a later
improvement. Unbatchable leftovers are reported in `training_report.json`.
[Sentence Transformers loss documentation](https://sbert.net/docs/package_reference/sentence_transformer/losses.html)

Generated title queries are a starter experiment. They do not establish
accuracy for real shoppers, unseen brands, multiword spacing errors, or every
typo. Add reviewed natural queries and typo examples with product IDs for a
more representative evaluation. Keep those query families out of training.

## Fuzzy matching safeguards

Suggestions use catalog words and edit distance, including adjacent swaps.
RapidFuzz accelerates this calculation when installed; a Python fallback
supports the same rule.

Known words, stop words, short terms under four letters, terms containing
digits, and non-Latin terms are preserved. Unknown words under eight letters
allow one edit; longer words allow two. Similarity must be at least 80%, and
equally close candidates are left unchanged. These constraints are intended
to keep suggestions conservative, but they still need evaluation.

This version expands individual words. It does not handle every joined-word
typo, valid-word substitution such as `cat` versus `car`, price constraints,
or arbitrary irrelevant queries. A semantic retriever returns nearby products
even when the query has no genuinely relevant catalog product; deciding when
to show no results needs separate labeled examples and threshold calibration.

## Relevant files

| File | Purpose |
| --- | --- |
| `src/search/typos.py` | Catalog spelling suggestions |
| `src/search/hybrid.py` | BM25, fuzzy, semantic rank fusion |
| `src/semantic/prepare_training.py` | Starter pairs and held-out splits |
| `src/semantic/fine_tune.py` | Training and candidate FAISS index |
| `src/semantic/evaluate_typos.py` | Six-system evaluation |
| `api/main.py` | Cached search engine and API |

Datasets, model checkpoints, and generated reports stay local and are ignored
by Git. Training refuses to overwrite an existing saved model; pass a new
`--output-dir` for another experiment.
