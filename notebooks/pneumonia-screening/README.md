# From chest X-ray pixels to a review queue

Teaching notebook for **ITAI 2372 - Module 3**. It follows the same five-stage structure
as the Session 2 fraud case, then places the image-model score inside a bounded healthcare
workflow.

| | Stage | What happens |
|---|---|---|
| 1 | **Data Ingestion** | Verify provenance, labels, checksum, and source splits |
| 2 | **Image EDA and Preparation** | Inspect pixels, tensors, augmentation, and quality routing |
| 3 | **Model Training** | Expose the majority baseline and train a compact CNN |
| 4 | **Model Validation** | Select a cutoff on validation data, then evaluate untouched test data |
| 5 | **Model Prediction** | Create the queue, influence overlay, and app artifacts |

## Safety boundary

This is an educational workflow demonstration, not a diagnostic system. It accepts no
arbitrary image upload. The model ranks packaged benchmark examples for **priority review**
or **standard review**. A radiologist still interprets every study, and a clinician retains
authority over diagnosis and treatment.

## Run it

In a Codespace, open `01_pneumonia_build.ipynb`, select `.venv/bin/python`, and run all
cells. The source archive is committed, so the notebook does not download data during
class.

Locally, from the repository root:

```bash
npm run setup:notebook
```

Then open the notebook with the `.venv` interpreter. The latest validated CPU run takes
about three minutes, including training, artifact export, and reload verification.

To regenerate the notebook source or prepare the app artifacts without changing notebook
outputs:

```bash
node scripts/venv-python.mjs notebooks/pneumonia-screening/scripts/build_notebook.py
node scripts/venv-python.mjs notebooks/pneumonia-screening/scripts/prepare_app_artifacts.py
```

## Package layout

```text
01_pneumonia_build.ipynb   Executed teaching notebook
pneumonialab/              Shared data, model, metrics, charts, and handoff logic
data/                      Checksum-verified PneumoniaMNIST 128 archive
artifacts/                 Reproducible model and app contract; generated locally
backup/                    Standalone offline HTML
scripts/                   Notebook, artifact, and backup builders
```

The final notebook cells export `model.pt`, `model_card.json`, `operating_policy.json`,
`evaluation.json`, and `sample_manifest.parquet`. The app service loads those exact files.

## Data provenance

- Dataset: [MedMNIST v2](https://medmnist.com/), PneumoniaMNIST 128
- Record: [Zenodo 10519652](https://zenodo.org/records/10519652)
- License: CC BY 4.0 as stated by MedMNIST
- Source archive MD5: `05b46931834c231683c68f40c47b2971`
- Population: pediatric chest X-rays represented by the source study
- Use boundary: MedMNIST states that the benchmark is not intended for clinical use

The source study reports patient separation between its training and test sets. The
notebook preserves the published train, validation, and test arrays.