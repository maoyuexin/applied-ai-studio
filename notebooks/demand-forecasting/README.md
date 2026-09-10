# Demand Forecasting Lab — Weekly Demand, an Honest Interval, One Order

ITAI 2372 Module 6, Case 1. Instructor-led demonstration; students rerun later in Codespaces.

## The case

A UK gift wholesaler ships to small independent retailers and has to decide, every week, how
many of each product to have on the shelf. Too few and the sale walks away; too many and the
money sits in a box. This lab forecasts next week's units per product, puts an honest range
around that forecast, and turns the range into a **proposed** order quantity.

**Claim boundary — read this before using any number here.** The forecast is **not a promise**,
the interval is **not a guarantee**, and **a planner approves every order — the system never
places one.** On the 26 held-out weeks the 80% band contained actual demand **84.06%** of the
time across 12,194 product-weeks. It **does not hold at Christmas**: on the 50 most Q4-skewed
products inside the October–November ramp the same band caught only **66.2%**, and **69% of
those misses were above the band** — the direction that empties a shelf. Every currency figure
in the notebook is a labeled classroom assumption, not any real retailer's economics.

## The data

Real transaction records from **one** UK-registered, non-store online gift wholesaler,
published by the UCI Machine Learning Repository as **Online Retail II** (dataset 502) under
**CC BY 4.0**, DOI **10.24432/C5CG6D**.

- 1,067,371 raw transaction lines, 2009-12-01 to 2011-12-09, 8 columns, 43 countries
- Committed here as weekly units per product: `data/online_retail_weekly.csv.gz`, 952,490 bytes,
  197,951 product-weeks. The 45.6 MB source workbook is **not** committed.
- **The retailer is closed on Saturdays — exactly one open Saturday in 739 days.** A daily model
  would learn the shutter as a weekly demand collapse, which is why this lab works in weeks.
  104 weeks in the file; the two partial edge weeks are dropped, leaving **102 complete weeks**.
- Quirks that are stated out loud rather than quietly cleaned: **19,494 cancellation lines**
  (removed), **34,335 exact duplicate rows** (kept once), 22,950 non-positive quantities and
  6,207 non-positive prices (removed), **243,007 guest-checkout lines with no customer at all —
  22.8%** (kept: demand is demand), and non-product stock codes such as `POST`, `DOT`, `M`,
  `BANK CHARGES` (removed by name; a handful survive and the cohort rule is what excludes them).
- **The median product sells nothing in 68.6% of the 102 weeks.** Only **469 of 4,871 products
  (9.6%)** clear the cohort rule, and those 469 carry **41.8%** of all units shipped. The rest
  are intermittent demand and this lab refuses to forecast them.
- The cohort is chosen on the **76 training weeks only**. The same rule read over all 102 weeks
  admits 442 products — fewer, and **leaked**, because the membership test has read the test
  window.
- What the file contains is **sales**, not demand: units a customer wanted and could not get
  leave no trace. Every historical stockout here is invisible.

**Checksum note.** The digest that is verified is taken on the **decompressed CSV content**
(`4af85e40…`), not on the gzip archive. A gzip member stores the time it was written, so the
archive's own digest changes every time the file is rebuilt from identical data and cannot be
reproduced on another machine.

## How to view or run it

**No installation.** Open `backup/01_forecast_build.html` in any browser. It is self-contained,
works offline, and shows the committed run with all nine figures rendered.

**To rerun the source notebook**, from the repository root:

```bash
node scripts/venv-python.mjs notebooks/demand-forecasting/scripts/prepare_app_artifacts.py
```

Then open `01_forecast_build.ipynb`. It executes end to end in about three seconds and needs no
network. Nothing downloads at setup or during class.

**To regenerate the notebook itself**, edit `scripts/build_notebook.py` and run it — never
hand-edit the `.ipynb`:

```bash
node scripts/venv-python.mjs notebooks/demand-forecasting/scripts/build_notebook.py
node scripts/venv-python.mjs -m nbconvert --to notebook --execute --inplace \
  notebooks/demand-forecasting/01_forecast_build.ipynb
node scripts/venv-python.mjs notebooks/demand-forecasting/scripts/make_backup.py
```

## What is in here

| Path | What it is |
|---|---|
| `01_forecast_build.ipynb` | The executed teaching notebook, five stages, outputs committed |
| `backup/01_forecast_build.html` | The same notebook as a self-contained offline page |
| `fclab/` | The lab package: config, data, features, forecast, intervals, metrics, policy, charts, handoff |
| `data/online_retail_weekly.csv.gz` | The committed weekly dataset |
| `scripts/build_dataset.py` | Rebuilds the weekly CSV from the raw UCI download (run once, not at setup) |
| `scripts/build_notebook.py` | Generates the notebook — **the canonical source; edit this, not the .ipynb** |
| `scripts/make_backup.py` | Produces the offline HTML and refuses to finish if it loads anything remote |
| `scripts/prepare_app_artifacts.py` | Headless artifact build for the web app |
| `artifacts/` | Exported forecaster, model card, evaluation, operating policy, sample manifest (gitignored; regenerate with `prepare_app_artifacts.py`) |

## The exported contract

The demo service loads these exact files, so it scores with the same model the notebook fitted:

- `forecaster.joblib` — the MA8 windows and each product's residual distribution
- `operating_policy.json` — the critical ratios, the cost assumptions, and the boundary statement
- `evaluation.json` — every measured number the notebook prints, including the baseline
  leaderboard, the interval comparison, the seasonal coverage slices, and the frozen check
- `model_card.json`, `sample_manifest.parquet` — model facts and the ten packaged demo products,
  which include the three where the policy loses money

The notebook's last cell reloads the artifact **from disk** and re-scores all 12,194 held-out
product-weeks, requiring **bitwise-identical** forecasts and order quantities before it will
call the run complete.

## Honest limitations, which are also the lesson

- **The interval fails at Christmas, and that is measured, not suspected.** One product's annual
  coverage is a textbook **80.8%** — and **all five of its misses are above the band, inside the
  autumn ramp**. An aggregate metric can be exactly right and still describe the wrong thing.
- **Aggregate seasonality is 1.65x; product-level seasonality reaches 9.36x.** The average hid a
  factor of nine.
- **The policy makes 115 of 469 products more expensive**, all of them declining sellers. In
  cash terms the worst of the walked-through cases is `PAPER CHAIN KIT EMPIRE`, whose holdout
  cost goes from about `$162` to about `$785` — **+383.6%**. A rule that wins 75.5% of the time
  visibly loses the rest, and the planner whose name is on those orders will notice.
- **The textbook seasonal method is the worst real method here.** Seasonal-naive scores MAE
  **84.52** and loses to forecasting zero forever (**84.33**), because one year of history gives
  one noisy observation per week rather than a season. MA8 wins at **52.31**.
- **The accurate model was the wrong model.** Quantile gradient boosting beat the deployed method
  on MAE (47.97 vs 51.57) and delivered **75.0%** coverage against a promised 80%, predicting
  negative demand on **3.63%** of rows. Empirical residual quantiles delivered 84.06%, fit
  ~200x faster, and yield any quantile for free — which is the only reason the interactive
  cost-ratio control can respond in real time.
- **MAPE recommends closing the warehouse.** It scores the real forecast at **8.27e+15** and a
  flat-zero forecast at **0.9073**. It appears in this lab exactly once, as a warning. MAE is not
  innocent either: by MAE, flat zero beat seasonal-naive.
- **The band is wider than the forecast.** Median band width is **88.08 units** against a median
  non-zero week of 34 — **2.59x**. That width is a measurement of the business's real variance,
  and a narrower band would simply be a band that lies.
- **The dollar figures are classroom assumptions**, clearly labeled as such. Overstock
  `co = 0.10 x unit price` per unit-week; understock `cu = ratio x co`. They are not measured
  costs from any retailer, and `cu` and `co` are the two numbers only operations and finance can
  supply.

## Attribution

Chen, D. (2019). *Online Retail II*. UCI Machine Learning Repository.
https://doi.org/10.24432/C5CG6D — dataset 502, **CC BY 4.0**.

This lab is educational. It is not a validated demand-planning system for any real business.
