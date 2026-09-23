"""Build the preserved advanced Module 6 forecasting reference notebook.

This file is the canonical source of the notebook. Never hand-edit the
generated JSON: change the text here and regenerate, so the notebook, the
``fclab`` package, and the exported artifacts can never drift apart.

    node scripts/venv-python.mjs notebooks/demand-forecasting/scripts/build_notebook.py

Monetary amounts in markdown are written inside backticks (`$25,200`). A bare
pair of dollar signs in one paragraph is read as inline math by both
JupyterLab and nbconvert, which silently swallows the text between them.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_DIR / "backup" / "02_forecast_reference.ipynb"

notebook = nbf.v4.new_notebook()
cells: list = []


def cell_metadata(language: str) -> tuple[str, dict[str, str]]:
    cell_id = f"fc-build-{len(cells) + 1:03d}"
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
# From two years of till receipts to one purchase order

**ITAI 2372 - Module 6 - AI in Retail and Supply Chain**

Module 5 watched a machine in real time and asked *is something wrong right now*. Tonight the
question points the other way: **what will happen next week, and how much of it should we buy
today?** That change brings two things no earlier case had - a **number instead of a class**,
and a **range around that number** that has to be honest enough to spend money on.

| | Stage | What happens |
|---|---|---|
| **1** | **Data Ingestion and Provenance** | Verify the source, the license, the checksum, and the quirks we refuse to hide |
| **2** | **EDA and Cohort Selection** | Find out what most products actually look like, then choose who gets forecast - without reading the future |
| **3** | **Forecasting** | Four baselines. The clever one loses. The eight-week average wins |
| **4** | **The Interval, and Why the Simple One Wins** | Three ways to build a range, the metric set, and the metric that lies |
| **5** | **From a Range to an Order, and Handoff** | The newsvendor rule, who it loses money for, where it breaks at Christmas, and what ships |

### The case

A UK gift wholesaler ships to small independent retailers. Somebody has to decide, every
week, how many of each product to have on the shelf. Too few and the sale walks away. Too many
and the money sits in a box. The narrow question is:

> **How many units of this product should we order for next week?**

### The authority boundary, stated once and enforced throughout

```text
weekly sales  ->  point forecast  ->  interval  ->  proposed quantity  ->  planner approves  ->  order
```

**The forecast is not a promise. The interval is not a guarantee. A planner approves every
order, and the system never places one.** The notebook produces a suggested quantity and the
evidence behind it. A person decides.

Three words that are not synonyms, and that this notebook keeps apart on purpose:

| Word | What it is here |
|---|---|
| **Forecast** | One number: our best single guess at next week's units |
| **Interval** | A low-to-high range around that number, with a stated hit rate |
| **Order** | The quantity a policy proposes, which is deliberately **not** the forecast |

### The claim we are allowed to make, and the one we are not

On 26 held-out weeks this system's 80% band **contained the actual demand 84.06% of the
time** across 12,194 product-weeks. It **does not hold at Christmas**: on the 50 most
autumn-skewed products, inside the October-November ramp, the same band caught only **66.2%**,
and every miss it made was **above** the band, which is the direction that empties a shelf.
Stage 5 shows that table rather than talking around it.

### The data

- **Online Retail II**: one UK-registered, non-store online gift wholesaler
- **1,067,371 raw transaction lines**, 2009-12-01 to 2011-12-09, UCI dataset 502, CC BY 4.0
- One committed row is **one product in one week**; one modeled row is **one product-week**
- The retailer was open on a Saturday **exactly once in 739 days**, which is the whole reason
  this lab works in weeks and not in days

Nothing downloads while this notebook runs. Every currency figure in Stage 5 is a **synthetic
classroom assumption**, labeled as such wherever it appears.
""")

code(r"""
# ===============================================================
# SETUP
# ===============================================================
import gzip
import hashlib
import json
import textwrap
import time
import warnings

import numpy as np
import pandas as pd
import plotly.io as pio

from fclab import (charts, config, data, features, forecast, handoff,
                   intervals, metrics, policy)

warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", 40)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 95)
pio.renderers.default = "notebook"

NOTEBOOK_STARTED = time.time()
print(config.describe())
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 1
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 1 - Data Ingestion and Provenance

**The question this stage answers:** *whose sales are these, am I allowed to use them, and
what is in the file that a spreadsheet view would quietly hide from me?*

**What you should expect to see:** a provenance table, a checksum that a second person can
reproduce, a list of six quirks we found and what we did about each one, and one weekday count
that changes the entire design of the lab.

**Why this stage exists in a real workflow:** a forecast is a claim about a specific business.
If you cannot say which business, over which dates, with which rows removed, then nobody can
audit the number and nobody should act on it. Provenance is not paperwork; it is the only
thing that makes the rest reproducible.

**What it passes to Stage 2:** a verified weekly file of 197,951 product-weeks, with every
cleaning decision written down.
""")

md(r"""
## 1.1 Who is being measured, and can we prove we have the same file

The source is the **Online Retail II** dataset in the UCI Machine Learning Repository
(dataset 502, CC BY 4.0, DOI 10.24432/C5CG6D). It is a real transaction log from **one**
UK-registered, non-store online gift wholesaler selling mainly to small business retailers.

That last sentence is a limit, not a footnote. Everything measured below is true of this one
wholesaler in 2010 and 2011. None of it is a fact about retail.

The raw workbook is 45.6 MB and is **not committed**. What ships with the lab is a 0.95 MB
gzipped CSV of weekly units per product, built once by `scripts/build_dataset.py`.
""")

code(r"""
# ===============================================================
# 1.1 PROVENANCE OF THE COMMITTED FILE
# ===============================================================
weekly = data.load_weekly()
print(data.provenance_summary(weekly).to_string(index=False, line_width=140))
print(f"\nCitation: {config.DATASET_CITATION}")
""")

md(r"""
## 1.2 The checksum, and why it is taken on the CSV and not on the .gz

**Term - checksum (SHA-256):** a fixed-length fingerprint of a byte sequence. Identical bytes
give an identical fingerprint; a single changed character gives a completely different one. It
is how a second person proves they are holding your file and not a lookalike.

There is a trap here. **A gzip archive stores the time it was written inside itself.** Gzip
the exact same CSV twice, a minute apart, and the two `.gz` files have different bytes and
different digests even though not one row of data changed. So the archive's own digest is
recorded for reference but is **not reproducible on another machine**.

The digest that is checked is taken on the **decompressed CSV content**, which is the thing we
actually care about being identical.
""")

code(r"""
# ===============================================================
# 1.2 VERIFY THE CONTENT DIGEST, NOT THE ARCHIVE DIGEST
# ===============================================================
CONTENT_SHA256 = "4af85e406cbb7253e93e82ef5e184e43a88028057dbb6e5f916e8f97c8246d68"

payload = gzip.decompress(config.WEEKLY_CSV.read_bytes())
content_digest = hashlib.sha256(payload).hexdigest()

print(f"CSV content SHA-256   {content_digest}")
print(f"expected              {CONTENT_SHA256}")
print(f"match                 {content_digest == CONTENT_SHA256}")
print(f"\ngzip archive SHA-256  {data.file_digest()}")
print("  ^ recorded for reference only: gzip embeds a write timestamp, so this")
print("    digest changes every time the archive is rebuilt from identical data.")
assert content_digest == CONTENT_SHA256, "The committed weekly file is not the one this lab was measured on."
""")

md(r"""
## 1.3 Six things in the raw file we refuse to hide

Every one of these is a decision somebody made, and every one of them changes the demand
number. They are listed rather than silently applied, because "we cleaned the data" is not a
sentence an auditor can check.

Two of them are worth arguing about in class:

- **34,335 exact duplicate lines.** Counting them twice would inflate demand by roughly 3%.
  Counting them once assumes they are a system artifact and not two genuine identical
  purchases. We chose once. That is an assumption, not a fact.
- **243,007 lines with no customer at all (22.8%, guest checkout).** A recommender case would
  have to drop these; there is nobody to recommend to. A **demand** case keeps them, because
  a unit that left the warehouse is demand whether or not we know who bought it.

**Term - demand vs sales:** what we actually have is *sales* - units that left the warehouse.
*Demand* includes the units a customer wanted and could not get, and no till receipt in the
world records those. Every stockout in this file is invisible. That is a permanent ceiling on
what this lab can claim.
""")

code(r"""
# ===============================================================
# 1.3 WHAT WAS IN THE RAW WORKBOOK
# ===============================================================
print(data.quirks_table().to_string(index=False, line_width=140))
print(f"\nNon-product stock codes removed by name: {', '.join(config.NON_PRODUCT_CODES)}")
print(f"Codes that survive that list and are still not products: "
      f"{', '.join(config.SURVIVING_NON_PRODUCT_CODES)}")
print("  ^ left in on purpose. The cohort rule in Stage 2 is what actually keeps them out,")
print("    and a rule that works is better than a hand-maintained blocklist that rots.")
""")

md(r"""
## 1.4 One weekday count that decides the whole design

Here is the count that made this a weekly lab rather than a daily one.
""")

code(r"""
# ===============================================================
# 1.4 THE RETAILER IS CLOSED ON SATURDAYS
# ===============================================================
print(data.trading_days_frame().to_string(index=False, line_width=140))
print(f"\nTrading days in the record: {config.TRADING_DAYS} over {config.RAW_SPAN_DAYS} calendar days.")
print(f"Saturdays with any sale at all: {config.SATURDAYS_OPEN} "
      f"(the one exception is {config.SATURDAY_OPEN_DATE}).")
""")

md(r"""
**Read that table again.** Every other weekday has 94-104 trading days. **Saturday has one.**

A daily forecasting model trained on this file would learn a real, strong, perfectly
reproducible pattern: *demand collapses to zero every seventh day*. That pattern is not
demand. It is the shutter being down. The model would then spend its capacity predicting the
company's opening hours, and every weekly total built from it would still be right, which is
exactly why the bug would survive review.

**Aggregating to weeks makes the closure disappear into the aggregate**, where it belongs. One
row from here on is **one product in one week**, and a week is Monday through Sunday.

The file holds **104** weeks. The first and last are partial - the record starts mid-week on
2009-12-01 and stops mid-week on 2011-12-09 - so both edges are dropped and **102 complete
weeks** go forward. Keeping them would put two artificially small weeks at the two most
influential positions in a time series.
""")

md(r"""
### Stage 1 conclusion

The data is one wholesaler's real sales, licensed for reuse, verified by a digest taken on
content rather than on a timestamped archive, and cleaned by six decisions that are all
written down. The weekly grain is not a convenience - it is a **correction for a closed
shop**, and it is the first modeling decision this lab makes.
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 2 - EDA and Cohort Selection

**The question this stage answers:** *what does a typical product in this catalog actually
look like week to week, and which products are we honestly able to forecast at all?*

**What you should expect to see:** a rectangle of 4,871 products by 102 weeks, a distribution
showing that the median product sells nothing in most weeks, one product's series read out
loud, and then the single most important decision in the notebook - **which products join the
cohort, decided using only the training weeks.**

**Why this stage exists in a real workflow:** a planner does not want a forecast for every
line in the catalog. They want a forecast for the lines that move, and an honest "we cannot
forecast this" for the rest. Choosing that set is a modeling decision with a leakage trap
buried in it, and this stage walks straight into the trap on purpose.

**What it passes to Stage 3:** a dense panel, a 76/26 chronological split, and a cohort of
469 products chosen without ever looking at the test weeks.
""")

md(r"""
## 2.1 What one row is, and what a zero means

The weekly file only stores product-weeks in which **something sold**. A forecaster has to see
the weeks in which nothing sold, so `build_panel()` re-inflates it into a dense rectangle:
**one row per product, one column per week, an explicit `0` where nothing left the warehouse.**

**Term - dense panel:** a table with a row for every entity and a column for every time step,
with no gaps. The alternative - only storing the weeks that have data - is smaller, and it
quietly teaches a model that a product with two sales in two years is a product that sells
every time you look at it.

A zero in this rectangle means **no units of this product shipped that week**. It does not
mean the product was unavailable, discontinued, or out of stock; the file cannot tell those
apart. That ambiguity is a real limitation and it is why Stage 2 ends by refusing to forecast
most of the catalog.
""")

code(r"""
# ===============================================================
# 2.1 THE DENSE PRODUCT x WEEK PANEL
# ===============================================================
panel, names, prices = data.build_panel(weekly)
train_weeks, test_weeks = data.split_columns(panel)

print(data.panel_summary(panel).to_string(index=False, line_width=140))
print(f"\nOne row of the panel, {config.DEMO_PRODUCTS[0]}, first eight weeks:")
print(data.product_weeks(panel, config.DEMO_PRODUCTS[0], names).to_string(index=False, line_width=140))
""")

md(r"""
## 2.2 Most of this catalog cannot be forecast, and that is the finding

Before choosing a model, look at what there is to model.
""")

code(r"""
# ===============================================================
# 2.2 HOW OFTEN DOES A PRODUCT SELL NOTHING?
# ===============================================================
zero_share = 1 - features.nonzero_share(panel)
histogram = features.zero_week_histogram(panel)

print(f"Products in the catalog          {panel.shape[0]:,}")
print(f"Median product's zero-week share {zero_share.median():.1%}  "
      f"(of {panel.shape[1]} weeks)")
print(f"Products with NO zero weeks      {(zero_share == 0).sum():,}")
print(f"Products zero in >= 90% of weeks {(zero_share >= 0.90).sum():,}")

charts.zero_week_distribution(histogram, config.COHORT_SIZE, panel.shape[0]).show()
""")

md(r"""
### How to read this plot

- **Question:** across the whole catalog, how often does a product sell nothing in a week -
  and is the typical product something a forecaster can even work with?
- **Marks and axes:** one bar per 5-percentage-point band. The horizontal axis is the share of
  this product's **102 weeks** in which it sold zero units; the vertical axis counts products
  falling in that band. Green bars are the bands at or below the 10% cohort line; grey bars are
  everything else. The dashed vertical line is that 10% line.
- **Denominator:** each product's zero share divides by **102 weeks**. The bar heights divide
  by nothing - they are raw product counts out of **4,871**.
- **What to notice:** the distribution piles up on the **right**. The **median product sells
  nothing in 68.6% of weeks** - roughly seven weeks in ten with no sale at all. The green
  sliver on the left is small: only **469 of 4,871 products (9.6%)** clear the line.
- **Term - intermittent demand:** a series that is mostly zeros with occasional spikes. A
  moving average of a mostly-zero series returns a small fraction of a unit every week, which
  is never the right order quantity and is wrong in a way the usual error metrics barely
  notice. Intermittent series need their own methods (Croston's, or a compound
  demand-size-times-arrival-rate model), and this lab does not pretend otherwise.
- **Why it matters:** those 469 products carry **41.8% of all units** the wholesaler shipped.
  Refusing to forecast the other 90.4% of the catalog is not a failure of nerve; it is the
  decision that keeps every number later in this notebook meaningful.
- **Boundary:** this chart is measured over **all 102 weeks** so you can see the catalog's
  shape. **The cohort rule used to deploy reads the 76 training weeks only** - section 2.4
  shows why that difference matters, and it is not a small one.
""")

md(r"""
## 2.3 One product, read out loud

An aggregate distribution tells you what the catalog is. It does not tell you what a
forecaster is being asked to chase. Here is one of the cohort's steadiest sellers.
""")

code(r"""
# ===============================================================
# 2.3 ONE PRODUCT ACROSS ALL 102 WEEKS
# ===============================================================
charts.product_demand(panel, config.DEMO_PRODUCTS[0], names).show()
""")

md(r"""
### How to read this plot

- **Question:** what does a **good** case look like - a product that sells nearly every week -
  and how much of its week-to-week movement is actually predictable?
- **Marks and axes:** the dark line with markers is units sold per week for
  `JUMBO BAG RED RETROSPOT` (stock code 85099B). Horizontal axis is the Monday that begins
  each week; vertical axis is units. The dotted horizontal line is this product's **mean
  training week**. The shaded region and vertical rule mark the **train/test wall** - weeks to
  the right of it are never used to fit anything.
- **Denominator:** none. Every point is a raw weekly unit count, not a rate.
- **What to notice:** three separate things are happening at once. There is a **level** that
  drifts upward over two years. There is a **seasonal ramp** into the autumn, visible in both
  the 2010 and 2011 Q4s. And there is **week-to-week noise** large enough that any given week
  can double or halve without meaning anything. A point forecast can follow the first two. It
  cannot follow the third, and pretending otherwise is how forecasts get oversold.
- **Term - train/test split, chronological:** the first 76 weeks fit the model, the last 26
  score it, and the order is never shuffled. Shuffling a time series lets the model see
  November while predicting September, which is not a subtle leak - it is the whole game.
- **Why it matters:** the irreducible noise you see here is exactly what Stage 4's interval
  is built to measure. The width of that band is not a modeling weakness; it is a measurement
  of this chart.
- **Boundary:** this is one of the **easiest** products in the catalog. Do not read its
  regularity as typical - section 2.2 just showed you that the typical product is mostly zeros.
""")

md(r"""
## 2.4 The cohort, and the leak that is easy to miss

Now the decision. The rule is: **a product joins the cohort if it sold at least one unit in
at least 90% of the weeks the rule is allowed to read.**

The whole question is *which weeks the rule is allowed to read.*

- Read all **102** weeks -> **442 products**.
- Read only the **76 training** weeks -> **469 products**.

The 442 number is **smaller**, so it looks conservative, and that is exactly what makes the
mistake convincing. It is not conservative. It is **leaked**.

**Term - data leakage:** using information at model-build time that would not be available at
the moment the model has to make its prediction. Here the leak is not in the model's inputs;
it is in the **selection**. Choosing a cohort using all 102 weeks means the membership test
has read the 26 weeks the model is about to be graded on. Any product that faltered during the
test period gets quietly excluded before scoring, and the test score improves for a reason
that has nothing to do with forecasting.

The next cell measures exactly what that leak buys itself.
""")

code(r"""
# ===============================================================
# 2.4 CHOOSING THE COHORT ON THE TRAINING WEEKS ONLY
# ===============================================================
cohort = features.select_cohort(panel)           # reads the 76 TRAIN weeks only
leaky = features.leaky_cohort(panel)             # reads all 102 weeks - shown, never used
leak = features.leakage_evidence(panel)

print(features.cohort_rule_comparison(panel).to_string(index=False, line_width=140))
print()
print(f"honest cohort (train weeks only)     {leak['honest_size']} products")
print(f"leaky cohort  (all 102 weeks)        {leak['leaky_size']} products")
print(f"in both                              {leak['in_both']}")
print(f"only the leaky rule admits           {leak['only_in_leaky']}")
print(f"only the honest rule admits          {leak['only_in_honest']}")
print()
print("Share of TEST weeks with a sale, by group -- this is what the leak bought:")
print(f"  the 27 products only the LEAKY rule admits   "
      f"{leak['only_leaky_test_nonzero_share']:.1%}")
print(f"  the 54 products only the HONEST rule admits  "
      f"{leak['only_honest_test_nonzero_share']:.1%}")
print()
print(config.check_named_products(names, cohort))
""")

md(r"""
Look at the last two lines. The 27 products the leaky rule admits sell in **98.7%** of test
weeks. The 54 products the honest rule admits sell in **49.6%** of test weeks.

The leaky rule did not find better products. **It found products that were about to have a
good six months, by reading the six months.** Score a model on that cohort and it looks
better than it is, by an amount nobody can estimate after the fact.

We use the **469**. Some of them will disappoint during the test window, and they are supposed
to, because that is what next week does in a real business.
""")

code(r"""
# ===============================================================
# 2.4b WHAT THE COHORT IS, AND WHAT CHOOSING IT COSTS
# ===============================================================
print(features.cohort_stats(panel, cohort).to_string(index=False, line_width=140))
""")

md(r"""
## 2.5 The seasonality that Stage 5 will come back to collect

One last measurement before modeling, because it sets up the notebook's most important
failure.
""")

code(r"""
# ===============================================================
# 2.5 HOW SEASONAL IS THIS BUSINESS?
# ===============================================================
skew = features.q4_skew(panel, cohort)
print(features.seasonality_summary(panel, cohort).to_string(index=False, line_width=140))
print("\nThe five most autumn-skewed products in the cohort (Oct-Dec mean / Jan-Sep mean):")
print(pd.DataFrame({
    "StockCode": skew.head(5).index,
    "product": [names.get(c, "") for c in skew.head(5).index],
    "Q4 skew": skew.head(5).round(2).to_numpy(),
}).to_string(index=False, line_width=140))
""")

md(r"""
**The aggregate seasonality is mild. The product-level seasonality is not.**

Catalog-wide, the autumn averages about **1.65x** a normal week. That is a number a planner
would shrug at. But the median cohort product's skew is only **1.08x**, while the most skewed
product in the cohort runs at **9.36x** - it sells nine times as much per week in the autumn
as it does the rest of the year.

An average has hidden a factor of nine. Stage 5 shows what that does to an interval that was
validated on the average.
""")

md(r"""
### Stage 2 conclusion

The catalog is mostly zeros - the median product sells nothing in **68.6%** of weeks - so we
forecast **469 products** that carry **41.8%** of the units and say plainly that we cannot
forecast the rest. The cohort was chosen on the **76 training weeks only**; the same rule read
over all 102 weeks would have admitted 442 products whose test-window behaviour it had already
seen. **The 27-product difference is the leak, and it is worth 49 percentage points of
test-week activity.**
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 3
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 3 - Forecasting

**The question this stage answers:** *what is our single best guess at next week's units, and
how do we know it is any good?*

**What you should expect to see:** six candidate rules scored on exactly the same held-out
weeks, ranked worst to best. One of them is the textbook seasonal method and it comes **last**,
behind a rule that forecasts nothing at all. The winner is an eight-week average.

**Why this stage exists in a real workflow:** every forecasting project has somebody in the
room who wants to start with a neural network. The answer is not "no", it is "beat this first",
and this stage builds the *this*. A baseline that is never measured is a baseline that can
never be beaten, which means the fancy model can never be justified.

**What it passes to Stage 4:** a fitted forecaster whose entire learned state is, per product,
a list of past errors and its last eight observed weeks.
""")

md(r"""
## 3.1 Six candidate rules, one evaluation policy

All six are scored **one step ahead on a rolling origin**: to forecast week `t`, a rule may use
weeks up to `t-1` and nothing later, and after scoring, week `t`'s true value is revealed
before moving to `t+1`. That is what a planner actually experiences - every Monday you know
last week and you do not know this one.

**Term - MAE (mean absolute error):** average of `|actual - forecast|` across every scored
product-week, in units. Denominator: **12,194 product-weeks** (469 products x 26 test weeks).
It is in the same units as demand, so "MAE 52" means the typical week is missed by about 52
units.

**Term - RMSE (root mean squared error):** square the errors, average, square-root. Same units,
but it punishes one enormous miss far more than many small ones. Reported beside MAE because
in retail the enormous miss is the stockout, and the stockout is the thing you were worried
about.

The candidates:

| Rule | What it does |
|---|---|
| **Flat zero** | Forecast nothing, ever. Not a forecast - a floor |
| **Naive** | Next week equals last week |
| **Seasonal-naive** | Next week equals **the same week last year** |
| **Train mean** | Next week equals this product's average training week |
| **MA4** | Mean of the last 4 observed weeks |
| **MA8** | Mean of the last 8 observed weeks |
""")

code(r"""
# ===============================================================
# 3.1 THE BASELINE LEADERBOARD
# ===============================================================
baselines = forecast.baseline_table(panel, cohort)
print(baselines.to_string(index=False, line_width=140))

charts.baseline_mae(baselines).show()
""")

md(r"""
### How to read this plot

- **Question:** which simple rule predicts next week's units best, and is the seasonal method
  everyone reaches for actually any good here?
- **Marks and axes:** one horizontal bar per candidate rule, sorted worst at the top to best at
  the bottom. Bar length is **MAE in units** over the held-out weeks; the number printed at the
  end of each bar is that MAE. Green marks the adopted rule; red marks the seasonal method;
  grey is everything else. Hover shows each rule's RMSE too, so colour is never the only signal.
- **Denominator:** every bar averages over the **same 12,194 held-out product-weeks**. Nothing
  is scored on a different sample, which is the only reason the comparison means anything.
- **What to notice:** two results, and the second one is the lesson.
  1. **MA8 wins at MAE 52.31**, with MA4 close behind at 53.78. Averaging eight weeks is slow
     enough to ignore one loud week and fast enough to follow a real trend.
  2. **Seasonal-naive is last, at 84.52 - worse than forecasting zero forever (84.33).** Its
     RMSE is 231.85, the worst on the board by a wide margin.
- **Term - seasonal-naive:** predict this week with the same week one year ago. It is the
  standard baseline for seasonal series, and it works when you have several years to average.
  Here there is **one** prior year, so "the same week last year" is a **single noisy
  observation**, not a seasonal estimate. One promotion, one bulk order, one stockout in
  November 2010 becomes the entire plan for November 2011.
- **Why it matters:** the method that *sounds* most appropriate for a seasonal business is the
  one that fails hardest, and no amount of domain intuition would have told you that. Only
  scoring it did. This is the argument for baselines in one bar chart.
- **Boundary:** this ranks **point forecasts only**. It says nothing about uncertainty, and a
  point forecast alone cannot size an order - Stage 4 and Stage 5 are where that gets fixed.
  Nor does it prove MA8 is the best possible model; it proves MA8 beats five reasonable
  alternatives on this cohort and this window.
""")

md(r"""
## 3.2 The fit, which is a subtraction and a percentile

The adopted model has **no learned weights**. Fitting it means, for each of the 469 products:

1. walk the training weeks from week 8 onward;
2. forecast each one with the mean of the 8 weeks before it;
3. keep the error, `actual - forecast`.

That is **68 residuals per product** and they are the entire uncertainty model. Nothing is
optimized, there is no loss surface, and the seed does not matter.

**Term - residual:** the error a model made on data it was fitted on. Not a prediction - a
record of past misses. Stage 4 turns these into the interval, and that is the only place they
are used.
""")

code(r"""
# ===============================================================
# 3.2 FIT ON THE TRAINING WEEKS ONLY
# ===============================================================
fit_started = time.time()
forecaster = forecast.fit(panel, cohort, names, prices)
fit_seconds = time.time() - fit_started

demo = config.DEMO_PRODUCTS[0]
print(f"fitted {len(forecaster.product_ids)} products in {fit_seconds:.3f} s")
print(f"residuals kept per product: {len(forecaster.residuals[demo])}  "
      f"(weeks {config.WINDOW} to {config.N_TRAIN - 1} of the training window)")
print(f"\n{forecaster.name(demo)} ({demo}) -- its own error percentiles, in units:")
print(forecaster.residual_table(demo).to_string(index=False, line_width=140))
print(f"\nnext-week point forecast: {forecaster.point(demo):,.1f} units")
""")

md(r"""
### Stage 3 conclusion

**The eight-week moving average won, at MAE 52.31 units.** The textbook seasonal method came
last, behind forecasting nothing at all, because one year of history is one noisy observation
per week and not a season. The fit takes milliseconds and stores no weights - which is exactly
why the interval in Stage 4 can be computed at any quantile for free.
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 4
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 4 - The Interval, and Why the Simple One Wins

**The question this stage answers:** *how wrong could next week be, and can we put a number on
that which actually holds up?*

**What you should expect to see:** three families of interval method scored on identical weeks,
a gradient booster that wins the accuracy contest and **loses the promise**, the frozen metric
set for the deployed model, and one metric that ranks a useless forecast first.

**Why this stage exists in a real workflow:** you cannot size an order from a point forecast.
"Order 26,045" has no answer to "and what if it's a busy week?" The interval is the thing that
turns a forecast into a decision, so the interval - not the point forecast - is what has to be
validated.

**What it passes to Stage 5:** a scored holdout of 12,194 product-weeks with a low, a median
and a high on every row, and permission to read that band at **any** quantile.
""")

md(r"""
## 4.1 What an 80% interval actually promises

**Term - prediction interval:** a low-to-high range around a forecast, with a stated
probability that the real value lands inside it. Our band runs from the **10th to the 90th
percentile**, so it promises **80%**.

**Term - coverage:** the share of scored product-weeks whose actual fell inside the band.
Numerator: rows where `low <= actual <= high`. Denominator: **all 12,194 scored
product-weeks**. If a band promises 80% and delivers 60%, the band is not conservative or
aggressive - it is **wrong**, and every order sized from it is wrong in the same direction.

Three ways to build one, all scored on the same weeks:

| | Method | The idea |
|---|---|---|
| **A** | **Empirical residual quantiles** | Add the 10th and 90th percentile of *this product's own past errors* to its forecast |
| **B** | **Quantile gradient boosting** | Fit three separate gradient-boosted models, one per quantile, on lag and calendar features |
| **C** | **Split conformal** | Hold back training weeks, measure a half-width there, apply it everywhere |

Method A is about ten lines of numpy. Method B is the one that sounds like machine learning.
""")

code(r"""
# ===============================================================
# 4.1 THREE WAYS TO BUILD A BAND, SAME HELD-OUT WEEKS
# ===============================================================
design = features.design_matrix(panel, cohort)
interval_table, interval_extra = intervals.comparison_table(design)
print(intervals.readable_comparison(interval_table).to_string(index=False, line_width=140))

charts.interval_method_coverage(interval_table).show()
""")

md(r"""
### How to read this plot

- **Question:** which interval method keeps the promise it made? Not which is most accurate -
  which one, having said 80%, delivers 80%?
- **Marks and axes:** one horizontal bar per method. Bar length is **delivered coverage**; the
  percentage is printed at the end of each bar. The dashed vertical line is the **promised
  80%**. Green is the deployed method, red marks any method that came in **under** its promise,
  grey is the rest. Hover gives median band width and fit time, so colour is never the only cue.
- **Denominator:** every bar divides by the **same 12,194 held-out product-weeks**. Identical
  rows, identical rolling origin, for all seven variants.
- **What to notice:** **the thing to read is the distance from the dashed line, not the height
  of the bar.**
  - **A3, the deployed method, delivers 84.06%** against a promise of 80% - slightly wide,
    which errs toward having stock.
  - **B1/B2, gradient boosting, deliver 75.0%.** They come in **short**, which errs toward
    empty shelves.
  - C2, conformal scaled per product, lands at 81.1% and is a perfectly reasonable third choice.
- **Term - pinball loss (quantile loss):** the score a *quantile* forecast is judged on. It
  penalises a 90th-percentile prediction gently for being too high and harshly for being too
  low, and the reverse at the 10th. It is the honest way to score an interval, because plain
  MAE only ever looks at the middle line.
- **Why it matters:** B1 has the **best MAE of its middle line, 47.97 against A3's 51.57.** It
  is the more accurate model, and it is the wrong choice, because a band that promises 80% and
  pays 75% quietly under-orders on one week in twenty more than the planner was told. Accuracy
  is not the same property as calibration, and only one of them is what an order is sized from.
- **Boundary:** these coverages are averages over the whole holdout. An average coverage of 84%
  does not mean any particular product or any particular month gets 84%, and section 5.5 finds
  the slice where it does not.
""")

md(r"""
## 4.2 What the booster does that a demand model must not do

Before dismissing gradient boosting on coverage alone, look at what it actually printed.
""")

code(r"""
# ===============================================================
# 4.2 THE BOOSTER'S DEFECTS, COUNTED
# ===============================================================
print(intervals.gradient_boosting_defects(interval_extra["boosted"]).to_string(index=False, line_width=140))

simple = interval_table.loc[interval_table["method"].str.contains("DEPLOYED"),
                            "fit_seconds"].iloc[0]
boosted = interval_table.loc[interval_table["method"].str.contains("B1"),
                             "fit_seconds"].iloc[0]
print(f"\nfit time, empirical quantiles  {simple:.3f} s")
print(f"fit time, gradient boosting    {boosted:.3f} s  "
      f"({boosted / max(simple, 1e-9):,.0f}x slower, and that is three fits for three quantiles)")
""")

md(r"""
Two defects, and the second is the expensive one.

**The quantiles cross** on 8 rows: the model's 90th percentile comes in *below* its own 50th.
Three independently fitted models have no idea they are supposed to be ordered. Sorting the
three numbers per row repairs it in one line, which is why B2 exists in the table above - and
notice that repairing it moved coverage by **0.02 percentage points**. The defect was real and
was not the problem.

**The lower edge is negative demand on 443 rows - 3.63% of the holdout**, with a floor of
**-4.2 units**. The model has no concept that units cannot be negative. Clipping at zero fixes
the output and is a modeling assumption you have to state out loud, because it silently makes
the band asymmetric on exactly the low-volume products where the band matters most.

**And then the reason the simple method actually wins.** Empirical quantiles fit in about
**0.01 seconds**; the booster takes the better part of **two seconds** for three quantiles -
**roughly 200x slower**, with the exact multiple printed by the cell above and moving a little
from run to run. That gap is not about impatience. Because the simple method stores each
product's raw residuals, **any quantile can be read out of it for free, at any time, without
refitting.** The booster would need a whole new fit for every new quantile.

**That is the only reason Stage 5's interactive cost-ratio control can exist.** Move the
stockout-to-overstock ratio and the required order quantile moves with it; the simple method
answers instantly, and the booster would have to be retrained mid-conversation. The simplest
method won on calibration, and then won again on the thing the workflow needed.
""")

md(r"""
## 4.3 Scoring the deployed model, once

The holdout is scored **one time**. Nothing after this point is allowed to change the model,
which is what makes the number a measurement rather than a search result.
""")

code(r"""
# ===============================================================
# 4.3 THE FROZEN HOLDOUT
# ===============================================================
scored = forecast.score_holdout(panel, forecaster)
summary = metrics.score_frame(scored)

print(f"scored {summary['n_rows']:,} product-weeks "
      f"({summary['n_products']} products x {summary['n_test_weeks']} held-out weeks)")
print()
print(metrics.metric_table(summary).to_string(index=False, line_width=140))

charts.metric_panel(summary).show()
""")

md(r"""
### How to read this plot

- **Question:** taken together, what did the deployed forecaster actually deliver on data it
  had never seen?
- **Marks and axes:** four panels, each a small bar chart, each with its value printed on the
  bar. **Top left** - MAE and RMSE in units, beside the MAE of a flat-zero forecast.
  **Top right** - delivered coverage beside the promised 80%. **Bottom left** - pinball loss at
  the lower edge, the middle line and the upper edge. **Bottom right** - the median band width
  beside the median non-zero week of demand.
- **Denominator:** every panel is measured over the **same 12,194 held-out product-weeks**.
  Coverage is a share of those rows; MAE, RMSE and band width are in units; pinball is a loss
  with no units and is only meaningful in comparison.
- **What to notice:**
  - **MAE 51.57, RMSE 133.26.** RMSE is 2.6x MAE, which tells you the error distribution has a
    long tail: most weeks are missed by a little, a few are missed enormously.
  - **Coverage 84.06% against a promised 80%** - the band is slightly wider than it needed to
    be, and it errs toward having stock rather than toward an empty shelf.
  - **Pinball 8.894 / 25.783 / 19.027.** The lower edge is the easiest to get right; the middle
    line is the hardest.
  - **Median band width 88.08 units, against a median non-zero week of 34 units.** The honest
    interval is **2.59x wider than the typical week of demand it describes.**
- **Term - flat-zero comparison:** the grey bar top-left is what you score by forecasting
  nothing, ever - 84.33 units. It is printed beside MAE deliberately. A model that does not
  clear that bar by a wide margin has not learned anything, and section 4.5 shows a metric that
  fails this test spectacularly.
- **Why it matters:** that last panel is the honest news. The band is **wider than the
  forecast**, and a planner who was expecting a tidy plus-or-minus-ten is going to say so. The
  right answer is that the width is a measurement of the business's real week-to-week variance,
  not a defect of the model - and a narrower band would simply be a band that lies.
- **Boundary:** every number here is an **average over the whole holdout**. None of them
  licenses a claim about a specific product or a specific month.
""")

md(r"""
## 4.4 One product, one band, twenty-six weeks

The aggregate is the audit. This is what a planner is actually shown on a Monday morning.
""")

code(r"""
# ===============================================================
# 4.4 THE FAN CHART
# ===============================================================
charts.fan_chart(scored, config.DEMO_PRODUCTS[0], names).show()
""")

md(r"""
### How to read this plot

- **Question:** for one real product, week by week, did the band hold - and when it failed,
  which way did it fail?
- **Marks and axes:** horizontal axis is each held-out week; vertical axis is units. The shaded
  blue region is the **80% band** (10th to 90th percentile). The dashed blue line is the
  **point forecast**, the mean of the last eight observed weeks. Each dot is **what actually
  sold**: a dark circle when it landed inside the band, a **red X** when it did not - shape as
  well as colour, so the misses are readable without relying on colour at all.
- **Denominator:** the title counts covered weeks out of this product's **26 held-out weeks**,
  not out of the full 12,194.
- **What to notice:** the band **moves**. It is not a fixed plus-or-minus; it widens as the
  product's recent weeks get noisier and narrows when they settle, because it is built from
  this product's own residuals and those residuals are re-read every week. Watch the dashed
  line lag the actuals during the autumn climb - an eight-week average is structurally late to
  a ramp, and the band is what absorbs that lateness.
- **Term - rolling origin:** each week's forecast uses only the weeks before it, and then the
  true value is revealed before the next forecast is made. The dashed line is 26 separate
  one-week-ahead forecasts, not one long projection.
- **Why it matters:** this is the picture a planner actually reasons about. The point forecast
  answers "what do we expect"; the shaded region answers "how wrong could this be", and Stage 5
  reads an order quantity off the **top** of that region rather than off the dashed line.
- **Boundary:** one product covering most of its weeks proves nothing about the other 468. This
  is an illustration of the mechanism; section 4.3 is the evidence.
""")

md(r"""
## 4.5 The metric that ranks a useless forecast first

**Term - MAPE (mean absolute percentage error):** the average of
`|actual - forecast| / |actual|`. It is popular because it is unit-free and sounds
interpretable - "we were 12% off". It is also, on intermittent demand, **catastrophically
broken**, and this is the cleanest demonstration in the notebook.

The problem is the denominator. **MAPE divides by the actual.** On a week where the actual is
zero, the denominator becomes the smallest positive float the machine holds, and the error for
that one row becomes astronomically large. And the forecast that avoids that penalty best is
the forecast that predicts **zero**.
""")

code(r"""
# ===============================================================
# 4.5 MAPE RANKS THE USELESS FORECAST FIRST
# ===============================================================
intermittent = features.intermittent_set(panel)
mape_demo = metrics.mape_demonstration(panel, cohort, intermittent, scored)
print(metrics.mape_table(mape_demo).to_string(index=False, line_width=140))

print(f"\nOn the deployed cohort ({summary['n_rows']:,} product-weeks):")
print(f"  MAPE of the real forecast        {summary['MAPE_sklearn']:.3e}")
print(f"  MAPE of 'forecast nothing, ever' {summary['MAPE_flat_zero']:.4f}   <-- WINS")
print(f"  MAE  of the real forecast        {summary['MAE_point']:.2f} units")
print(f"  MAE  of 'forecast nothing, ever' {summary['MAE_flat_zero']:.2f} units")
""")

md(r"""
Read the two columns against each other.

**MAPE of the deployed point forecast: 8.27e+15.** MAPE of a forecast that says *zero units,
every product, every week, forever*: **0.9073**. By MAPE, forecasting nothing is roughly
nine quadrillion times better. **MAPE's advice is to shut the warehouse.**

MAE says the opposite and says it plainly: the real forecast misses by **52.31** units a week,
the flat zero by **84.33**. The real forecast is better by 38%.

**And MAE is not innocent either.** Look back at the Stage 3 leaderboard: **flat zero scored
84.33 and seasonal-naive scored 84.52.** By MAE, forecasting nothing at all beat the standard
seasonal method. That is not MAE malfunctioning the way MAPE is - it is a true statement about
how bad seasonal-naive is here - but it is a warning with the same shape. **A metric is a
proxy for a decision, and no single number is the decision.** That is why Stage 4 reports MAE
*and* RMSE *and* coverage *and* three pinball losses, and why Stage 5 stops using error
metrics entirely and starts counting money.
""")

md(r"""
## 4.6 Freezing the result

Eleven numbers were scored once by the technical spike and written into `fclab/config.py`. The
notebook re-measures them and refuses to continue if any has moved by more than 1%. If a
library upgrade or a data edit changes an answer, this cell is where you find out - not three
slides later in front of a class.
""")

code(r"""
# ===============================================================
# 4.6 ASSERT THE FROZEN TARGETS
# ===============================================================
frozen = handoff.assert_frozen(summary)
print(frozen.to_string(index=False, line_width=140))
print(f"\n{len(frozen)} frozen numbers checked, "
      f"{int((frozen['status'] == 'OK').sum())} OK, "
      f"{int((frozen['status'] != 'OK').sum())} drifted.")
""")

md(r"""
### Stage 4 conclusion

**The ten-line method beat the machine-learning method at the job that mattered.** Empirical
residual quantiles delivered **84.06%** coverage against a promised 80%; quantile gradient
boosting won on MAE (**47.97** against 51.57) and delivered **75.0%**, predicting **negative
demand on 3.63%** of rows along the way. The simple method is ~200x faster to fit and yields
**any** quantile for free, which is the only reason Stage 5's cost-ratio control can respond in
real time. And MAPE, on this data, recommends forecasting nothing - which is why it appears in
this notebook exactly once, as a warning.
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 5
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 5 - From a Range to an Order, and Handoff

**The question this stage answers:** *given a forecast and a band, how many units do we
actually propose - and who does that proposal hurt?*

**What you should expect to see:** one line of arithmetic students do themselves, a cost sweep
that confirms it, the products the policy makes **worse**, the month the interval stops
working, and then the exported files with a reload check.

**Why this stage exists in a real workflow:** everything before this point is a measurement.
This is where the measurement becomes an action with a cost attached, and where the difference
between "our model is 84% accurate" and "here is what to buy" gets closed - or gets exposed.

**What it passes on:** five artifact files, a manifest of ten walked-through products, and a
written boundary.

> **Every currency figure below is a CLASSROOM ASSUMPTION.** Nothing here is Online Retail II's
> real economics, and nothing here is any retailer's real margin.
""")

md(r"""
## 5.1 The newsvendor rule, in one line

Ordering the point forecast is the intuitive choice and it is the **wrong** one, for a reason
that has nothing to do with accuracy: **the two ways of being wrong do not cost the same.**

- Order too few - you lose the margin on a sale you could have made. Call that **`cu`**, the
  **understock** cost per unit.
- Order too many - you carry a unit for a week and risk marking it down. Call that **`co`**,
  the **overstock** cost per unit.

If `cu` is bigger than `co`, the cheapest plan is to deliberately over-order. The question is
*by how much*, and the newsvendor formula answers it exactly:

> **Order the quantity you expect to be enough with probability `cr = cu / (cu + co)`.**
> That is, read the demand band at the **`cr`-th quantile**.

**Term - critical ratio (`cr`):** the share of the cost of being wrong that sits on the
understock side. It is a probability, and it is the quantile you read the band at.

**Do this one yourself before running the cell.** If a stockout costs 4x what an overstock
costs, then `cu = 4`, `co = 1`, and:

```text
cr = cu / (cu + co) = 4 / (4 + 1) = 0.80
```

So order the **80th percentile** of the demand band - not the middle. Notice what this means:
the right order quantity **depends on the economics, not on the forecast.** Change the ratio
and the quantile moves, with the model untouched.
""")

code(r"""
# ===============================================================
# 5.1 THE CRITICAL RATIO, AND THE CLASSROOM COST ASSUMPTIONS
# ===============================================================
for ratio in config.RATIOS_TAUGHT:
    cr = policy.critical_ratio(cu=ratio, co=1.0)
    print(f"stockout costs {ratio}x an overstock  ->  cr = {ratio} / ({ratio} + 1) "
          f"= {cr:.3f}  ->  order the {cr:.0%} quantile of the band")

print()
assumptions = policy.cost_assumptions(prices, cohort)
print(assumptions[["Parameter", "Value"]].to_string(index=False, line_width=140))
print("\nWhere each of those comes from:")
for _, row in assumptions.iterrows():
    print(f"  {row['Parameter']}")
    for line in textwrap.wrap(row["Where it comes from"], 116):
        print(f"      {line}")
print()
for line in textwrap.wrap(config.COST_ASSUMPTION_NOTE, 116):
    print(line)
""")

md(r"""
## 5.2 Deriving the answer, then checking it

The formula predicted the answer before any sweep was run. That prediction is worth nothing
until it is checked against what the held-out weeks actually cost, so here is the check:
order the band at ten different quantiles, price every outcome, and see where the curve bottoms.
""")

code(r"""
# ===============================================================
# 5.2 THE COST CURVE
# ===============================================================
board = policy.PolicyBoard(panel, scored, forecaster, prices)
sweep = board.sweep()
cost_curve = board.cost_curve()

print(board.readable_sweep(sweep).to_string(index=False, line_width=140))
print("\nCheapest order quantile found by the sweep, against the formula's prediction:")
for row in cost_curve[cost_curve["is_minimum"]].itertuples():
    print(f"  {row.ratio}: sweep bottoms at the {row.order_quantile:.0%} quantile, "
          f"formula said {row.critical_ratio:.0%}  ->  "
          f"{'MATCH' if abs(row.order_quantile - row.critical_ratio) < 1e-9 else 'MISMATCH'}")

charts.cost_vs_quantile(cost_curve).show()
""")

md(r"""
### How to read this plot

- **Question:** does the newsvendor formula actually find the cheapest order quantity on
  held-out data, or does it just sound right?
- **Marks and axes:** horizontal axis is **which quantile of the band we order at**, from the
  30th to the 95th. Vertical axis is **total cost over all 26 held-out weeks** in classroom
  dollars - lower is better. Blue is a 4:1 stockout-to-overstock ratio, orange is 9:1. The
  **diamond** on each curve is that curve's cheapest point, found by brute force. The **dotted
  vertical lines** are where the formula said the minimum would be, drawn before the sweep ran.
- **Denominator:** none - these are total costs summed over **12,194 product-weeks**, not rates.
  Every one of them rests on `co = 0.10 x unit price`, which is an assumption.
- **What to notice:** **the diamond sits exactly on the dotted line, on both curves.** At 4:1
  the formula said 0.80 and the sweep bottoms at the 80th percentile; at 9:1 the formula said
  0.90 and the sweep bottoms at the 90th. Notice also that both curves are **asymmetric** -
  ordering too little climbs the cost much faster than ordering too much, which is the
  cost asymmetry showing up as a shape.
- **Term - out-of-sample:** this curve is priced on the 26 weeks the model never saw. A cost
  curve drawn on training data would prove nothing; it would only show that the model fits
  where it was fitted.
- **Why it matters:** this is the moment the rule stops being a formula from a textbook and
  becomes something you can defend to a planner. **We derived a quantile, then went and checked
  it on money.** That is why we are willing to apply it to next week, which has no cost curve.
- **Boundary:** the minimum is exact **for these assumed costs**. Change `co`, and the whole
  curve moves. The formula does not tell you what a stockout costs your business - somebody in
  operations has to, and that conversation is the actual deliverable here.
""")

md(r"""
## 5.3 The same rule makes some products worse, and we are going to look at them

At 4:1 the policy is cheaper **in total**. An average is a poor way to describe a decision that
is applied 469 separate times, so here is every product's outcome.
""")

code(r"""
# ===============================================================
# 5.3 WINNERS AND LOSERS UNDER ONE RULE
# ===============================================================
per_product = board.per_product(4)
outcomes = board.outcome_split()
print(outcomes.to_string(index=False, line_width=140))

at_four = outcomes[outcomes["ratio"] == "4:1"].iloc[0]
print(f"\nAt 4:1 the newsvendor order is cheaper on {at_four['cheaper']} of "
      f"{at_four['products']} products ({at_four['cheaper_share']:.1%}) and MORE "
      f"expensive on {at_four['more_expensive']}.")

charts.policy_outcomes(per_product, names).show()
""")

md(r"""
### How to read this plot

- **Question:** the policy is cheaper overall - but is it cheaper for **every** product, and if
  not, who pays for the average?
- **Marks and axes:** one thin bar per product, **469 of them**, ranked left to right from best
  outcome to worst. Bar height is the **percentage change in that product's holdout cost** when
  we order the 80th-percentile quantity instead of the point forecast. Bars **above** the zero
  line (green) are products the policy made cheaper; bars **below** it (red) are products the
  policy made **more expensive**. Hover names any bar and gives both cost figures.
- **Denominator:** each bar divides that product's cost change by **its own** point-forecast
  cost, so a product with a tiny absolute cost can show an enormous percentage. The counts in
  the annotation divide by **469 products**.
- **What to notice:** **354 of 469 products (75.5%) are cheaper. 115 are more expensive.** The
  red tail on the right is not noise and it is not a rounding artifact - it is roughly a quarter
  of the catalog getting a worse plan from a rule that the aggregate calls a success.
- **Display note - read the shape, not the scale.** One product, `RED RETROSPOT STORAGE JAR`,
  is annotated at **-13,990%**, and it flattens every other bar into the baseline. That figure
  is real arithmetic and almost no money: its holdout cost went from **`$0.98` to `$138.70`**.
  When a denominator is under a dollar, a percentage stops being informative. Nothing is capped
  or hidden here - hover any bar for its actual cost in both plans - but the cash losses worth a
  planner's attention are the ones in the next cell, where **`PAPER CHAIN KIT EMPIRE` goes from
  about `$162` to about `$785`, +383.6%**.
- **Term - the losers all have one thing in common:** they are **declining sellers**. The band
  is built from a product's own past errors; if a product sold well and is now fading, its
  80th-percentile quantity keeps buying for the business it used to be. The policy does not
  know the difference between a quiet week and a decline, and neither does the point forecast -
  but the policy is the one that pays extra for the mistake.
- **Why it matters:** this is what a planner needs to be told **before** the rule is switched
  on, not after. A rule that is right 75.5% of the time is a rule that visibly fails on 115
  products, and the person whose name is on those orders will notice. The next cell shows the
  cases the demo walks through by name.
- **Boundary:** "cheaper" here means cheaper **under the assumed 4:1 cost ratio, on these 26
  weeks**. It is not a profit claim, and it is not a promise about next quarter.
""")

code(r"""
# ===============================================================
# 5.3b THE NAMED WALK-THROUGH: FOUR WINNERS AND THE WORST LOSER
# ===============================================================
walk = list(config.D06_PRODUCTS) + [config.POLICY_LOSER]
print(policy.demo_table(per_product, names, walk, prices).to_string(index=False, line_width=140))
print("\n('Change' is the change in holdout cost: negative is cheaper under the policy.)")
""")

md(r"""
Four of those five are the deck's demonstration products, and they behave the way the rule
promises: `JUMBO BAG RED RETROSPOT` **-29.0%**, `WOODEN FRAME ANTIQUE WHITE` **-47.5%**,
`JUMBO BAG BAROQUE BLACK WHITE` **-38.3%**, `CHOCOLATE HOT WATER BOTTLE` **-23.1%**. In each
case the policy bought more, was short far less often, and the units left over cost less than
the sales it saved.

The fifth is `PAPER CHAIN KIT EMPIRE` at **+383.6%**, and it is in the demo on purpose. It is
a Christmas product whose 2011 autumn never arrived, so an 80th-percentile order kept buying
into a season that did not happen. **A demo that only shows the four winners is a sales pitch,
not an evaluation.**
""")

md(r"""
## 5.4 Where the interval stops working: the Christmas problem

Stage 4 reported **84.06%** coverage. Stage 2 warned that the catalog's mild 1.65x aggregate
seasonality hides product-level skews up to **9.36x**. Now the two meet.

The question is not "is the average good". It is **"is the average good in the weeks that
matter most"** - and in this business the weeks that matter most are the autumn ramp.
""")

code(r"""
# ===============================================================
# 5.4 COVERAGE, SLICED BY SEASON AND BY PRODUCT
# ===============================================================
coverage_weekly = intervals.coverage_by_week(scored)
seasonal = intervals.seasonal_coverage(scored, skew)
print(seasonal.to_string(index=False, line_width=140))

charts.christmas_coverage(coverage_weekly, scored, config.CHRISTMAS_PRODUCT, names).show()
""")

md(r"""
### How to read this plot

- **Question:** the band promised 80% and delivered 84% on average - does that promise still
  hold once the Christmas season starts?
- **Marks and axes:** two stacked panels sharing one time axis. **Top** - for each held-out
  week, the share of all **469** products whose actual landed inside its band; the dashed line
  is the promised 80%. **Bottom** - one product, `RED WOOLLY HOTTIE WHITE HEART.` (84029E): the
  shaded blue region is its 80% band, the dark line and markers are what actually sold, and a
  **red X** marks a week that fell outside the band. The **orange shaded column** across both
  panels is the **October-November ramp**.
- **Denominator:** each point in the top panel divides by the **469 products scored that week**.
  The bottom panel is raw units for one product across its **26 held-out weeks**.
- **What to notice:** the top panel sits comfortably above the dashed line through the summer
  and then **sags inside the orange column**. The bottom panel shows why in a form you can
  picture: this product ticks along at single-digit units all summer, well inside a band, and
  then sells **331 units in the week of 10 October and 673 in the week of 14 November**. The
  band never sees it coming. **All five of its misses are above the band.**
- **Term - conditional coverage:** coverage measured *within a slice* rather than over
  everything. A band can hit its target overall and miss badly in the one slice you care about;
  reporting only the aggregate is how that gets missed. The table above the plot is exactly
  this measurement.
- **Why it matters:** read the four slices again. All products outside the ramp: **85.2%**. All
  products inside the ramp: 82.0%. The **50 most Q4-skewed products** outside the ramp:
  **84.0%**. Those same 50 products **inside the ramp: 66.2%** - and **69% of those misses are
  above the band.** Above the band means demand exceeded the high estimate, which means the
  order was too small, which means an empty shelf in the highest-margin weeks of the year.
- **Boundary:** this is a **measured limitation, not a bug to be argued away.** An eight-week
  moving average cannot anticipate a spike it has never seen, and one year of history cannot
  teach it the shape of a season - Stage 3 proved that when seasonal-naive came last. The
  honest statement is: **this system should not be trusted unsupervised on Q4-skewed products
  during the ramp**, and the manifest flags them so a planner is shown that in the demo.
""")

code(r"""
# ===============================================================
# 5.4b ONE PRODUCT, WEEK BY WEEK, WITH THE VERDICT SPELLED OUT
# ===============================================================
table = intervals.product_week_table(scored, config.CHRISTMAS_PRODUCT)
covered = int((table["Result"] == "covered").sum())
above = int((table["Result"] == "MISS - above the band").sum())
below = int((table["Result"] == "MISS - below the band").sum())

print(f"{names.get(config.CHRISTMAS_PRODUCT)} ({config.CHRISTMAS_PRODUCT})")
print(table.to_string(index=False, line_width=140))
print(f"\ncovered {covered} of {len(table)} weeks = {covered / len(table):.1%} "
      f"against a promised {config.NOMINAL_COVERAGE:.0%}")
print(f"misses ABOVE the band (demand exceeded the plan): {above}")
print(f"misses BELOW the band (we over-ordered):          {below}")
""")

md(r"""
**This is the single most important table in the notebook.**

*(A note on the stock code, because a code that has drifted onto another product is the one bug
a teaching notebook cannot survive. The Module 6 spike report labelled this table
`KNITTED UNION FLAG HOT WATER BOTTLE`. In this dataset that name belongs to code **84029G**;
the 80.8% and five-misses-all-high numbers the spike printed are **84029E**,
`RED WOOLLY HOTTIE WHITE HEART.` - which is also the code its own demo manifest names. The code
is what was measured, so the code wins over the label, and `config.check_named_products`
asserts it in section 2.4 on every run.)*

Its annual coverage is **80.8%** - twenty-one weeks of twenty-six. Against a promise of 80%,
that is essentially perfect. Any dashboard would show this product as green, and any monthly
report would file it as a success.

Now read *when* the misses happened. The first miss is the week of **12 September**, the next
**10 October**, then **31 October**, then **14 November**, then **28 November**. **Every single
one is inside the Christmas ramp, and every single one is above the band.** There is not one
week all summer where the band failed.

So the product with textbook-perfect annual coverage failed **five times out of five in the
only weeks the business makes money**, and failed in the direction that empties the shelf.
**An aggregate metric can be exactly right and still be describing the wrong thing.**
""")

md(r"""
## 5.5 What ships, and proving it is what was measured

An artifact that was not reloaded and re-scored in a fresh state is an artifact nobody has
checked. The export writes five files; the verification loads them back **from disk** and
re-scores the entire holdout, requiring the forecasts to be **bitwise identical**.
""")

code(r"""
# ===============================================================
# 5.5 EXPORT
# ===============================================================
manifest = handoff.sample_manifest(panel, scored, per_product, names, prices)
evidence = handoff.assemble_evidence(
    data.provenance_summary(weekly),
    data.panel_summary(panel),
    features.cohort_rule_comparison(panel),
    leak,
    baselines,
    interval_table,
    summary,
    mape_demo,
    coverage_weekly,
    seasonal,
    sweep,
    cost_curve,
    outcomes,
    frozen,
    time.time() - NOTEBOOK_STARTED,
)
sizes = handoff.export(forecaster, evidence, manifest, prices)
for name, size in sizes.items():
    print(f"  {name:<26} {size}")

print(f"\nsample_manifest.parquet holds {len(manifest)} products chosen by rule:")
print(manifest[["StockCode", "product", "why_this_product", "coverage",
                "cost_change_pct", "policy_is_cheaper"]].to_string(index=False, line_width=140))
""")

code(r"""
# ===============================================================
# 5.5b RELOAD FROM DISK AND DEMAND IDENTICAL ANSWERS
# ===============================================================
identity = handoff.verify(panel, scored, forecaster)

print(f"status                       {identity['status']}")
print(f"rows re-scored               {identity['rows_rescored']:,}")
print(f"forecasts bitwise identical  {identity['forecasts_bitwise_identical']}")
print("max abs difference           "
      + ", ".join(f"{k} {v:.3e}" for k, v in identity["max_abs_difference"].items()))
print("max abs order difference     "
      + ", ".join(f"{k} {v:.3e}" for k, v in identity["max_abs_order_difference"].items()))
print(f"coverage after reload        {identity['coverage_after_reload']:.4f}")
print(f"MAE after reload             {identity['MAE_after_reload']:.4f}")
print(f"versions from disk           model {identity['version_from_disk']}, "
      f"policy {identity['policy_version_from_disk']}")

assert identity["status"] == "identical", "The exported artifact does not reproduce the notebook."
assert identity["forecasts_bitwise_identical"], "Reloaded forecasts differ from the notebook's."
print(f"\nNotebook complete in {time.time() - NOTEBOOK_STARTED:.1f}s. Nothing downloaded.")
""")

md(r"""
## 5.6 Where the handoff ends

```text
weekly sales -> dense panel -> cohort (TRAIN weeks only) -> MA8 point forecast
             -> residual-quantile band -> newsvendor quantile -> PROPOSED quantity
             -> a planner approves, adjusts, or overrides
             -> the order
```

**The system stops at "proposed".** It does not place orders, does not commit spend, does not
adjust safety stock, and does not decide which products to discontinue. A planner sees the
forecast, the band, the proposed quantity, and the cost assumption behind it, and then makes
the call.

Three sentences this lab is not allowed to say, stated here so nobody says them by accident:

- **The forecast is not a promise.** It is the mean of the last eight weeks, and Stage 4
  measured how often it is wrong and by how much.
- **The interval is not a guarantee.** It is a range that held **84%** of the time on held-out
  weeks against a promised 80%, and that held **66.2%** on Q4-skewed products during the ramp.
- **Neither figure is a statement about any real retailer's operations.** Every cost in Stage 5
  is a classroom assumption.

### The five stages, and who has to be in the room

| Stage | What happened | Who is needed |
|---|---|---|
| **1 - Ingestion** | Source, license, content checksum verified; six cleaning decisions written down | Data team **and** whoever knows the trading calendar - the Saturday count came from them |
| **2 - Cohort** | Weekly grain justified; 469 products chosen on training weeks only; the 442-product leak shown | ML team **and** a category manager who can say whether a product belongs in scope |
| **3 - Forecasting** | Six baselines scored; the seasonal method came last, behind forecasting nothing | ML team **and** whoever will have to explain the number to a planner |
| **4 - Interval** | Three interval families compared; the simple one kept its promise, the booster did not | ML team **and** whoever signs off on what "80%" is allowed to mean |
| **5 - Policy and handoff** | Newsvendor rule derived then checked on money; 115 losers shown; Christmas failure measured | Ops **and** finance - they own `cu` and `co`, and nobody else can set them |

**The model is one component. The ordering workflow is the thing that had to be designed.**

---

### What to take away

1. **The grain is a modeling decision.** The shop is closed on Saturdays - one open Saturday in
   739 days - and a daily model would have learned the shutter instead of the demand.
2. **Selection leaks too.** Choosing the cohort over all 102 weeks admits 442 products that sell
   in 98.7% of test weeks, while the honest rule's extra 54 products sell in 49.6%. The leak
   was in *who got measured*, not in any feature.
3. **The intuitive seasonal method was the worst real method.** Seasonal-naive scored MAE 84.52,
   losing to a forecast of zero at 84.33, because one year of history is one noisy number per
   week rather than a season.
4. **Calibration is not accuracy.** Gradient boosting won MAE (47.97 vs 51.57) and broke its
   promise (75.0% vs a nominal 80%), predicting negative demand on 3.63% of rows. The ten-line
   method delivered 84.06%, fits ~200x faster, and yields any quantile for free - which is the
   only reason the cost-ratio control can respond live.
5. **MAPE recommends closing the warehouse.** It scores the real forecast at 8.27e+15 and a
   flat zero at 0.9073. And MAE is not innocent either - by MAE, flat zero beat seasonal-naive.
   No single metric is the decision.
6. **The order is not the forecast.** `cr = cu / (cu + co)`; at 4:1 that is the 80th percentile,
   and the out-of-sample cost curve bottoms exactly there. The economics choose the quantile;
   the model only supplies the band.
7. **An aggregate win hides individual harm.** The policy is cheaper on 354 of 469 products and
   **more expensive on 115**, all of them declining sellers, the worst at **+383.6%**.
8. **A metric can be right and still describe the wrong thing.** One product's annual coverage
   is a textbook 80.8%, and all five of its misses are above the band inside the Christmas ramp.
9. **The artifact that ships has to be the artifact that was measured**, and the only proof is
   reloading it from disk and demanding bitwise-identical forecasts.
""")


notebook["cells"] = cells
notebook.metadata["kernelspec"] = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}
notebook.metadata["language_info"] = {"name": "python", "version": "3.11"}
nbf.write(notebook, OUTPUT)
print(f"wrote {OUTPUT} with {len(cells)} cells")
