# Start the 40,000-example run in Google Colab


The generated notebook has been removed for now. Recreate it only when requested;
the instructions below apply after it is regenerated.
> Commands and artifact paths in this guide are relative to `backend/`, unless stated otherwise.

Use these two files from this project:

* Notebook: `notebooks/02_colab_data_training.ipynb`
* Prepared data and code: `colab/data_colab_bundle.zip` (about 54 MiB)

## Open the notebook

1. Go to [Google Colab](https://colab.research.google.com/).
2. Choose **File → Upload notebook** and select
   `02_colab_data_training.ipynb`.
3. Choose **Runtime → Change runtime type → GPU**. Select T4 if available,
   then save and connect. The first cell checks that CUDA is available.
4. Run the cells from top to bottom. Colab will ask you to authorize mounting
   your Google Drive and to upload `data_colab_bundle.zip`.
5. Run the training cell. It processes all **40,000 examples** in one epoch:
   20,000 English Exact query–product pairs plus 20,000 generated typo variants.

The local partial training checkpoint is excluded from the upload. This starts
a fresh cloud run from the original MiniLM. No training runs on your Mac when
you execute the notebook in a Colab hosted GPU runtime.

The supplied ZIP includes the prepared catalog, labels, training code, tests,
and Amazon's license and notice. You do not need to clone the GitHub repository
or download the original 1 GB product file. The notebook verifies the bundle's
checksum and each packaged file before training.

## If Colab rejects the ZIP upload

**File → Upload notebook** accepts the `.ipynb` notebook, not the data ZIP.
Open `02_colab_data_training.ipynb` there first. The ZIP belongs in the
file picker shown by notebook cell 3.

You can also bypass that picker using Google Drive:

1. Open Google Drive and create `semantic-product-search` inside **My Drive**.
2. Open that folder and use **New → File upload** to upload
   `data_colab_bundle.zip`. Keep the filename unchanged.
3. In Colab, run cells 1 and 2 and authorize Drive access.
4. Run cell 3. It automatically reads the ZIP from Drive and verifies it.
5. Continue running the remaining cells in order.

The expected location is
`My Drive/backend/data_colab_bundle.zip`.

## Where outputs are saved

The notebook creates a dedicated Google Drive folder:

```text
MyDrive/backend/
  data_colab_bundle.zip
  models/esci-minilm-20k/
    checkpoints/latest.pt
    training_report.json
    ...trained model files...
  reports/esci-minilm-20k/
    validation_metrics.json
    selection.json
    test_metrics.json
  data_minilm_model.zip
```

Training uses batch size 32, sequence length 128, and one epoch (1,250 steps).
It writes a resumable checkpoint every 100 steps and reports the estimated
remaining time every 25 steps. The early estimate includes setup overhead;
use the estimate after 50–100 steps to judge the remaining time.

## If Colab disconnects

Reconnect to a GPU and rerun cells 1–6 with the same `RUN_NAME` and settings.
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

The final cell downloads `data_minilm_model.zip` and saves a copy in Drive.
That download includes deployable weights and reports, excluding the large
optimizer checkpoints.

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
