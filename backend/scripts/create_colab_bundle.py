"""Package the prepared 40k ESCI dataset and generate a Google Colab notebook."""

import hashlib
import json
from pathlib import Path
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data" / "dataset" / "prepared"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cell(kind, source):
    result = {"cell_type": kind, "id": hashlib.sha256((kind + source).encode()).hexdigest()[:12],
              "metadata": {}, "source": source.strip().splitlines(keepends=True)}
    result["source"] = [line if line.endswith("\n") else line + "\n" for line in result["source"]]
    if kind == "code":
        result.update(execution_count=None, outputs=[])
    return result


def notebook(bundle_sha):
    """Build the Colab cells in the order a user runs them."""
    cells = [
        cell("markdown", """# Fine tune MiniLM on all 40,000 Amazon ESCI examples

Open this notebook in Google Colab and choose **Runtime → Change runtime type → GPU**.
Then run the cells in order. Training and evaluation run on Google's computer.

Before opening Colab, follow the repository's `docs/colab-training.md` preparation
steps from a fresh checkout: install backend requirements, run
`python -m src.semantic.download_esci`,
`python -m src.semantic.prepare_esci --pairs 20000 --validation-queries 200 --test-queries 200 --seed 42`,
then `python scripts/create_colab_bundle.py` from `backend/`.
Use the regenerated notebook and `colab/esci_colab_bundle.zip` together; the ZIP
is generated locally and is not included in the repository.

The bundle contains 20,000 human-labeled English Exact pairs, 20,000 typo views,
and labeled Irrelevant negatives. Validation and official test query families
are separate. This starts a fresh one-epoch cloud run from the original MiniLM.

Model weights and resumable checkpoints are saved in your Google Drive.
GPU availability and runtime limits vary: [Colab FAQ](https://research.google.com/colaboratory/faq.html).
Data source: [Amazon ESCI](https://github.com/amazon-science/esci-data), Apache-2.0.
"""),
        cell("markdown", "## 1. Verify the cloud GPU\nIf this cell fails, select a GPU runtime before proceeding."),
        cell("code", """import torch
assert torch.cuda.is_available(), "Choose Runtime → Change runtime type → GPU, then reconnect."
print("GPU:", torch.cuda.get_device_name(0))
print("GPU memory (GB):", round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1))
"""),
        cell("markdown", """## 2. Connect Google Drive
Authorize access when Colab asks. The notebook stores its bundle, models, and reports
in a dedicated `MyDrive/semantic-product-search` folder. Change RUN_NAME for a new
experiment. Keep the same name to resume a disconnected run.
"""),
        cell("code", """from google.colab import drive
from pathlib import Path
import json, os, shutil, subprocess, sys, zipfile, hashlib

drive.mount("/content/drive")
RUN_NAME = "esci-minilm-20k"
DRIVE_ROOT = Path("/content/drive/MyDrive/semantic-product-search")
DRIVE_ROOT.mkdir(parents=True, exist_ok=True)
MODEL_DIR = DRIVE_ROOT / "models" / RUN_NAME
REPORTS_DIR = DRIVE_ROOT / "reports" / RUN_NAME
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
PROJECT = Path("/content/esci_runtime/semantic-product-search")
DATA_DIR = PROJECT / "data/dataset/prepared"
"""),
        cell("markdown", """## 3. Upload and verify the prepared bundle
Upload **esci_colab_bundle.zip** when the file picker opens. On reconnect, the
verified copy in Drive is reused. Extraction happens on the Colab VM for fast reads.
The original 1 GB download is already processed and is not needed here.
"""),
        cell("code", """from google.colab import files

EXPECTED_SHA256 = "__BUNDLE_SHA__"
BUNDLE_NAME = "esci_colab_bundle.zip"
drive_bundle = DRIVE_ROOT / BUNDLE_NAME
runtime_bundle = Path("/content") / BUNDLE_NAME
if not drive_bundle.exists():
    uploaded = files.upload()
    assert BUNDLE_NAME in uploaded, "Upload the generated esci_colab_bundle.zip."
    shutil.copy2(runtime_bundle, drive_bundle)
    del uploaded
else:
    shutil.copy2(drive_bundle, runtime_bundle)

def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

assert file_hash(runtime_bundle) == EXPECTED_SHA256, "Wrong bundle. Replace the ZIP in Drive with the newly generated file."
extract_root = PROJECT.parent
extract_root.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(runtime_bundle) as archive:
    for member in archive.infolist():
        destination = (extract_root / member.filename).resolve()
        assert destination.is_relative_to(extract_root.resolve()), "Unsafe archive path."
    archive.extractall(extract_root)
bundle_manifest = json.loads((PROJECT / "colab_bundle_manifest.json").read_text())
for relative, expected in bundle_manifest["sha256"].items():
    assert file_hash(PROJECT / relative) == expected, f"File verification failed: {relative}"
os.chdir(PROJECT)
print("Code and data verified:", PROJECT)
""".replace("__BUNDLE_SHA__", bundle_sha)),
        cell("markdown", "## 4. Install the training libraries\nThe runtime's CUDA-enabled PyTorch is kept."),
        cell("code", """subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "sentence-transformers==5.1.2", "transformers>=4.41,<5",
    "faiss-cpu>=1.7.4,<2", "rapidfuzz>=3,<4", "pymongo>=4.6,<5", "pytest>=7,<9",
    "python-dotenv>=1,<2"
], check=True)
sys.path.insert(0, str(PROJECT))
"""),
        cell("markdown", """## 5. Verify all 40,000 examples and the split
This checks query leakage and relevant-product protection before training.
It confirms that batching uses every example and prints the number of steps per epoch.
"""),
        cell("code", """from src.semantic.dataset import read_jsonl, catalog_fingerprint, grouped_batches
from src.semantic.train_esci import validate_training_rows

manifest = json.loads((DATA_DIR / "manifest.json").read_text())
rows = read_jsonl(DATA_DIR / "train.jsonl")
held = read_jsonl(DATA_DIR / "validation.jsonl") + read_jsonl(DATA_DIR / "test.jsonl")
validate_training_rows(rows, manifest, held)
products = json.loads((DATA_DIR / "products.json").read_text())
assert catalog_fingerprint(products) == manifest["catalog_sha256"]
assert len(rows) == 40000 and manifest["clean_training_pairs"] == 20000
batches = grouped_batches(rows, 32, manifest["seed"], include_remainder=True)
assert sum(map(len, batches)) == 40000
print("Clean pairs:", manifest["clean_training_pairs"])
print("Training examples:", len(rows), "| Steps:", len(batches))
print("Product catalog:", len(products))
del rows, held, products, batches
subprocess.run([sys.executable, "-m", "pytest",
    "tests/test_esci_training.py", "tests/test_typo_search.py", "tests/test_keyword_search.py", "-q"
], check=True)
"""),
        cell("markdown", """## 6. Train on the Colab GPU
One epoch processes all 40,000 examples. Checkpoints are saved to Drive every
100 steps. After reconnecting, rerun cells 1–6 to resume automatically.

The time estimate becomes more useful after 50–100 steps. Keep the default
settings unchanged when resuming. If GPU memory is insufficient, choose a new
RUN_NAME and restart with a smaller batch size; that still trains on all examples.
"""),
        cell("code", """import signal

def run_command(command):
    process = subprocess.Popen(command, cwd=PROJECT, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1)
    try:
        for line in process.stdout:
            print(line, end="", flush=True)
        code = process.wait()
    except KeyboardInterrupt:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            print("The process is still finishing its current operation; retain the latest Drive checkpoint.")
        raise
    if code:
        raise RuntimeError(f"Command exited with status {code}. Review its output above.")

expected_run = {
    "dataset_manifest_sha256": file_hash(DATA_DIR / "manifest.json"),
    "dataset_files_sha256": {name: file_hash(DATA_DIR / name)
        for name in ("train.jsonl", "validation.jsonl", "test.jsonl")},
    "base_model": "all-MiniLM-L6-v2", "epochs": 1, "batch_size": 32,
    "learning_rate": 0.00002, "max_length": 128, "seed": manifest["seed"],
    "source_revision": manifest["source_revision"],
}
# A changed bundle (including training code) needs a separate run directory.
run_identity = {"bundle_sha256": EXPECTED_SHA256, "config": expected_run}
identity_file = MODEL_DIR / "run_identity.json"
if MODEL_DIR.exists() and any(MODEL_DIR.iterdir()):
    assert identity_file.exists(), "Unverified old run; choose a new RUN_NAME."
    assert json.loads(identity_file.read_text()) == run_identity, "Bundle/settings changed; choose a new RUN_NAME."
MODEL_DIR.mkdir(parents=True, exist_ok=True)
identity_file.write_text(json.dumps(run_identity, indent=2))
report_file = MODEL_DIR / "training_report.json"
already_complete = (MODEL_DIR / "modules.json").exists() and report_file.exists()
if already_complete:
    report = json.loads(report_file.read_text())
    assert all(report.get(key) == value for key, value in expected_run.items()), "Saved configuration changed; choose a new RUN_NAME."
    assert report["status"] == "trained" and report["trained_examples"] == 40000
    print("This run is already complete. Proceed to evaluation.")
else:
    command = [sys.executable, "-u", "-m", "src.semantic.train_esci",
        "--data-dir", str(DATA_DIR), "--output-dir", str(MODEL_DIR),
        "--device", "cuda", "--epochs", "1", "--batch-size", "32",
        "--max-length", "128", "--learning-rate", "0.00002",
        "--threads", "2", "--checkpoint-every", "100"]
    if (MODEL_DIR / "checkpoints/latest.pt").exists():
        command.append("--resume")
    run_command(command)
    report = json.loads(report_file.read_text())
    assert all(report.get(key) == value for key, value in expected_run.items()), "Saved configuration changed; choose a new RUN_NAME."
    assert report["status"] == "trained" and report["trained_examples"] == 40000
    print("Completed:", report["trained_examples"], "examples on", report["device"])
"""),
        cell("markdown", """## 7. Evaluate clean and misspelled validation queries
This compares keyword, fuzzy, original semantic, and trained semantic search on
the same 42,617-product sampled corpus. Labels are incomplete outside the judged
candidate lists, and typo variants are generated. These are benchmark results,
not a guarantee of real shopper accuracy.
"""),
        cell("code", """VALIDATION_REPORT = REPORTS_DIR / "validation_metrics.json"
run_command([sys.executable, "-u", "-m", "src.semantic.evaluate_typos",
    "--data-dir", str(DATA_DIR), "--catalog", str(DATA_DIR / "products.json"),
    "--model", str(MODEL_DIR), "--split", "validation", "--device", "cuda",
    "--output", str(VALIDATION_REPORT)])
validation = json.loads(VALIDATION_REPORT.read_text())
for system, buckets in validation["metrics"].items():
    print(system, {kind: buckets[kind] for kind in ("clean", "typo")})
"""),
        cell("markdown", """## 8. Select on validation, then run the test comparison once
The example rule below recommends the candidate only when typo ranking improves
and clean-query recall drops by no more than one percentage point. Selection
uses validation data. Do not tune settings against the test results.
"""),
        cell("code", """base = validation["metrics"]["base-hybrid"]
candidate = validation["metrics"]["fine-tuned-hybrid"]
recommend_candidate = (
    candidate["typo"]["mrr@10"] > base["typo"]["mrr@10"]
    and candidate["clean"]["recall@5"] >= base["clean"]["recall@5"] - 0.01
)
print("Validation recommendation:", "fine tuned model" if recommend_candidate else "original model")
selection = {"recommended_model": "fine-tuned" if recommend_candidate else "base",
             "selection_source": "validation", "candidate_path": str(MODEL_DIR)}
(REPORTS_DIR / "selection.json").write_text(json.dumps(selection, indent=2))
TEST_REPORT = REPORTS_DIR / "test_metrics.json"
if TEST_REPORT.exists():
    print("Existing test report retained; read it below.")
else:
    run_command([sys.executable, "-u", "-m", "src.semantic.evaluate_typos",
        "--data-dir", str(DATA_DIR), "--catalog", str(DATA_DIR / "products.json"),
        "--model", str(MODEL_DIR), "--split", "test", "--device", "cuda",
        "--output", str(TEST_REPORT)])
test_results = json.loads(TEST_REPORT.read_text())
for system, buckets in test_results["metrics"].items():
    print(system, {kind: buckets[kind] for kind in ("clean", "typo")})
"""),
        cell("markdown", """## 9. Download the model and reports
The ZIP contains deployable weights, tokenizer files, and reports. Optimizer
checkpoints remain in Drive for resuming and are excluded from this download.
After downloading, extract `esci-minilm-20k` into your project's `models/` folder.
Use `SEMANTIC_MODEL_PATH=models/esci-minilm-20k` when starting the API after
reviewing the results.
"""),
        cell("code", """download_zip = Path("/content/esci_minilm_model.zip")
with zipfile.ZipFile(download_zip, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in MODEL_DIR.rglob("*"):
        relative = path.relative_to(MODEL_DIR)
        if path.is_file() and "checkpoints" not in relative.parts:
            archive.write(path, str(Path("esci-minilm-20k") / relative))
    for path in REPORTS_DIR.glob("*.json"):
        archive.write(path, str(Path("reports") / path.name))
shutil.copy2(download_zip, DRIVE_ROOT / download_zip.name)
print("Saved to Drive:", DRIVE_ROOT / download_zip.name)
files.download(str(download_zip))
"""),
    ]
    return {
        "nbformat": 4, "nbformat_minor": 5, "cells": cells,
        "metadata": {"colab": {"name": "02_colab_esci_fine_tuning.ipynb"},
                     "accelerator": "GPU", "kernelspec": {"display_name": "Python 3", "name": "python3"}},
    }


def main():
    if not (DATA / "manifest.json").exists():
        raise SystemExit("Prepare the bundle inputs first: python -m src.semantic.download_esci; "
                         "python -m src.semantic.prepare_esci --pairs 20000. "
                         "See docs/colab-training.md from the repository root.")
    manifest = json.loads((DATA / "manifest.json").read_text())
    if manifest["clean_training_pairs"] != 20000 or manifest["augmented_training_pairs"] != 40000:
        raise ValueError("This notebook is configured for the prepared 20k + 20k dataset.")
    # Include source, tests, API files, prepared data, and dataset license.
    paths = sorted((PROJECT / "src").rglob("*.py"))
    paths += sorted((PROJECT / "tests").rglob("*.py"))
    paths += sorted((PROJECT / "api").glob("*.py"))
    paths += [PROJECT / "requirements.txt"]
    paths += [DATA / name for name in ("manifest.json", "train.jsonl", "validation.jsonl", "test.jsonl", "products.json")]
    paths += [PROJECT / "data/dataset/raw" / name for name in ("LICENSE", "NOTICE", "source.json")]
    # Hash every input so the notebook can verify the uploaded bundle.
    hashes = {path.relative_to(PROJECT).as_posix(): sha256(path) for path in paths}
    directory = PROJECT / "colab"
    directory.mkdir(exist_ok=True)
    bundle = directory / "esci_colab_bundle.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in paths:
            archive.write(path, (Path("semantic-product-search") / path.relative_to(PROJECT)).as_posix())
        archive.writestr("semantic-product-search/colab_bundle_manifest.json",
                         json.dumps({"sha256": hashes, "source_revision": manifest["source_revision"]}, indent=2))
    bundle_sha = sha256(bundle)
    # Keep the notebook and ZIP together by recording the ZIP hash in a cell.
    notebook_path = PROJECT / "notebooks" / "02_colab_esci_fine_tuning.ipynb"
    notebook_path.parent.mkdir(exist_ok=True)
    notebook_path.write_text(json.dumps(notebook(bundle_sha), indent=2) + "\n")
    report = {"bundle": str(bundle), "sha256": bundle_sha, "bytes": bundle.stat().st_size,
              "files": len(paths), "notebook": str(notebook_path)}
    (directory / "bundle_build_manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
