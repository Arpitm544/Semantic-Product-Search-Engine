# Search evaluation and spelling

The search evaluator uses backend/data/dataset/prepared/ by default.
Its product catalog and validation/test query splits come from the same prepared
Amazon dataset used by the training workflow.

## Run evaluation

From backend/:

~~~sh
python -m src.semantic.evaluate_typos --lexical-only
~~~

This compares BM25 keyword retrieval with spelling-aware retrieval.
To evaluate a selected local model as well:

~~~sh
python -m src.semantic.evaluate_typos --model models/colab-export/esci-minilm-20k --local-files-only
~~~

Use --split test for the held-out test split. The evaluator also compares the
base embedding model, which must already be cached when --local-files-only is set.
Training and evaluation libraries must be installed.

## Metrics

- Recall@5: fraction of the labeled relevant products retrieved in the first five results.
- Hit rate@5: whether at least one relevant product appears in the first five.
- MRR@10: reciprocal rank of the first relevant result within the first ten.

Reports separate clean and misspelled searches. The evaluator checks that the
catalog fingerprint matches the dataset manifest before using a split.

By default reports are written under backend/reports/. These are offline
experiment results; they do not automatically measure the website's full
expanded-query and cross-encoder reranking pipeline.

## Training and serving

The dataset preparation code builds spelling variations of real labeled
queries. The training workflow protects relevant products from becoming false
negatives and keeps held-out query families separate.

The production API reads products from MongoDB and loads local model weights.
Its spelling suggestions can be disabled by adding fuzzy=0 to a search request.

See [Colab training](colab-training.md) and [backend setup](backend.md).
