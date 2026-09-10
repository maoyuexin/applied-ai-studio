# From a monthly account snapshot to an analyst review queue

Teaching notebook for **ITAI 2372 - Module 4, AI in Finance and Credit Risk Management**.
It walks one credit-risk model from a raw 2005 spreadsheet to a review queue an analyst
could actually work, and every number in it is computed by the cell above it rather than
quoted from a slide.

The five sections match the five stages used in Modules 2 and 3:

| | Stage | What happens |
|---|---|---|
| 1 | **Data Ingestion and Provenance** | Verify the source, the license, the checksum, and what one row means |
| 2 | **EDA and Feature Preparation** | Find the signal, set the protected attributes aside, build 7 features |
| 3 | **Model Training** | Baseline, logistic regression, gradient boosting on one identical split |
| 4 | **Validation and Operating Policy** | Turn scores into a money rule, compare feature removal, score the test split once |
| 5 | **Prediction, Reason Codes and Handoff** | Walk real accounts end to end and export the measured system |

## The authority boundary

This is an educational workflow demonstration, not a lending system. The model produces a
probability. A written policy turns that probability into `priority_review` or
`standard_monitoring`. **A credit analyst decides what happens to the account**, and
compliance owns any notice a customer receives. The model never contacts a customer, never
changes a credit limit, and never labels anyone a defaulter.

Three words the notebook keeps apart throughout: a **score** is the model's number, a
**decision** is what the policy does with it, an **outcome** is what the account actually
did a month later.

## Run it

In a Codespace everything is installed - open `01_credit_build.ipynb`, select the `.venv`
interpreter, and run all cells. It takes about **20 seconds** end to end, including model
fitting, SHAP, artifact export, and the reload check. Nothing downloads while it runs.

Locally, from the repository root:

```bash
npm run setup:notebook        # one time
```

The notebook additionally needs **`shap`**, which is not in the `notebook` extra:

```bash
node scripts/venv-python.mjs -m pip install "shap>=0.46,<1"
```

To regenerate the notebook source, re-execute it, or prepare the app artifacts without
touching the notebook file:

```bash
node scripts/venv-python.mjs notebooks/credit-risk/scripts/build_notebook.py
node scripts/venv-python.mjs -m nbconvert --to notebook --execute --inplace \
     notebooks/credit-risk/01_credit_build.ipynb
node scripts/venv-python.mjs notebooks/credit-risk/scripts/prepare_app_artifacts.py
node scripts/venv-python.mjs notebooks/credit-risk/scripts/make_backup.py
```

**`scripts/build_notebook.py` is the canonical notebook source.** Never hand-edit the
`.ipynb` JSON: change the generator and regenerate, so the notebook, the `creditlab`
package, and the exported artifacts cannot drift apart.

Generation preserves saved cells whose source is unchanged. Re-execute edited cells
and their affected dependents before publishing; matching source alone does not prove
an output is still valid after an upstream change.

The current notebook has **79 cells, 29 code cells, and 8 figures**. Section 1.2 shows
five real rows before the monthly account example. Sections 4.1-4.4 follow one explicitly
made-up account: understand a 30% risk estimate, assume half of a `NT$100,000` balance
is lost after default, compare `NT$15,000` estimated loss with a `NT$10,000` review cost,
then inspect the real 6,000-account validation confusion matrix. These supplied assumptions
are not measured costs or a real account's prediction. Detailed calibration and cost-sweep
calculations are retained in the Stage 5 evidence handoff, not displayed in that lesson.

Section 4.5 compares the same model
before and after removing `SEX`, `MARRIAGE`, and `AGE` and retraining, with one sentence
limiting the conclusion to ranking performance. Section 4.6 checks the chosen model on unseen accounts. Detailed group
checks are calculated in the Stage 5 handoff for the app, not displayed as teaching tables.

## The notebook versus the standalone HTML

Two copies exist and they are for different moments:

| | `01_credit_build.ipynb` | `backup/01_credit_build.html` |
|---|---|---|
| What it is | The executable notebook, committed **with outputs** | A frozen render of that exact run |
| Use it when | Teaching normally - you can edit, re-run, and answer "what if" | The kernel will not start, the venv is broken, or the room has no network |
| Interactivity | Full: re-run any cell, change any number | Plotly hover and zoom work; nothing re-computes |
| Network | None needed | None needed - everything is inlined |

The HTML backup is **genuinely offline**: `scripts/make_backup.py` runs `nbconvert`,
inlines `require.js` (which Plotly's notebook renderer needs to draw), drops the unused
MathJax tags, and then refuses to write the file unless zero remote scripts, stylesheets,
or images remain. Building it needs the network once; opening it never does.

## Package layout

```text
01_credit_build.ipynb        The executed teaching notebook - the thing you read
creditlab/                   The helper package, so visible cells stay short
  config.py                  Paths, frozen decisions, cost parameters, palette
  data.py                    Loading with validation, the stratified 60/20/20 split
  features.py                The engineered 7 - shared with the scoring service
  models.py                  The three candidates and the deployable pipeline
  metrics.py                 Ranking metrics, reliability table, the policy arithmetic
  explain.py                 SHAP reason codes in adverse-action-ready language
  charts.py                  Every Plotly figure
  handoff.py                 The five artifacts and the reload verification
data/accounts.parquet        The committed snapshot - 1.3 MB, no download needed
artifacts/                   Written by the notebook; the app loads these exact files
backup/                      Standalone offline HTML
scripts/
  build_dataset.py           One-time XLS -> parquet converter, with checksum
  build_notebook.py          Canonical notebook generator
  prepare_app_artifacts.py   The same workflow headlessly, for a `prepare:credit` script
  make_backup.py             Offline HTML export
```

**Every visible notebook cell is short.** Anything longer lives in `creditlab`. The course
is about business judgement, not programming, and a wall of code loses the room in ninety
seconds.

## Data provenance

| Property | Value |
|---|---|
| Dataset | Default of Credit Card Clients, UCI Machine Learning Repository id 350 |
| Download | https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients |
| License | CC BY 4.0 |
| Source file | `default of credit card clients.xls`, 5.5 MB |
| SHA-256 of the XLS | `30c6be3abd8dcfd3e6096c828bad8c2f011238620f5369220bd60cfc82700933` |
| Citation | Yeh, I-C. & Lien, C-H. (2009), *Expert Systems with Applications* 36(2), 2473-2480 |
| Population | 30,000 existing cardholders of one Taiwanese issuer, April-September 2005 |
| Target | Missed the October 2005 payment: 6,636 accounts (22.1%) |
| One row | One cardholder; no customer appears twice |

The only transformations between the published XLS and `data/accounts.parquet` are: verify
the checksum, take the second header row as the column names (the XLS has a generic
`X1...X23` row above the real ones), and rename `default payment next month` to `DEFAULT`.
No row, column, or value is altered. That conversion is `scripts/build_dataset.py`, run
once, and it needs `xlrd` for the legacy `.xls` format.

**Context worth teaching:** these accounts are a snapshot of the 2005-2006 Taiwan
credit-card debt crisis. A 22.1% default rate is not a normal month at a normal bank.
Nothing measured here transfers to US consumers in 2026, and the model card says so.

**Two documented limitations, both stated in the notebook and the model card:**

- Every account is observed over the same six-month window, so an **out-of-time split is
  impossible** in this dataset. A real bank validates behavioral models out-of-time.
- All cost parameters (review cost `NT$10,000`, loss given default `0.5`) are **synthetic
  classroom assumptions** in New Taiwan dollars, not measured bank costs.

## The frozen decisions

Set by the Module 4 technical spike and reproduced exactly by the notebook:

| | |
|---|---|
| Split | 60/20/20 stratified on `DEFAULT`, seed 42, two-stage |
| Features | 7 engineered behavior features; `SEX`, `MARRIAGE`, `AGE` excluded from the inputs |
| Model | `HistGradientBoostingClassifier(random_state=42)`, library defaults |
| Calibration | None - raw probabilities (isotonic improved Brier by only 0.0009) |
| Reason codes | `shap.TreeExplainer`, up to 3 risk-raising reasons, never padded |
| Policy | Flag when `p(default) x exposure x 0.5 > NT$10,000` |
| Exposure | `BILL_AMT1` clipped to `[0, LIMIT_BAL]` |

Measured on the 6,000 test accounts, scored once after everything above was frozen:

| Metric | Value |
|---|---|
| AUC | 0.7852 |
| Flagged | 761 of 6,000 (12.68%) |
| Precision among flagged | 0.4823 |
| Recall of defaulters | 0.2766 |
| Confusion | TP 367, FP 394, FN 960, TN 4,279 |
| Net savings vs reviewing nobody | `NT$14,623,904` |
| Cost of excluding the protected attributes | 0.0015 AUC |

## Artifacts

Stage 5 writes exactly five files to `artifacts/`, and the credit API loads these and
nothing else:

| File | What it is |
|---|---|
| `model.joblib` | The fitted pipeline - **feature builder and model in one object** |
| `model_card.json` | Intended use, provenance, measured results, limitations, excluded uses |
| `operating_policy.json` | The rule, its parameters, the two routes, and the fallback |
| `evaluation.json` | Every table from Stages 3 and 4, for the governance view |
| `sample_manifest.parquet` | 60 test accounts with scores, routes, reason codes, and outcomes |

The feature builder travels **inside** `model.joblib`, so the service cannot compute
utilization one way while the notebook computed it another - the most common reason a
deployed model quietly stops matching the numbers it was approved on. The final notebook
cell reloads the saved files from disk and asserts the probabilities are **bitwise
identical** to the exported ones and that no route changed. If that assertion fails, the
handoff is broken, which is far better to discover here than in front of a room.

`sample_manifest.parquet` also carries `audit_sex` and `audit_age_band`. Those are
**withheld columns the model never saw**, exported only so the application's governance
screen can rerun the notebook's fairness audit. They are audit data and are never model
inputs.
