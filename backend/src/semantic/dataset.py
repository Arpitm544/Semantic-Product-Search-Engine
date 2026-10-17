"""Shared helpers for the product-search dataset and its training workflow."""

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import re

from src.search.typos import STOP_WORDS


TYPO_KINDS = ("deletion", "transposition", "substitution", "repetition")


KEYBOARD_NEIGHBORS = {
    "a": "sqwz", "b": "vghn", "c": "xdfv", "d": "serfc", "e": "wsdr",
    "f": "drtgv", "g": "ftyhb", "h": "gyujn", "i": "ujko", "j": "huikm",
    "k": "jiolm", "l": "kop", "m": "njk", "n": "bhjm", "o": "iklp",
    "p": "ol", "q": "wa", "r": "edft", "s": "awedz", "t": "rfgy",
    "u": "yhji", "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu", "z": "asx",
}


def catalog_fingerprint(products):
    """Hash searchable product fields to detect catalog changes."""
    searchable = [
        {key: product.get(key) for key in (
            "id", "title", "description", "brand", "category", "tags", "representation_text",
        )}
        for product in sorted(products, key=lambda product: str(product["id"]))
    ]
    return hashlib.sha256(json.dumps(searchable, sort_keys=True).encode()).hexdigest()


def load_catalog(path):
    """Read and validate the offline product catalog."""
    products = json.loads(Path(path).read_text())
    if not isinstance(products, list) or len(products) < 10:
        raise ValueError("Training needs a catalog of at least 10 products.")
    if any(not product.get("title") or "id" not in product for product in products):
        raise ValueError("Every product must have an id and a title.")
    if len({product["id"] for product in products}) != len(products):
        raise ValueError("Product IDs must be unique.")
    return products


def typo_query(query, kind, rng):
    """Change one word to simulate a specified spelling mistake."""
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
    """Create the original query and its distinct spelling variations."""
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


def read_jsonl(path):
    """Read one JSON object from each nonempty line."""
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def grouped_batches(rows, batch_size, seed, include_remainder=False):
    """Separate query groups; include remainder only with a masked loss."""
    if batch_size < 2:
        raise ValueError("Contrastive learning requires a batch size of at least two.")
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[row["negative_group"]].append(index)
    if len(groups) < 2:
        raise ValueError("Training requires at least two negative groups/categories.")
    rng = random.Random(seed)
    for indices in groups.values():
        rng.shuffle(indices)
    batches = []
    while True:
        active = [group for group, indices in groups.items() if indices]
        if len(active) < 2:
            break
        rng.shuffle(active)
        # Use larger groups first so fewer rows are left without a second group.
        active.sort(key=lambda group: len(groups[group]), reverse=True)
        batches.append([groups[group].pop() for group in active[:batch_size]])
    if include_remainder:
        remaining = [index for indices in groups.values() for index in indices]
        batches.extend(remaining[offset:offset + batch_size]
                       for offset in range(0, len(remaining), batch_size))
    return batches
