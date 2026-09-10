"""Build 01_credit_build.ipynb in the five Module 4 teaching stages.

This file is the canonical source of the notebook. Never hand-edit the
generated JSON: change the text here and regenerate, so the notebook, the
`creditlab` package, and the exported artifacts can never drift apart.
Generation retains outputs for unchanged cell sources. Re-execute changed
cells and their affected dependents before publishing the notebook or HTML.

    node scripts/venv-python.mjs notebooks/credit-risk/scripts/build_notebook.py

Monetary amounts in markdown are written inside backticks (`NT$10,000`).
A bare pair of dollar signs in one paragraph is read as inline math by both
JupyterLab and nbconvert, which silently swallows the text between them.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import nbformat as nbf

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_DIR / "01_credit_build.ipynb"

notebook = nbf.v4.new_notebook()
cells: list = []


def cell_metadata(language: str) -> tuple[str, dict[str, str]]:
    cell_id = f"credit-build-{len(cells) + 1:03d}"
    return cell_id, {"id": cell_id, "language": language}


def md(text: str) -> None:
    cell_id, metadata = cell_metadata("markdown")
    cells.append(nbf.v4.new_markdown_cell(text.strip("\n"), id=cell_id, metadata=metadata))


def code(text: str) -> None:
    cell_id, metadata = cell_metadata("python")
    cells.append(nbf.v4.new_code_cell(text.strip("\n"), id=cell_id, metadata=metadata))


# ═══════════════════════════════════════════════════════════════════════════
# Title
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
# From a monthly account snapshot to an analyst review queue

**ITAI 2372 - Module 4 - AI in Finance and Credit Risk Management**

Modules 2 and 3 built a fraud model and an image model in the same five stages. Tonight we
use those stages again on **credit risk**, and add the thing finance brings that the other
two cases did not: **a decision that costs money either way**. Reviewing an account costs
staff time. Not reviewing it can cost the unpaid balance.

| | Stage | What happens |
|---|---|---|
| **1** | **Data Ingestion and Provenance** | Verify the source file, the license, and what one row means |
| **2** | **EDA and Feature Preparation** | Find the signal, set the protected attributes aside, build 7 features |
| **3** | **Model Training** | Baseline, then two real models on one identical split |
| **4** | **Validation and Operating Policy** | Turn probabilities into a money rule, then score untouched accounts once |
| **5** | **Prediction, Reason Codes and Handoff** | Walk real accounts end to end and export the exact measured system |

### The case

A card issuer's risk team can review a few hundred accounts a month, out of tens of
thousands. The narrow question is:

> **Which accounts should a credit analyst look at this month, before next month's payment
> is due?**

### The authority boundary, stated once and enforced throughout

```text
score  ->  policy decision  ->  analyst review  ->  intervention
```

**The model never contacts a customer, never changes a credit limit, and never labels
anyone a defaulter.** It produces a number. A written policy turns that number into
"review" or "do not review". A credit analyst decides what, if anything, happens to the
account. Compliance owns any notice the customer receives.

Three words that are not synonyms, and that this notebook keeps apart on purpose:

| Word | What it is here |
|---|---|
| **Score** | The model's estimated probability that this account misses its next payment |
| **Decision** | What the written policy does with that score: flag for review, or not |
| **Outcome** | What the account actually did the following month, recorded after the fact |

### The data

- **30,000 credit-card accounts** from one Taiwanese bank, observed April-September 2005
- **22.1%** of them missed the October 2005 payment
- One row is one cardholder; nobody appears twice
- CC BY 4.0, checksummed before conversion, committed beside this notebook

Nothing downloads while this notebook runs. All money amounts are in **New Taiwan dollars**
(written `NT$`), and every cost parameter in Stage 4 is a **synthetic classroom
assumption**, not a measured bank cost.
""")

code(r"""
# ===============================================================
# SETUP
# ===============================================================
import json
import time
import warnings

import numpy as np
import pandas as pd
import plotly.io as pio

from creditlab import charts, config, data, explain, features, handoff, metrics, models

warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 120)
pio.renderers.default = "notebook"
print(config.describe())
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 1
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 1 - Data Ingestion and Provenance

**Question:** Do we know exactly where this file came from, who it describes, and what one
row actually means?

**What you should expect to see:** a short table of verified facts - source, license,
checksum, row count, missing values - and then one real account displayed month by month.

**Why this stage exists in a real workflow:** a bank cannot use a model whose training data
it cannot trace. Federal Reserve model-risk guidance (SR 11-7, revised as SR 26-2 in April
2026) asks for the data's origin, its limits, and its fitness for the intended use *before*
anyone looks at accuracy.

**Output passed to Stage 2:** one verified dataframe of 30,000 accounts.
""")

md(r"""
## 1.1 The source file, and what happened to it

The original is a single Excel file published by the UCI Machine Learning Repository:
**"default of credit card clients.xls"**, 5.5 MB, donated by a Taiwanese bank and released
under CC BY 4.0.

Two things were done to it before it reached this folder, and nothing else:

1. **The checksum was verified.** A **SHA-256** is a file fingerprint: change one byte
   anywhere in the file and the fingerprint changes completely. Recording it means anyone
   can prove they have the same file we used, not a lookalike.
2. **It was converted to Parquet.** The XLS has a *two-row header* - a generic
   `X1, X2, X3...` row sitting above the real column names - so the converter takes the
   second row as the header. **Parquet** is a columnar file format that loads in
   milliseconds instead of seconds and stores the column types instead of guessing them.
   No row, column, or value was altered. That conversion is `scripts/build_dataset.py`,
   run once, not part of this notebook.

The target column was renamed from `default payment next month` to `DEFAULT`. That is the
only rename.
""")

code(r"""
# ===============================================================
# 1.1 LOAD THE COMMITTED SNAPSHOT AND VERIFY ITS PROVENANCE
# ===============================================================
accounts = data.load_accounts()
data.provenance_summary(accounts)
""")

md(r"""
`load_accounts()` is not just a read. It refuses the file unless it has 30,000 rows, zero
missing values, unique account IDs, and a 22.12% default rate. If someone swaps the parquet
for a different file, the notebook stops here instead of quietly teaching from the wrong
data.

### The context this data comes from

These accounts are a snapshot of the **2005-2006 Taiwan credit-card debt crisis**. Card
issuers had competed by handing out cards and limits with little underwriting; by 2006 the
country had roughly 700,000 "card slaves" carrying debt they could not service, and the
regulator forced the industry to restructure. A 22.1% default rate is not a normal month at
a normal bank. It is a crisis, captured in a spreadsheet.

That matters for a reason that outlives this dataset: **a model learns the era it was
trained on.** Nothing measured in this notebook transfers to US consumers in 2026.
""")

md(r"""
## 1.2 What one row means

One row is **one cardholder at the end of September 2005**: their credit limit, four
demographic fields, six months of behavior, and one outcome recorded a month later.

Six months of behavior means three readings per month:

| Reading | Column | Plain meaning |
|---|---|---|
| Repayment status | `PAY_0`, `PAY_2` ... `PAY_6` | On time, or how many months behind |
| Bill amount | `BILL_AMT1` ... `BILL_AMT6` | What the statement said they owed |
| Payment amount | `PAY_AMT1` ... `PAY_AMT6` | What they actually paid |

The column numbering is a real-data quirk worth ten seconds: **there is no `PAY_1`.** The
September column is called `PAY_0`, and the sequence resumes at `PAY_2` for August. The
`BILL_AMT`/`PAY_AMT` columns count backwards - `1` is September, `6` is April.

Here are the **first five actual rows**, with selected columns so the table stays readable.
Money is in `NT$`. `DEFAULT` is the later outcome: `1` = missed the October payment,
`0` = did not. It is the answer we learn to predict, never an input to the model.
`SEX` and `MARRIAGE` are category codes; these and `AGE` are shown as data, not permission
to use them in our classroom model. Below the preview, we unpack the first account.
""")

code(r"""
# ===============================================================
# 1.2 FIRST FIVE ACCOUNTS, THEN ONE ACCOUNT MONTH BY MONTH
# ===============================================================
preview_columns = [
  "ID", "LIMIT_BAL", "SEX", "MARRIAGE", "AGE",
  "PAY_0", "BILL_AMT1", "PAY_AMT1", "DEFAULT",
]
display(accounts.loc[:, preview_columns].head(5))

one = accounts.iloc[0]
months = ["April", "May", "June", "July", "August", "September"]
pd.DataFrame({
    "Month (2005)": months,
    "Repayment status": [one[c] for c in reversed(features.PAY_COLS)],
    "Billed (NT$)": [one[c] for c in reversed(features.BILL_COLS)],
    "Paid (NT$)": [one[c] for c in reversed(features.PAYAMT_COLS)],
}).assign(**{"Credit limit (NT$)": one["LIMIT_BAL"], "Missed October payment": one["DEFAULT"]})
""")

md(r"""
Read that row as a story rather than a table. This cardholder has a `NT$20,000` limit. In
April and May the repayment status is `-2` (no balance to pay). By August and September it
is `2` - **two months behind**. They were billed `NT$3,913` in September and paid nothing.
The last column says they missed October's payment too.

### The repayment-status codes, including the undocumented ones

| Code | Documented meaning |
|---|---|
| `-2` | No consumption that month - nothing to pay |
| `-1` | Paid the balance in full |
| `0` | Used revolving credit and paid at least the minimum |
| `1` to `8` | Months of payment delay |

The published paper that accompanies this dataset only defines `-1` and `1` through `9`.
The codes `-2` and `0` appear in the file with no documentation at all - and `0` is the
single most common value, 14,737 of 30,000 accounts. Guessing wrong here would corrupt
every feature built on top. Stage 2 states the interpretation we chose and why.
""")

md(r"""
## 1.3 What the file contains, and what it does not

Five groups of fields, each with a different job in this workflow.
""")

code(r"""
# ===============================================================
# 1.3 FIELD GROUPS AND THEIR ROLE
# ===============================================================
pd.DataFrame([
    ("Exposure", "LIMIT_BAL", 1, "How much money can be at risk"),
    ("Demographics", "SEX, EDUCATION, MARRIAGE, AGE", 4, "Audit only - never a model input"),
    ("Behavior: status", "PAY_0, PAY_2 ... PAY_6", 6, "How many months behind, each month"),
    ("Behavior: bills", "BILL_AMT1 ... BILL_AMT6", 6, "What the statement said they owed"),
    ("Behavior: payments", "PAY_AMT1 ... PAY_AMT6", 6, "What they actually paid"),
    ("Target", "DEFAULT", 1, "Did they miss the October 2005 payment"),
], columns=["Group", "Columns", "Count", "Role in this workflow"])
""")

md(r"""
### The fields that are absent, and why that is the more interesting list

A real issuer's behavioral risk model would also see income, employment, other debts, this
customer's bureau file, prior interventions, and the outcome of those interventions. **None
of that is here.** Two consequences we cannot argue our way out of:

- Everything measured later is about *this* population, in *that* year, with *these* seven
  behaviors. It is not a general statement about creditworthiness.
- Every account is observed over the **same** April-September window. There is no second
  time period, so an **out-of-time split** - training on early months and testing on later
  ones, the way Module 2 split fraud by date - is impossible here. A real bank validates
  behavioral models out-of-time. We cannot, and the model card has to say so.

### Stage 1 conclusion

The file is traceable, complete, and internally consistent, and one row is one cardholder
observed for six months. That is enough to start looking for signal - and the two
limitations above are now on the record before a single number gets measured.
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 2 - EDA and Feature Preparation

**Question:** What in these six months actually predicts a missed payment - and which
columns are we legally not allowed to use even though they would help?

**What you should expect to see:** the target rate, the single strongest pattern in the
dataset, three demographic gaps that we then deliberately set aside, and seven engineered
features each answering a question a credit analyst would ask out loud.

**Why this stage exists in a real workflow:** the model sees only what we hand it. What
gets built here decides both how accurate the model can be and whether anyone can explain a
decision to the customer it affects.

**Output passed to Stage 3:** a 60/20/20 split and a 7-column feature matrix.
""")

md(r"""
## 2.1 The target, and the three splits

**Target:** `DEFAULT` = 1 if the account missed its October 2005 payment.
**Rate:** 6,636 of 30,000 accounts = **22.1%**. Denominator: every account in the file.

Before measuring anything we cut the data three ways, and each part has exactly one job:

| Split | Accounts | Job |
|---|---|---|
| **Train** | 18,000 | The model learns its patterns here |
| **Validation** | 6,000 | We compare models and choose the policy here |
| **Test** | 6,000 | Scored **once**, at the very end, after everything is frozen |

The split is **stratified**: the 22.1% default rate is forced to be identical in all three
parts, so a difference between splits is never just a difference in how many defaulters
landed in each. One row is one customer and nobody appears twice, so a random split cannot
leak the same person across two parts - which is why a random split is safe here and was
not safe for fraud in Module 2.
""")

code(r"""
# ===============================================================
# 2.1 SPLIT 60/20/20, STRATIFIED ON THE TARGET, SEED 42
# ===============================================================
splits = data.split_accounts(accounts)
train_df, val_df, test_df = splits["train"], splits["validation"], splits["test"]
summary = data.split_summary(splits)
print(summary.to_string(index=False))
charts.class_balance(summary).show()
""")

md(r"""
### How to read this plot

- **Question:** Did the split preserve the outcome we are trying to predict, or did it
  concentrate the defaulters somewhere?
- **Marks and axes:** one bar per split; bar height is the number of accounts in that
  split. Blue is accounts that paid October 2005, red is accounts that missed it.
- **Denominator:** the percentage in the hover is *within that split* - 1,327 of 6,000
  validation accounts, not 1,327 of all 30,000.
- **What to notice:** the red band is 22.1% of every bar. Train, validation, and test carry
  the same outcome mix.
- **Term - class imbalance:** when one outcome is much rarer than the other. Here roughly
  one account in five defaults, so a model that predicts "nobody defaults" is right 77.9%
  of the time and useless. That number is the accuracy trap from Module 2, and it is why
  Stage 4 measures money rather than accuracy.
- **Why it matters:** a fair comparison between models needs an unchanging yardstick. If
  validation had a different default rate than train, we could not tell a better model from
  an easier split.
- **Boundary:** equal proportions do **not** mean the splits are interchangeable in every
  way. All three come from the same six months of one bank, so agreement between them says
  nothing about a different year or a different country.
""")

md(r"""
## 2.2 The strongest signal in the dataset

**The domain question:** *is this account already behind on its payments?*

That is the first thing a credit analyst asks, and the dataset answers it directly in
`PAY_0`, the repayment status for September 2005 - the most recent month before the outcome
we are predicting.
""")

code(r"""
# ===============================================================
# 2.2 DEFAULT RATE BY CURRENT REPAYMENT STATUS
# ===============================================================
charts.delinquency_gradient(train_df).show()
""")

md(r"""
### How to read this plot

- **Question:** how much does being behind *right now* change the chance of missing the
  next payment?
- **Marks and axes:** one bar per repayment-status group in September 2005. Bar height is
  the share of that group that went on to miss the October payment. Blue means not behind,
  orange one month, red two or more.
- **Denominator:** each bar's percentage is *within its own group* - the "2 months behind"
  bar is 1,635 training accounts, and 69.7% of those 1,635 defaulted. The bars do not sum
  to 100%.
- **What to notice:** the jump is not gentle. Not behind, **13.7%**. One month behind,
  **33.5%** - roughly two and a half times higher. Two months behind, **69.7%** - more
  likely to default than not. Three or more, **72.6%**.
- **Term - gradient:** a steady, ordered rise in the outcome rate as an input increases. A
  gradient this steep means the column carries real information; a flat bar chart would
  mean the column is noise.
- **Why it matters:** this one column does most of the work in every model we are about to
  fit, and it is the reason the reason codes in Stage 5 are readable - "is currently two
  months behind" is a sentence a customer can act on.
- **Boundary:** this is an **association measured in this population**, not a cause. Being
  two months behind does not *make* someone miss October; both are symptoms of whatever is
  actually happening in that household. And 30.3% of the accounts two months behind paid
  October just fine - a high-risk group is not a group of guaranteed defaulters.
""")

md(r"""
## 2.3 The columns we can see and may not use

The file contains sex, education, marital status, and age. They are not decoration - they
are measurably associated with the outcome. So we are going to look at them once, honestly,
and then take them out of the model.
""")

code(r"""
# ===============================================================
# 2.3 DEFAULT RATE BY SEX, EDUCATION, AND AGE BAND
# ===============================================================
charts.demographic_gaps(train_df).show()
""")

md(r"""
### How to read this plot

- **Question:** do the demographic columns in this file carry signal about the outcome?
- **Marks and axes:** three panels, one per column. Each bar is one group; bar height is
  the share of that group that missed the October payment. All three panels share the same
  vertical scale, so the bars are directly comparable.
- **Denominator:** each bar is a share *of that group in the training split* - the male bar
  is 24.4% of 7,179 male-coded accounts, not 24.4% of all 18,000.
- **What to notice:** real gaps, and small ones. Male-coded accounts default at **24.4%**
  versus **20.6%** female-coded. Graduate school **19.4%**, university **23.9%**, high
  school **24.5%**. Age is close to flat from 20 to 50 and drifts up after that. Nothing
  here is a clean separator, but nothing here is zero either.
- **Term - protected attribute:** a personal characteristic that law forbids a lender from
  using in a credit decision. In the US, the **Equal Credit Opportunity Act** and
  **Regulation B** cover sex, marital status, age, race, national origin, religion, and
  receipt of public assistance.
- **Why it matters:** **these columns exist in the data; US fair-lending law restricts
  using them in credit decisions; so we set them aside for the model and keep them only to
  audit it later.** `SEX`, `MARRIAGE`, and `AGE` will not be model inputs. They stay in the
  dataframe so Stage 4 can check whether the finished model treats those groups
  differently - which is a check you cannot run if you delete the columns.
- **Boundary:** a gap in a bar chart is not evidence of discrimination by anyone, and it is
  not a fact about the groups. It is a description of 18,000 accounts at one Taiwanese bank
  in 2005, shaped by whoever that bank issued cards to.

**`EDUCATION` is the uncomfortable middle case.** It is not a protected class under ECOA,
but it correlates with income, ethnicity, and national origin, and a model leaning on it
can produce a **disparate impact** - a neutral-looking rule that lands harder on a
protected group. We exclude it from the model inputs too, and we say why out loud rather
than letting the leaderboard decide.
""")

md(r"""
## 2.4 Undocumented codes, disclosed rather than quietly fixed

The codebook defines `EDUCATION` as 1-4 and `MARRIAGE` as 1-3. The file contains other
values. This is what real data looks like, and how it is handled is itself a governance
decision.
""")

code(r"""
# ===============================================================
# 2.4 UNDOCUMENTED CATEGORY CODES, BEFORE AND AFTER
# ===============================================================
before = accounts["EDUCATION"].value_counts().sort_index()
after = features.consolidate_codes(accounts)["EDUCATION"].value_counts().sort_index()
print("EDUCATION codes before:", before.to_dict())
print("EDUCATION codes after :", after.to_dict())
print("MARRIAGE code 0 rows  :", int((accounts["MARRIAGE"] == 0).sum()))
""")

md(r"""
`EDUCATION` codes `0`, `5`, and `6` appear on **345 accounts** and mean nothing documented.
`MARRIAGE` code `0` appears on **54**. Together that is 1.3% of the file.

The choice we made: **collapse undocumented codes into the documented "other" category**
(`EDUCATION` 0/5/6 -> 4, `MARRIAGE` 0 -> 3) and disclose it here, in the model card, and in
the exported evaluation file.

The alternatives, and why not:

| Option | Why we did not choose it |
|---|---|
| Guess what they meant | An undocumented guess becomes a permanent, invisible assumption |
| Drop those 399 accounts | Throws away real customers because of a codebook gap |
| Leave them as separate codes | Trains the model on categories nobody can define or defend |

None of this changes the model's inputs - `EDUCATION` and `MARRIAGE` are excluded anyway.
It changes the **audit tables**, and an audit that silently reclassified 399 people would
not be worth running.
""")

md(r"""
## 2.5 Seven features, each answering a question an analyst would ask

We do not hand the model the 20 raw behavior columns. We hand it **seven engineered
features**.

**Term - feature engineering:** turning raw stored columns into quantities that state the
thing you actually care about. Input: 20 raw monthly columns. Operation: arithmetic across
those columns - a maximum, a count, a ratio, a difference. What is learned versus
configured: **nothing here is learned**; these definitions are written by hand and frozen
before any model runs. Output: one row of 7 numbers per account, in a fixed order. What it
does not prove: an engineered feature is only as meaningful as the question behind it.

| # | The analyst's question | Feature | How it is computed |
|---|---|---|---|
| 1 | Are they behind **right now**? | `months_late_now` | September status, floored at 0 |
| 2 | How bad did it get **at worst**? | `worst_delay_6m` | Largest delay across the 6 months |
| 3 | Is lateness a **habit**? | `num_late_months_6m` | Count of months at least 1 month late |
| 4 | How much of the limit are they **using**? | `utilization` | September bill / credit limit |
| 5 | Are they **paying down** what they are billed? | `payment_ratio_6m` | 6 months paid / 6 months billed |
| 6 | Is the balance **growing**? | `bill_trend_6m` | (September bill - April bill) / limit |
| 7 | How much can be **at risk**? | `credit_limit` | The credit limit itself |

**The repayment-code decision.** Codes `-2` (no consumption), `-1` (paid in full) and `0`
(revolving credit, minimum paid) are all treated as **not late** and clipped to zero. Only
values of 1 or more count as delinquency. Those three codes describe *how* someone paid on
time, not lateness - and collapsing them is what makes "is currently 2 months behind"
literally true when a reason code says it in Stage 5. A wrong choice here would put
"currently 0 months behind" in an adverse-action notice.

**Why seven and not twenty.** A technical check on validation accounts found the 20 raw
columns score **0.7684** and these seven score **0.7655** - a difference of 0.003. We give
up almost nothing, and in exchange every feature converts directly into a sentence. A
reason code that says "`BILL_AMT5` was influential" is unusable in a letter to a customer.
""")

code(r"""
# ===============================================================
# 2.5 BUILD THE SEVEN FEATURES AND LOOK AT THEIR RANGES
# ===============================================================
X_train = features.build_features(train_df)
X_val = features.build_features(val_df)
y_train = train_df[config.TARGET].to_numpy()
y_val = val_df[config.TARGET].to_numpy()

feature_frame = features.feature_frame(train_df)
feature_frame.describe().T[["mean", "50%", "max"]].assign(
    **{"What the analyst reads": [config.FEATURE_DISPLAY_NAMES[f] for f in features.ENGINEERED]}
)
""")

md(r"""
Two of those ranges are deliberate and worth naming.

**Term - clipping (capping):** replacing values beyond a chosen limit with the limit
itself. `utilization` and `payment_ratio_6m` are capped at `2.0`, and `bill_trend_6m` at
plus or minus `2.0`. A handful of accounts have a bill larger than twice their limit, or a
payment that clears months of arrears at once; uncapped, those few rows would stretch every
chart axis and dominate a linear model. The cap is a **display and stability choice we are
disclosing**, not a correction of the data.

The median `payment_ratio_6m` is **0.108** - the typical account in this crisis snapshot
paid about a tenth of what it was billed over six months. That is the 2005 story in one
number.

**The domain question behind feature 4:** *does using more of the limit go with missing
payments?*
""")

code(r"""
# ===============================================================
# 2.6 DEFAULT RATE BY SHARE OF THE CREDIT LIMIT USED
# ===============================================================
charts.utilization_gradient(feature_frame["utilization"].to_numpy(), y_train).show()
""")

md(r"""
### How to read this plot

- **Question:** does an account that is using more of its credit limit miss payments more
  often?
- **Marks and axes:** one bar per utilization band. Bar height is the share of accounts in
  that band that missed the October payment.
- **Denominator:** within the band - the "0-20%" bar is 7,923 training accounts, and 17.8%
  of those 7,923 defaulted.
- **What to notice:** a real but **much gentler** climb than the delinquency gradient:
  **17.8%** at the low end rising to **30.4%** for accounts billed more than their limit.
  Compare that with 13.7% to 69.7% in section 2.2.
- **Term - utilization:** the share of an available credit limit currently drawn down. Here
  it is the September statement balance divided by the credit limit, capped at 2.0.
- **Why it matters:** it confirms the feature earns its place while showing it is a
  *supporting* signal, not the story. Stage 5 will show one account flagged largely because
  of utilization plus a large balance, and the reason codes have to be honest about that.
- **Boundary:** high utilization is not misconduct. Someone can run near their limit for
  years and pay every month - about **74%** of the accounts in the 80-100% band did exactly
  that, and about **70%** of the accounts billed more than their limit did too.

### Stage 2 conclusion

Payment behavior carries the signal, the demographics are out of the model and kept for the
audit, and seven hand-written features now stand between the raw file and everything that
follows. **The features were frozen before any model was fitted** - so no model got to
choose the inputs that make it look good.
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 3
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 3 - Model Training

**Question:** Does a model beat the obvious rule - and if two models both work, which one
should a bank actually deploy?

**What you should expect to see:** a deliberately useless baseline, two real models trained
on the identical split, one leaderboard, and an argument that does **not** end with "pick
the top row".

**Why this stage exists in a real workflow:** a model that cannot beat a one-line rule is
not worth its maintenance cost, and a model whose decisions cannot be explained is not
usable in lending regardless of its accuracy.

**Output passed to Stage 4:** one selected model and its validation probabilities.
""")

md(r"""
## 3.1 The baseline that has to be beaten

**Term - baseline:** the simplest rule that requires no model, used as the floor everything
else must clear. Ours predicts the training default rate - 22.1% - for every single
account.

It is a bad model on purpose. It gives every account the same number, so it cannot put one
account above another, and a review queue is nothing but an ordering. But it exposes the
accuracy trap: convert it into a yes/no prediction of "will not default" and it is right
**77.9%** of the time while catching zero defaulters.
""")

code(r"""
# ===============================================================
# 3.1 THE MAJORITY BASELINE
# ===============================================================
baseline = models.majority_baseline(y_train, len(y_val))
print(f"Predicts {baseline.val_probabilities[0]:.4f} for all {len(y_val):,} validation accounts.")
print(f"Accuracy of the rule 'nobody defaults': {1 - y_val.mean():.1%}")
print(f"Defaulters it would catch: 0 of {int(y_val.sum()):,}")
""")

md(r"""
## 3.2 Two real models, one identical split

**Logistic regression** is the direct ancestor of the credit scorecard. It fits one weight
per feature and adds them up; the weights are the whole model, so it is inspectable by
anyone who can read a table. Banks have used this shape for fifty years.

**Gradient boosting** builds many small decision trees in sequence, each one correcting
what the previous ones got wrong. It captures interactions - "two months behind *and* high
utilization" behaving differently than either alone - that a straight weighted sum cannot.
The cost is that no human reads 100 trees.

Both are fitted on the **same 18,000 training accounts** with the **same 7 features** and
judged on the **same 6,000 validation accounts**. Holding the comparison fixed is what
makes it a comparison.
""")

code(r"""
# ===============================================================
# 3.2 FIT BOTH CANDIDATES AND BUILD THE LEADERBOARD
# ===============================================================
logistic = models.fit_logistic(X_train, y_train, X_val)
boosted = models.fit_gradient_boosting(X_train, y_train, X_val)
leaderboard = models.leaderboard([baseline, logistic, boosted], y_val)
leaderboard.style.format({"Validation AUC": "{:.4f}", "Validation PR-AUC": "{:.4f}",
                          "Fit seconds": "{:.2f}"}).hide(axis="index")
""")

md(r"""
**Term - AUC (area under the ROC curve):** the probability that the model gives a randomly
chosen defaulting account a higher score than a randomly chosen paying account. `0.5` is a
coin flip; `1.0` is perfect ordering. It measures **ranking only** and is completely
unaffected by where you later draw the line between "review" and "do not review" - which is
exactly why it is the right metric *before* a policy exists.

**Term - PR-AUC (area under the precision-recall curve):** a summary that focuses on the
rare outcome. Its no-skill floor is the base rate itself, so `0.2212` here means "no
better than chance", and the boosted model's `0.5277` is more than double that floor.

Reading the leaderboard: the baseline is pinned at `0.5000` because constant scores rank
nothing. Logistic regression reaches `0.7386`. Gradient boosting reaches `0.7655` - about
**2.7 AUC points** better.
""")

code(r"""
# ===============================================================
# 3.3 RANKING SKILL ON VALIDATION ACCOUNTS
# ===============================================================
charts.roc_curves(y_val, {
    "Logistic regression": logistic.val_probabilities,
    "Gradient boosting": boosted.val_probabilities,
}).show()
""")

md(r"""
### How to read this plot

- **Question:** if we walked down each model's ranking from riskiest to safest, how quickly
  would we accumulate the accounts that actually defaulted?
- **Marks and axes:** each line is one model. The horizontal axis is the share of *paying*
  accounts wrongly ranked above the cut - the false-alarm rate. The vertical axis is the
  share of *defaulting* accounts ranked above the cut. Every point on a line is one possible
  cut; the whole line exists without choosing any of them. The grey dashed diagonal is a
  model with no skill.
- **Denominator:** two different ones, on purpose. The horizontal axis divides by the 4,673
  validation accounts that paid; the vertical axis divides by the 1,327 that defaulted.
- **What to notice:** both curves sit clearly above the diagonal, and the boosted curve
  stays above the logistic one across nearly the whole range. Neither is close to the
  top-left corner - at a false-alarm rate of 20%, roughly half the defaulters are still
  below the cut. This is a genuinely hard prediction.
- **Term - ROC curve:** the trade-off between catching defaulters and raising false alarms,
  traced across every possible cut, with no cut chosen.
- **Why it matters:** the gap between the curves is the entire accuracy argument for
  gradient boosting. It is real, and it is small.
- **Boundary:** a curve is not a policy. Nothing on this chart says how many accounts to
  review - that decision needs money, and money arrives in Stage 4.
""")

md(r"""
## 3.4 Choosing a model, which is not the same as reading the top row

A leaderboard ranks on one axis. A bank's choice has at least three, and in lending the
second one can veto the first.

**Accuracy.** Gradient boosting wins by 0.027 AUC. Real, and modest.

**Explainability.** This is the one that decides it. **Regulation B requires an
adverse-action notice to state the specific principal reasons** for the decision - not
"our model declined you". **CFPB Circular 2022-03 (2022)** closes the obvious escape route:
a lender may not use a model whose reasons it cannot produce accurately, and the complexity
of the model is not a defense. So the question is not "is boosting explainable in the
abstract" but "**can this specific model produce accurate per-account reasons?**"

It can, and the mechanism is **SHAP**.

**Term - SHAP (SHapley Additive exPlanations):** a method that splits one prediction into
per-feature contributions that add up to that prediction. For a single account it answers
"how much did *this* account's utilization push *this* score, up or down?". It works on any
tree model, including 100 trees nobody reads. What it is **not**: a statement about cause,
about the customer's circumstances, or about what would happen if the feature changed. It
describes the model's arithmetic on this row.

**Runtime and maintainability.** Logistic regression fits in hundredths of a second and
gradient boosting in about one second, so retraining is cheap either way. The measurement
below is the one that matters operationally: the per-account cost of producing the reasons,
because in production that runs on every scored account, every month.
""")

code(r"""
# ===============================================================
# 3.4 CAN THE BOOSTED MODEL PRODUCE PER-ACCOUNT REASONS, AND HOW FAST?
# ===============================================================
explainer = explain.build_explainer(boosted.estimator)
start = time.perf_counter()
contributions = explain.shap_matrix(explainer, X_val)
elapsed = time.perf_counter() - start
print(f"SHAP for all {len(X_val):,} validation accounts: {elapsed:.3f} s "
      f"({elapsed / len(X_val) * 1000:.4f} ms per account)")

pd.DataFrame({
    "Feature": [config.FEATURE_DISPLAY_NAMES[f] for f in features.ENGINEERED],
    "Average influence on the score": np.abs(contributions).mean(axis=0),
}).sort_values("Average influence on the score", ascending=False).reset_index(drop=True)
""")

md(r"""
Reasons cost a fraction of a millisecond per account, so explainability is free at this
scale. And the ranking is the sanity check: **the two delinquency features dominate**,
exactly as Stage 2 predicted. A model whose most influential feature had been the credit
limit would have needed a hard look before going anywhere near a customer.

### Stage 3 conclusion

**Selected: gradient boosting.** It is the most accurate of the three by a modest margin,
it produces accurate per-account reasons in plain language at negligible cost, and it fits
in under a second so it can be retrained and re-validated on demand. Had the reason codes
not worked, the correct answer would have been logistic regression at 0.7386 - **because in
lending, an unexplainable model is not a legal option, however accurate it is.**
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 4
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 4 - Validation and Operating Policy

**Question:** A score is a number between 0 and 1. Who gets reviewed?

**What you should expect to see:** a check that the probabilities mean what they say, a
decision rule written down **before** any tuning, the one parameter we cannot look up,
a fairness experiment, and finally a single scoring of accounts the model has never seen.

**Why this stage exists in a real workflow:** the model does not decide anything. A written
policy does, and it is the policy that gets reviewed by risk committees, audited, and
defended. This is where a score becomes an action with a cost attached.

**Output passed to Stage 5:** a frozen model, a frozen policy, and honest numbers measured
on untouched accounts.
""")

md(r"""
## 4.1 Do the probabilities mean what they say?

Before a probability can be multiplied by money, it has to be **honest**. If the model says
`0.30` for a group of accounts, roughly 30% of them should actually default. If it says 30%
and 60% default, every cost calculation built on it is wrong.

**Term - calibration:** the agreement between predicted probabilities and observed
outcomes. AUC does not check this at all - a model can rank perfectly while stating
probabilities that are all far too low.

**How to check it:** sort the validation accounts into ten bins by predicted probability
(0.0-0.1, 0.1-0.2, and so on). In each bin, compare the average predicted probability with
the share that actually defaulted. This is a **reliability table**.
""")

code(r"""
# ===============================================================
# 4.1 RELIABILITY: PREDICTED VS OBSERVED, TEN BINS
# ===============================================================
calibration_table = metrics.reliability_table(y_val, boosted.val_probabilities)
print(calibration_table.to_string(index=False))
print(f"\nBrier score (lower is better): {metrics.ranking_metrics(y_val, boosted.val_probabilities)['brier']:.4f}")
charts.reliability_curve(calibration_table).show()
""")

md(r"""
### How to read this plot

- **Question:** when the model says 30%, do about 30% of those accounts actually default?
- **Marks and axes:** each dot is one probability bin. Horizontal position is what the
  model predicted on average in that bin; vertical position is what actually happened.
  Marker size is how many accounts fell in the bin. The grey diagonal is perfect honesty:
  predicted equals observed.
- **Denominator:** each dot's vertical value is a share *of the accounts in that bin only*
  - the 0.7-0.8 dot is 234 validation accounts, 67.5% of which defaulted.
- **What to notice:** the dots track the diagonal closely wherever there is data. The model
  says 6.6% and 7.4% default; it says 24.4% and 26.8% default; it says 44.7% and 44.1%
  default. Two mid-range bins are a few points off in each direction. The top-right dot is
  a **single account** - it sits at 100% because that one account defaulted, and it should
  be ignored.
- **Term - Brier score:** the average squared gap between predicted probability and actual
  outcome, across all accounts. `0.1396` here. It is a single-number summary of the same
  thing this plot shows; lower is better, and it is only meaningful compared with another
  model on the same data.
- **Why it matters:** because the next section multiplies these probabilities by real money.
  Honest probabilities are the licence to do that arithmetic at all.
- **Boundary:** calibration is a **group** property, not a per-account one. "27% of accounts
  in this bin defaulted" says nothing about which 27%. No individual account is 27%
  defaulted.

We tested a calibration wrapper (isotonic regression) and it improved the Brier score by
`0.0009` - not visibly better on the table above. We use the **raw probabilities**, which
keeps the deployed object one estimator and means SHAP explains exactly the model that made
the decision.
""")

md(r"""
## 4.2 The decision rule, written down before any tuning

Here is the rule, and it is written before we look at a single result.

> **Review an account when the money we expect to lose on it is larger than the cost of
> reviewing it.**

In arithmetic:

```text
probability of default  x  money at risk  x  share lost if it defaults   >   cost of one review
```

Four quantities, and it is worth being precise about where each comes from:

| Quantity | Value here | Where it comes from |
|---|---|---|
| Probability of default | The model's score | Measured, and calibrated in 4.1 |
| Money at risk (exposure) | September bill, capped at the credit limit | Observed in the data |
| Share lost if it defaults | `0.5` | **Synthetic classroom assumption** |
| Cost of one review | To be chosen in 4.3 | **Synthetic classroom assumption** |

**Term - exposure:** the money that would actually be at stake if this account went bad.
Not the credit limit - an unused limit costs nothing. We use the September statement
balance, capped at the limit.

**Term - loss given default (LGD):** the share of the exposed balance the bank does not
recover after a default. Real LGD comes from years of recovery data. `0.5` here is a round
classroom number.

**Why the rule needs two ingredients.** A 90% chance of losing `NT$800` is not worth an
analyst's afternoon. A 15% chance of losing `NT$400,000` is. Ranking by score alone would
get both of those backwards, and that is the whole lesson of this stage: **in finance the
model's output is an input to an economic decision, never the decision itself.**
""")

code(r"""
# ===============================================================
# 4.2 WHERE EVERY VALIDATION ACCOUNT SITS ON RISK x MONEY
# ===============================================================
expo_val = metrics.exposure(val_df)
charts.risk_exposure_plane(boosted.val_probabilities, expo_val, config.REVIEW_COST_NT).show()
""")

md(r"""
### How to read this plot

- **Question:** what does the rule actually select, seen from above?
- **Marks and axes:** the horizontal axis is money at risk if the account defaults; the
  vertical axis is the model's probability. Each cell is a small rectangle of that plane,
  shaded by **how many validation accounts fall in it** - darker means more accounts. The
  green curve is the rule's boundary; everything up and to the right of it gets flagged.
- **Denominator:** the shading is a count of accounts, not a rate. All 6,000 validation
  accounts are somewhere on this plane.
- **What to notice:** most accounts pile into the bottom-left - low probability, modest
  balance - and are nowhere near the boundary. The curve is a hyperbola, not a horizontal
  line: at `NT$50,000` of exposure it takes a probability around 0.40 to be flagged, while
  at `NT$400,000` a probability of 0.05 is enough. Two accounts with the same score land on
  opposite sides of it.
- **Term - operating policy:** the written rule that converts a model score into a workflow
  action. It is a separate object from the model, and it can be changed without retraining.
- **Why it matters:** this is the picture to keep when someone asks "what score gets you
  reviewed?" There is no such score. There is a curve, and where you sit on it depends on
  how much money is at stake.
- **Boundary:** exposure is capped at `NT$400,000` **for display only** so the dense region
  stays readable; the rule itself uses the uncapped value. And being above the line means
  *an analyst will look*, not that the account will default - the vertical axis makes that
  plain, since most flagged accounts sit well below 0.5.
""")

md(r"""
## 4.3 The one number we cannot look up

Three of the four quantities are settled. The fourth - **what one review costs** - is a
business input, not a data-science one, and reasonable people give very different answers:

- An analyst's hour, fully burdened: perhaps `NT$1,000`.
- An hour, plus the phone call, plus the case notes, plus the compliance check on anything
  the analyst does next, plus the share of the team's time that gets spent on accounts that
  were fine: closer to `NT$10,000`.

Rather than assert one, we **sweep** it: hold the model and the rule fixed, vary the review
cost, and watch what happens to the queue. Note the direction of the effect - a *higher*
assumed review cost makes the rule *more* selective, because the expected loss has to clear
a higher bar.
""")

code(r"""
# ===============================================================
# 4.3 SWEEP THE ASSUMED REVIEW COST (VALIDATION ONLY)
# ===============================================================
sweep = metrics.policy_sweep(boosted.val_probabilities, y_val, expo_val)
print(sweep.to_string(index=False))
charts.policy_sweep_chart(sweep, config.REVIEW_COST_NT).show()
""")

md(r"""
### How to read this plot

- **Question:** how does the assumed cost of one review change the size and the value of
  the queue?
- **Marks and axes:** both panels share a horizontal axis - the assumed cost of one review,
  from `NT$1,000` to `NT$20,000`. The top panel is the share of validation accounts flagged;
  the bottom is net savings in millions. The green dashed line marks the value we are about
  to freeze.
- **Denominator:** the top panel is a share of **all 6,000 validation accounts**. The bottom
  panel is a total, not a rate: prevented losses on flagged accounts that actually
  defaulted, minus the review cost paid on every flagged account.
- **What to notice, and this is the surprising one:** at `NT$1,000` per review, the
  economically optimal rule flags **57.1% of the book** - 3,425 of 6,000 accounts - and
  produces the *highest* net savings on the chart, `NT$26.7 million`. **If reviews are
  cheap, review broadly.** The arithmetic is not being clever; it is telling us that at
  `NT$1,000` a review pays for itself on a fairly ordinary account.
- **Term - net savings:** prevented losses minus review costs, measured against reviewing
  nobody. Every number in the bottom panel rests on the synthetic LGD of `0.5` and on the
  assumption that a review prevents the loss entirely.
- **Why it matters:** the model did not change between the left and right edges of this
  chart. **The business assumption changed, and the workload moved by a factor of ten.**
  When someone asks why the queue is the size it is, the honest answer is usually a number
  in a policy document, not a model.
- **Boundary:** "optimal" here means optimal *under these assumptions*. A team of six
  analysts cannot review 3,425 accounts a month, and this chart knows nothing about that.
  Capacity is a real constraint that the expected-cost rule does not contain.

**Freezing the parameter: `NT$10,000` per review.** That is the fully loaded figure -
analyst time, customer outreach, case notes, and the compliance work on whatever the
analyst decides. At that value the rule flags **13.0%** of validation accounts, a queue a
real team could staff, and returns `NT$11.9 million` in net savings. From here on, nothing
about the model or the policy changes.
""")

md(r"""
## 4.4 What the frozen policy does, and what it is worth comparing to

A single number is not evidence. Three comparison lines make it one.
""")

code(r"""
# ===============================================================
# 4.4 THE FROZEN POLICY ON VALIDATION, AGAINST THREE BASELINES
# ===============================================================
val_flags = metrics.policy_flags(boosted.val_probabilities, expo_val, config.REVIEW_COST_NT)
val_policy = metrics.policy_eval(boosted.val_probabilities, y_val, expo_val, config.REVIEW_COST_NT)
val_confusion = metrics.confusion(val_flags, y_val)
val_review_everybody = metrics.review_everybody_savings(y_val, expo_val, config.REVIEW_COST_NT)

# Fixed-capacity alternative: just review the top 10% by score, ignoring exposure.
top_k = int(0.10 * len(y_val))
capacity_flags = np.zeros(len(y_val), bool)
capacity_flags[np.argsort(-boosted.val_probabilities)[:top_k]] = True
capacity_savings = round(float(
    (y_val[capacity_flags] * expo_val[capacity_flags] * config.LOSS_GIVEN_DEFAULT
     - config.REVIEW_COST_NT).sum()))

# Money as NT$1,234 or -NT$1,234, never the confusing NT$-1,234.
def nt(amount: float) -> str:
    return f"{'-' if amount < 0 else ''}NT${abs(amount):,.0f}"

print(f"Expected-cost rule : {val_policy['flagged']:,} flagged ({val_policy['flagged_share']:.1%}), "
      f"net savings {nt(val_policy['net_savings_NT'])}")
print(f"Review nobody      : 0 flagged, net savings {nt(0)}")
print(f"Review everybody   : {len(y_val):,} flagged (100.0%), net savings {nt(val_review_everybody)}")
print(f"Top 10% by score   : {top_k:,} flagged (10.0%), net savings {nt(capacity_savings)}")
""")

md(r"""
**Review nobody** is the do-nothing line, worth `NT$0` by definition.

**Review everybody** loses `NT$29.2 million`. Six thousand reviews at `NT$10,000` cost far
more than the losses they prevent. This is the line that shows why prioritization is the
product: the bank is not short of accounts to look at, it is short of reviews to spend.

**Top 10% by score** is the obvious alternative policy - forget the money, just take the
riskiest accounts. It is *more precise* (67.0% of those flagged do default, versus 41.7%)
and it earns **less than half** the savings, `NT$5.7 million` versus `NT$11.9 million`,
because it spends reviews on high-risk accounts that owe very little. **Precision is not
the objective. Money prevented is.**
""")

code(r"""
# ===============================================================
# 4.4b VALIDATION CONFUSION AT THE FROZEN POLICY
# ===============================================================
metrics.confusion_table(val_confusion)
""")

md(r"""
Read the four counts as a workload plan, using the **validation split's 6,000 accounts** as
the denominator:

- **325** accounts flagged that did miss the payment. These are the reviews that could pay
  for themselves.
- **455** accounts flagged that paid anyway. **Term - false positive:** a flag on an account
  whose outcome turned out fine. This is not a malfunction. It is 455 customers who get a
  phone call they did not need, and 455 reviews the team spends.
- **1,002** accounts that missed the payment and were never flagged. **Term - false
  negative:** the miss. This is by far the largest error, and it is the price of a queue
  small enough to staff.
- **4,218** correctly left alone.

Two rates read off those counts, each with its own denominator:

- **Precision = 325 / 780 = 41.7%.** Of the accounts we flag, the share that actually
  default. This is what an analyst experiences: roughly two in five reviews find a real
  problem.
- **Recall = 325 / 1,327 = 24.5%.** Of the accounts that default, the share we flagged.
  Three quarters of defaults are missed.

**24.5% recall would be a failure for a smoke alarm and is fine here**, because the policy
was never asked to catch every default. It was asked to spend a limited number of reviews
where they prevent the most money - and the `NT$11.9 million` line is the answer to the
question that was actually asked.
""")

md(r"""
## 4.5 Remove the demographic columns, retrain, compare

Our classroom model excludes **`SEX`, `MARRIAGE`, and `AGE`**. What changes when we
leave them out?

1. Train a comparison model with the seven behavior features **plus** those three columns.
2. Remove the three demographic columns and **train again** on the seven behavior features.
3. Compare both models on the **same 6,000 validation accounts**.

Only the inputs change; the model type, settings, and training accounts stay the same.
**AUC** measures how well the model ranks accounts that later default above those that
do not: `0.5` is random ranking, `1.0` is perfect ranking. It is not percent correct.
""")

code(r"""
# ===============================================================
# 4.5 BEFORE AND AFTER REMOVING THREE COLUMNS
# ===============================================================
with_protected = models.fit_gradient_boosting_with_protected(
    X_train, y_train, X_val, train_df, val_df
)
without_protected = models.fit_gradient_boosting(X_train, y_train, X_val)
fairness = {
  "auc_without": metrics.ranking_metrics(y_val, without_protected.val_probabilities)["auc"],
    "auc_with": metrics.ranking_metrics(y_val, with_protected.val_probabilities)["auc"],
}
pd.DataFrame([
  {"Model": "Before: with SEX, MARRIAGE, AGE", "Input features": 10,
   "Validation AUC": fairness["auc_with"]},
  {"Model": "After: demographics removed, retrained", "Input features": 7,
   "Validation AUC": fairness["auc_without"]},
]).style.format({"Validation AUC": "{:.4f}"}).hide(axis="index")
""")

md(r"""
**Result: AUC goes from `0.7670` to `0.7655`, a decrease of `0.0015`.** Removing the
three columns changed ranking performance very little in this run. We keep the model
without them. This result is specific to this dataset, not a guarantee for another one.
""")

md(r"""
## 4.6 One limit to that result

**Removing columns does not prove fairness.** Other inputs can still reflect differences
between groups. This comparison measures the performance change only. Detailed group
checks stay in the exported governance data; they are not another table to work through here.
""")

md(r"""
## 4.7 Final check on 6,000 unseen accounts

Now ask a different question: **how does our chosen model work on accounts we did not
use to make any choices?**

Keep the seven behavior features and the review rule fixed. Fit the deployable model
on the training accounts, then check it once on the separate **test** accounts.
Do not change the model or rule to improve this test result. The same feature-preparation
steps travel with the model into the app.
""")

code(r"""
# ===============================================================
# 4.7 FIT THE DEPLOYABLE PIPELINE AND SCORE THE TEST SPLIT ONCE
# ===============================================================
y_test = test_df[config.TARGET].to_numpy()
pipeline, fit_seconds = models.fit_final_pipeline(train_df, y_train)
p_test = pipeline.predict_proba(test_df)[:, 1]

expo_test = metrics.exposure(test_df)
test_flags = metrics.policy_flags(p_test, expo_test, config.REVIEW_COST_NT)
test_metrics = metrics.ranking_metrics(y_test, p_test)
test_policy = metrics.policy_eval(p_test, y_test, expo_test, config.REVIEW_COST_NT)
test_confusion = metrics.confusion(test_flags, y_test)
test_review_everybody = metrics.review_everybody_savings(y_test, expo_test, config.REVIEW_COST_NT)

print(f"Pipeline fitted in {fit_seconds:.2f} s on {len(train_df):,} training accounts.\n")
print(f"AUC                 {test_metrics['auc']:.4f}")
print(f"Flagged             {test_policy['flagged']:,} of {len(y_test):,} ({test_policy['flagged_share']:.2%})")
print(f"Of those flagged, later defaulted: {test_policy['precision']:.1%}")
print(f"Of all defaults, flagged         : {test_policy['recall']:.1%}")
""")

code(r"""
# ===============================================================
# 4.7b WHERE THE 6,000 TEST ACCOUNTS LANDED
# ===============================================================
charts.confusion_heatmap(test_confusion, "test").show()
""")

md(r"""
### How to read this plot

Rows show **review or no review**; columns show **what happened the following month**.
The four counts add to 6,000 test accounts:

- **367:** flagged, then missed the payment.
- **394:** flagged, but paid.
- **960:** not flagged, but missed the payment.
- **4,279:** not flagged, and paid.

The queue contains **761 accounts**. Of those, **48.2%** later defaulted (precision).
Of all 1,327 defaults, we flagged **27.7%** (recall). This historical test checks the
review decisions; it does not tell us whether an analyst's intervention would help.

### The test numbers, compared with validation

| Metric | Validation | Test |
|---|---|---|
| AUC | 0.7655 | **0.7852** |
| Flagged | 780 (13.0%) | **761 (12.68%)** |
| Precision | 41.7% | **48.2%** |
| Recall | 24.5% | **27.7%** |
| Net savings | `NT$11,939,426` | **`NT$14,623,904`** |

The test results are a little better than validation. Different samples can give different
results; that is not a reason to retune on the test accounts.

### Stage 4 conclusion

The model is frozen, the policy is frozen, and on 6,000 accounts nobody tuned against, the
system flags **12.68%** of the book, finds a real problem in **48.2%** of the reviews it
asks for, and is worth **`NT$14,623,904`** under stated assumptions. Removing the three
demographic columns changed AUC very little; it did not prove fairness.
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 5
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 5 - Prediction, Reason Codes and Handoff

**Question:** What does a credit analyst actually receive on Monday morning - and can we
hand the exact measured system to software without it changing on the way?

**What you should expect to see:** three real flagged accounts walked from raw inputs to a
draft notice sentence, with the retrospective outcome kept deliberately separate; then five
artifacts exported and reloaded from disk to prove they reproduce.

**Why this stage exists in a real workflow:** a model that only exists inside a notebook has
never made a decision. The handoff is where the measured system becomes the running one,
and the only defense against silent drift is to reload the saved files and check.

**Output passed to the application:** `model.joblib`, `model_card.json`,
`operating_policy.json`, `evaluation.json`, and `sample_manifest.parquet`.
""")

md(r"""
## 5.1 Three real accounts from the flagged queue

All three are **test** accounts - never trained on, never used to choose anything - and all
three were flagged by the frozen policy. They are picked by position in the queue, not by
how well they illustrate a point:

| Pick | Rule | What it represents |
|---|---|---|
| **A** | Highest probability among the flagged | The clear case |
| **B** | Middle of the flagged queue by probability | The ordinary case |
| **C** | Lowest probability among the flagged | The borderline case |
""")

code(r"""
# ===============================================================
# 5.1 SELECT THREE FLAGGED TEST ACCOUNTS BY QUEUE POSITION
# ===============================================================
flagged_positions = np.where(test_flags)[0]
queue = flagged_positions[np.argsort(-p_test[flagged_positions])]
picks = {"A - highest risk": queue[0],
         "B - middle of the queue": queue[len(queue) // 2],
         "C - borderline flag": queue[-1]}

pd.DataFrame([{
    "Account": f"ID {int(test_df.iloc[i]['ID'])}",
    "Pick": label,
    "Credit limit (NT$)": int(test_df.iloc[i]["LIMIT_BAL"]),
    "September bill (NT$)": int(test_df.iloc[i]["BILL_AMT1"]),
    "Paid in September (NT$)": int(test_df.iloc[i]["PAY_AMT1"]),
    "Months behind now": int(max(test_df.iloc[i]["PAY_0"], 0)),
} for label, i in picks.items()])
""")

md(r"""
## 5.2 The same four steps for each account

For every account the workflow does exactly this, in this order:

```text
inputs  ->  score  ->  policy arithmetic  ->  route  ->  reasons
```

The **route** is one of two values and nothing else: `priority_review` (a named analyst
picks it up this month) or `standard_monitoring` (no review; it stays in ordinary
monitoring and is scored again next month).
""")

code(r"""
# ===============================================================
# 5.2 WALK EACH ACCOUNT FROM INPUTS TO REASONS
# ===============================================================
X_test = features.build_features(test_df)
test_explainer = explain.build_explainer(pipeline.named_steps["model"])
pick_positions = list(picks.values())
pick_contributions = explain.shap_matrix(test_explainer, X_test[pick_positions])

for (label, i), contribution in zip(picks.items(), pick_contributions):
    row = test_df.iloc[i]
    expected_loss = p_test[i] * expo_test[i] * config.LOSS_GIVEN_DEFAULT
    print(f"=== {label}  -  account ID {int(row['ID'])} " + "=" * 26)
    print(f"  score              p(missed next payment) = {p_test[i]:.4f}")
    print(f"  money at risk      NT${expo_test[i]:,.0f}")
    print(f"  policy arithmetic  {p_test[i]:.4f} x NT${expo_test[i]:,.0f} x {config.LOSS_GIVEN_DEFAULT} "
          f"= NT${expected_loss:,.0f}  vs  review cost NT${config.REVIEW_COST_NT:,}")
    print(f"  route              {config.ROUTE_FLAGGED}")
    for n, reason in enumerate(explain.top_reasons(contribution, X_test[i]), start=1):
        text = reason["text"]
        print(f"  reason {n}           {text[0].upper()}{text[1:]}")
    print()
""")

md(r"""
Three accounts, three different arguments for the same decision.

**Account A** is flagged the way you would expect: a score of `0.89` and `NT$282,944` at
risk. Expected loss `NT$126,031` against a `NT$10,000` review - it clears the bar twelve
times over. Its reasons are pure delinquency.

**Account B** sits in the middle: `0.53` probability, `NT$54,033` at risk, expected loss
`NT$14,443`. It clears the bar, but not by much.

**Account C is the one to look at.** Its probability is `0.0633` - **lower than the 22.1%
base rate**. This account looks *safe*. It is flagged because it owes `NT$338,106`, so
`0.0633 x NT$338,106 x 0.5 = NT$10,695`, which just clears `NT$10,000`. And notice it
produced **one** reason, not three: only one of its seven features pushes risk up at all.

That is the reason-code function being honest rather than filling a quota. The rule is *up
to* three reasons, never padded - because a notice that lists three reasons when the model
had one is a false statement about how the decision was made.

For account C, the truthful summary is: **flagged for the size of the balance, not for the
level of risk.** That is a legitimate reason to spend an analyst's time, and it is a very
different conversation to have with the customer.
""")

code(r"""
# ===============================================================
# 5.3 ACCOUNT A - WHAT PUSHED THE SCORE, FEATURE BY FEATURE
# ===============================================================
position_a = picks["A - highest risk"]
frame_a = explain.contribution_frame(pick_contributions[0], X_test[position_a])
charts.reason_bar(frame_a, f"account ID {int(test_df.iloc[position_a]['ID'])}").show()
""")

md(r"""
### How to read this plot

- **Question:** which of this account's seven features pushed its score up, which pushed it
  down, and by how much?
- **Marks and axes:** one bar per feature. Bars to the **right** (red) pushed the score up;
  bars to the **left** (blue) pushed it down. Length is the size of the push. The vertical
  line at zero is "this feature made no difference for this account".
- **Denominator:** none - this is not a rate. It is a decomposition of **one account's**
  score. The units are log-odds, the internal scale on which the model adds contributions
  together before converting to a probability.
- **What to notice:** every bar is on the right. "Worst payment delay" pushes hardest
  (`+1.43`), then "months behind right now" (`+1.11`), then "late months in the last six"
  (`+0.39`). Nothing about this account argues in its favour.
- **Term - contribution:** how much this feature's value moved this account's score,
  relative to what the model would have said knowing nothing about it. Contributions are
  per-account: the same utilization can push one account up and another down, depending on
  everything else in the row.
- **Why it matters:** the top three red bars are literally the reason codes printed above.
  This chart is the audit trail behind the sentence a customer would read.
- **Boundary:** this describes **the model's arithmetic on this row**. It is not a cause,
  not a diagnosis of the customer's finances, and not a prediction of what would happen if
  a feature changed. "Worst delay contributed most" does not mean "fixing the delay would
  drop the score by 1.43".
""")

code(r"""
# ===============================================================
# 5.4 ACCOUNT C - THE SAME CHART FOR THE BORDERLINE FLAG
# ===============================================================
position_c = picks["C - borderline flag"]
frame_c = explain.contribution_frame(pick_contributions[2], X_test[position_c])
charts.reason_bar(frame_c, f"account ID {int(test_df.iloc[position_c]['ID'])}").show()
""")

md(r"""
### How to read this plot

- **Question:** what does the same decomposition look like for an account that was flagged
  despite a low score?
- **Marks and axes:** identical to the previous chart - red to the right pushes risk up,
  blue to the left pushes it down, length is the size of the push.
- **Denominator:** none; again a decomposition of one account's score.
- **What to notice:** the picture is inverted. **Six of the seven bars are blue.** The
  credit limit pushes hardest *downward* (`-0.47`), followed by utilization and past delays.
  Exactly one feature pushes up: "paid only 4% of billed amounts over the last 6 months"
  (`+0.16`), and it is the smallest bar on the chart.
- **Term - up to three reasons:** the reason-code rule emits only features whose
  contribution is positive, capped at three. Here that yields one. The function does not
  pad the list with the least-negative feature to reach three.
- **Why it matters:** an analyst opening this account should see immediately that the model
  is *not* alarmed. The policy flagged it, and the policy had a good reason - `NT$338,106`
  is a lot of money at 6% risk - but the model's own opinion is visible in this chart and it
  is mild.
- **Boundary:** do not read "only one risk reason" as "this account is safe". The expected
  loss still cleared the review cost. The chart explains the **score**; the decision came
  from the score **and** the balance together.
""")

md(r"""
## 5.5 What the analyst does, and what the customer might receive

**What lands in the queue.** The analyst gets the account, its score, its route, its
reasons, and the full account history. Nothing is decided for them. Their options are the
ordinary ones - call the customer, offer a payment plan, review the credit line, refer to
collections, or close the case with no action, which is the right answer for a large share
of flagged accounts.

**If, and only if, the analyst takes an adverse action** - reducing a credit line, denying
an increase, changing terms unfavourably - the customer must receive an **adverse-action
notice**. **Term - adverse-action notice:** the written statement Regulation B requires,
naming the **specific principal reasons** for the decision. Not "your score was low". Not
"our model flagged you". The actual reasons.

The reason codes are the raw material for that sentence. They are **not** the notice: a
compliance team writes the notice, in reviewed language, about an action a human took.
""")

code(r"""
# ===============================================================
# 5.5 DRAFT REASON SENTENCE - RAW MATERIAL, NOT A SENT NOTICE
# ===============================================================
SECOND_PERSON = {                      # the model's phrasing -> a customer-facing phrasing
    "is currently": "you are currently",
    "was up to": "your account was up to",
    "paid late in": "you paid late in",
    "paid only": "you paid only",
    "is using": "you are using",
    "balance grew": "your balance grew",
    "credit limit of": "your account has a credit limit of",
}

for label, position in [("A - highest risk", picks["A - highest risk"]),
                        ("C - borderline flag", picks["C - borderline flag"])]:
    contribution = pick_contributions[list(picks.values()).index(position)]
    phrases = []
    for reason in explain.top_reasons(contribution, X_test[position]):
        text = reason["text"]
        for model_phrase, customer_phrase in SECOND_PERSON.items():
            if text.startswith(model_phrase):
                text = customer_phrase + text[len(model_phrase):]
                break
        phrases.append(text)
    sentence = phrases[0] if len(phrases) == 1 else ", ".join(phrases[:-1]) + ", and " + phrases[-1]
    print(f"{label}, account ID {int(test_df.iloc[position]['ID'])} - draft principal reasons:")
    print(f"  \"We took this action because {sentence}.\"")
    print()
""")

md(r"""
Read account C's draft sentence and notice what it does not say. It does not mention the
`NT$338,106` balance that is the actual reason the policy selected the account. A notice
built only from SHAP reasons would be **accurate about the score and incomplete about the
decision** - and Regulation B asks for the principal reasons for the *decision*.

That is the discussion this account exists to start. The fix is not a better explainer; it
is recognising that the decision had two inputs and the explanation currently covers one.

## 5.6 The outcome, kept separate on purpose

Everything so far - score, policy, route, reasons - was computed from data available **in
September 2005**. Now, and only now, we look at what these accounts actually did in
October.
""")

code(r"""
# ===============================================================
# 5.6 WHAT ACTUALLY HAPPENED, LOOKED AT LAST
# ===============================================================
pd.DataFrame([{
    "Pick": label,
    "Account": f"ID {int(test_df.iloc[i]['ID'])}",
    "Score (September)": round(float(p_test[i]), 4),
    "Decision (September)": config.ROUTE_FLAGGED,
    "Outcome (October)": "missed the payment" if test_df.iloc[i][config.TARGET] == 1 else "paid",
} for label, i in picks.items()])
""")

md(r"""
Account A missed the payment. Accounts B and C paid.

The temptation is to score the model on this table: one right, two wrong. **That reading is
wrong, and it is the single most common misunderstanding of a probabilistic system.**

- Account B's score was `0.53`. The model said this account is roughly a coin flip. It paid.
  The model was not wrong; a 53% chance means 47 of every 100 such accounts pay.
- Account C's score was `0.0633`. The model said it was *very likely to pay*, and it paid.
  **The model was right about C.** The policy flagged it anyway, on purpose, because of the
  balance. Score and decision are different objects, and here they disagreed.

The only place a probability can be judged is in aggregate - which is precisely what the
reliability table in 4.1 and the 6,000-account confusion matrix in 4.7 are for. **A single
account's outcome can never confirm or refute a single account's score.**

This is also why the outcome column is the last thing shown, in its own cell, after the
decision. In the real workflow it does not exist yet.
""")

md(r"""
## 5.7 Hand the exact measured system to the application

Five files leave this notebook, and nothing else:

| Artifact | What it carries |
|---|---|
| `model.joblib` | The fitted pipeline - feature builder **and** model, in one object |
| `model_card.json` | Intended use, provenance, measured results, and limitations |
| `operating_policy.json` | The rule, its parameters, the routes, and the fallback |
| `evaluation.json` | Every table in Stages 3 and 4, for the governance view |
| `sample_manifest.parquet` | 60 test accounts with scores, routes, reasons, and outcomes |

The feature builder travels **inside** `model.joblib`, so the service cannot compute
utilization one way while this notebook computed it another. That mismatch -
**training-serving skew** - is one of the most common reasons a deployed model quietly
stops matching the numbers it was approved on.

The manifest also carries `audit_sex` and `audit_age_band`. Those are **withheld columns
the model never saw**, exported so the application's governance screen can rerun the
group checks mentioned in 4.6. The next cell calculates those checks for the handoff
without adding more tables to the lesson. They are audit data, never model inputs.
""")

code(r"""
# ===============================================================
# 5.7 BUILD THE MANIFEST, ASSEMBLE THE EVIDENCE, EXPORT
# ===============================================================
audit_sex = metrics.slice_audit(
  val_df, boosted.val_probabilities, val_flags, val_df["SEX"].map(config.SEX_LABELS), "sex")
audit_age = metrics.slice_audit(
  val_df, boosted.val_probabilities, val_flags, data.age_band(val_df["AGE"]), "age_band")
manifest = handoff.build_manifest(test_df, X_test, p_test, test_flags, test_explainer)
evidence = handoff.assemble_evidence(
    splits, leaderboard, calibration_table, sweep,
    val_policy, val_confusion, val_review_everybody,
    fairness, audit_sex, audit_age,
    test_metrics, test_policy, test_confusion, test_review_everybody,
)
sizes = handoff.export(pipeline, evidence, manifest)
for name, size in sizes.items():
    print(f"  {name:<26} {size}")
print(f"\nManifest: {len(manifest)} accounts, "
      f"{int((manifest['route'] == config.ROUTE_FLAGGED).sum())} priority_review, "
      f"{int((manifest['route'] == config.ROUTE_SAFE).sum())} standard_monitoring.")
""")

md(r"""
## 5.8 Reload from disk and prove nothing changed

The last check is the one that matters. Load `model.joblib` and `sample_manifest.parquet`
back **from disk**, re-score the manifest's accounts, and require the probabilities to be
**bitwise identical** to the stored ones - not close, identical - and every route to match.

Bitwise is the right bar because anything less hides real problems. A pipeline that
rebuilds features slightly differently, or a library version that rounds differently, would
produce scores that look fine and land a handful of accounts on the wrong side of the
policy boundary.
""")

code(r"""
# ===============================================================
# 5.8 FRESH RELOAD FROM DISK - SCORE AND ROUTE IDENTITY
# ===============================================================
identity = handoff.verify()
print(identity)
assert identity["probabilities_bitwise_identical"], "reloaded scores differ from exported scores"
assert identity["route_changes"] == 0, "reloaded routes differ from exported routes"

stored = json.loads((config.ARTIFACT_DIR / "evaluation.json").read_text())["test_frozen"]
assert stored["auc"] == round(test_metrics["auc"], 4)
assert stored["flagged"] == test_policy["flagged"]
assert stored["net_savings_NT"] == test_policy["net_savings_NT"]
print(f"\nOK - the model on disk reproduces the exported scores and routes exactly.")
print(f"OK - evaluation.json carries the measured test result: AUC {stored['auc']}, "
      f"{stored['flagged']} flagged, net savings NT${stored['net_savings_NT']:,}.")
""")

md(r"""
## 5.9 Where the handoff ends

```text
account snapshot -> validity check -> model score -> policy decision -> analyst queue
                                                                     -> analyst review
                                                                     -> intervention
                                                                     -> compliance notice
                                                                     -> next month's outcome
```

**The validity check comes before the model, not after.** An account with missing fields or
a code outside the documented range is excluded and logged for manual data review. It is
never silently scored, because a silently scored bad row produces a confident number nobody
can trace.

What this system does: **it orders a queue.** What it does not do: contact a customer,
change a credit limit, deny an application, price a loan, label anyone a defaulter, or send
a notice. Every one of those belongs to a person, and every one of them stays there.

### The five stages, and who has to be in the room

| Stage | What happened | Who is needed |
|---|---|---|
| **1 - Data Ingestion** | Source, license, checksum, population, and limits verified | Data team **and** the data steward who can say what a column means |
| **2 - EDA and Features** | Signal found, protected attributes set aside, 7 features frozen | ML team **and** credit-risk experts **and** compliance |
| **3 - Model Training** | Baseline beaten; model chosen on accuracy **and** explainability | ML team **and** whoever will defend a notice |
| **4 - Validation and Policy** | Costs turned scores into a queue; feature removal compared; test scored once | ML team **and** the business owner **and** model risk management |
| **5 - Prediction and Handoff** | Reasons produced, artifacts exported and verified | Engineering **and** credit analysts **and** compliance |

**The model is one component. The credit workflow is the thing that had to be designed.**

---

### What to take away

1. **Score, decision, and outcome are three different things.** Account C had a low score,
   a flag, and a clean outcome - all three at once, and all three correct.
2. **The policy, not the model, sets the workload.** Changing one assumed cost moved the
   queue from 13% to 57% of the book without touching the model.
3. **Removing the three demographic columns changed AUC by `0.0015` here.** That small
  performance change is not proof of fairness.
4. **A model that cannot explain itself cannot be used in lending**, whatever its AUC.
5. **The artifact that gets deployed has to be the artifact that was measured**, and the
   only way to know is to reload it and check.
""")


notebook["cells"] = cells
notebook.metadata["kernelspec"] = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}
notebook.metadata["language_info"] = {"name": "python", "version": "3.11"}

if __name__ == "__main__":
  previous = nbf.read(OUTPUT, as_version=4).cells if OUTPUT.exists() else []
  saved_cells = {(cell.cell_type, cell.source): cell for cell in previous}
  for index, cell in enumerate(notebook.cells):
    saved = saved_cells.get((cell.cell_type, cell.source))
    if saved is not None:
      notebook.cells[index] = saved
    else:
      digest = sha256(f"{cell.cell_type}:{cell.source}".encode()).hexdigest()[:12]
      cell.id = f"credit-build-{digest}"
      cell.metadata["id"] = cell.id
  nbf.validate(notebook)
  assert len({cell.id for cell in notebook.cells}) == len(notebook.cells)
  nbf.write(notebook, OUTPUT)
  print(f"wrote {OUTPUT} with {len(cells)} cells")
