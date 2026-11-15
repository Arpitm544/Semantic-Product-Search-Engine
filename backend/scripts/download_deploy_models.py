"""Download and verify the exported inference models during a Render build."""
import hashlib
import os
from pathlib import Path
import tarfile
import tempfile
from urllib.request import urlopen


def main():
    url = os.environ['MODEL_ARTIFACT_URL']
    expected = os.environ['MODEL_ARTIFACT_SHA256']
    if not url.startswith('https://'):
        raise ValueError('Model artifact URL must use HTTPS.')
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / 'models.tar.gz'
        digest = hashlib.sha256()
        with urlopen(url, timeout=120) as response, archive.open('wb') as target:
            for block in iter(lambda: response.read(1024 * 1024), b''):
                digest.update(block)
                target.write(block)
        if digest.hexdigest() != expected:
            raise ValueError('Model artifact checksum mismatch.')
        with tarfile.open(archive) as source:
            for member in source.getmembers():
                parts = Path(member.name).parts
                if (not parts or parts[0] != 'models' or '..' in parts
                        or member.name.startswith('/') or member.issym() or member.islnk()):
                    raise ValueError('Unsafe model archive entry.')
            source.extractall('.', filter='data')
    print('Verified deployment models installed.')


if __name__ == '__main__':
    main()
