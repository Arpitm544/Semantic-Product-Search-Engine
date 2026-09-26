# Exploratory Data Analysis (EDA) Report: Product Catalog

**Catalog Source:** DummyJSON E-Commerce Catalog  
**Total Products Indexed:** 194  
**Unique Categories:** 24  
**Unique Vocabulary Size:** 1,363 terms (7,371 total tokens)  

---

## 1. Summary Statistics

| Metric | Min | Max | Mean | Median |
| :--- | :--- | :--- | :--- | :--- |
| **Price ($)** | $0.79 | $36999.99 | $1570.10 | $34.99 |
| **Rating (1-5)** | 2.51 | 4.99 | 3.80 | - |
| **Title Word Count** | 1 | 7 | 2.8 | 2 |
| **Description Word Count** | 10 | 37 | 25.8 | 27 |
| **Canonical Text Word Count** | 17 | 52 | 38.0 | 40 |

---

## 2. Category Distribution (Top 10)

| Category | Product Count | % of Catalog |
| :--- | :--- | :--- |
| kitchen-accessories | 30 | 15.5% |
| groceries | 27 | 13.9% |
| sports-accessories | 17 | 8.8% |
| smartphones | 16 | 8.2% |
| mobile-accessories | 14 | 7.2% |
| mens-watches | 6 | 3.1% |
| beauty | 5 | 2.6% |
| fragrances | 5 | 2.6% |
| furniture | 5 | 2.6% |
| home-decoration | 5 | 2.6% |

---

## 3. Preprocessing & Embedding Suitability Findings
1. **Sequence Lengths:** The maximum canonical representation length is **52 words**, well within the 256-token context window of standard sentence-transformers (such as `all-MiniLM-L6-v2`), ensuring zero truncation leakage during dense embedding generation.
2. **Missingness & Hygiene:** All 194 records contain valid titles, categories, and prices.
3. **Lexical Baseline Impact:** Rich descriptions and tag structures provide sufficient token overlap for BM25/TF-IDF baseline comparisons.
