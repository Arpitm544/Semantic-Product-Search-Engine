"""Prepare real English ESCI relevance pairs, hard negatives, and typo views."""

import argparse
from collections import defaultdict, deque
import hashlib
import html
import json
from pathlib import Path
import random
import re
import unicodedata

from src.config import DATASET_DIR
from src.semantic.dataset import (
    TYPO_KINDS, catalog_fingerprint, query_records, typo_query,
)
from src.search.typos import STOP_WORDS


def normalize_query(query):
    """Make case, spacing, and punctuation consistent when comparing queries."""
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", query).casefold()))


def clean_field(value, max_chars):
    """Remove HTML and extra spaces, then limit the text length."""
    if value is None:
        return ""
    value = html.unescape(str(value))
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()[:max_chars]


def has_typo_word(query):
    """Check whether the query has an English word suitable for a generated typo."""
    return any(match.group().lower() not in STOP_WORDS
               for match in re.finditer(r"\b[a-zA-Z]{4,}\b", query))


def group_judgments(examples):
    """Collect relevance labels for queries with the same normalized text."""
    groups = {}
    for query, product_id, label, query_id in examples[
            ["query", "product_id", "esci_label", "query_id"]].itertuples(index=False, name=None):
        if not isinstance(query, str):
            continue
        family = normalize_query(query)
        if not family:
            continue
        group = groups.setdefault(family, {
            "query": query.strip(), "query_ids": set(), "grades": {},
        })
        group["query_ids"].add(str(query_id))
        pid = f"esci:us:{product_id}"
        grade = {"E": 3, "S": 2, "C": 1, "I": 0}[label]
        # Conflicting judgments should never manufacture an irrelevant negative.
        group["grades"][pid] = max(grade, group["grades"].get(pid, -1))
    return groups


def choose_training_pairs(groups, families, count, held_queries, seed):
    """Select exact matches and irrelevant negatives without using held-out queries."""
    rng = random.Random(seed)
    queues = {}
    for family in sorted(families):
        group = groups[family]
        positives = sorted(pid for pid, grade in group["grades"].items() if grade == 3)
        negatives = sorted(pid for pid, grade in group["grades"].items() if grade == 0)
        if not positives or not negatives or not has_typo_word(group["query"]):
            continue
        rng.shuffle(positives)
        queues[family] = deque(positives)
    selected = []
    while queues and len(selected) < count:
        active = list(queues)
        rng.shuffle(active)
        for family in active:
            group = groups[family]
            typo = None
            for _ in range(16):
                kind = rng.choice(TYPO_KINDS)
                candidate = typo_query(group["query"], kind, rng)
                if (candidate != group["query"] and normalize_query(candidate) not in held_queries
                        and normalize_query(candidate) != family):
                    typo = (candidate, kind)
                    break
            positive = queues[family].popleft()
            if not queues[family]:
                del queues[family]
            if typo is not None:
                negatives = sorted(pid for pid, grade in group["grades"].items() if grade == 0)
                selected.append({
                    "family": family, "query": group["query"], "product_id": positive,
                    "negative_id": rng.choice(negatives), "typo": typo[0], "typo_kind": typo[1],
                    # Protect all E/S/C products when constructing in-batch negatives.
                    "relevant_product_ids": sorted(
                        pid for pid, grade in group["grades"].items() if grade > 0
                    ),
                })
            if len(selected) == count:
                break
    if len(selected) < count:
        raise ValueError(f"Only {len(selected)} usable Exact pairs; requested {count}.")
    return selected


def evaluation_records(groups, families, seed):
    """Create clean and typo queries for measuring search quality."""
    rng = random.Random(seed)
    records = []
    for family in sorted(families):
        group = groups[family]
        relevant = sorted(pid for pid, grade in group["grades"].items() if grade > 0)
        query_id = "esci-" + hashlib.sha256(family.encode()).hexdigest()[:16]
        for record in query_records(query_id, group["query"], relevant, rng, "amazon-esci"):
            records.append({
                **record, "query_family": family, "candidate_doc_ids": sorted(group["grades"]),
                "grades": group["grades"],
            })
    return records


def select_splits(train_groups, test_groups, validation_count, test_count, seed):
    # Even duplicate normalized query strings with different IDs stay together.
    """Keep related queries together and separate training from evaluation."""
    test_families = set(test_groups)
    eligible = sorted(
        family for family, group in train_groups.items()
        if family not in test_families and 3 in group["grades"].values()
    )
    rng = random.Random(seed)
    rng.shuffle(eligible)
    reserved_count = max(validation_count, int(len(eligible) * 0.1))
    validation_pool = eligible[:reserved_count]
    training_families = eligible[reserved_count:]
    validation_families = validation_pool[:validation_count]
    test_pool = sorted(
        family for family, group in test_groups.items() if 3 in group["grades"].values()
    )
    rng.shuffle(test_pool)
    if len(validation_families) < validation_count or len(test_pool) < test_count:
        raise ValueError("Not enough labeled validation or test queries.")
    return training_families, validation_pool, validation_families, test_pool[:test_count]


def read_needed_products(parquet_path, needed_ids):
    """Read only the selected US products from the large source file."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    wanted_asins = pa.array(sorted(pid.removeprefix("esci:us:") for pid in needed_ids))
    columns = [
        "product_id", "product_locale", "product_title", "product_description",
        "product_bullet_point", "product_brand", "product_color",
    ]
    products = {}
    source = pq.ParquetFile(parquet_path)
    for batch in source.iter_batches(batch_size=10000, columns=columns):
        mask = pc.and_(
            pc.equal(batch.column("product_locale"), "us"),
            pc.is_in(batch.column("product_id"), value_set=wanted_asins),
        )
        for item in batch.filter(mask).to_pylist():
            title = clean_field(item["product_title"], 400)
            if not title:
                continue
            brand = clean_field(item["product_brand"], 100)
            description = clean_field(item["product_description"], 1200)
            features = clean_field(item["product_bullet_point"], 800)
            color = clean_field(item["product_color"], 100)
            parts = [f"[Title] {title}"]
            if brand:
                parts.insert(0, f"[Brand] {brand}")
            if description:
                parts.append(f"[Details] {description}")
            if features:
                parts.append(f"[Features] {features}")
            if color:
                parts.append(f"[Color] {color}")
            pid = f"esci:us:{item['product_id']}"
            products[pid] = {
                "id": pid, "title": title, "brand": brand, "description": description,
                "category": "amazon-esci", "tags": [color] if color else [],
                "representation_text": " | ".join(parts),
            }
    missing = needed_ids - products.keys()
    if missing:
        raise ValueError(f"{len(missing)} selected products lack metadata: {sorted(missing)[:5]}")
    return [products[pid] for pid in sorted(products)]


def write_jsonl(path, rows):
    """Write one JSON object per line."""
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_arguments():
    """Read options supplied after the command name."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DATASET_DIR / "raw")
    parser.add_argument("--output-dir", type=Path, default=DATASET_DIR / "prepared")
    parser.add_argument("--pairs", type=int, default=20000)
    parser.add_argument("--validation-queries", type=int, default=200)
    parser.add_argument("--test-queries", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    return parser, parser.parse_args()


def build_training_rows(selected, products):
    """Create one clean row and one typo row for each selected product pair."""
    by_id = {product["id"]: product for product in products}
    rows = []
    for pair in selected:
        common = {
            "query_family": pair["family"], "product_id": pair["product_id"],
            "negative_id": pair["negative_id"], "negative_group": pair["family"],
            "positive": by_id[pair["product_id"]]["representation_text"],
            "negative": by_id[pair["negative_id"]]["representation_text"],
            "relevant_product_ids": pair["relevant_product_ids"],
        }
        rows.append({**common, "query": pair["query"], "kind": "clean"})
        rows.append({**common, "query": pair["typo"], "kind": pair["typo_kind"]})
    return rows


def prepare_dataset(args, parser):
    """Build separate training, validation, and test data from source labels."""
    if min(args.pairs, args.validation_queries, args.test_queries) < 1:
        parser.error("Pair and query counts must be positive.")
    if (args.output_dir / "manifest.json").exists():
        parser.error("Prepared data already exists; choose another output directory for a new experiment.")
    import pandas as pd

    examples = pd.read_parquet(
        args.raw_dir / "shopping_queries_dataset_examples.parquet",
        columns=["query", "query_id", "product_id", "esci_label", "split"],
        filters=[("product_locale", "=", "us"), ("small_version", "=", 1)],
    )
    print(f"Loaded {len(examples):,} official English ranking judgments.", flush=True)
    train_groups = group_judgments(examples[examples["split"] == "train"])
    test_groups = group_judgments(examples[examples["split"] == "test"])
    training_families, validation_pool, validation_families, test_families = select_splits(
        train_groups, test_groups, args.validation_queries, args.test_queries, args.seed,
    )
    validation = evaluation_records(train_groups, validation_families, args.seed + 1)
    test = evaluation_records(test_groups, test_families, args.seed + 2)
    held_queries = set(validation_pool) | set(test_groups) | {
        normalize_query(row["query"]) for row in validation + test
    }
    selected = choose_training_pairs(
        train_groups, training_families, args.pairs, held_queries, args.seed,
    )
    needed = {pair[key] for pair in selected for key in ("product_id", "negative_id")}
    needed.update(pid for row in validation + test for pid in row["candidate_doc_ids"])
    print(f"Reading metadata for {len(needed):,} selected products.", flush=True)
    products = read_needed_products(
        args.raw_dir / "shopping_queries_dataset_products.parquet", needed,
    )
    rows = build_training_rows(selected, products)
    rng = random.Random(args.seed)
    rng.shuffle(rows)
    source = json.loads((args.raw_dir / "source.json").read_text())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, records in (("train", rows), ("validation", validation), ("test", test)):
        write_jsonl(args.output_dir / f"{name}.jsonl", records)
    (args.output_dir / "products.json").write_text(json.dumps(products, ensure_ascii=False))
    manifest = {
        "seed": args.seed, "catalog_sha256": catalog_fingerprint(products),
        "source": "Amazon ESCI official English ranking judgments; Exact positives, Irrelevant negatives, synthetic typo views",
        "source_repository": source["repository"], "source_revision": source["revision"],
        "source_file_hashes": source["files"], "license": "Apache-2.0",
        "split_protocol": "normalized query families; official train/test; validation reserved from train",
        "product_overlap_note": "Products may occur in multiple query splits; query families never overlap.",
        "clean_training_pairs": len(selected), "augmented_training_pairs": len(rows),
        "catalog_products": len(products), "training_query_families": len({pair["family"] for pair in selected}),
        "counts": {"train": len(rows), "validation": len(validation), "test": len(test)},
        "validation_families": sorted(validation_families),
        "reserved_validation_families": sorted(validation_pool),
        "official_test_families": sorted(test_groups),
        "test_families": sorted(test_families),
        "evaluation_note": "Sampled corpus retrieval with incomplete relevance judgments; typo queries are generated.",
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({key: manifest[key] for key in (
        "clean_training_pairs", "augmented_training_pairs", "catalog_products",
        "training_query_families", "counts",
    )}, indent=2), flush=True)
    print(f"Prepared data: {args.output_dir}", flush=True)


def main():
    parser, args = parse_arguments()
    prepare_dataset(args, parser)


if __name__ == "__main__":
    main()
