# How the search project works

## The dataset

The local dataset lives in backend/data/dataset/.

- raw/ holds the original Amazon product and search-label files.
- prepared/ holds the selected product catalog and training, validation, and test examples.
- train.jsonl supplies examples the model learns from.
- validation.jsonl measures progress while choosing a model.
- test.jsonl is held aside for the final evaluation.
- manifest.json records counts, split information, and the catalog fingerprint.

ESCI labels mean Exact, Substitute, Complement, and Irrelevant. They describe
the relationship between a search query and a product.

## MongoDB and the website

The importer copies prepared/products.json into MongoDB and records a successful
catalog version. The website API reads this MongoDB collection. A missing or
incomplete import makes search unavailable.

The prepared JSON is used for imports and offline training; normal website
searches read product documents from MongoDB.

## Finding and ranking products

1. Spelling correction suggests likely catalog words.
2. Keyword retrieval finds matching brand and title words.
3. The embedding model finds products with related meanings.
4. A reranker compares the query with candidate products.
5. The backend blends retrieval and reranker ranks and returns the best results.

The vector index caches numeric representations so the backend can reuse them.
It is rebuilt when the published catalog version or relevant model changes.

## Measuring results

Training examples teach the model; evaluation examples measure its performance.
Keep validation and test query families separate from training so the results
measure how well the model handles searches it has not learned directly.

Hit rate measures how often any relevant result appears near the top.
Recall measures how many of the relevant products were retrieved.
Reciprocal rank rewards finding a relevant product earlier.

Use [commands](commands.md) to run the project and
[Colab training](colab-training.md) for the cloud notebook.
