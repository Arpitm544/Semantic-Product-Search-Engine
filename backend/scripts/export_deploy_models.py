"""Package only inference models with a verified Atlas generation binding."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import PROJECT_ROOT
from src.data.catalog import database, version
from src.semantic.identity import vector_generation, model_digest


def export(destination):
    catalog = version()
    encoder = (PROJECT_ROOT / os.getenv('SEMANTIC_MODEL_PATH', 'models/colab-export/esci-minilm-20k')).resolve()
    reranker = (PROJECT_ROOT / os.getenv('RERANKER_MODEL_PATH', 'models/ms-marco-MiniLM-L6-v2')).resolve()
    generation = vector_generation(str(encoder), catalog['sha256'])
    manifest = database()['vector_manifests'].find_one({'_id': generation})
    if not manifest or manifest.get('status') != 'ready' or manifest.get('catalog_sha256') != catalog['sha256']:
        raise ValueError('The current encoder/catalog has no ready Atlas generation.')
    binding = {'generation': generation, 'catalog_sha256': catalog['sha256'],
               'model_sha256': model_digest(encoder)}
    with tarfile.open(destination, 'w:gz') as archive:
        for folder, target in [(encoder, 'models/colab-export/esci-minilm-20k'),
                               (reranker, 'models/ms-marco-MiniLM-L6-v2')]:
            for path in sorted(folder.rglob('*')):
                if (path.is_file() and not any(p.startswith('.') for p in path.relative_to(folder).parts)
                        and path.name not in {'atlas_generation.json', 'README.md', 'progress.json', 'training_report.json'}):
                    archive.add(path, arcname=target + '/' + path.relative_to(folder).as_posix(), recursive=False)
        payload = json.dumps(binding).encode()
        info = tarfile.TarInfo('models/colab-export/esci-minilm-20k/atlas_generation.json')
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    with Path(destination).open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(stream.read()).hexdigest()
    print('Artifact:', destination)
    print('SHA256:', digest)
    print('Atlas generation:', generation)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    export(parser.parse_args().destination)
