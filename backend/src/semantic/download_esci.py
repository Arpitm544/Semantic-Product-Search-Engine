"""Download the official Amazon ESCI files and verify their Git LFS hashes."""

import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

from src.config import DATASET_DIR

REPOSITORY = "amazon-science/esci-data"
FILES = (
    "shopping_queries_dataset_examples.parquet",
    "shopping_queries_dataset_products.parquet",
)


def fetch_bytes(url):
    """Download a small source or metadata file."""
    request = Request(url, headers={"User-Agent": "semantic-product-search-training"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def file_sha256(path):
    """Hash a file in chunks without loading the whole file into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(url, destination, expected_sha, expected_size):
    """Reuse verified downloads or check a new file before accepting it."""
    if (destination.exists() and destination.stat().st_size == expected_size
            and file_sha256(destination) == expected_sha):
        print(f"Verified cached {destination.name}", flush=True)
        return
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = Request(url, headers={"User-Agent": "semantic-product-search-training"})
    digest = hashlib.sha256()
    written = 0
    last_logged = 0
    with urlopen(request, timeout=120) as response, temporary.open("wb") as output:
        while True:
            chunk = response.read(4 * 1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            digest.update(chunk)
            written += len(chunk)
            if written - last_logged >= 64 * 1024 * 1024:
                print(f"{destination.name}: {written / expected_size:.0%}", flush=True)
                last_logged = written
    if written != expected_size or digest.hexdigest() != expected_sha:
        raise ValueError(f"Size or SHA256 mismatch for {destination.name}; .part file was not accepted.")
    temporary.replace(destination)
    print(f"Downloaded and verified {destination.name} ({written / 1024**2:.1f} MiB)", flush=True)


def parse_arguments():
    """Read options supplied after the command name."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DATASET_DIR / "raw")
    parser.add_argument("--revision", default=None, help="Pinned Git commit; defaults to current main.")
    return parser, parser.parse_args()


def download_dataset(args, parser):
    """Choose a source revision, download verified files, and save source information."""
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = args.output_dir / "source.json"
    existing = json.loads(metadata_path.read_text()) if metadata_path.exists() else None
    revision = args.revision or (existing["revision"] if existing else None)
    if revision is None:
        revision = json.loads(fetch_bytes(
            f"https://api.github.com/repos/{REPOSITORY}/commits/main",
        ))["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        parser.error("revision must be a full Git commit SHA.")
    print(f"Official ESCI revision: {revision}", flush=True)
    metadata = {"repository": f"https://github.com/{REPOSITORY}", "revision": revision, "files": {}}
    for name in FILES:
        relative = f"shopping_queries_dataset/{name}"
        pointer_url = f"https://raw.githubusercontent.com/{REPOSITORY}/{revision}/{relative}"
        if existing and existing["revision"] == revision:
            info = existing["files"][name]
        else:
            pointer = fetch_bytes(pointer_url).decode("ascii")
            sha = re.search(r"oid sha256:([0-9a-f]{64})", pointer)
            size = re.search(r"size (\d+)", pointer)
            if not sha or not size:
                raise ValueError(f"Expected a Git LFS pointer for {name}.")
            info = {"sha256": sha.group(1), "bytes": int(size.group(1))}
        url = f"https://media.githubusercontent.com/media/{REPOSITORY}/{revision}/{relative}"
        download_verified(url, args.output_dir / name, info["sha256"], info["bytes"])
        metadata["files"][name] = {**info, "url": url}
    for name in ("LICENSE", "NOTICE"):
        destination = args.output_dir / name
        if not destination.exists() or not existing or existing["revision"] != revision:
            destination.write_bytes(fetch_bytes(
                f"https://raw.githubusercontent.com/{REPOSITORY}/{revision}/{name}",
            ))
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Source manifest: {metadata_path}", flush=True)


def main():
    parser, args = parse_arguments()
    download_dataset(args, parser)


if __name__ == "__main__":
    main()
