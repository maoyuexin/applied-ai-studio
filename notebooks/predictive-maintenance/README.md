# Predictive Maintenance Lab — Compressor Health Monitoring

ITAI 2372 Module 5, Case 1. Instructor-led demonstration; students rerun later in Codespaces.

## The case

A transit depot's maintenance team can service only a few units each week. This lab scores an
air compressor's sensor behavior hour by hour and raises a work order when the machine is
working too hard to hold pressure.

**Claim boundary — read this before using any number here.** The system **detects a fault that
is developing now, within hours. It does not forecast failure days ahead.** That boundary was
set by measurement, not preference: of the four documented failures in this record, three give
no usable advance warning. The system also never locks out equipment and never certifies a
machine as safe — a technician inspects and decides.

## The data

Real air production unit (compressor) telemetry from a Metro do Porto train, published by the
UCI Machine Learning Repository as **MetroPT-3** (dataset 791) under **CC BY 4.0**.

- 1,516,948 raw readings, 2020-02-01 to 2020-09-01, 15 sensors
- Sampling is roughly every 10 seconds and **irregular** — UCI's "1 Hz" description is incorrect
- Committed here as 1-minute means: `data/metropt_1min.parquet`, about 4.9 MB
- **Only 4,216 of the 5,116 hours can be scored (82.4%)** — 700 hours carry no reading at all, the
  equivalent of 904 hours is missing across 331 recorder gaps, and those gaps fall inside
  pre-onset windows (of the 24 hours before each failure: F1 20, F2 20, F3 24, F4 18)
- Four documented air-leak failures are the only ground truth; there are no row labels

Sensors in plain language: motor current (about 0 A off, 4 A idling, 7 A working hard), the
compressor and panel pressures in bar, oil temperature in Celsius, and digital flags for the
valves, dryer towers, and low-pressure switch.

## How to view or run it

**No installation.** Open `backup/01_pdm_build.html` in any browser. It is self-contained,
works offline, and shows the committed run with every figure rendered.

**To rerun the source notebook**, from the repository root:

```bash
npm run setup:pdm        # installs the service and lab dependencies
npm run prepare:pdm      # rebuilds artifacts/ from the committed data
```

Then open `01_pdm_build.ipynb`. It executes end to end in well under a minute and needs no
network. Nothing downloads at setup or during class.

## What is in here

| Path | What it is |
|---|---|
| `01_pdm_build.ipynb` | The executed teaching notebook, five stages, outputs committed |
| `backup/01_pdm_build.html` | The same notebook as a self-contained offline page |
| `pdmlab/` | The lab package: config, data, features, detection, metrics, policy, charts, handoff |
| `data/metropt_1min.parquet` | The committed 1-minute dataset |
| `scripts/build_dataset.py` | Rebuilds the parquet from the raw UCI download (run once, not at setup) |
| `scripts/build_notebook.py` | Generates the notebook — **the canonical source; edit this, not the .ipynb** |
| `scripts/make_backup.py` | Produces the offline HTML |
| `scripts/prepare_app_artifacts.py` | Headless artifact build for the web app |
| `artifacts/` | Exported model, model card, evaluation, operating policy, sample manifest (gitignored; regenerate with `prepare:pdm`) |

## The exported contract

The demo service loads these exact files, so it scores with the same model the notebook trained:

- `model.joblib` — the detector and its baseline statistics
- `operating_policy.json` — the alert threshold, the routes, the cost assumptions, and the
  boundary statement
- `evaluation.json` — every measured number the notebook prints, including the drift table and
  the frozen test result
- `model_card.json`, `sample_manifest.parquet` — model facts and the packaged demo windows

## Honest limitations, which are also the lesson

- **Four events cannot support a confident accuracy figure.** The notebook deliberately refuses
  to print one.
- **The operating regime drifts hard.** The compressor ran about 37% of the time in February and
  about 55% by July. A threshold tuned in spring floods the queue by summer for reasons that have
  nothing to do with failure.
- **The "clean" training window is not clean.** Dozens of hours in it score above the alert
  threshold. We call them normal only because nobody filed a work order.
- **The dollar figures are classroom assumptions**, clearly labeled as such. They are not
  measured costs from Metro do Porto.

## Attribution

Veloso, Ribeiro, Gama, Pereira — MetroPT-3 dataset, UCI Machine Learning Repository (CC BY 4.0).
This lab is educational. It is not a validated maintenance system for any real equipment.
