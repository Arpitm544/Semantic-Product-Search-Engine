"""Package judged ESCI pairs and training code for Google Colab."""

import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys
import zipfile

from create_colab_bundle import PROJECT, sha256

sys.path.insert(0, str(PROJECT))
from src.search.relevance import product_pair_text
from src.semantic.prepare_esci import group_judgments, read_needed_products, read_us_esci_examples, select_splits, write_jsonl


def create_bundle(raw, output, max_train_pairs, held_queries):
    examples = read_us_esci_examples(raw)
    train_groups = group_judgments(examples[examples["split"] == "train"])
    test_groups = group_judgments(examples[examples["split"] == "test"])
    train, _, calibration, test = select_splits(train_groups, test_groups, held_queries, held_queries, 42)
    if not train:
        raise ValueError("No training queries remain after reserving calibration and test families.")
    random.Random(42).shuffle(train)
    count = 0
    for end, family in enumerate(train, 1):
        count += len(train_groups[family]["grades"])
        if count >= max_train_pairs:
            break
    splits = {"train": (train_groups, train[:end]), "calibration": (train_groups, calibration),
              "test": (test_groups, test)}
    needed = {pid for groups, families in splits.values() for family in families for pid in groups[family]["grades"]}
    print(f"Reading {len(needed):,} products from ESCI.", flush=True)
    texts = {p["id"]: product_pair_text(p) for p in read_needed_products(
        raw / "shopping_queries_dataset_products.parquet", needed, strict=False,
    )}
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"source_revision": json.loads((raw / "source.json").read_text())["revision"],
                "seed": 42, "splits": {}}
    paths = []
    for split, (groups, families) in splits.items():
        rows = [
            {"family": family, "query": groups[family]["query"], "product_id": pid, "text": texts[pid], "grade": grade}
            for family in families for pid, grade in groups[family]["grades"].items() if pid in texts
        ]
        counts = Counter(row["grade"] for row in rows)
        if set(counts) != {0, 1, 2, 3}:
            raise ValueError(f"{split} must contain all ESCI grades, found {dict(counts)}.")
        manifest["splits"][split] = {"pairs": len(rows), "labels": counts,
                                     "query_families": len({row["family"] for row in rows}),
                                     "missing_product_rows": sum(len(groups[f]["grades"]) for f in families) - len(rows)}
        path = output / f"{split}.jsonl"
        write_jsonl(path, rows)
        paths.append(path)
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    paths.append(manifest_path)
    paths.extend(raw / name for name in ("LICENSE", "NOTICE", "source.json"))
    files = {f"data/{path.name}": path for path in paths}
    files.update({path.relative_to(PROJECT).as_posix(): path for path in (PROJECT / "src").rglob("*.py")})
    bundle = output / "esci_reranker_bundle.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, path in files.items():
            archive.write(path, name)
        archive.writestr("checksums.json", json.dumps({name: sha256(path) for name, path in files.items()}))
    print(json.dumps(manifest, indent=2))
    print(f"Colab bundle: {bundle} ({bundle.stat().st_size:,} bytes)", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=PROJECT / "data/dataset/raw")
    parser.add_argument("--output-dir", type=Path, default=PROJECT / "colab/reranker")
    parser.add_argument("--train-pairs", type=int, default=40000)
    parser.add_argument("--held-queries", type=int, default=400)
    args = parser.parse_args()
    if min(args.train_pairs, args.held_queries) < 1:
        parser.error("Pair and query counts must be positive.")
    create_bundle(args.raw_dir, args.output_dir, args.train_pairs, args.held_queries)
