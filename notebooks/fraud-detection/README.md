# How a fraud model actually gets built

Teaching notebook for **ITAI 2372 · Module 2**. It walks one fraud-detection model from raw
transactions to a deployable artefact, and every number in it is computed live rather than
quoted from a slide.

## Run it

In a codespace everything is already installed — open `01_fraud_build.ipynb` and run all
cells. It takes about **45 seconds** end to end.

Locally:

```bash
npm run setup:notebook       # one time
```

Then open the notebook and select the `.venv` interpreter.

## What is in here

```
01_fraud_build.ipynb    the notebook — the thing you read
fraudlab/               the helper package, so cells stay short
  config.py             paths, dates, and the business constants
  data.py               loading, joining, label maturity, the time split
  features.py           feature engineering — shared with the scoring service
  charts.py             every Plotly figure
  metrics.py            the confusion matrix and everything read off it
  models.py             candidates, balancing bake-off, sweep
  handoff.py            the three artefacts a service consumes
data/                   committed parquet — 42 MB, no download needed
scripts/build_dataset.py  regenerates data/ from the Sparkov generator
artifacts/              written by the notebook, gitignored
```

**Every visible notebook cell is under about ten lines.** Anything longer lives in
`fraudlab`. The course is about business judgement, not programming, and a wall of code
loses the room in ninety seconds.

## The data

955,000 synthetic card transactions, 500 cardholders, July 2024 – August 2026, 0.50% fraud.

Generated with [Sparkov](https://github.com/namebrandon/Sparkov_Data_Generation) (MIT) at
seed 42, so it is byte-identical for everyone. **It is committed, so nothing downloads and
nothing needs a Kaggle account** — the notebook runs with no network at all.

No real fraud data was used and none exists publicly in usable form. Section 1 of the
notebook explains why that is itself worth knowing.

To regenerate at a different size or window:

```bash
git clone https://github.com/namebrandon/Sparkov_Data_Generation.git
cd Sparkov_Data_Generation && pip install "Faker>=13,<26" "numpy<2"
python datagen.py -n 500 -seed 42 -o /tmp/sparkov_out 07-01-2024 08-31-2026
cd - && python scripts/build_dataset.py /tmp/sparkov_out
```

## The windows

| Window | Dates | Used for |
|---|---|---|
| Train | 2024-07-01 → 2025-12-31 | fitting |
| Test | 2026-01-01 → 2026-06-30 | the only honest score |
| Frontier | 2026-07-01 → 2026-08-31 | **never scored** — labels have not matured |

"Today" is 2026-08-31 and a chargeback confirms about 60 days after the transaction, so the
frontier exists to make the label-lag problem concrete rather than theoretical.

## Two conventions worth knowing before you read the code

**Models are compared at a fixed review budget, not a fixed 0.5 threshold.** Six models put
their scores in six different places on the 0–1 line; at 0.5 one flags everything and
another flags nothing. Giving them all the same 3% of transactions to spend is what makes
the comparison fair — and every number reported is read off the resulting confusion matrix.

**`features.py` is shared, not copied.** When the scoring service is built it imports these
functions rather than reimplementing them. A feature computed one way in a notebook and
another way in a service is the most common reason a deployed model quietly stops matching
its validation score.

## Artefacts

The last section writes three files to `artifacts/` (gitignored — rerun the notebook to
recreate them):

| File | What it is |
|---|---|
| `model.joblib` | the selected pipeline, exactly as it was scored |
| `model_card.json` | what it is, how it was chosen, and what it measured |
| `test_stream.parquet` | the held-out period, engineered, with labels |

The final cell reloads all three and asserts they reproduce the numbers in the card. If
that assertion fails, the handoff is broken — which is far better to discover here than in
front of a room.
