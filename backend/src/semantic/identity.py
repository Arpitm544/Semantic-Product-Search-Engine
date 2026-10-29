"""Identify Atlas vector generations by catalog and local encoder checkpoint."""
import hashlib
from pathlib import Path


def vector_generation(model_path, catalog_hash):
    model_dir = Path(model_path)
    weights = sorted(path for pattern in ("*.safetensors", "pytorch_model*.bin", "*.index.json")
                     for path in model_dir.rglob(pattern))
    if not weights:
        raise FileNotFoundError(f"No supported checkpoint weights in {model_dir}")
    fingerprint = [(str(path.relative_to(model_dir)), path.stat().st_size,
                    path.stat().st_mtime_ns) for path in weights]
    identity = catalog_hash + str(model_path) + repr(fingerprint)
    return hashlib.sha256(identity.encode()).hexdigest()
