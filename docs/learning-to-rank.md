# Learning to rank (LambdaMART)

Can a trained model order search results better than the hand-set rule the site
uses today (25% retrieval rank + 75% cross-encoder rank, fused as
`1 / (60 + rank)`)? This experiment trains a LambdaMART ranker on Amazon ESCI
relevance judgments and tests it on held-out queries.

**Result: no.** The learned ranker ties the current blend on the test split
(NDCG@10 +0.004, 95% CI −0.007 to +0.015, p = 0.51). The site therefore keeps
the blend by default; the model can be switched on with `SEARCH_RANKER=learned`.
The ablation and SHAP analysis explain why: the cross-encoder already carries
almost all of the useful signal, and the blend uses it well.

## Data and protocol

| Part | What was used |
|---|---|
| Candidates | Exactly what the served pipeline reranks: spelling variations → keyword (BM25) + meaning (fine-tuned MiniLM) retrieval, fused; 50–150 products per query |
| Labels | ESCI grades: Exact 3, Substitute 2, Complement 1, Irrelevant 0. Unjudged candidates count as 0, the same convention as the quality report |
| Training | ESCI **validation** split: 200 query families × (1 clean + 4 typo variants) = 1,000 queries, 69,365 candidate rows |
| Model selection | 5-fold cross-validation **grouped by query family**, so typo variants of one query never sit on both sides of a fold |
| Test | ESCI **test** split: 200 other families, 992 queries, 68,639 candidate rows. Used once, after every choice was fixed |
| Significance | 10,000 bootstrap resamples **over families** (typo variants are not independent) and a 10,000-round paired randomization test |

Why not the ESCI training queries? The meaning encoder was fine-tuned on them,
so their similarity scores would look unrealistically good and the ranker would
learn to over-trust them. The prep script's reserved pool avoids that, but only
5% of its judged products are in the catalog, so the labels would be mostly
missing. The validation split is fully in the catalog and was not used for
encoder training.

## Features (21 per candidate)

All come from signals the pipeline already computes, so serving adds no model
calls: cross-encoder score, rank, gap to the best score and z-score within the
query; retrieval, keyword and meaning-search ranks; cosine similarity and its gap
to the best; spelling-correction flags; query length; share of query words in the
title and product text; brand named in the query; title length; candidate count.
See `backend/src/ranking/features.py` for the full list.

## Model

LightGBM `LGBMRanker` (lambdarank objective, NDCG gains 0/1/3/7 to match our
metric, truncation level 20, learning rate 0.05, column sampling 0.8, L2 1.0).
Grid over `num_leaves` {7, 15, 31} × `min_child_samples` {10, 40}; tree count by
early stopping inside each fold.

| num_leaves | min_child_samples | CV NDCG@10 | trees |
|---|---|---|---|
| **7** | **40** | **0.6085** | 62 |
| 7 | 10 | 0.6084 | 81 |
| 15 | 10 | 0.6059 | 41 |
| 15 | 40 | 0.6054 | 43 |
| 31 | 40 | 0.6045 | 20 |
| 31 | 10 | 0.6017 | 18 |
| *current blend* | | *0.5725* | |

Small trees won and early stopping kept the model short: with 200 families
there is little data, and larger models overfit.

## Test results (992 queries, 200 families)

| System | NDCG@10 | MRR@10 | Hit@5 | Recall@10 |
|---|---|---|---|---|
| Current blend (served) | 0.5999 | 0.6986 | 0.8468 | 0.5322 |
| **Learned ranker** | **0.6042** | 0.7020 | 0.8397 | 0.5309 |
| Learned ranker without cross-encoder features | 0.5784 | 0.6917 | 0.8256 | 0.5147 |

| Comparison | Metric | Difference | 95% CI | p |
|---|---|---|---|---|
| Learned − blend | NDCG@10 | +0.0038 | −0.0073 to +0.0149 | 0.51 |
| Learned − blend | MRR@10 | +0.0033 | −0.0279 to +0.0337 | 0.82 |
| Learned − blend | Hit@5 | −0.0070 | −0.0270 to +0.0120 | 0.53 |
| No cross-encoder − blend | NDCG@10 | **−0.0216** | **−0.0385 to −0.0049** | **0.014** |

Clean and typo queries behave the same way (clean: 0.622 → 0.628; typo:
0.594 → 0.598).

## What drives the model (SHAP)

Mean absolute SHAP contribution on test candidates; "direction" is the
correlation between a feature's value and its contribution (+ means higher
values raise the score).

| Feature | Mean \|SHAP\| | Direction |
|---|---|---|
| Cross-encoder score vs. other candidates (z-score) | 0.451 | +0.94 |
| Meaning similarity minus the best in the search | 0.316 | +0.83 |
| Cross-encoder score minus the best | 0.267 | +0.94 |
| Position under the current blend | 0.186 | −0.69 |
| Meaning-search rank | 0.126 | −0.51 |
| Meaning similarity | 0.071 | +0.87 |

Every direction is sensible: better cross-encoder scores and closer meaning
raise a product; worse ranks lower it. Keyword and text-overlap features
matter little once the cross-encoder has read the query and product together.

## Conclusions

1. **The hand-set blend is already near-optimal for these signals.** A learned
   combination of 21 features does not beat it significantly on any metric.
2. **The cross-encoder is the essential signal.** Removing its features makes
   the learned ranker significantly worse (p = 0.014), and it dominates SHAP.
3. **Cross-validation overstated the gain.** +6% in CV became +0.6% on test.
   With only 200 training families, and validation queries drawn from ESCI's
   training split while the test queries come from its official test split,
   held-out folds were not a perfect stand-in for new queries. Reporting the
   untouched test result, rather than the CV number, matters.
4. **Where gains are likely:** improving the cross-encoder itself (fine-tuning
   it on ESCI instead of using the MS MARCO model), or more training families
   (importing the catalog products for the reserved query pool).

## Reproduce

```sh
cd backend
.venv/bin/python -m pip install lightgbm==4.6.0      # training only
.venv/bin/python scripts/ltr_features.py              # about 45 minutes on CPU
.venv/bin/python scripts/train_ltr.py                 # about 1 minute
```

This writes `backend/ranking/ltr_model.json` (the model) and
`backend/ranking/ltr_report.json` (every number above). To serve the model, set
`SEARCH_RANKER=learned` in `backend/.env` and restart. "Why this result?" then
names the factors that moved each result.

**Serving needs no LightGBM.** On macOS, LightGBM's OpenMP runtime and
PyTorch's crash when loaded in one process, and the server always loads PyTorch.
So the model is exported as LightGBM's JSON tree dump and scored by a small
NumPy evaluator (`backend/src/ranking/learned.py`). The training script checks
that it matches LightGBM's own predictions exactly (largest difference: 0.0),
and adds about 5 ms per search.
