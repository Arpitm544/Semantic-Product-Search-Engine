"""Download the official Amazon SDK; no credentials are read or printed."""
import io
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

root = Path(__file__).resolve().parents[1] / 'vendor'
root.mkdir(exist_ok=True)
url = 'https://affiliate-program.amazon.com/creatorsapi/docs/assets/sdk-archived/creatorsapi-python-sdk.zip'
with urllib.request.urlopen(url, timeout=30) as response:
    archive = zipfile.ZipFile(io.BytesIO(response.read()))
for item in archive.infolist():
    if not (root / item.filename).resolve().is_relative_to(root.resolve()):
        raise ValueError('Unsafe SDK archive path.')
archive.extractall(root)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-r',
                str(root / 'creatorsapi-python-sdk/requirements.txt')], check=True)
print('Official Amazon SDK installed.')
