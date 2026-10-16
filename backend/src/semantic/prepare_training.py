"""Generate reproducible starter pairs and keep product families in one split."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import re

from src.config import EVAL_SET_PATH, PROJECT_ROOT, PROCESSED_DATA_PATH
from src.search.typos import STOP_WORDS

TRAINING_DIR = PROJECT_ROOT / "data" / "training"
TYPO_KINDS = ("deletion", "transposition", "substitution", "repetition")
KEYBOARD_NEIGHBORS = {
    "a": "sqwz", "b": "vghn", "c": "xdfv", "d": "serfc", "e": "wsdr",
    "f": "drtgv", "g": "ftyhb", "h": "gyujn", "i": "ujko", "j": "huikm",
    "k": "jiolm", "l": "kop", "m": "njk", "n": "bhjm", "o": "iklp",
    "p": "ol", "q": "wa", "r": "edft", "s": "awedz", "t": "rfgy",
    "u": "yhji", "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu", "z": "asx",
}


def catalog_fingerprint(products):
    searchable = [
        {key: product.get(key) for key in (
            "id", "title", "description", "brand", "category", "tags", "representation_text",
        )}
        for product in sorted(products, key=lambda product: str(product["id"]))
    ]
    return hashlib.sha256(json.dumps(searchable, sort_keys=True).encode()).hexdigest()


def load_catalog(path):
    products = json.loads(Path(path).read_text())
    if not isinstance(products, list) or len(products) < 10:
        raise ValueError("Training needs a catalog of at least 10 products.")
    if any(not product.get("title") or "id" not in product for product in products):
        raise ValueError("Every product must have an id and a title.")
    if len({product["id"] for product in products}) != len(products):
        raise ValueError("Product IDs must be unique.")
    return products


def product_text(product):
    return product.get("representation_text") or " ".join(str(product.get(key, "")) for key in (
        "brand", "title", "category", "description",
    ))


def typo_query(query, kind, rng):
    words = [
        match for match in re.finditer(r"\b[a-zA-Z]{4,}\b", query)
        if match.group().lower() not in STOP_WORDS
    ]
    rng.shuffle(words)
    for match in words:
        word = match.group().lower()
        positions = list(range(len(word)))
        rng.shuffle(positions)
        for position in positions:
            if kind == "deletion":
                changed = word[:position] + word[position + 1:]
            elif kind == "repetition":
                changed = word[:position] + word[position] + word[position:]
            elif kind == "substitution":
                changed = word[:position] + rng.choice(KEYBOARD_NEIGHBORS[word[position]]) + word[position + 1:]
            elif kind == "transposition":
                if position + 1 >= len(word) or word[position] == word[position + 1]:
                    continue
                changed = word[:position] + word[position + 1] + word[position] + word[position + 2:]
            else:
                raise ValueError(f"Unknown typo kind: {kind}")
            return query[:match.start()] + changed + query[match.end():]
    return query


def query_records(query_id, query, relevant_ids, rng, source):
    records = [{
        "query_id": f"{query_id}-clean", "query": query, "clean_query": query,
        "relevant_doc_ids": relevant_ids, "kind": "clean", "source": source,
    }]
    seen = {query.lower()}
    for kind in TYPO_KINDS:
        changed = typo_query(query, kind, rng)
        if changed.lower() not in seen:
            records.append({
                "query_id": f"{query_id}-{kind}", "query": changed, "clean_query": query,
                "relevant_doc_ids": relevant_ids, "kind": kind, "source": source,
            })
            seen.add(changed.lower())
    return records


def prepare_data(products, eval_queries, seed=42):
    rng = random.Random(seed)
    product_ids = {product["id"] for product in products}
    reserved_ids = {product_id for query in eval_queries for product_id in query["relevant_doc_ids"]}
    if reserved_ids - product_ids:
        raise ValueError("Evaluation labels reference IDs absent from the catalog.")
    # Duplicate titles are the same family even if their IDs differ.
    families = defaultdict(list)
    for product in products:
        family = " ".join(product["title"].lower().split())
        families[family].append(product)
    available = [
        family for family, members in families.items()
        if not any(product["id"] in reserved_ids for product in members)
    ]
    rng.shuffle(available)
    held_count = max(1, int(len(available) * 0.15))
    if len(available) - 2 * held_count < 2:
        raise ValueError("Too few products remain after reserving evaluation labels.")
    split_families = {
        "validation": available[:held_count],
        "test": available[held_count:2 * held_count],
        "train": available[2 * held_count:],
    }
    output = {"train": [], "validation": [], "test": []}
    for split in ("validation", "test"):
        for family in split_families[split]:
            members = families[family]
            output[split].extend(query_records(
                f"product-{members[0]['id']}", members[0]["title"],
                [product["id"] for product in members], rng, "synthetic-title",
            ))
    for query in eval_queries:
        output["test"].extend(query_records(
            query["query_id"], query["query"], query["relevant_doc_ids"], rng, "curated-eval",
        ))
    held_queries = {
        row["query"].lower() for split in ("validation", "test") for row in output[split]
    }
    for family in split_families["train"]:
        product = families[family][0]
        title = product["title"]
        clean_queries = [title]
        brand = product.get("brand")
        if brand and brand.lower() not in title.lower() and brand.lower() != "generic":
            clean_queries.append(f"{brand} {title}")
        seen = set()
        for clean in clean_queries:
            variants = [clean] + [typo_query(clean, kind, rng) for kind in TYPO_KINDS]
            for query in variants:
                if query.lower() in seen or query.lower() in held_queries:
                    continue
                seen.add(query.lower())
                output["train"].append({
                    "query": query, "positive": product_text(product),
                    "product_id": product["id"],
                    "negative_group": product.get("category") or family,
                })
    manifest = {
        "seed": seed, "catalog_sha256": catalog_fingerprint(products),
        "source": "synthetic catalog title queries; review and add real labeled queries",
        "counts": {split: len(rows) for split, rows in output.items()},
        "product_ids": {
            split: sorted({
                product["id"] for family in split_families[split]
                for product in families[family]
            }) for split in split_families
        },
        "reserved_eval_product_ids": sorted(reserved_ids),
    }
    return output, manifest


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=PROCESSED_DATA_PATH)
    parser.add_argument("--eval-set", type=Path, default=EVAL_SET_PATH)
    parser.add_argument("--output-dir", type=Path, default=TRAINING_DIR)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    products = load_catalog(args.catalog)
    eval_queries = json.loads(args.eval_set.read_text())
    datasets, manifest = prepare_data(products, eval_queries, args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for split, rows in datasets.items():
        (args.output_dir / f"{split}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        )
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest["counts"], indent=2))
    print(f"Prepared starter data at {args.output_dir}; evaluation products were excluded from training.")


if __name__ == "__main__":
    main()
