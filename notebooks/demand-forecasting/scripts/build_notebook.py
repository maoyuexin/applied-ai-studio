"""Build the undergraduate Module 6 demand-regression notebook."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_DIR / "01_forecast_build.ipynb"


def build_notebook() -> nbf.NotebookNode:
    notebook = nbf.v4.new_notebook()
    cells: list[nbf.NotebookNode] = []

    def metadata(language: str) -> tuple[str, dict[str, str]]:
        cell_id = f"forecast-classroom-{len(cells) + 1:03d}"
        return cell_id, {"id": cell_id, "language": language}

    def md(text: str) -> None:
        cell_id, meta = metadata("markdown")
        cells.append(nbf.v4.new_markdown_cell(text.strip(), id=cell_id, metadata=meta))

    def code(text: str) -> None:
        cell_id, meta = metadata("python")
        cells.append(nbf.v4.new_code_cell(text.strip(), id=cell_id, metadata=meta))

    def guide(marks: str, finding: str, action: str) -> None:
        md(f"""
### How to read this plot

- **Marks:** {marks}
- **Finding:** {finding}
- **Workflow meaning:** {action}
""")

    md("""
# Demand Forecasting with Regression

**ITAI 2372 - Module 6 - AI in Retail and Supply Chain**

**Business question:** How many units of a steady-selling product might be needed next week?

This notebook follows the same five stages used throughout the course. It compares one simple
baseline with one trained regression model. The output supports a planner; it does not place an
order.

| Stage | Question |
|---|---|
| 1. Data Ingestion | What sales history do we have? |
| 2. Feature Engineering | How do earlier weeks become model inputs? |
| 3. Model Training | What numeric pattern does the regressor learn? |
| 4. Model Validation | Is it better than the simple baseline on later weeks? |
| 5. Model Prediction | What does one forecast mean in the workflow? |

**Important boundary:** these records show units sold, not every unit customers wanted. A
stockout can hide unmet demand.
""")

    code("""
import warnings

import pandas as pd
import plotly.io as pio

from fclab import config
from fclab import teaching

warnings.filterwarnings("ignore")
pd.set_option("display.width", 150)
pd.set_option("display.max_colwidth", 80)
pio.renderers.default = "notebook"
""")

    md("""
---
# 1 - Data Ingestion

**Question:** What does one row measure, where did it come from, and which products can we
reasonably forecast?

The source is **UCI Online Retail II**, DOI `10.24432/C5CG6D`, licensed CC BY 4.0. It records
transactions from one UK online gift wholesaler from December 2009 through December 2011.

The prepared classroom file has one row per product per week. Cancelled invoices, duplicate
lines, non-products, and non-positive sales were removed before the weekly file was created.
The first and last partial weeks are excluded. Nothing downloads when this notebook runs.
""")

    code("""
lesson = teaching.load_lesson()
print(teaching.lesson_summary(lesson).to_string(index=False))
print(f"\\nSource: {config.DATASET_CITATION}")
""")

    md("""
## 1.1 EDA: what weekly sales look like

**EDA** means exploratory data analysis: inspect the data before asking a model to learn from
it. These three products show why next-week sales are difficult to predict. Some weeks are
quiet, some drift, and some jump sharply near the holiday season.
""")

    code("""
figure_1 = teaching.history_figure(lesson)
figure_1.show()
""")

    guide(
        "Each line is one product. The horizontal axis is week; the vertical axis is units sold.",
        "The products have different levels and all contain week-to-week noise and spikes.",
        "Use each product's own recent history, and keep later weeks out of training.",
    )

    md("""
Only products that sold in at least 90% of the **training** weeks enter this classroom model.
That gives 469 steady-selling products. The rule is narrow on purpose: this model is not a good
choice for the thousands of products that sell only occasionally.
""")

    md("""
---
# 2 - Feature Engineering

**Question:** How do we turn a sequence of weekly sales into a regression table?

**Regression** learns to predict a numeric target. Here, one training example represents one
product in one target week:

- **recent sales:** units 1, 2, 3, 4, and 8 weeks ago;
- **recent level:** 4-week and 8-week averages;
- **recent variation:** standard deviation over the previous 4 weeks;
- **seasonality:** the same week last year and week-of-year features;
- target: units sold in the next week.

The target is never used as an input for that same row.
""")

    code("""
print(teaching.feature_dictionary().to_string(index=False))
print("\\nOne real feature row:")
example = teaching.feature_example(lesson)
print(example.to_string(index=False))
""")

    code("""
figure_2 = teaching.feature_window_figure(lesson)
figure_2.show()
""")

    guide(
        "The first eight bars are known inputs. The red ninth bar is the future target.",
        "The dashed line is the baseline: the average of the eight known weeks.",
        "The regressor gets the same historical evidence and must beat this simple rule.",
    )

    md("""
## 2.1 Keep time in order

Randomly mixing weeks would let the model learn from the future. We use three chronological
periods instead:

1. **fit period:** learn model rules;
2. **validation period:** choose between the baseline and regressor;
3. **final test period:** measure the fixed choice once on the latest 26 weeks.
""")

    code("""
figure_3 = teaching.split_figure(lesson)
figure_3.show()
""")

    guide(
        "The line is total units across modeled products; shaded bands mark fit, validation, and test.",
        "Every validation and test week occurs after the weeks used to fit the model.",
        "Freeze the model after validation, then open the final test period once.",
    )

    md("""
---
# 3 - Model Training

**Question:** Can a trained model combine recent sales signals better than an eight-week
average?

We compare four deliberately small candidates on the **validation period**, using MAE as the
selection rule:

1. the eight-week average baseline;
2. Ridge regression, one weighted linear equation;
3. gradient boosting trained with squared-error loss; and
4. gradient boosting trained with absolute-error loss.

The selected algorithm is a **histogram gradient-boosted regressor**. It builds a sequence of
small decision trees. Each tree focuses on errors left by earlier trees. Absolute-error loss
matches our goal: reduce the typical size of a miss, measured by MAE.

### One shared model, not one model per product

We stack the product-week examples and train **one pooled model across all 469 products**. During
model selection, each product contributes 52 fit rows and 16 validation rows. After selection,
the same estimator is refit on 68 pre-test rows per product. A prediction still uses only that
product's own lag and rolling features.

Why pool the products? Fifty-two fit examples per product is too little for a separate boosted
model. Pooling supplies thousands of examples and lets the trees learn reusable sales-pattern
rules. The tradeoff is that product identity is not a feature: the model cannot learn a permanent
special rule for one stock code, and large unit errors can influence training more strongly.

The model sees no product names, prices, customer identities, promotions, inventory levels, or
competitor activity. Missing business context remains a limitation even when the code runs.
""")

    code("""
selection = teaching.model_selection_table(lesson.design)
selection_display = selection.drop(columns="Fit seconds").copy()
selection_display[["Validation MAE", "Validation RMSE"]] = selection_display[
    ["Validation MAE", "Validation RMSE"]].round(2)
print(selection_display.to_string(index=False))
print("\\nHow the training rows are combined:")
print(teaching.training_structure(lesson.design).to_string(index=False))
validation_model = teaching.fit_validation_model(lesson.design)
print(f"\\nSelected: {teaching.MODEL_LABEL} (lowest validation MAE)")
""")

    md("""
The model output is a number in units. It is not a probability, a guaranteed sale, or an order
quantity. A replenishment system would also need inventory on hand, incoming orders, lead time,
case-pack size, service targets, and planner rules.
""")

    md("""
---
# 4 - Model Validation

**Question:** Which method makes smaller errors on later weeks it did not train on?

We use two metrics, both in units:

- **MAE (mean absolute error):** average size of a miss. If MAE is 48, predictions are about
  48 units away from actual sales on average. Lower is better.
- **RMSE (root mean squared error):** also measures error in units, but gives large misses more
  weight. If RMSE worsens while MAE improves, the usual week improved but some spikes got worse.

The denominator for both metrics is every scored product-week in the period.
""")

    code("""
validation_table = teaching.validation_comparison(lesson.design)
print(validation_table.round(2).to_string(index=False))
""")

    code("""
figure_4 = teaching.metric_figure(
    validation_table,
    "Validation period: choose by the typical miss (MAE)",
)
figure_4.show()
""")

    guide(
        "Each panel compares the baseline and regressor; bar height is error in units.",
        "The regressor has lower validation MAE, so it is selected before the test is opened.",
        "A better typical week does not guarantee better performance on the largest spikes.",
    )

    md("""
## 4.1 Final check on untouched weeks

Now we refit the already-selected regressor on all pre-test examples and score the latest 26
weeks. We do not change the model after seeing these results.
""")

    code("""
final_model = teaching.fit_final_model(lesson.design)
predictions = teaching.prediction_frame(lesson.design, final_model)
test_table = teaching.test_comparison(predictions)
print(test_table.round(2).to_string(index=False))
""")

    md("""
On the final test, the regressor reduces MAE from about 52.31 to 47.97 units, an improvement of
about 8.3% in the typical miss. RMSE rises from about 129.75 to 133.78 units. That second result
matters: the trained model handles ordinary weeks better but still misses some large surges more
severely than the baseline.
""")

    code("""
figure_5 = teaching.weekly_predictions_figure(predictions)
figure_5.show()
""")

    guide(
        "The dark line is actual units; dotted and dashed lines are the two forecasts by week.",
        "Both methods follow the general level but lag behind parts of the autumn surge.",
        "A planner should inspect unusual seasonal weeks rather than treating the number as a promise.",
    )

    md("""
---
# 5 - Model Prediction

**Question:** What should a planner do with one model prediction?

The production-shaped flow is:

```text
recent weekly sales -> feature row -> predicted units -> planner review -> replenishment plan
```

The model supplies one piece of evidence. The planner still checks current inventory, purchase
orders, promotions, lead time, and known events before acting.
""")

    code("""
figure_6 = teaching.product_prediction_figure(
    predictions,
    lesson.names,
)
figure_6.show()
""")

    guide(
        "Three lines show actual sales, the baseline, and the regression prediction for one product.",
        "The model follows many weeks but reacts late when demand rises quickly.",
        "Escalate unusual seasonal changes for planner review; do not auto-order from this forecast alone.",
    )

    code("""
latest = predictions.sort_values("week").iloc[-1]
worked = teaching.worked_prediction_example(lesson, final_model)
print(f"Worked example: {worked.attrs['product']} ({worked.attrs['code']}), "
    f"week of {worked.attrs['week']}")
print(worked.round(2).to_string(index=False))
print("\\nPlanner review for the latest scored row:")
planner_review = pd.DataFrame([
    ("Product", lesson.names.get(latest.StockCode, latest.StockCode)),
    ("Week", latest.week.date()),
    ("Predicted units", round(latest.regression, 1)),
    ("Decision owner", "Inventory planner"),
    ("Next action", "Check inventory, lead time, promotions, and case packs"),
])
print(planner_review.to_string(index=False, header=False))
""")

    md("""
## What this lesson established

1. Forecasting can be framed as supervised regression when the target is a number.
2. Lag features use earlier weeks to predict a later week.
3. A chronological validation period protects the final test from model selection.
4. MAE describes the typical miss; RMSE exposes large misses.
5. The model improves the typical error here, but seasonal spikes remain a visible weakness.

**Claim boundary:** this is an educational model for one historical wholesaler. It does not
measure unmet demand, prove future performance, or authorize an order.
""")

    notebook["cells"] = cells
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    return notebook


def main() -> None:
    notebook = build_notebook()
    nbf.write(notebook, OUTPUT)
    print(f"Wrote {OUTPUT} ({len(notebook['cells'])} cells)")


if __name__ == "__main__":
    main()