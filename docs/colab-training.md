# Start the 40,000-example run in Google Colab

> Commands and artifact paths in this guide are relative to `backend/`, unless stated otherwise.
> The shopping cross-encoder has a separate [reranker workflow](#fine-tune-and-calibrate-the-reranker).

## Prepare the bundle from a fresh checkout

The ZIP and prepared dataset are generated artifacts, not tracked files. From
`backend/`, create and activate the environment before downloading the official
Amazon ESCI data (roughly 1 GB; allow disk space for raw and prepared copies):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.semantic.download_esci
python -m src.semantic.prepare_esci --pairs 20000 --validation-queries 200 --test-queries 200 --seed 42
python scripts/create_colab_bundle.py
```

The downloader records its pinned revision and verifies source hashes. Reruns
reuse that revision; preparation refuses to overwrite an existing manifest.
Packaging regenerates the notebook with the matching ZIP checksum. Use the ZIP
and notebook generated together. Preparation runs locally; training runs in Colab.

Use these two generated files:

* Notebook: `notebooks/02_colab_esci_fine_tuning.ipynb`
* Prepared data and code: `colab/esci_colab_bundle.zip` (about 54 MiB)

## Open the notebook

1. Go to [Google Colab](https://colab.research.google.com/).
2. Choose **File → Upload notebook** and select
   `02_colab_esci_fine_tuning.ipynb`.
3. Choose **Runtime → Change runtime type → GPU**. Select T4 if available,
   then save and connect. The first cell checks that CUDA is available.
4. Run the cells from top to bottom. Colab will ask you to authorize mounting
   your Google Drive and to upload `esci_colab_bundle.zip`.
5. Run the training cell. It processes all **40,000 examples** in one epoch:
   20,000 English Exact query–product pairs plus 20,000 generated typo variants.

The local partial training checkpoint is excluded from the upload. This starts
a fresh cloud run from the original MiniLM. No training runs on your Mac when
you execute the notebook in a Colab hosted GPU runtime.

The generated ZIP includes the prepared catalog, labels, training code, tests,
and Amazon's license and notice. The Colab runtime does not need the raw download; the local preparation above does. The notebook verifies the bundle's
checksum and each packaged file before training.

## If Colab rejects the ZIP upload

**File → Upload notebook** accepts the `.ipynb` notebook, not the data ZIP.
Open `02_colab_esci_fine_tuning.ipynb` there first. The ZIP belongs in the
file picker under **3. Upload and verify the prepared bundle**.

You can also bypass that picker using Google Drive:

1. Open Google Drive and create `semantic-product-search` inside **My Drive**.
2. Open that folder and use **New → File upload** to upload
   `esci_colab_bundle.zip`. Keep the filename unchanged.
3. In Colab, run all cells through **2. Connect Google Drive** and authorize access.
4. Run all cells under **3. Upload and verify the prepared bundle** to read and verify the ZIP.
5. Continue running the remaining cells in order.

The expected location is
`My Drive/semantic-product-search/esci_colab_bundle.zip`.

## Where outputs are saved

The notebook creates a dedicated Google Drive folder:

```text
MyDrive/semantic-product-search/
  esci_colab_bundle.zip
  models/esci-minilm-20k/
    checkpoints/latest.pt
    training_report.json
    ...trained model files...
  reports/esci-minilm-20k/
    validation_metrics.json
    selection.json
    test_metrics.json
  esci_minilm_model.zip
```

Training uses batch size 32, sequence length 128, and one epoch. The verification cell reports the step count, which depends on group sizes.
It writes a resumable checkpoint every 100 steps and reports the estimated
remaining time every 25 steps. The early estimate includes setup overhead;
use the estimate after 50–100 steps to judge the remaining time.

## If Colab disconnects

Reconnect to a GPU and rerun all cells through **6. Train on the Colab GPU** with the same `RUN_NAME` and settings.
The bundle is reused from Drive, and training resumes from
`checkpoints/latest.pt`. A completed run is detected and is not trained again.

If you intentionally change batch size, learning rate, or sequence length,
change `RUN_NAME` to make a separate run. The trainer rejects incompatible
resume settings.

Colab's GPU availability and runtime limits vary. The official
[Colab FAQ](https://research.google.com/colaboratory/faq.html) documents uploads,
Google Drive access, and runtime behavior.

## After training

Run the validation cell, select a model using validation results, then run the
test comparison once. The reports separate clean and typo queries. Do not
compare these percentages directly with the earlier 194-product experiment;
this experiment uses a 42,617-product sampled Amazon corpus.

The final cell downloads `esci_minilm_model.zip` and saves a copy in Drive.
That download includes deployable weights and reports, excluding the large
optimizer checkpoints.

## Fine-tune and calibrate the reranker

From the same backend environment, download Amazon ESCI if needed, then prepare
the reranker bundle from the original judgments.

```bash
python -m src.semantic.download_esci
python scripts/create_reranker_bundle.py
```

Open `notebooks/03_colab_esci_reranker.ipynb` in Colab, select a T4 GPU runtime,
and run the cells in order. When prompted, upload
`colab/reranker/esci_reranker_bundle.zip`. You can also upload the ZIP through
Colab's Files sidebar before running the upload cell. Training starts from MS MARCO
MiniLM-L6-v2 and processes approximately 40,000 judged pairs from complete
query groups. Exact, Substitute, Complement, and Irrelevant training targets
are 1.0, 0.85, 0.65, and 0.0.

Platt scaling fits the single reranker logit on 400 separate calibration query
families. Its event is a judge labeling the pair Exact, Substitute, or
Complement. Another 400 families from the official test split supply the
reliability diagram, before/after Brier score, log loss, calibration error,
and the base versus fine-tuned nDCG@10 comparison. The report also shows
how many test pairs fall below 20% and how many of those actually were relevant.
These estimates describe judged English ESCI pairs. Live shopping traffic can
have a different mix of items and relevance.

Extract `esci-reranker` from the downloaded `esci_reranker_export.zip` to
`models/colab-export/esci-reranker` and restart the backend. Remove any existing
`RERANKER_MODEL_PATH` override or point it at that directory. The probability
mapping is stored in `calibration.json` beside the exact weights it was fitted
on. The deployment model exporter includes both. The encoder and Atlas
vector index do not need rebuilding.

Search exposes `relevanceProbability` between 0 and 1. Online shops keep
products at or above 20% when at least one clears the threshold. If every
product falls below 20%, the closest products stay visible with a notice.
System health uses the same threshold on the displayed results. With the
original reranker, the probability is null and a scored miss is unknown.

To use a selected model later, extract the `esci-minilm-20k` folder into this
project's `models/` directory, then start the API with:

```bash
SEMANTIC_MODEL_PATH=models/esci-minilm-20k python api/main.py
```

Review the evaluation results before choosing it over the original model.

## Rebuild the bundle after changing the code

From `backend/`:

```bash
python scripts/create_colab_bundle.py
```

This recreates the ZIP and notebook together, including matching checksums.
