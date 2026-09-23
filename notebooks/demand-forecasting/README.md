# Demand Forecasting with Regression

ITAI 2372 Module 6, Case 1. Instructor-led undergraduate lesson.

## The decision

**Question:** How many units of a steady-selling product might be needed next week?

The notebook turns recent weekly sales into lag and rolling-window features, then compares:

- an eight-week moving-average baseline; and
- a trained histogram gradient-boosted regressor using absolute-error loss.

The output is a predicted number of units for planner review. It is not a probability, a
guaranteed sale, or an automatically approved purchase order.

## The five stages

1. Data Ingestion
2. Feature Engineering
3. Model Training
4. Model Validation
5. Model Prediction

The classroom notebook contains 32 cells, 13 code cells, and six instructional plots. Every plot
has a short guide explaining its marks, finding, and workflow consequence.

## The data

The source is **UCI Online Retail II**, dataset 502, DOI `10.24432/C5CG6D`, licensed CC BY 4.0.
It records transactions from one UK online gift wholesaler from December 2009 through December
2011.

The committed classroom file is `data/online_retail_weekly.csv.gz`:

- 197,951 product-week rows;
- 102 complete weeks after dropping two partial edge weeks;
- 4,871 products in the weekly panel;
- 469 steady-selling products selected using training weeks only; and
- 12,194 product-week rows in the final 26-week test period.

These records show **sales**, not every unit customers wanted. Historical stockouts can hide unmet
demand.

## Features and model selection

One supervised-learning row represents one product in one target week. The model inputs are:

| Group | Columns | Meaning |
|---|---|---|
| Recent sales | `lag1`, `lag2`, `lag3`, `lag4`, `lag8` | Units in selected earlier weeks |
| Recent level | `ma4`, `ma8` | Four- and eight-week averages |
| Recent variation | `std4` | Standard deviation over four weeks |
| Seasonality | `lag52`, `woy`, `woy_sin`, `woy_cos` | Same week last year and calendar position |

The target is next week's units. Product name, price, inventory, promotion, lead time, and customer
identity are not features.

Four candidates are compared on chronological validation weeks, and the lowest validation MAE is
selected before the final test is opened:

| Candidate | Validation MAE | Selection result |
|---|---:|---|
| Eight-week average | 51.37 | Baseline |
| Ridge regression | 52.96 | Not selected |
| Gradient boosting, squared-error loss | 53.03 | Not selected |
| Gradient boosting, absolute-error loss | **48.81** | **Selected** |

The selected `HistGradientBoostingRegressor` builds small decision trees in sequence. Each tree
corrects part of the error left by earlier trees. Absolute-error loss aligns training with the
primary goal: reducing the typical absolute miss.

### One shared model across products

This lesson does **not** train 469 separate models. It stacks product-week rows and trains one
shared estimator:

| Period | Combined rows |
|---|---:|
| Model-selection fit | 24,388 = 469 products × 52 target weeks |
| Validation | 7,504 = 469 products × 16 target weeks |
| Final pre-test refit | 31,892 = 469 products × 68 target weeks |
| Final test | 12,194 = 469 products × 26 target weeks |

Each row uses only that product's own lag, average, variation, and calendar features. `StockCode`
and product name are not inputs, so the model learns relationships shared across products rather
than memorizing an item. Pooling is used because 52 selection-fit rows per product is too little
for a separate boosted-tree model. The tradeoff is that the shared model cannot learn a permanent
item-specific rule, and errors on high-volume products can have more influence in raw units.

## Measured result

Model choice uses a chronological validation period before the final test is opened. On the
untouched 26-week test period:

| Method | MAE | RMSE |
|---|---:|---:|
| Eight-week average | 52.31 units | 129.75 units |
| Gradient-boosted regression | 47.97 units | 133.78 units |

MAE is the average size of a miss. The regressor improves this typical miss by about 8.3%.
RMSE gives extra weight to large misses; its increase shows that some seasonal spikes became
worse. Both results belong in the conclusion.

**Worked example.** For `JUMBO BAG RED RETROSPOT` in the week of November 21, 2011, actual sales
were 753 units. The eight-week average predicted 1,386.75 (absolute error 633.75); the selected
regressor predicted 824.15 (absolute error 71.15). One example explains the calculation, while the
12,194-row test result justifies the model choice.

## View or run

Open `backup/01_forecast_build.html` for the self-contained offline classroom copy.

From the repository root, regenerate and execute the notebook with:

```bash
node scripts/venv-python.mjs notebooks/demand-forecasting/scripts/build_notebook.py
node scripts/venv-python.mjs -m nbconvert --to notebook --execute --inplace \
  notebooks/demand-forecasting/01_forecast_build.ipynb
node scripts/venv-python.mjs notebooks/demand-forecasting/scripts/make_backup.py
```

Run the focused teaching checks with:

```bash
node scripts/venv-python.mjs -m pytest -q \
  notebooks/demand-forecasting/tests/test_demand_teaching.py
```

## Paths

| Path | Purpose |
|---|---|
| `01_forecast_build.ipynb` | Executed five-stage classroom notebook |
| `backup/01_forecast_build.html` | Offline classroom HTML |
| `fclab/teaching.py` | Small classroom calculation and plotting API |
| `scripts/build_notebook.py` | Canonical classroom notebook source |
| `tests/test_demand_teaching.py` | Structure and frozen-result checks |
| `backup/02_forecast_reference.ipynb` | Preserved advanced interval and inventory lesson |
| `backup/02_forecast_reference.html` | Offline advanced reference |
| `scripts/build_reference_notebook.py` | Advanced reference generator |
| `scripts/prepare_app_artifacts.py` | Existing application-artifact build |

## Classroom and application boundary

The existing application artifacts still use the earlier MA8 plus empirical-residual interval
model. The rebuilt classroom notebook teaches genuine supervised regression and never writes or
replaces application artifacts. The two paths are labeled separately until the application is
explicitly redesigned and revalidated.

## Limits

- The cohort excludes intermittent products that sell in fewer than 90% of training weeks.
- Promotions, inventory, lead time, competitor activity, and stockouts are unavailable.
- One wholesaler from 2009-2011 does not represent current retail.
- Better MAE does not mean every week or every product improved.
- A planner remains responsible for the replenishment decision.

## Attribution

Chen, D. (2019). *Online Retail II*. UCI Machine Learning Repository.
https://doi.org/10.24432/C5CG6D, CC BY 4.0.