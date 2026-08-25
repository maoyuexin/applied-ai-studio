"""Build 01_fraud_build.ipynb -- five sections matching the Session 2 slide stages."""

import nbformat as nbf

nb = nbf.v4.new_notebook()
C = []


def cell_metadata(language):
    cell_id = f"fraud-build-{len(C) + 1:03d}"
    return cell_id, {"id": cell_id, "language": language}


def md(text):
    cell_id, metadata = cell_metadata("markdown")
    C.append(nbf.v4.new_markdown_cell(text.strip("\n"), id=cell_id, metadata=metadata))


def code(text):
    cell_id, metadata = cell_metadata("python")
    C.append(nbf.v4.new_code_cell(text.strip("\n"), id=cell_id, metadata=metadata))


# ══════════════════════════════════════════════════════════ TITLE ═══════════
md(r"""
# How a fraud model actually gets built

**ITAI 2372 · Module 2 · From data to decision**

Last week you decided that screening a payment was worth building. Tonight we build it, in
the five stages from the slides:

| | Stage | What happens |
|---|---|---|
| **1** | **Data Ingestion** | Get the data, understand it, split it |
| **2** | **Feature Engineering** | Turn records into signals a model can use |
| **3** | **Model Training** | Fit several models and pick one |
| **4** | **Model Validation** | Find out whether it is actually any good |
| **5** | **Model Prediction** | Use it on transactions it has never seen |

> **Model** means a set of patterns learned from earlier examples. Here the model reads
> facts about a transaction and produces an estimate of how likely it is to be fraud. It
> does not "know" that a transaction is fraud, and its output is not proof.

### The case

A card issuer wants to stop fraudulent transactions without blocking real customers.

- **955,000 card transactions** over two years, 500 cardholders
- **0.5% of them are fraud** — about 1 in 200
- Analysts can review about **3% of transactions**. That is the budget.

### Where the data comes from

This is **synthetic data** — computer-generated transactions, not records from real
customers or a real bank. It was generated locally with the MIT-licensed
[Sparkov Data Generation](https://github.com/namebrandon/Sparkov_Data_Generation) project
using random seed 42, so everyone in the class works with the same transactions.

### How to read this notebook

Every chart is interactive — **hover to read a value**, drag to zoom, double-click to reset.

The code is deliberately short. Anything longer than a few lines lives in the `fraudlab`
folder next to this file, so each cell shows *one step*.
""")

code(r"""
# ===============================================================
# SETUP
# ===============================================================
# Purpose:  Import the helper package and print the configuration.
# ===============================================================
import warnings

import numpy as np
import pandas as pd
import plotly.io as pio

from fraudlab import charts, config, data, features, handoff, metrics, models

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)
pio.renderers.default = "notebook"

print(config.describe())
""")

# ═══════════════════════════════════════════ 1 · DATA INGESTION ═════════════
md(r"""
---
# 1 · Data Ingestion

**Question:** Do we have trustworthy data arranged in a way the model can learn from?

In this stage we load and join the source tables, understand what one row means, inspect
the data, and split earlier transactions from later ones. By the end we will have a
training period and a held-out evaluation period. In a real project this is where most of
the time goes.

> A **label**, also called the **target**, is the answer the model is supposed to learn.
> Here `is_fraud = 1` means fraud and `is_fraud = 0` means a **normal transaction** —
> simply, one not labelled as fraud.
""")

md(r"""
## 1.1 Load the source tables

Two tables, from two different systems. The card system knows about **cardholders**. The
payment system knows about **transactions**.
""")

code(r"""
# ===============================================================
# 1.1  LOAD
# ===============================================================
customers = data.load_customers()
transactions = data.load_transactions()

print(f"customers     : {len(customers):>9,} rows   {customers.shape[1]} columns")
print(f"transactions  : {len(transactions):>9,} rows   {transactions.shape[1]} columns")
print(f"date range    : {transactions['trans_date_trans_time'].min():%Y-%m-%d} "
      f"to {transactions['trans_date_trans_time'].max():%Y-%m-%d}")
print(f"fraud         : {int(transactions['is_fraud'].sum()):,} "
      f"({transactions['is_fraud'].mean():.3%})")
""")

code(r"""
# ===============================================================
# 1.2  WHAT A TRANSACTION LOOKS LIKE
# ===============================================================
transactions.head(5)
""")

code(r"""
# ===============================================================
# 1.3  WHAT WE KNOW ABOUT THE CARDHOLDER
# ===============================================================
customers.head(3)
""")

md(r"""
### Profile every source column

**Data profiling** is a quick inventory before analysis: what columns exist, what type of
value each holds, whether values are missing, and how varied the values are. The final
column also answers a different question: **does this notebook use the source column
directly, use it to build a feature, use it only for workflow context, or leave it out?**

Available does not mean appropriate for a model. Names and addresses, for example, exist
in the customer table but are not model inputs.
""")

code(r"""
# ===============================================================
# PROFILE  --  all 12 transaction columns
# ===============================================================
(data.profile_source_columns(transactions, "transactions").style
 .hide(axis="index")
 .set_caption(f"Transactions: {len(transactions):,} rows × {transactions.shape[1]} columns"))
""")

code(r"""
# ===============================================================
# PROFILE  --  all 13 customer columns
# ===============================================================
(data.profile_source_columns(customers, "customers").style
 .hide(axis="index")
 .set_caption(f"Customers: {len(customers):,} rows × {customers.shape[1]} columns"))
""")

md(r"""
## 1.2 Join them

A transaction on its own does not tell you much. Joined to the cardholder, you can start
asking useful questions — *was this near their home? is this a lot of money for them?*
""")

code(r"""
# ===============================================================
# 1.4  JOIN  --  one row per transaction, carrying who made it
# ===============================================================
joined = data.join(transactions, customers)

print(f"joined     : {len(joined):,} rows   {joined.shape[1]} columns")
print(f"unmatched  : {int(joined['dob'].isna().sum()):,}")
""")

md(r"""
> ### A note on the label
>
> We have a target column called `is_fraud`, and it is tempting to treat it as simple
> truth.
>
> In a real bank that column does not arrive with the transaction. It arrives when a
> customer disputes a charge and the bank agrees — a **chargeback** — and that takes about
> **two months**. So your training data always trails reality, and the transactions you
> *blocked* never get a label at all, because you stopped them.
>
> **Before you ask anything else about a dataset, ask what the label means and when it
> arrives.**
""")

md(r"""
## 1.3 Exploratory Data Analysis (EDA)

EDA means looking at the data before you model it. Six views, and each one changes a
decision we make later.

The first view checks **class balance**: how many rows belong to each possible answer, or
**class**. Here the two classes are fraud and normal transactions.

The amount chart also uses a **log transform**. It compresses very large dollar values so
we can see the shape of the many smaller purchases without deleting the original data.
""")

code(r"""
# ===============================================================
# 1.5  EDA  --  class balance
# ===============================================================
# The same two numbers, drawn twice. The right panel is what an untransformed
# chart of this problem actually looks like.
# ===============================================================
charts.class_balance(transactions).show()
""")

code(r"""
# ===============================================================
# 1.6  EDA  --  how much is a transaction?
# ===============================================================
charts.amount_distribution(transactions).show()
""")

code(r"""
# ===============================================================
# 1.7  EDA  --  does amount separate fraud from normal transactions?
# ===============================================================
charts.amount_by_class(transactions).show()
""")

code(r"""
# ===============================================================
# 1.8  EDA  --  when does fraud happen?
# ===============================================================
charts.fraud_rate_by_hour(transactions).show()
""")

code(r"""
# ===============================================================
# 1.9  EDA  --  where does fraud happen?
# ===============================================================
charts.rate_by_category(transactions, "category", "merchant category").show()
""")

code(r"""
# ===============================================================
# 1.10  EDA  --  is the problem stable over time?
# ===============================================================
# Drag the slider under the chart to move the window across the two years.
# ===============================================================
charts.weekly_volume_and_rate(data.weekly_volume(transactions)).show()
""")

md(r"""
### What EDA already decided for us

| What we saw | What it forces |
|---|---|
| Fraud is **0.5%** of transactions | Accuracy will be a useless headline number |
| Amount is **right-skewed**: most purchases are small, but a few are very large | Add a **log transform**: take the logarithm of each amount to compress the largest values |
| Fraud amounts sit in a **different band** | Amount carries useful **signal**: a pattern that helps separate the classes |
| Fraud concentrates in the **small hours** | Hour of day becomes a feature |
| A few categories carry most of it | Category becomes a feature |
| The fraud rate **moves over time** | Split the data by date, not at random |

Nobody handed us that list. We looked.

**Class imbalance** means one class greatly outnumbers the other. **Accuracy** is the share
of all predictions that are correct; with 99.5% normal transactions, a model can have
high accuracy simply by saying "normal" every time.
""")

md(r"""
## 1.4 Split the data by date

The model learns from the **earlier** months and is scored on the **later** ones.

This matters because fraud changes over time. Split randomly and the model could train on
March and be tested on February — it would already have seen the answers, and the score
would look far better than anything achievable in production.

Most data-science projects give the partitions three separate jobs:

| Partition | Job |
|---|---|
| **Training set** | Examples the model uses to learn its internal rules |
| **Validation set** | Unseen examples used to compare models and settings |
| **Test set** | A final check used only after all choices are fixed |

All three should come from **later dates** in a time-changing problem such as fraud. To
keep this classroom demonstration short, we use a training period and one held-out period
for evaluation, followed by a still-later batch in section 5. A production study should
keep validation and final test periods separate.

**Held out** means set aside and not used while the model learns.
""")

code(r"""
# ===============================================================
# 1.11  SPLIT BY DATE
# ===============================================================
parts_raw = data.split_by_time(joined)

charts.split_timeline(parts_raw).show()
data.split_summary(parts_raw)
""")

# ═══════════════════════════════════════ 2 · FEATURE ENGINEERING ════════════
md(r"""
---
# 2 · Feature Engineering

**Question:** What information should the model use?

A model cannot use the idea of "a transaction." It uses **numbers computed from** a
transaction. Those inputs are called **features**, and choosing them is the craft. By the
end of this stage we will have a feature table and know how to avoid data leakage.

This is also where the fraud analyst — not the data scientist — does the real work.

In the code, `X` is the **feature matrix** — rows are transactions and columns are feature
values. `y` is the target column containing the answer for each row. The suffixes `_train`
and `_test` tell us which time period each table came from.
""")

code(r"""
# ===============================================================
# 2.1  BUILD THE FEATURES
# ===============================================================
# Features are computed BEFORE splitting, because some of them need the card's
# earlier history. Every one uses only information that exists at the moment the
# customer presses Buy.
# ===============================================================
featured = features.build_features(joined)
parts = data.split_by_time(featured)

x_train, y_train = features.feature_matrix(parts["train"])
x_test, y_test = features.feature_matrix(parts["test"])
x_test = features.align_columns(x_test, x_train)
amounts_test = parts["test"]["amt"].to_numpy()

print(f"columns before : {joined.shape[1]}")
print(f"columns after  : {featured.shape[1]}")
print(f"model concepts : {len(features.NUMERIC_FEATURES) + len(features.CATEGORICAL_FEATURES)}")
print(f"matrix columns : {x_train.shape[1]} after expanding merchant category")
""")

md(r"""
### Which columns reach the model?

The profile above started with **25 source columns across two tables**. The model does not
receive all 25. It receives the 13 concepts below: two direct source fields and eleven
engineered features. Merchant category then expands into one yes/no column per category,
which is why the numeric model matrix has more than 13 columns.
""")

code(r"""
# ===============================================================
# MODEL INPUT CATALOG  --  what X actually contains
# ===============================================================
(features.model_feature_catalog().style
 .hide(axis="index")
 .set_caption("The 13 conceptual inputs used by the model"))
""")

md(r"""
## 2.1 Three features, one at a time

Each one gets the same treatment: **the question a fraud analyst would ask**, the picture,
and the number.
""")

code(r"""
# ===============================================================
# 2.2  FEATURE  --  "Is this a lot of money FOR THIS PERSON?"
# ===============================================================
# Not "is $840 large?" but "is $840 large for this cardholder?" -- measured against
# their own spending, using only transactions that already happened.
# ===============================================================
charts.numeric_by_class(featured, "amt_ratio_to_card_mean",
                        "Amount as a multiple of this card's own average",
                        finding="Fraud purchases are often far above the card's usual spending.").show()

print(features.describe_signal(x_train, y_train, "amt_ratio_to_card_mean"))
""")

code(r"""
# ===============================================================
# 2.3  FEATURE  --  "How fast is this card being used?"
# ===============================================================
# One purchase is a purchase. Nine in ten minutes is somebody testing a stolen
# card until it works -- or so every fraud analyst will tell you. Let us check.
# ===============================================================
charts.numeric_by_class(featured, "card_txn_count_24h",
                        "Transactions on this card in the previous 24 hours",
                        finding="The groups overlap heavily, so this feature is weak by itself.").show()

print(features.describe_signal(x_train, y_train, "card_txn_count_24h"))
""")

code(r"""
# ===============================================================
# 2.4  FEATURE  --  "How far from home was this?"
# ===============================================================
# The cardholder's home coordinates and the merchant's, converted to kilometres.
# Neither column existed; the distance between them is a decision somebody made.
# ===============================================================
charts.numeric_by_class(featured, "distance_km",
                        "Distance from cardholder home to merchant (km)",
                        finding="The groups overlap heavily, so distance is weak by itself.").show()

print(features.describe_signal(x_train, y_train, "distance_km"))
""")

md(r"""
### Two of those three look useless. Do not delete them yet.

The amount ratio is strong. Velocity and distance are barely better than guessing — even
though an experienced fraud analyst would have insisted both matter.

There are three possible reasons, and they lead to different actions:

1. The pattern only works **in combination** with something else. A single-feature test
   cannot see that; the model can.
2. The pattern is real in the world but **not in this data**.
3. We built the feature badly — a 24-hour window when the real pattern is ten minutes.

> **When the data disagrees with the expert, that is the start of a conversation, not the
> end of one.** We come back to this in section 3.
""")

md(r"""
## 2.2 Which features carry signal?

**Pearson correlation** measures how strongly two columns move together in a straight-line
pattern. It runs from **-1** (opposite directions) through **0** (no linear relationship)
to **+1** (same direction).

Our target, `is_fraud`, is stored as 0 or 1, so we can include it. Read across its row or
down its column to see which numeric features have the strongest linear relationship with
fraud. A value near zero does not prove a feature is useless; it may still matter in
combination with other features or through a non-linear pattern.
""")

code(r"""
# ===============================================================
# 2.5  PEARSON CORRELATION  --  numeric features plus the target
# ===============================================================
# Use the training period only. The model has not seen the test period.
# ===============================================================
pearson = features.correlation_frame(parts["train"], include_target=True)
charts.correlation_heatmap(pearson, "Pearson").show()
""")

md(r"""
## 2.3 The mistake that looks like success — data leakage

**Data leakage** means training with information that would not exist when a real
prediction must be made. It is the most expensive mistake in the whole workflow, and it
is invisible on every dashboard.

Somebody adds a column called `flagged_by_dispute_team`. It is right there in the
warehouse, and it is obviously relevant.

This demonstration uses two measurements for the first time:

- **Recall** is the share of all real fraud that the model catches.
- **Precision** is the share of the model's flags that really are fraud.

Section 4 will derive both from the confusion matrix.
""")

code(r"""
# ===============================================================
# 2.6  ADD THE LEAKED COLUMN AND TRAIN
# ===============================================================
leak_train = features.add_leaky_feature(parts["train"])
leak_test = features.add_leaky_feature(parts["test"])

xl_train, yl_train = features.feature_matrix(leak_train, include_leak=True)
xl_test, yl_test = features.feature_matrix(leak_test, include_leak=True)
xl_test = features.align_columns(xl_test, xl_train)

tree = models.candidate_models()["Decision tree"]["estimator"]
leaky_model = models.build_pipeline(tree, "class_weight").fit(
    xl_train.iloc[-250_000:], yl_train.iloc[-250_000:])

leaky_lab = metrics.evaluate_at_budget(yl_test.to_numpy(), models.score_on(leaky_model, xl_test))
print(f"Validation recall: {leaky_lab['recall']:.1%}   precision: {leaky_lab['precision']:.1%}")
print("Ship it.")
""")

code(r"""
# ===============================================================
# 2.7  NOW DEPLOY IT
# ===============================================================
# At 2:14pm on a Tuesday, the instant the customer presses Buy, no transaction
# has been disputed yet. The column is empty. Nothing else changes.
# ===============================================================
production = xl_test.copy()
production[features.LEAKY_FEATURE] = 0.0

leaky_prod = metrics.evaluate_at_budget(yl_test.to_numpy(), models.score_on(leaky_model, production))

print(f"In validation : recall {leaky_lab['recall']:6.1%}")
print(f"In production : recall {leaky_prod['recall']:6.1%}")
print(f"\nThe promise missed reality by {leaky_lab['recall'] - leaky_prod['recall']:.1%} recall.")
""")

md(r"""
### The two questions that catch leakage

1. **Would this value exist at 2:14pm on Tuesday, the second the customer presses Buy?**
   Distance to merchant — yes. Dispute status — no, that is two months away.

2. **Was it recorded *because of* the decision we are trying to predict?**
   "Reviewed by an analyst" only exists because we flagged it.

Leakage does not look like a bug. **It looks like success** — the validation score is
excellent, everyone is pleased, and the problem only surfaces weeks after launch.
""")

# ═══════════════════════════════════════════ 3 · MODEL TRAINING ═════════════
md(r"""
---
# 3 · Model Training

**Question:** Which learning approach works best under the same conditions?

**Training**, also called **fitting**, means letting an algorithm examine labeled examples
and adjust its internal rules. Back to the honest feature set, we make two decisions:
**how to handle the 0.5% class imbalance**, and **which model to use**. By the end we will
have one selected candidate to validate.

We change **one thing at a time** — first the imbalance, then the model. Changing both at
once gives you a table nobody can interpret.
""")

md(r"""
## 3.1 Handling the imbalance

Only 1 transaction in 200 is fraud, so a model can score well while mostly ignoring fraud.
There are several standard fixes, and they are not equally good.

| Treatment | What it does |
|---|---|
| **None** | Leave the imbalance alone |
| **Class weight** | Tell the model that missing a fraud costs more |
| **Undersample** | Throw away most of the normal-transaction rows |
| **Oversample** | Duplicate the fraud rows |
| **SMOTE** | **Synthetic Minority Over-sampling Technique**: create synthetic fraud rows between real ones |

### How to read the comparison

In classification, **positive** means the event we are looking for — fraud here. It does
not mean "good." These abbreviations appear in the results:

| Term | Full name | Plain-language meaning |
|---|---|---|
| **TP** | True positive | Fraud correctly flagged — a fraud caught |
| **FP** | False positive | Normal transaction incorrectly flagged — a false alarm |
| **FN** | False negative | Fraud incorrectly cleared — a fraud missed |
| **TN** | True negative | Normal transaction correctly cleared |
| **Precision** | — | Of everything flagged, the share that really was fraud |
| **Recall** | — | Of all real fraud, the share the model caught |
| **Fit (s)** | Fit time in seconds | How long the model took to learn from the training rows |
""")

code(r"""
# ===============================================================
# 3.1  THE BALANCING BAKE-OFF
# ===============================================================
# Same model, same data, same review budget. Only the treatment changes.
# ===============================================================
forest = models.candidate_models()["Random forest"]["estimator"]
bakeoff = models.run_balancing_bakeoff(forest, x_train, y_train, x_test, y_test, amounts_test)

charts.balancing_chart(bakeoff).show()
bakeoff[["Treatment", "TP", "FP", "FN", "Precision", "Recall", "Fit (s)"]]
""")

md(r"""
**The technique with the famous name did not win.** Read the table, not the reputation —
the simplest treatment here beats SMOTE, and is far faster to fit.

Worth carrying: *"we used SMOTE"* is not evidence that a model is good. Measuring is.
""")

md(r"""
## 3.2 Choosing a model

We will test four **candidate models** — different learning algorithms competing for the
job. A **model sweep** means training those candidates under the same conditions and
comparing their results.

| Model | High-level idea | Main trade-off |
|---|---|---|
| **Logistic regression** | Combines weighted features into one fraud score | Simple and explainable; limited to relatively simple boundaries |
| **Decision tree** | Learns a sequence of if/then questions | Easy to follow; one tree can **overfit**, memorizing examples instead of learning patterns that generalize |
| **Random forest** | Lets many decision trees vote | Usually more stable; harder to explain than one tree |
| **Gradient boosting** | Builds trees in sequence, each correcting earlier errors | Often powerful; more complex to tune and explain |

The balancing treatment is now **held constant** at the comparison winner, so the only
thing changing is the model itself. That makes the comparison fair.
""")

code(r"""
# ===============================================================
# 3.2  THE SWEEP
# ===============================================================
best_treatment = bakeoff.iloc[0]["Treatment"]
print(f"Holding the balancing treatment constant at: {best_treatment}\n")

leaderboard, fitted = models.run_model_sweep(
    x_train, y_train, x_test, y_test, amounts_test, treatment_name=best_treatment)

leaderboard[["Model", "TP", "FP", "FN", "Precision", "Recall", "Fit (s)", "Explainable"]]
""")

code(r"""
# ===============================================================
# 3.3  THE LEADERBOARD
# ===============================================================
charts.leaderboard_chart(leaderboard).show()
""")

md(r"""
### What is feature importance?

**Feature importance** estimates how much the fitted model depends on each input. Here we
shuffle one feature at a time and watch how much performance falls. A larger fall means
the model relied on that feature more. Importance does **not** prove that the feature
causes fraud.
""")

code(r"""
# ===============================================================
# 3.4  WHAT IS THE WINNER ACTUALLY USING?
# ===============================================================
# Measured by shuffling each column in turn and watching the score fall.
# ===============================================================
winner_name = leaderboard.iloc[0]["Model"]
selected_model = fitted[winner_name]["model"]

importance = models.permutation_importance_frame(
    selected_model, x_test.sample(40_000, random_state=42),
    y_test.sample(40_000, random_state=42), top_n=12)

charts.association_bars(importance, "Importance", f"What {winner_name} leans on",
                        "The columns the model would miss most if you took them away").show()
""")

md(r"""
### Two things to take from this

**Choosing a model is not just picking the top row.** Four things matter, and only the
first is on the leaderboard:

| | The question |
|---|---|
| **Performance** | How much fraud does it catch? |
| **Explainability** | Can we identify which features made the model flag this transaction? In lending, explaining a decline can be a legal duty |
| **Speed** | Can it score inside a checkout? |
| **Operability** | Who retrains it, and how often? |

**And it answers the question from section 2.** Amount and time of day are doing nearly all
the work. Distance and velocity barely register — so in *this* data, the two features the
analyst insisted on genuinely are not helping. That is worth taking back to them, not
quietly deleting.
""")

# ═══════════════════════════════════════ 4 · MODEL VALIDATION ═══════════════
md(r"""
---
# 4 · Model Validation

**Question:** How does the selected model behave on transactions it did not learn from?

We have a model. Now: **is it any good?** By the end of this stage we will understand its
mistakes, calculate precision and recall, and choose how many transactions humans can
review.

The tool for this is the **confusion matrix** — a 2 × 2 table comparing the model's
decision with what actually happened. Its four boxes are TP, FP, FN, and TN from section
3. A "confusion" is simply a disagreement between prediction and reality.
""")

code(r"""
# ===============================================================
# 4.1  THE CONFUSION MATRIX
# ===============================================================
# Scored on the six months the model has never seen. The cut is set so that
# exactly 3% of transactions go to a human -- the review budget the business has.
# ===============================================================
winner_scores = fitted[winner_name]["scores"]
result = metrics.evaluate_at_budget(y_test.to_numpy(), winner_scores, amounts_test)

charts.confusion_heatmap(result, "Held-out period: January to June 2026").show()
""")

md(r"""
## 4.1 The two numbers that matter

Both come straight out of those four boxes.

- **Precision** — of everything we flagged, how much really was fraud?
- **Recall** — of all the fraud that happened, how much did we catch?
""")

code(r"""
# ===============================================================
# 4.2  WORK THEM OUT BY HAND
# ===============================================================
tp, fp, fn = result["tp"], result["fp"], result["fn"]

print(f"Precision = {tp:,} / ({tp:,} + {fp:,}) = {tp / (tp + fp):.1%}")
print(f"Recall    = {tp:,} / ({tp:,} + {fn:,}) = {tp / (tp + fn):.1%}")
""")

code(r"""
# ===============================================================
# 4.3  SO IS IT GOOD?  --  compare it to doing nothing
# ===============================================================
# One line of code that says every transaction is clean and never flags anything.
# ===============================================================
nothing = metrics.never_fraud_baseline(y_test.to_numpy(), amounts_test)

pd.DataFrame({
    "Our model": [f"{result['accuracy']:.2%}", f"{result['recall']:.1%}", f"{result['tp']:,}"],
    'A model that says "never fraud"': [f"{nothing['accuracy']:.2%}",
                                        f"{nothing['recall']:.1%}", f"{nothing['tp']:,}"],
}, index=["Accuracy", "Recall", "Frauds caught"])
""")

md(r"""
### The do-nothing model scores higher on accuracy, and is worth nothing

That is **class imbalance**, and it is why accuracy is the wrong headline number. When the
thing you care about is rare, accuracy mostly measures how rare it is.

Fraud, defects, disease, churn, safety incidents — everywhere the interesting case is a
small minority, accuracy makes a useless system look excellent.

> **If a vendor leads with an accuracy figure on a rare event, ask for precision and
> recall. Every time.**
""")

md(r"""
## 4.2 The threshold is a business decision

A **threshold**, also called a **cutoff**, is the score a transaction must reach to be
flagged. We have been flagging 3% of transactions because that is what the analysts can
handle. That number came from the business, not from the maths — and moving it changes
everything.
""")

code(r"""
# ===============================================================
# 4.4  SWEEP THE REVIEW BUDGET
# ===============================================================
sweep = metrics.threshold_sweep(y_test.to_numpy(), winner_scores, amounts_test)
charts.threshold_sweep_chart(sweep, config.REVIEW_BUDGET).show()
""")

code(r"""
# ===============================================================
# 4.5  WHAT EACH CHOICE COSTS
# ===============================================================
options = pd.DataFrame([
    metrics.evaluate_at_budget(y_test.to_numpy(), winner_scores, amounts_test, b)
    for b in (0.005, 0.01, 0.02, 0.03, 0.05, 0.10)
])[["review_rate", "flagged", "tp", "fp", "fn", "precision", "recall",
    "review_hours", "dollars_missed"]]

options.columns = ["Review rate", "Flagged", "Caught", "False alarms", "Missed",
                   "Precision", "Recall", "Analyst hours", "$ missed"]
options.style.format({
    "Review rate": "{:.1%}", "Precision": "{:.1%}", "Recall": "{:.1%}",
    "Analyst hours": "{:,.0f}", "$ missed": "${:,.0f}", "Flagged": "{:,.0f}",
    "Caught": "{:,.0f}", "False alarms": "{:,.0f}", "Missed": "{:,.0f}",
})
""")

md(r"""
**Nothing in the maths says which row is right.**

Flag more, and you catch more fraud but interrupt more real customers. Flag fewer, and the
reverse. The answer depends on what a blocked customer costs against what a chargeback
costs — and only the business can answer that.

> The data scientist builds the slider. **The fraud lead decides where it sits.**
""")

code(r"""
# ===============================================================
# 4.6  PERFORMANCE WEEK BY WEEK
# ===============================================================
# Fraud tactics move on purpose, because there are people on the other side.
# Model decay means performance gets worse as real-world patterns change.
# ===============================================================
weekly = metrics.weekly_performance(parts["test"], winner_scores, result["threshold"])
charts.weekly_performance_chart(weekly).show()

print(f"Recall over the six months: best week {weekly['recall'].max():.0%}, "
      f"worst week {weekly['recall'].min():.0%}")
""")

# ═══════════════════════════════════════ 5 · MODEL PREDICTION ═══════════════
md(r"""
---
# 5 · Model Prediction

**Question:** How does a model output become a decision somebody can act on?

The model is trained and validated. Now it does the job it was built for: score
transactions it has never seen and hand a queue to a human. By the end we will have
individual predictions, a review queue, and saved files another application can use.

## 5.1 Score and decide

For each new transaction, this classifier returns an **estimated fraud probability**
between 0 and 1. We use it as a **risk score**: higher means more suspicious, not proven
fraud. Treat 80% as "rank this above 20%," not as a promise that exactly 8 of 10 similar
transactions are fraudulent.

The decision is a simple comparison:

| Term | Meaning here |
|---|---|
| **Score / estimated probability** | The model's risk estimate for one transaction |
| **Threshold / cutoff** | The minimum score that sends a transaction to review |
| **Flag** | The score reached the threshold; a human should review it |
| **Clear** | The score stayed below the threshold; do not send it to this queue |

The model is **not confirming fraud**. It is deciding which transactions deserve limited
analyst attention.
""")

code(r"""
# ===============================================================
# 5.1  SCORE THE MOST RECENT TRANSACTIONS
# ===============================================================
# These arrived after the test window. To the model they are brand new.
# ===============================================================
recent = features.build_features(data.join(data.recent_batch(transactions), customers))
x_recent, _ = features.feature_matrix(recent)
x_recent = features.align_columns(x_recent, x_train)

recent_scores = models.score_on(selected_model, x_recent)
recent["fraud_score"] = recent_scores

print(f"Scored {len(recent):,} transactions from "
      f"{recent['trans_date_trans_time'].min():%d %b %Y} to "
      f"{recent['trans_date_trans_time'].max():%d %b %Y}")
""")

md(r"""
### Four example predictions

The middle two rows are especially important: one is above the cutoff and one is below it.
Their different decisions come from which side of the same threshold they land on, not
from certainty about what happened.
""")

code(r"""
# ===============================================================
# 5.2  EXAMPLES  --  score + threshold = decision
# ===============================================================
examples = metrics.prediction_examples(recent, recent_scores, result["threshold"])
examples.style.hide(axis="index").format({
    "Transaction": "{:%Y-%m-%d %H:%M}", "Amount": "${:,.2f}",
    "Estimated fraud probability": "{:.1%}",
})
""")

md(r"""
The **Why this decision** column gives the exact rule: compare the score with the cutoff.
The amount, category, and observed context help an analyst investigate, but they are not
proof and should not be described as causes of fraud.
""")

code(r"""
# ===============================================================
# 5.3  WHERE DID THE MODEL PUT THE WHOLE BATCH?
# ===============================================================
charts.score_distribution(recent_scores, result["threshold"]).show()
""")

code(r"""
# ===============================================================
# 5.4  THE REVIEW QUEUE  --  what an analyst opens in the morning
# ===============================================================
queue = (recent[recent["fraud_score"] >= result["threshold"]]
         .sort_values("fraud_score", ascending=False)
         .head(10)[["trans_date_trans_time", "fraud_score", "amt", "category",
                    "merchant", "distance_km", "card_txn_count_24h"]])

queue.style.format({"fraud_score": "{:.3f}", "amt": "${:,.2f}", "distance_km": "{:,.0f} km"})
""")

md(r"""
Notice what the analyst gets: not a verdict, but a **ranked queue**, sorted by fraud score
with the highest-risk transaction first, and transaction context attached. They can see
the amount, category, distance from home, and how busy the card has been. Those facts
support investigation; they do not prove why the model assigned its score or whether the
transaction is truly fraudulent.
""")

md(r"""
## 5.5 Handing the model over

A model is not finished when it is accurate. It is finished when **somebody else can run
it**. Four artefacts leave this notebook, including an MLflow package that a service can
load without knowing which training library created it.
""")

code(r"""
# ===============================================================
# 5.5  EXPORT THE MODEL, ITS MLFLOW PACKAGE, CARD, AND TEST BATCH
# ===============================================================
rationale = (
    f"{winner_name} with {best_treatment} balancing. Chosen at a "
    f"{config.REVIEW_BUDGET:.0%} review budget on a held-out period "
    f"({config.TEST_START:%b %Y} to {config.TEST_END:%b %Y}). "
    f"Recall {result['recall']:.1%}, precision {result['precision']:.1%}."
)

sizes = handoff.export(
    model=selected_model, model_name=winner_name, leaderboard=leaderboard,
    bakeoff=bakeoff, balancing_treatment=best_treatment, result=result,
    feature_columns=list(x_train.columns), test_frame=parts["test"],
    selection_rationale=rationale)

for name, size in sizes.items():
    print(f"  {name:<24} {size}")
""")

code(r"""
# ===============================================================
# 5.6  CHECK THE HANDOFF REPRODUCES
# ===============================================================
# Reload from disk and re-score. If the saved model does not reproduce the numbers
# in its own card, the handoff is broken -- better to find out here.
# ===============================================================
check = handoff.verify()

print(f"claimed    : recall {check['claimed']['recall']:.4f}")
print(f"reproduced : recall {check['reproduced']['recall']:.4f}")
assert all(abs(v) < 1e-6 for v in check["drift"].values()), "Artefacts do not reproduce"
assert check["mlflow_max_probability_delta"] < 1e-12, "MLflow probabilities changed"
assert check["mlflow_decision_changes"] == 0, "MLflow changed review decisions"
print(f"MLflow maximum probability difference: {check['mlflow_max_probability_delta']:.2e}")
print("\nOK -- both models on disk are the model that was measured.")
""")

# ══════════════════════════════════════════════════════════ WRAP ════════════
md(r"""
---
## The five stages, and who has to be in the room

| Stage | What happened | Who is needed |
|---|---|---|
| **1 · Data Ingestion** | Two systems joined, the label questioned, the split made by date | Data engineer **+ the fraud team** |
| **2 · Feature Engineering** | Ratios, velocity, distance — none of which existed in the source | Data scientist **+ fraud analysts** |
| **3 · Model Training** | Five balancing treatments, then four models, one change at a time | Data scientist |
| **4 · Model Validation** | Confusion matrix, precision and recall, then the threshold | Data scientist **+ the business** |
| **5 · Model Prediction** | A ranked queue, with reasons, that a person can act on | **The fraud team** |

**Four of those five stages need somebody who understands the business.** One needs
somebody who understands models. Most of you will spend your career in the four.
""")

nb["cells"] = C
nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
nb.metadata["language_info"] = {"name": "python", "version": "3.11"}

out = "/Users/yuexinmao/Documents/customer_workshop/applied-ai-studio/notebooks/fraud-detection/01_fraud_build.ipynb"
nbf.write(nb, out)
print(f"wrote {out} with {len(C)} cells")
