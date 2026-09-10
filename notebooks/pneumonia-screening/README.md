# From chest X-ray pixels to a review queue

Teaching notebook for **ITAI 2372 - Module 3**. It follows the same five-stage CNN build
as the Session 2 fraud case, places the image-model score inside a bounded healthcare
workflow, and then adds a separate multimodal-LLM capability experiment.

| | Stage | What happens |
|---|---|---|
| 1 | **Data Ingestion** | Verify provenance, labels, checksum, and source splits |
| 2 | **Image EDA and Preparation** | Inspect pixels, tensors, augmentation, and quality routing |
| 3 | **Model Training** | Expose the majority baseline and train a compact CNN |
| 4 | **Model Validation** | Select a cutoff on validation data, then evaluate untouched test data |
| 5 | **Model Prediction** | Create the queue, influence overlay, and app artifacts |

After the measured build is complete, optional **Stage 6** sends one fixed packaged
priority-review example to a vision-capable model. The LLM does not receive the CNN score,
cutoff, route, or dataset label. Its generated interpretation attempt is compared with the
limited evidence available in this binary-label dataset.

## Safety boundary

This is an educational workflow demonstration, not a diagnostic system. It accepts no
arbitrary image upload. The CNN ranks packaged benchmark examples for **priority review**
or **standard review**. The optional multimodal section produces unverified language about
one packaged thumbnail and does not alter that route. A radiologist still interprets every
study, and a clinician retains authority over diagnosis and treatment.

## Run it

In a Codespace, open `01_pneumonia_build.ipynb`, select `.venv/bin/python`, and run all
cells. The source archive is committed, so the notebook does not download data during
class. Stage 6 defaults to a captured response, so it also runs without network access or
Copilot authentication.

Locally, from the repository root:

```bash
npm run setup:notebook
```

Then open the notebook with the `.venv` interpreter. The latest validated CPU run takes
about three minutes, including training, artifact export, and reload verification.

To try the optional live multimodal call, sign in to GitHub Copilot, confirm that the
selected model supports vision, and set `LIVE_MULTIMODAL_DEMO = True` in Stage 6. The
notebook sends only the fixed packaged course image. If the live request fails, it labels
the failure and uses the captured response for the same image and prompt.

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
artifacts/                 Validated model/app contract plus the captured LLM response
backup/                    Standalone offline HTML
scripts/                   Notebook, artifact, and backup builders
```

The final notebook cells export `model.pt`, `model_card.json`, `operating_policy.json`,
`evaluation.json`, and `sample_manifest.parquet`. The app service loads those exact files.
The validated bundle is versioned so Codespaces uses the same `0.748` cutoff and predictions
shown in the executed notebook. Run `npm run prepare:pneumonia` only when intentionally
rebuilding and revalidating that bundle.

`artifacts/multimodal_demo_response.json` is separate from the CNN deployment bundle. It
records the model, prompt version, sample ID, time, and exact generated sections used by the
captured classroom fallback. The pneumonia API and app do not load it.

## Data provenance

- Dataset: [MedMNIST v2](https://medmnist.com/), PneumoniaMNIST 128
- Record: [Zenodo 10519652](https://zenodo.org/records/10519652)
- License: CC BY 4.0 as stated by MedMNIST
- Source archive MD5: `05b46931834c231683c68f40c47b2971`
- Population: pediatric chest X-rays represented by the source study
- Use boundary: MedMNIST states that the benchmark is not intended for clinical use

The source study reports patient separation between its training and test sets. The
notebook preserves the published train, validation, and test arrays.