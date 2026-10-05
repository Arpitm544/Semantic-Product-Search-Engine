# Semantic Product Search — Notes You Can Read and Remember

These notes explain the code in `semantic-product-search` as it stood on 6 October 2026. Read the project as a story: a shop gives us its products, we prepare them, and a customer searches for something.

Imagine the customer types **“eyewear for sunny days.”** A product might be called **“sunglasses.”** Our job is to find suitable products and put the strongest matches first. This is a teaching example; a specific result depends on the catalog and the model.

The flow to remember is:

```text
Get products → Check them → Prepare their text → Build indexes
                                                 ↓
Customer query → Search the indexes → Return ranked products
```

## 1. First, we get the products

A product record is like a shop's information card. It has an ID, title, description, category, price, brand, and other details.

`src/ingestion.py` fetches these cards from the DummyJSON product API. `src/data/db.py` helps save them in MongoDB. Think of MongoDB as the cupboard holding our product records.

`src/data/load_data.py` brings the records into Python. It tries MongoDB first, then falls back to a saved JSON file if usable database records are unavailable.

The saved raw file is `data/raw/products.json`. The local snapshot has 194 products.

**Remember:** ingestion brings the products in; the loader brings saved products into our code.

## 2. Then, we check and prepare them

Before using the data, `src/data/validation.py` checks for problems such as duplicate IDs, missing titles, and invalid prices. This is similar to checking that the shop's information cards are usable.

Next, `src/data/preprocess.py` prepares a simpler version of each product. It removes HTML and extra whitespace, keeps useful fields, and makes one searchable description called `representation_text`.

For the Essence mascara product, that description looks like this, shortened here:

```text
[Category] beauty | [Brand] Essence |
[Title] Essence Mascara Lash Princess |
[Details] ... | [Tags] beauty, mascara
```

Why combine the fields? Because a title alone may leave out useful information. The category, brand, description, and tags give search more clues.

Both search methods read this prepared text. The cleaned local records are in `data/processed/products_cleaned.json`.

**Remember:** preprocessing makes one useful description from several product fields.

## 3. We have two ways to search

The project builds a keyword index and a semantic index from the prepared products.

| Search method | Main question it asks |
| --- | --- |
| BM25 keyword search | “Which products contain these query words?” |
| Semantic search | “Which product descriptions have a similar meaning to this query?” |

BM25 is useful when the customer gives words that appear in the product details. Semantic search can help when the customer describes the same idea using different wording. Neither method guarantees a good match for every query.

## 4. BM25: count words and give matches a score

The keyword algorithm lives in `src/baseline/bm25.py`.

It first turns text into lowercase tokens:

```text
“Wireless Headphones” → [“wireless”, “headphones”]
```

It records how often each word appears inside each product and how many products contain that word.

When a query arrives, BM25 gives matching products scores. A rare word usually gives a stronger clue than a word found across the catalog. Repeating a matching word can increase the score, but the benefit gets smaller with more repetitions. The algorithm also adjusts for text length, so a long description does not get an automatic advantage just from having more words.

The code uses two settings: `k1 = 1.5` controls the effect of repeated words, and `b = 0.75` controls the length adjustment. You can understand the flow before memorizing the formula.

```text
Query words → Match product words → Add scores → Sort → Return the top K
```

Here, **K means the number of results requested**. `top_k=5` asks for up to five products.

BM25 does not expand synonyms or reduce words to their roots in this implementation. For example, `run` and `running` are separate tokens. A product with no matching query words gets a zero score and is left out.

**Remember:** BM25 scores word overlap, with adjustments for rarity, repetition, and length.

## 5. Semantic search: turn text into numbers

The semantic search code is in `src/dense/vector_search.py`. It uses the pretrained model **`all-MiniLM-L6-v2`**, loaded through the **Sentence Transformers** library.

An **embedding** is a list of numbers representing a piece of text. This model produces **384 numbers for each input text**. The values are learned features; we have not manually assigned a coordinate to “shoes,” “beauty,” or “price.” The model is designed for sentence and short-paragraph similarity. [Official model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).

A useful picture is to imagine product descriptions as points on a map. Related descriptions may be placed near each other. Our real map has 384 coordinates per point, so we cannot draw it directly on a page.

The project uses an already trained model. Its `fit()` function embeds the products and builds an index; it does not train new model weights.

**Remember:** the model turns text into numbers that we can compare.

## 6. What happens inside embedding generation?

We give the model each product's `representation_text`:

```python
embeddings = model.encode(product_texts, batch_size=32)
```

The library handles the steps inside this call:

```text
Text → Model tokens → Contextual token representations
                   → Pool them into one text vector
```

The transformer processes the tokens in context, and mean pooling combines their representations into one vector. The model's previous training makes these representations useful for comparing related text. [Model explanation](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).

`batch_size=32` means processing groups of up to 32 product texts at a time. It is separate from the number of results returned by search.

For 194 products, the expected embedding matrix has 194 rows and 384 columns: one row per product.

We prepare the product embeddings when building the catalog index. Every customer query gets a new query embedding, while the existing product embeddings are reused.

**Remember:** embed the catalog when building it; embed the query when searching it.

## 7. We normalize the vectors, then store them in FAISS

After creating embeddings, the code normalizes each vector to length 1. This prepares products and queries for the same similarity calculation.

For a small example, `[3, 4]` has length 5. Dividing by 5 gives `[0.6, 0.8]`, which has length 1. Real vectors have 384 coordinates.

Next, we put the product vectors into **FAISS**, using **`IndexFlatIP`**. FAISS performs the numerical search. The embedding model has already created the vectors.

`IP` means **inner product**. When both vectors have length 1, their inner product equals **cosine similarity**, which compares their directions. [Sentence Transformers similarity documentation](https://sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html).

This FAISS index compares a query with all stored product vectors and selects the highest scores. It gives an exact vector ranking, which is straightforward for this small catalog. [FAISS index documentation](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes).

**Remember:** the model creates vectors; FAISS finds the highest scoring ones.

## 8. Now follow one customer search

Suppose a customer types “eyewear for sunny days.” The semantic engine follows this sequence:

1. Encode the query with the same model used for the products.
2. Normalize the query vector.
3. Ask FAISS to compare it with the stored product vectors.
4. Get the best scores and their vector row positions.
5. Use those positions to retrieve the corresponding product records.
6. Return the products in ranked order.

```text
“eyewear for sunny days”
          ↓
Same embedding model
          ↓
Normalized query vector
          ↓
FAISS similarity search
          ↓
Vector positions → Product records → Ranked results
```

If FAISS returns row position 7, the code reads `self.products[7]`. That position refers to the eighth item in the list; it is not necessarily product ID 7.

Similarity scores help order the results. A score of 0.8 does not mean an 80% chance that the product is correct. The core semantic engine returns the nearest available products without a minimum relevance cutoff, so weak matches can still appear.

**Remember:** encode, normalize, compare, look up, return.

## 9. Why save an index?

Building product embeddings takes more work than loading embeddings we have already saved. The project therefore keeps these artifacts:

| Saved file | What is inside |
| --- | --- |
| `indexes/bm25_index.pkl` | BM25 word statistics and product records |
| `indexes/faiss_index.bin` | Product vectors stored in FAISS |
| `indexes/faiss_id_map.pkl` | Product list, model name, and vector dimension |

The last file lets us connect a vector position back to a product. Despite its name, it stores the product list rather than just a dictionary of IDs.

Changing product text or the embedding model requires rebuilding the relevant indexes. Saved files are snapshots; updating a product in MongoDB does not automatically update its saved vector.

**Remember:** an index saves the preparation work so we can reuse it.

## 10. How do we know whether search works well?

We use `data/eval/eval_set.json`. It contains 15 queries and the product IDs labeled relevant to each one. A relevant ID acts like an answer key for checking retrieval.

The two evaluation scripts search these queries and compare their results with that answer key. `src/compare_models.py` runs both and writes a comparison report.

| Metric | Easy way to remember it |
| --- | --- |
| Precision@K | “How many of my first K results are useful?” |
| Recall@K | “How many of the useful products did I find in the first K?” |
| MRR | “How soon did the first useful result appear?” |
| MAP | “Were useful results consistently near the top?” |
| NDCG@K | “Did the order put useful results early?” |
| Latency | “How long did the search take?” |

Example: two relevant hits among five results gives Precision@5 = `2/5`. If four products are labeled relevant in total, finding those two gives Recall@5 = `2/4`.

The saved comparison from 30 September 2026 shows Precision@5 of **0.40 for BM25** and **0.52 for dense search**. Dense search also recorded a higher median query time. These results describe this small evaluation set; we have not rerun the benchmark for these notes.

The current evaluators retrieve at most 10 results by default. Even the saved MRR and MAP use that retrieved list. Dense timing includes query encoding and can include the first model load.

**Remember:** evaluation checks the rankings against labeled product IDs.

## 11. Where does hybrid search fit?

The live hybrid search is in the sibling demo's API:

```text
Semantic-Product-Search-Engine/
└── demo/data/backend/app/main.py
```

It combines semantic and keyword scores. It first divides each BM25 score by the highest BM25 score for that query, then uses:

```text
Final score = 0.7 × semantic score + 0.3 × normalized keyword score
```

Those are the default weights; the API lets the semantic weight change. This is weighted score combination. The current endpoint does not implement the Reciprocal Rank Fusion mentioned in the README.

The demo also provides explicit category and maximum-price filters. For a request such as “under 50,” the core semantic engine compares text; a numeric price condition needs an explicit filter. Price is stored in the product record but is absent from the text we embed.

The demo has its own metadata and index files. The `semantic-product-search` folder builds and evaluates keyword and semantic search separately.

**Remember:** hybrid combines scores; filters enforce product conditions.

## 12. Keep this folder map beside you

```text
semantic-product-search/
├── data/                   The inputs
│   ├── raw/                Original product records
│   ├── processed/          Prepared product records
│   └── eval/               Queries and their relevant product IDs
│
├── src/                    The working code
│   ├── config.py           Paths, source URL, and model name
│   ├── ingestion.py        Fetch products
│   ├── compare_models.py   Compare search methods
│   ├── data/
│   │   ├── db.py           MongoDB helpers
│   │   ├── load_data.py    Load database or file records
│   │   ├── validation.py   Check records
│   │   └── preprocess.py   Prepare searchable text
│   ├── baseline/
│   │   ├── bm25.py         Keyword search
│   │   └── evaluate_baseline.py
│   ├── dense/
│   │   ├── vector_search.py  Embeddings and semantic search
│   │   └── evaluate_dense.py
│   └── eda/
│       └── eda_analysis.py Catalog statistics
│
├── indexes/                Saved search preparation
├── reports/                Saved statistics and evaluation results
├── notebooks/              Interactive data exploration
├── tests/                  Existing checks for the code
└── requirements.txt        Python dependencies
```

A useful reading order is: one raw product, then `preprocess.py`, then the corresponding cleaned product, then `bm25.py`, then `vector_search.py`, then the evaluation scripts.

For revision, connect four folders to four ideas: **data = inputs, src = work, indexes = reusable preparation, reports = results.**

## 13. Four details that matter when you run it

The code has a few defaults that are easy to miss:

- Ingestion attempts a MongoDB save. It does not refresh the local raw JSON file.
- Preprocessing writes a local cleaned JSON file only when `save_json_backup=True`. The default is `False`.
- A failed validation report is printed, but the preprocessing command still continues.
- Existing indexes can be reused by evaluation, so you must rebuild them after changing the searchable catalog.

The model's default limit is 256 word pieces. The EDA script counts ordinary words, which does not prove that a description fits the model token limit. [Model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).

From the `semantic-product-search` folder, run each executable module with its command below:

| File | Run command |
| --- | --- |
| `src/ingestion.py` | `python -m src.ingestion` |
| `src/data/validation.py` | `python -m src.data.validation` |
| `src/data/preprocess.py` | `python -m src.data.preprocess` |
| `src/eda/eda_analysis.py` | `python -m src.eda.eda_analysis` |
| `src/baseline/bm25.py` | `python -m src.baseline.bm25` |
| `src/baseline/evaluate_baseline.py` | `python -m src.baseline.evaluate_baseline` |
| `src/dense/vector_search.py` | `python -m src.dense.vector_search` |
| `src/dense/evaluate_dense.py` | `python -m src.dense.evaluate_dense` |
| `src/compare_models.py` | `python -m src.compare_models` |

`config.py`, `db.py`, and `load_data.py` provide helpers used by these modules. They have no standalone command that runs a pipeline step. Package marker files such as `__init__.py` do not need a run command.

See [Run Commands](RUN_COMMANDS.md) for environment setup, the outputs of each command, local JSON preprocessing, individual test commands, and the notebook command. These commands can write database records, indexes, or reports according to the code's options. They were not run while writing these notes.

## 14. Practise saying it in your own words

“We fetch product records, check them, and combine their important text fields into a searchable description. BM25 ranks products using word matches. For semantic search, we use the pretrained MiniLM model to turn product text and query text into embeddings. We normalize those vectors and use FAISS to find the most similar products. Then we return their records and evaluate the rankings against labeled product IDs.”

To check your understanding, try answering these without looking:

1. Why do we create `representation_text`?
2. Which component creates embeddings, and which searches them?
3. Why does the query use the same model as the products?
4. What is the difference between a vector row position and a product ID?
5. Why do we rebuild indexes after changing product text?
6. What is evaluation comparing our results against?
