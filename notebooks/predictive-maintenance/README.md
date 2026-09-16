# Predictive Maintenance Lab — Compressor Health Monitoring

ITAI 2372 Module 5, Case 1. Instructor-led demonstration; students rerun later in Codespaces.

## Undergraduate walkthrough (2026-09-16)

The instructor requested the teaching style of the Module 2 fraud and Module 3 pneumonia
notebooks, with **anomaly detection** as the central problem. After a complete cell-by-cell
review, the notebook has **58 cells, 24 short code cells (at most 12 lines), seven plots,
and about 4,090 explanation words**.
Each stage asks a question, runs small experiments, interprets their outputs, and states what
the evidence changes. It assumes little or no data-science experience.

1. **Data Ingestion:** raw rows, source-column profile, incomplete event labels, coverage, and time split.
2. **EDA and Feature Engineering:** minute-to-hour calculations and a two-feature view of reference behavior.
3. **Model Training:** fit and compare the robust-score baseline and Isolation Forest without target labels.
4. **Model Validation:** draw and freeze the selected model's cutoff, inspect test results and report alignment, then ask two practical
  questions: is there time to respond, and is review work manageable? The four-box plot is not fault accuracy.
5. **Model Prediction:** an aligned score/cutoff, model-flag, and reported-event timeline; test-period examples;
  incoming-hour replay; measured feature context; missing-data hold; and an assumed-cost comparison.

After instructor review, former Sections 4.4-4.6 are consolidated into **4.4 Does the alert help
a person?** The extra alert scatter, relative-time plot, and monthly drift plot are omitted
from the teaching path; their helpers remain available. A simple time table preserves the
13.5-hour potential-notice example, and a short paragraph retains the monitoring lesson.
Section 5.1 preserves the interactive date-based timeline and hourly prediction/report table,
with Example days and Full test views. Missing scores remain gaps; no report is not proof of health.

The cell-by-cell review corrected a sequencing problem: the older draft drew an Isolation Forest
cutoff before selecting the model. Stage 3 now finishes with the detector comparison and selection;
Stage 4 begins by drawing the selected forest's cutoff. The replacement chart orders validation
hours by their actual April-June date, shows one horizontal cutoff line, and colors the 36 flagged hours red.
Its table states the exact rules: 1,729 hours below the line receive no flag, while 36 hours at or
above 0.6792839227835988 request review. Scores remain unusualness values, not probabilities.

Section 5.3 now answers **"What looked different in this flagged hour?"** with a six-row table
in percentages, starts, minutes, Celsius, bar, and bar/min. It compares the selected hour with
the middle-half training range using plain higher/lower/within-range language. The unnecessary
"typical middle" column and former IQR-unit plot were removed. This table supplies investigation context; it is not feature importance,
Isolation Forest attribution, or a fault diagnosis.

Section 2.2 defines working time as **working-hard minutes / recorded minutes x 100**.
For example, 30 of 60 minutes means 50%, not a failure probability. The scatter axis now says
"Compressor working (%)"; the original feature values and model calculations are unchanged.

**Teaching model:** scikit-learn Isolation Forest, 300 trees, up to 256 reference rows per tree,
seed 42. Negated `score_samples` makes higher scores more anomalous. No failure labels enter fitting.
At the same approximately 2% validation alert allowance, both candidates flag 36 hours:
the baseline finds two reported events with zero false callouts; Isolation Forest finds three
with seven false callouts. The stated selection priority is event detection, then review burden.
This narrow comparison is not a claim that Isolation Forest is generally superior.

The selected validation cutoff is **0.6792839227835988**. On the later test period it flags
27 of 1,224 usable hours, finds the one reported event, and produces four false callouts
(1.96/month). F4's recorded lead is 14.5 hours, or 13.5 after waiting for the hourly aggregate,
before communication and intervention delays. Under the explicitly synthetic costs, the test
period costs **6,800 USD versus 5,400 USD** for no alerts; the unfavorable result stays visible.

The notebook **does not write app artifacts**. The application still uses its old robust-score
detector and cutoff 6.0, not this forest. The final notebook check proves the old saved baseline
is unchanged and that scoring one incoming hour reproduces the new forest's batch score.
The app and slides have not been redesigned as part of this teaching refresh.
The former long builder is retained as `scripts/build_reference_notebook.py`, historical
instructor reference, not the default teaching path. It generates a separately named notebook
under `backup/`; its older narrative has not been re-reviewed, and executing it can export artifacts.

## The case

A transit depot's maintenance team can service only a few units each week. This lab scores an
air compressor's sensor behavior hour by hour and raises a work order when the machine is
working too hard to hold pressure.

**Claim boundary:** the model flags operation that is unusual relative to its training
reference. Unusual does not mean broken, and unflagged does not mean confirmed healthy.
The available reports are incomplete ground truth. This notebook does not establish general
fault-detection accuracy or day-ahead forecasting. A technician investigates; no model output
authorizes work, stops equipment, or certifies safety.

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
```

Then open `01_pdm_build.ipynb`. It executes end to end in well under a minute and needs no
network once dependencies and data are present. Setup may download dependencies.
Existing `artifacts/` must be available for the final identity check. `npm run prepare:pdm`
is an app-artifact rebuild operation, not part of the classroom walkthrough.

To rebuild the teaching files from the repository root:

```bash
node scripts/venv-python.mjs notebooks/predictive-maintenance/scripts/build_notebook.py
node scripts/venv-python.mjs -m nbconvert --to notebook --execute --inplace notebooks/predictive-maintenance/01_pdm_build.ipynb
node scripts/venv-python.mjs notebooks/predictive-maintenance/scripts/make_backup.py
```

The builder preserves outputs only for unchanged source cells. The exporter requires every
code cell to be executed successfully and all seven charts to be present.

Focused checks from the repository root:

```bash
node scripts/venv-python.mjs -m pytest notebooks/predictive-maintenance/tests/test_anomaly_teaching.py notebooks/procedure-assistant/tests/test_teaching.py -q
```

They check validation-only selection, recorded results, aggregate availability, report-window
boundaries, SVG scatter rendering, timeline alignment and missing scores, source generation,
the simplified validation section, cutoff visualization, real-unit 5.3 table, cell metadata,
and the unchanged RAG notebook.

## What is in here

| Path | What it is |
|---|---|
| `01_pdm_build.ipynb` | The executed teaching notebook, five stages, outputs committed |
| `backup/01_pdm_build.html` | The same notebook as a self-contained offline page |
| `pdmlab/` | The lab package: config, data, features, detection, metrics, policy, charts, handoff |
| `pdmlab/teaching.py` | Notebook-only displays and anomaly-comparison helpers; not imported by the app |
| `data/metropt_1min.parquet` | The committed 1-minute dataset |
| `scripts/build_dataset.py` | Rebuilds the parquet from the raw UCI download (run once, not at setup) |
| `scripts/build_notebook.py` | Generates the notebook — **the canonical source; edit this, not the .ipynb** |
| `scripts/make_backup.py` | Produces the offline HTML |
| `scripts/prepare_app_artifacts.py` | Headless artifact build for the web app |
| `artifacts/` | Exported model, model card, evaluation, operating policy, sample manifest (gitignored; regenerate with `prepare:pdm`) |

## Existing app contract (not the new teaching model)

The unchanged demo service loads the original robust-score bundle:

- `model.joblib` — the detector and its baseline statistics
- `operating_policy.json` — the alert threshold, the routes, the cost assumptions, and the
  boundary statement
- `evaluation.json` — the original robust-score experiment's measurements, not the new forest's results
- `model_card.json`, `sample_manifest.parquet` — model facts and the packaged demo windows

## Limitations

- **Four events cannot support a confident accuracy figure.** The notebook deliberately refuses
  to print one.
- **Operating behavior changes.** A threshold can create more alerts later. Schedule changes,
  equipment condition, and sensor problems need investigation; the data alone does not establish
  that every change is unrelated to failure.
- **The reference period is not verified healthy.** Absence of a report does not exclude unreported
  defects, and an anomaly model can learn undesirable behavior as part of its reference.
- **The dollar figures are classroom assumptions**, clearly labeled as such. They are not
  measured costs from Metro do Porto.

## Attribution

Veloso, Ribeiro, Gama, Pereira — MetroPT-3 dataset, UCI Machine Learning Repository (CC BY 4.0).
This lab is educational. It is not a validated maintenance system for any real equipment.
