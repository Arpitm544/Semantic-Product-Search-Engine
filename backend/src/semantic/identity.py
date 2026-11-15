"""Identify Atlas vector generations by catalog and local encoder checkpoint."""
import hashlib
import json
from pathlib import Path


def vector_generation(model_path, catalog_hash):
    model_dir = Path(model_path)
    deployment = model_dir / 'atlas_generation.json'
    if deployment.exists():
        manifest = json.loads(deployment.read_text())
        if manifest.get('catalog_sha256') != catalog_hash:
            raise ValueError('Model artifact belongs to another catalog. Re-export the deployment models.')
        if model_digest(model_dir) != manifest.get('model_sha256'):
            raise ValueError('Deployment model content differs from the indexed encoder.')
        generation = manifest['generation']
        if len(generation) != 64 or any(c not in '0123456789abcdef' for c in generation):
            raise ValueError('Invalid Atlas generation in model artifact.')
        return generation
    weights = sorted(path for pattern in ("*.safetensors", "pytorch_model*.bin", "*.index.json")
                     for path in model_dir.rglob(pattern))
    if not weights:
        raise FileNotFoundError(f"No supported checkpoint weights in {model_dir}")
    fingerprint = [(str(path.relative_to(model_dir)), path.stat().st_size,
                    path.stat().st_mtime_ns) for path in weights]
    identity = catalog_hash + str(model_path) + repr(fingerprint)
    return hashlib.sha256(identity.encode()).hexdigest()


def model_digest(model_dir):
    """Fingerprint inference files without depending on paths or timestamps."""
    digest = hashlib.sha256()
    paths = sorted(p for p in Path(model_dir).rglob('*') if p.is_file()
                   and not any(part.startswith('.') for part in p.relative_to(model_dir).parts)
                   and p.name not in {'atlas_generation.json', 'README.md', 'progress.json', 'training_report.json'})
    for path in paths:
        digest.update(path.relative_to(model_dir).as_posix().encode() + b'\0')
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
    return digest.hexdigest()
