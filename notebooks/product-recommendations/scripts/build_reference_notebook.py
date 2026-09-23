"""Build the preserved advanced Module 6 recommendation reference notebook.

This file is the canonical source of the notebook. Never hand-edit the .ipynb:
change a cell here and regenerate, then execute the notebook so its committed
outputs match the code that produced them.

This is the historical advanced lesson. The canonical classroom notebook is
built separately by ``build_notebook.py``.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_DIR / "backup" / "02_recommendation_reference.ipynb"

notebook = nbf.v4.new_notebook()
cells: list = []


def cell_metadata(language: str) -> tuple[str, dict[str, str]]:
    cell_id = f"recommendation-build-{len(cells) + 1:03d}"
    return cell_id, {"id": cell_id, "language": language}


def md(text: str) -> None:
    cell_id, metadata = cell_metadata("markdown")
    cells.append(nbf.v4.new_markdown_cell(text.strip("\n"), id=cell_id,
                                          metadata=metadata))


def code(text: str) -> None:
    cell_id, metadata = cell_metadata("python")
    cells.append(nbf.v4.new_code_cell(text.strip("\n"), id=cell_id,
                                      metadata=metadata))


def guide(question: str, marks: str, denominator: str, notice: str,
          term: str, matters: str, boundary: str) -> None:
    md(f"""
### How to read this plot

- **Question:** {question}
- **Marks and axes:** {marks}
- **Denominator:** {denominator}
- **What to notice:** {notice}
- **Term:** {term}
- **Why it matters:** {matters}
- **Boundary:** {boundary}
""")


# ═══════════════════════════════════════════════════════════════════════════
# Header
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
# The model that wins the leaderboard and is worth nothing

**ITAI 2372 - Module 6 - AI in Retail and Supply Chain**

The other lab in this module asks *how many units of this product will we sell next week?*
This one keeps the customer column instead and asks *which products should we show this
shopper?* Same workbook, same retailer, a different question - and a much harder one to
grade, because the winning model here is a baseline with no parameters that recommends
people their own shopping list.

| | Stage | What happens |
|---|---|---|
| **1** | **The Data and the Split** | One retailer's baskets, the five cleaning rules re-tested, and a global time split made before any model exists |
| **2** | **Models and the First Leaderboard** | Popularity, item-item cosine, SVD-64, the reorder baseline and a measured fallback - seven metrics each |
| **3** | **The Evaluation Trap** | The same models, scored twice. First place becomes last, and lands below random |
| **4** | **Popularity Bias, Leaks and the Loop** | What each model actually shows people, what a leave-one-out split hides, and what ten rounds of deployment do to a catalog |
| **5** | **Policy, Cold Start and Handoff** | Ten slots, who gets nothing, the fallback that is labeled honestly, and the six exported files |

> **An offline ranking score is not evidence of revenue.** This system orders a list of
> products for one merchandising slot. Its hit rate is measured against what customers
> happened to buy next in one 13-week window of one retailer's history. A recommendation is
> not a statement about what the shopper needs, merchandisers own placement and exclusions,
> and nothing here describes any real retailer's current operations.

### The case

A UK giftware wholesaler sells online to buyers who come back, order after order. It wants
ten products in a "Recommended for you" module. The narrow question is:

> **Which ten products should this shopper see, and how would we know the list was any good?**

The second half of that sentence is the whole lab. There is a model in this notebook that
beats every other model on every accuracy metric, has no parameters, learns nothing, and is
commercially worthless. Finding out why is the work.

### The data

- **Online Retail II** (UCI dataset 502, CC BY 4.0), 1,067,371 raw invoice lines
- One UK-registered, non-store online retailer, **2009-12-01 to 2011-12-09**
- Cleaned once by `scripts/build_dataset.py` under five counted rules, committed as a
  3.3 MB parquet - running this notebook needs no download and no network
- Split **globally in time at 2011-09-09**, never randomly
- **4,962 customers x 4,443 products, 98.228% empty**
""")

code(r"""
# ===============================================================
# SETUP
# ===============================================================
import json
import warnings

import numpy as np
import pandas as pd
import plotly.io as pio

from reclab import (charts, config, data, evaluate, handoff, matrix,
                    models, policy)

warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 170)
pd.set_option("display.max_colwidth", 110)
pio.renderers.default = "notebook"
print(config.describe())
""")

# ═══════════════════════════════════════════════════════════════════════════
# Stage 1
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 1 - The Data and the Split

**Question:** What is one row of this file, and how do we hold out a test set that a
recommender could not have seen in production?

**What to expect in this stage:** where the workbook came from and what it is a record of,
the five cleaning rules re-tested against the file we actually shipped, the shape of the
demand - a long tail and a 98.2% empty matrix - and the global time split at 2011-09-09,
made once, before any model exists.

**Why this stage exists:** the split is the most consequential decision in the lab. A random
split puts December's baskets in training and September's in test: a question nobody can ask
in production, and a model that has already seen the future it is being graded on. And the
one measurement that explains the entire headline of this case - how much of the test window
is a customer buying something *again* - is made here, before there is anything to defend.

**What passes to stage 2:** a 4,962 x 4,443 training matrix, two ground truths built from the
same test window, and the repeat-purchase share that makes stage 3 inevitable.
""")

# ---------------------------------------------------------------------------
md(r"""
## 1.1 The same workbook the other lab in this module uses

The demand-forecasting lab in Module 6 reads **exactly this file**. Same retailer, same
1,067,371 raw invoice lines, same two years. It groups the rows by product and week and asks
*how many units will we sell next week?* - so the customer column is thrown away on the first
page.

This lab keeps the customer column and throws away almost everything else. The question is
*which products should we show this shopper?* Same rows, different question. That is worth
saying out loud, because it is the most common reason two teams in the same company end up
with two incompatible views of the same data: they were never looking at the same grain.

**Term - provenance:** the traceable record of where the data came from and everything that
happened to it between there and here. It is not paperwork. It is the only thing that lets a
second person reproduce a number you are asking them to act on.

The file was cleaned once, by `scripts/build_dataset.py`, under five counted rules, and
committed as a 3.3 MB Parquet. Nothing in this notebook downloads anything.
""")

code(r"""
# ===============================================================
# 1.1 LOAD THE COMMITTED FILE AND VERIFY WHAT IT IS
# ===============================================================
interactions = data.load_interactions()
descriptions = data.load_descriptions()
ledger = data.load_ledger()

print(data.provenance_summary(interactions).to_string(index=False))
""")

md(r"""
## 1.2 What one row means, and why customers come back

The committed grain is **one product on one invoice**. If a shopper buys six different
products in one order, that is six rows sharing an invoice number and a timestamp. Quantity
is gone; `revenue` is the line total. For a recommender, "did this customer ever buy this
product" is the signal, and how many of them they bought is not.

Below is one real basket, and then the column that decides this entire case: **how often the
same customer buys the same product again.**
""")

code(r"""
# ===============================================================
# 1.2 ONE REAL BASKET, AND HOW OFTEN CUSTOMERS COME BACK
# ===============================================================
print(data.one_row_example(interactions, descriptions).to_string(index=False))
print()
print(data.basket_profile(interactions).to_string(index=False))
""")

md(r"""
Read the second table before going on. **121,323 of the 480,976 (customer, product) pairs in
this file - 25.2% - appear in more than one basket**, and 72.4% of customers place more than
one order.
This is a wholesale giftware business: shops restock. Nothing about that is unusual, and it
is about to make the leaderboard in Stage 2 unusable on its own.

## 1.3 The five cleaning rules, re-tested rather than asserted

`scripts/build_dataset.py` applied five rules once and wrote a ledger beside the Parquet.
Printing the ledger is a claim. The second table below is the **test**: every guarantee
re-checked against the file that actually shipped, in this process, now.

A note on the third rule. `POST`, `DOT`, `M`, `C2`, `BANK CHARGES`, `PADS`, `ADJUST`,
`AMAZONFEE` and two `TEST` codes look like products because they sit in the `StockCode`
column. They are postage, carriage, discounts, manual adjustments, packing lines, fees and
the retailer's own test rows. A recommender that keeps them learns that postage is the
single most co-purchased item in the catalog and puts it in slot one for everybody.
""")

code(r"""
# ===============================================================
# 1.3 THE LEDGER, AND THE SAME GUARANTEES RE-TESTED
# ===============================================================
print(data.cleaning_ledger_table().to_string(index=False,
      formatters={"Share of raw": "{:.2%}".format}))
print()
checks = data.verify_cleaning(interactions)
print(checks.to_string(index=False))
print(f"\n{int(checks['Holds'].sum())}/{len(checks)} guarantees hold on the committed file.")
""")

md(r"""
## 1.4 The 23% with no name on them

Before choosing a model, answer a question the data can answer: **who are we personalizing
for?** A recommender needs a customer identity to attach a history to. This file does not
always have one.
""")

code(r"""
# ===============================================================
# 1.4 GUEST CHECKOUTS: TRANSACTIONS WITH NO CUSTOMER ID AT ALL
# ===============================================================
guests = data.guest_share(interactions)
print(f"Rows with no customer id : {guests['guest_rows']:,} of {guests['total_rows']:,} "
      f"= {guests['guest_row_share']:.1%}")
print(f"Baskets with no customer id: {guests['guest_baskets']:,} of "
      f"{guests['total_baskets']:,} = {guests['guest_basket_share']:.1%}")
print(f"Revenue with no customer id: {guests['guest_revenue']:,.0f} = "
      f"{guests['guest_revenue_share']:.1%} of all revenue in the file")
""")

md(r"""
**22.8% of the invoice lines in this file carry no customer id.** Those rows are 13.2% of the
revenue and 7.4% of the baskets - a smaller share of baskets than of rows, because
unidentified orders here are large ones.

They are not missing values to impute. There is no person to attach them to: the retailer
never captured one. Every one of those rows is a shopper this system **structurally cannot
personalize for**, no matter how good the model gets, and they are dropped from the matrix in
Section 1.5 with no way to earn them back.

Hold this apart from the other population that gets called "cold start" - a *registered*
customer we have simply never seen buy anything before the cut. Stage 5 counts both, keeps
them in separate columns, and refuses to add them together.
""")

md(r"""
## 1.5 The split: global, in time, at 2011-09-09, made before any model exists

This is the most consequential decision in the lab, and it is made once, here, before a
single model is fitted.

**Global time split:** everything on or before **2011-09-09** is training; everything after
is test - **for every customer at once**. Thirteen weeks of held-out future.

**Why not a random split?** A random 80/20 over rows would put some of December's baskets in
training and some of September's in test. That is not a hard version of the problem; it is a
different problem, and nobody can ask it in production. You would be grading a model on a
period it has already seen, and every number you printed would be too good.

Two more rules, both frozen with the split:

- **Registered customers only.** Guest rows have no identity to build a history from.
- **At least 5 distinct products bought before the cut.** Below that there is nothing to
  learn from, and including those customers would quietly measure the fallback list while
  calling it a model.

And out of the one test window come **two ground truths**, because the whole case turns on
the difference between them:

| Ground truth | What counts as a correct answer |
|---|---|
| `truth_standard` | every product the customer bought after the cut, repeats included |
| `truth_discovery` | only the products they had **never** bought before the cut |
""")

code(r"""
# ===============================================================
# 1.5 BUILD THE MATRIX AND SPLIT IT IN TIME
# ===============================================================
split = matrix.build_split(interactions)
print(matrix.split_summary(interactions, split).to_string(index=False))
assert (split.n_users, split.n_items) == config.EXPECTED_MATRIX_SHAPE
""")

md(r"""
## 1.6 The shape of the demand: a few products carry everything

**Term - the long tail:** in a retail catalog, a small number of products account for most
of the purchases and the great majority of products account for almost none. It is not a
defect of this dataset; it is what retail catalogs look like, and it is the reason a
"recommend the popular things" baseline is so hard to beat.
""")

code(r"""
# ===============================================================
# 1.6 HOW CONCENTRATED THE DEMAND IS
# ===============================================================
curve = data.popularity_curve(split.train_rows)
skew = matrix.concentration(split)
print(f"Products in the training catalog        : {skew['items']:,}")
print(f"Gini of the training interactions       : {skew['gini']:.3f}")
print(f"Share held by the 10 most-bought        : {skew['top_10_share']:.2%}")
print(f"Share held by the 100 most-bought       : {skew['top_100_share']:.2%}")
print(f"Share held by the 500 most-bought       : {skew['top_500_share']:.2%}")

charts.popularity_skew(curve, skew).show()
""")

guide(
    "How unevenly are purchases spread across the catalog, and how far into the catalog do "
    "you have to go before you have seen most of the buying?",
    "One point per product, ordered left to right from most-bought to least. Both axes on "
    "the left panel are logarithmic. The blue line (left axis) is how many distinct customers "
    "bought that product. The red line (right axis) is the running total: the share of all "
    "customer-product interactions held by everything up to that rank. Two dotted verticals "
    "mark rank 100 and rank 500.",
    "The red line divides by **all 391,220 distinct (customer, product) interactions bought "
    "before the cut**, spread over the 4,445 products that sold in that window. The blue line "
    "is a raw count of customers, not a share.",
    "The 500 most-bought products - **11% of the catalog** - hold **45%** of every "
    "interaction. The 100 most-bought hold **14.7%**. The blue line falls from about **1,385 "
    "customers** to single digits within the first few hundred products and then runs flat "
    "for thousands more.",
    "**Gini coefficient** - one number for how unequally something is shared out. 0 means "
    "every product is bought equally often; 1 means one product takes everything. This "
    "catalog is at **0.610**.",
    "A model that simply ranks by popularity is not a strawman here. It will be right often "
    "enough to look respectable, because the truth it is scored against is itself "
    "concentrated in the same head of the catalog. Beating it means being right about the "
    "tail, and the tail is where 89% of the products live.",
    "This is a picture of **what was bought**, which is downstream of what the retailer chose "
    "to show and promote. It is not a picture of what customers would have wanted if they had "
    "seen the whole catalog. Nothing here says the tail products are bad products.",
)

md(r"""
## 1.7 The matrix, and how empty it is

**Term - the customer x product matrix:** one row per customer, one column per product, and a
1 in a cell if that customer bought that product before the cut. Every model in Stage 2 sees
only this. It has no idea what the products are, what they cost, or what they are called.

**Term - sparsity:** the share of the cells that are empty. Numerator: cells with no purchase.
Denominator: all 4,962 x 4,443 = **22,046,166** cells. Here **98.228%** of them are empty.
""")

code(r"""
# ===============================================================
# 1.7 WHAT 98.228% EMPTY LOOKS LIKE FROM BOTH MARGINS
# ===============================================================
cells = split.n_users * split.n_items
print(f"Matrix    : {split.n_users:,} customers x {split.n_items:,} products = {cells:,} cells")
print(f"Filled    : {split.R.nnz:,}")
print(f"Sparsity  : {1 - split.R.nnz / cells:.3%} empty")
print(f"Median customer bought {np.median(np.asarray(split.R.sum(1)).ravel()):.0f} distinct "
      f"products; median product was bought by "
      f"{np.median(np.asarray(split.R.sum(0)).ravel()):.0f} customers")

charts.sparsity_profile(split).show()
""")

guide(
    "Is this matrix empty because a few customers are quiet, or is it empty everywhere?",
    "Two panels, both histograms, both with logarithmic axes on the count and on the value. "
    "Left (blue): each bar is a group of customers who bought a similar number of distinct "
    "products before the cut; bar height is how many customers are in that group. Right "
    "(green): each bar is a group of products, and the height is how many products were "
    "bought by that many customers.",
    "Left panel: **4,962 customers** in the training matrix. Right panel: **4,443 products** "
    "in it. Neither panel is a percentage - both are counts, on a log scale.",
    "Both distributions run from single digits to four figures with no cluster in the middle. "
    "The median customer bought **45** distinct products out of 4,443; the median product was "
    "bought by **42** customers out of 4,962. There is no dense core of the matrix hiding "
    "somewhere - it is thin in both directions at once.",
    "**Sparsity** - the share of cells with no purchase in them. Here 21,655,595 of "
    "22,046,166 cells are empty, which is 98.228%.",
    "Sparsity is why collaborative filtering is even possible: with a dense matrix you would "
    "have nothing to predict. It is also why every model here is fragile. A product bought by "
    "six customers has six numbers behind its similarity score, and a similarity computed "
    "from six co-purchases is not evidence.",
    "An empty cell does **not** mean the customer rejected that product. It almost always "
    "means they never saw it. This matrix records exposure and purchase mixed together, and "
    "no model in this notebook can separate them.",
)

md(r"""
## 1.8 The measurement that decides the rest of the notebook

One question, asked before any model exists: **in the 13-week test window, how much of what
customers bought was something they had already bought before?**

If the answer is "a lot", then a model that recommends people their own shopping list will
win the accuracy table without learning anything at all.
""")

code(r"""
# ===============================================================
# 1.8 HOW MUCH OF THE TEST WINDOW IS A REPEAT PURCHASE
# ===============================================================
repeat = matrix.repeat_purchase_profile(split)
print(f"Correct answers in the test window (customer, product pairs) : "
      f"{repeat['test_truth_pairs']:,}")
print(f"  ... already bought before the cut                          : "
      f"{repeat['repeat_pairs']:,} = {repeat['repeat_share']:.1%}")
print(f"  ... new to that customer                                   : "
      f"{repeat['new_pairs']:,} = {repeat['new_share']:.1%}")
print()
print(f"Test-window revenue                                          : "
      f"{repeat['test_revenue']:,.0f}")
print(f"  ... on a product the customer already owned                : "
      f"{repeat['repeat_revenue']:,.0f} = {repeat['repeat_revenue_share']:.1%}")
print()
print(f"Customers with at least one repeat purchase after the cut    : "
      f"{repeat['users_with_a_repeat']:,} of {repeat['users_scored']:,} "
      f"= {repeat['users_with_a_repeat_share']:.1%}")
""")

md(r"""
**38.4% of the correct answers, and 43.5% of the revenue, in the test window are a customer
buying something they already own.** 91.2% of scored customers do it at least once.

That single fact is the engine of this whole notebook. Everything in Stages 2 and 3 is a
consequence of it.

---

### Stage 1 conclusion

The split is a **global time split at 2011-09-09** and it was made before any model existed,
because a random split grades a model on a future it has already read. What came out of it is
a **4,962 x 4,443 matrix that is 98.228% empty**, **2,244 customers** who can be scored on
what they bought next, and **2,168** who can be scored on what they bought *for the first
time*.

And one number that is not a modeling detail: **38.4% of the test-window truth is a repeat
purchase.** A model with no parameters that recommends each customer their own purchase
history is about to top the leaderboard. Stage 2 fits it deliberately.
""")
# ---------------------------------------------------------------------------

# ═══════════════════════════════════════════════════════════════════════════
# Stage 2
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 2 - Models and the First Leaderboard

**Question:** What does each model actually compute, and which one wins?

**What to expect in this stage:** five scorers small enough to read in full - popularity,
item-item cosine, the same matrix truncated to fifteen neighbours, TruncatedSVD with 64
components, and the reorder baseline that recommends people what they already buy - plus a
generic fallback list chosen by measurement. Then the first leaderboard, with coverage and
novelty printed beside every accuracy number, because they will not be optional later.

**Why this stage exists:** every model here is ordinary, and that is the point. Nothing in
this case turns on model choice. It turns on what the analyst decided to count as a hit, and
you cannot see that decision until there are models to score.

**What passes to stage 3:** seven fitted scorers, one leaderboard, and a winner nobody
should be comfortable with.
""")

# ---------------------------------------------------------------------------
md(r"""
## 2.1 Seven scorers, each one a sentence

Every model here does the same job: turn the training matrix into a **score for every
(customer, product) cell**, so the ten highest-scoring products can be shown. None of them
sees a product name, a price or a category. They see 1s and 0s.

| Model | What it computes |
|---|---|
| **Popularity** | Count how many customers bought each product. Show the same ten to everyone. |
| **Fallback: recent revenue 28d** | The ten products with the most revenue in the last 28 days of training. No customer input at all. |
| **Item-item CF (full matrix)** | Products bought by the same customers are similar. Rank by similarity to what this customer already bought. |
| **Item-item CF (top-15)** | The same idea, but each product keeps only its 15 closest neighbours and forgets the rest. |
| **TruncatedSVD (64)** | Compress 4,443 products into 64 numbers per customer, then rebuild the missing entries. |
| **Reorder (already-bought)** | Show the customer the things they already buy, most-ordered first. No learning at all. |
| **Random 10** | Ten products drawn uniformly at random. The floor any model has to clear. |

**Term - collaborative filtering (CF):** predicting what one customer will want from what
*other* customers with overlapping histories bought. No product attributes are used - only
the pattern of co-purchase. Input: the 4,962 x 4,443 matrix. What is learned: nothing that
generalizes beyond these exact products; the "model" is a table of product-to-product
similarity. Output: a 4,443-long score vector per customer. What it does **not** prove: that
two similar products are substitutes, complements, or good for the shopper.

**Term - cosine similarity:** treat each product's column as a list of the customers who
bought it, scale every column to unit length, and take the dot product. Two products score 1
when exactly the same customers bought both, and 0 when no customer bought both. Scaling to
unit length is what stops the best-selling product being "similar" to everything.

**Term - matrix factorization (TruncatedSVD):** approximate the 22-million-cell matrix as the
product of two much smaller ones - a 4,962 x 64 customer table and a 64 x 4,443 product
table. Multiplying them back out fills in the empty cells with a guess. **64** is configured,
not learned; the two tables are learned. It cannot say *why* a product was ranked, because a
factor is not a product.

**Two of these seven are not optional.**

The **reorder baseline** has to be in the room. It is the thing the business already does for
free - a "Buy it again" strip - and any model that cannot beat it has no case. Section 1.8
already told us it will do embarrassingly well.

The **random floor** has to be in the room too, and it has to be built correctly. If the
random model held one generator and advanced it on every call, the discovery table would come
out differently depending on whether the standard table had been scored first. A floor whose
height depends on the order you ran your experiments in is not a floor. `fit_random` stores
the **seed**, and `score` seeds a fresh generator every call.
""")

code(r"""
# ===============================================================
# 2.1 FIT EVERY SCORER ONCE
# ===============================================================
fitted = models.fit_all(split)
for name in config.MODEL_ORDER:
    model = fitted[name]
    print(f"{name:<30} {model.kind:<12} fitted in {model.fit_seconds:6.2f}s")

deployed = fitted[config.DEPLOYED_MODEL_LABEL]
print(f"\nThe truncated similarity matrix stores {deployed.payload.nnz:,} links - at most "
      f"{config.ITEM_NEIGHBOURS} for each of the {split.n_items:,} products, and fewer for a "
      "product with no strong neighbours left.")
""")

md(r"""
## 2.2 Proving the floor is a floor

A one-line check with a real consequence: score the random model over the standard
population, then over the discovery population, then over the standard population again. If
the third result is identical to the first, the model is order-independent and the number it
produces is a floor. If it is not, every "beats random" claim in the notebook depends on the
order the cells happened to run in.
""")

code(r"""
# ===============================================================
# 2.2 THE RANDOM FLOOR MUST NOT DEPEND ON EXECUTION ORDER
# ===============================================================
floor = fitted[config.RANDOM_LABEL]
standard_users = sorted(split.truth_standard)
discovery_users = sorted(split.truth_discovery)

first = models.score(floor, split, standard_users)
_ = models.score(floor, split, discovery_users)      # scored in between, on purpose
again = models.score(floor, split, standard_users)

print(f"Payload held by the random model : {floor.payload!r} (a seed, not a generator)")
print(f"Identical after an intervening call: {np.array_equal(first, again)}")
del first, again, _
""")

md(r"""
## 2.3 The first leaderboard: the standard next-purchase protocol

**Term - protocol:** the pair of decisions that turns a ranking into a score - *what counts as
a correct answer*, and *which products the model was allowed to offer*. Two protocols over
the same predictions give two different numbers, and neither is wrong. This is the standard
one:

> **Ground truth:** every product the customer bought after 2011-09-09, **repeats included**.
> **Candidates:** the whole catalog. Products the customer already owns are **not** masked.
> **Question it answers:** did we predict what this customer bought next?

Every metric below, with its numerator and denominator stated once:

- **HR@10** (hit rate) - numerator: customers with **at least one** correct product in their
  ten slots. Denominator: the **2,244** customers scorable under this protocol. It is a
  per-customer yes/no, not a per-slot rate.
- **Precision@10** - correct slots divided by **10**, averaged over customers.
- **Recall@10** - correct slots divided by **that customer's whole truth set**, averaged over
  customers. A customer who bought 300 products cannot exceed 10/300 here.
- **NDCG@10** - like precision, but a hit in slot 1 counts more than a hit in slot 10,
  normalized so a perfect ordering scores 1.0.
- **Coverage** - distinct products that reached **anyone's** ten slots, divided by the
  **4,443** products in the catalog.
- **Novelty** - the mean of -log2(share of customers who bought the product), over every slot
  shown. Higher means the list is built from less-bought products.
- **Mean pop rank** - the average popularity rank of the products recommended, where 1 is the
  single most-bought product in the catalog.

Coverage and novelty sit in this table rather than in a later section, because in Stage 4
they stop being decoration and start deciding things.
""")

code(r"""
# ===============================================================
# 2.3 LEADERBOARD A - STANDARD NEXT-PURCHASE
# ===============================================================
def show_board(board):
    view = board.sort_values("HR@10", ascending=False).copy()
    for column in ["HR@10", "Precision@10", "Recall@10", "NDCG@10"]:
        view[column] = view[column].map("{:.4f}".format)
    view["Coverage"] = view["Coverage"].map("{:.2%}".format)
    view["Novelty"] = view["Novelty"].map("{:.2f}".format)
    view["Mean pop rank"] = view["Mean pop rank"].map("{:.0f}".format)
    return view.drop(columns=["Fit seconds"]).to_string(index=False)


standard = evaluate.leaderboard(split, fitted, config.PROTOCOL_STANDARD)
print(show_board(standard))
print(f"\nn = {int(standard['Customers scored'].iloc[0]):,} customers, "
      f"ground truth = everything bought after {split.cut.date()}, repeats included")
""")

md(r"""
## 2.4 The winner, and why nobody should be comfortable with it

Read the top row. **The reorder baseline wins: HR@10 0.7995.** Four customers in five get at
least one correct product in ten slots, and it beats TruncatedSVD (0.7594), item-item top-15
(0.6533) and popularity (0.5713) on **every accuracy column in the table**.

It has no parameters. It learned nothing. It ranks each customer's own purchase history by
how many baskets each product appeared in. Given Section 1.8 - 38.4% of the correct answers
in this window are repeat purchases - that is exactly what should have happened.

Three other rows are worth a moment:

- **Random 10 scores 0.0784.** Ten products from 4,443, and 7.8% of customers still get a
  hit, because the customers with the largest truth sets are easy to hit by accident. Any
  model near this number is doing nothing.
- **The fallback list (0.5526) is within 2 points of the popularity model (0.5713)**, and it
  never looks at the customer either. Two "no personalization" rows are already at 55% hit
  rate.
- **Coverage says something the accuracy columns cannot.** Popularity scores 0.5713 while
  showing **10 distinct products - 0.23% of the catalog - to all 2,244 customers**. Item-item
  top-15 scores 0.6533 while showing **28.49%** of it. Those two numbers are not the same kind
  of success, and only one column in this table can tell them apart.

So: is the reorder baseline the model we ship? It would be a "Buy it again" strip that we
call a recommender. Before answering, hold it to a second protocol.

---

### Stage 2 conclusion

Seven scorers, fitted in under a second in total, and a clean standard leaderboard with
**Reorder (already-bought) in first place at HR@10 0.7995**. The random floor is 0.0784 and
is order-independent, so every comparison against it is stable.

Nothing about the modeling is in question. What is in question is the table itself: it was
built by an analyst who decided that "the customer bought it again" counts as a correct
recommendation. Stage 3 changes that one decision and nothing else.
""")
# ---------------------------------------------------------------------------

# ═══════════════════════════════════════════════════════════════════════════
# Stage 3
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 3 - The Evaluation Trap

**Question:** How do you evaluate a recommender when the winning model is worthless?

**What to expect in this stage:** the same seven models, the same day, the same data, scored
against a second ground truth - only products the customer had never bought before, with
their whole purchase history masked out of the candidate set. The leaderboard inverts. The
model that was first is last, and below ten products drawn at random. Then the diagnosis of
*why* it lands below random, and the third protocol - the incoherent middle - that most
teams ship by accident.

**Why this stage exists:** both tables are real and they disagree, so at most one of them is
answering the question the business is paying for. A leaderboard without its protocol written
on it is not a result.

**What passes to stage 4:** two leaderboards that are always reported together, and the
knowledge that the metric did not measure the model - it measured the question.
""")

# ---------------------------------------------------------------------------
md(r"""
## 3.1 One decision, changed

Nothing about the models changes in this stage. The same seven fitted objects, the same test
window, the same day. What changes is the **protocol** - and it changes in two places at once,
because those two places have to agree:

> **Ground truth:** only the products the customer had **never** bought before 2011-09-09.
> **Candidates:** the catalog **minus** everything in that customer's training history. A
> product they already own can never be recommended, so it can never be a hit.
> **Question it answers:** did we show this shopper something they would not otherwise have
> found?

That is the question the merchandising slot is actually paying for. The "Buy it again" strip
already handles reordering, and it does not need a model. The slot we are building is meant
to introduce products.

**The denominator moves too.** 2,168 customers bought at least one product new to them in the
test window, against 2,244 who bought anything at all. The two tables are computed over
populations that differ by 76 customers, and any comparison of the two HR@10 columns has to
carry that caveat.
""")

code(r"""
# ===============================================================
# 3.1 LEADERBOARD B - DISCOVERY
# ===============================================================
discovery = evaluate.leaderboard(split, fitted, config.PROTOCOL_DISCOVERY)
print(show_board(discovery))
print(f"\nn = {int(discovery['Customers scored'].iloc[0]):,} customers "
      f"(vs {int(standard['Customers scored'].iloc[0]):,} under the standard protocol), "
      f"ground truth = products never bought before {split.cut.date()}")
""")

md(r"""
## 3.2 The two tables, side by side

This is the spine of the case. Read the rank columns, not the scores.
""")

code(r"""
# ===============================================================
# 3.2 THE SAME SEVEN MODELS, RANKED UNDER BOTH PROTOCOLS
# ===============================================================
comparison = evaluate.two_table_comparison(standard, discovery)
view = comparison.copy()
view["Standard HR@10"] = view["Standard HR@10"].map("{:.4f}".format)
view["Discovery HR@10"] = view["Discovery HR@10"].map("{:.4f}".format)
view["Discovery coverage"] = view["Discovery coverage"].map("{:.2%}".format)
print(view.to_string(index=False))

charts.two_leaderboards(
    comparison,
    random_discovery=float(discovery.loc[discovery["Model"] == config.RANDOM_LABEL,
                                         "HR@10"].iloc[0]),
).show()
""")

guide(
    "Does the choice of model decide which recommender is best, or does the choice of "
    "protocol decide it?",
    "One horizontal bar per model, the same seven models in the same vertical order in both "
    "panels, sorted by the standard protocol so the winner is the top bar on the left. Left "
    "panel: HR@10 under the standard next-purchase protocol. Right panel: HR@10 under the "
    "discovery protocol. Colors identify the model, not the score. The dashed vertical on the "
    "right marks where ten products drawn at random land.",
    "Left panel divides by the **2,244 customers** who bought anything after the cut. Right "
    "panel divides by the **2,168 customers** who bought something new to them. Different "
    "denominators, stated on each panel - the bars are not directly subtractable.",
    "**Reorder (already-bought) is the longest bar on the left (0.7995) and the shortest bar "
    "on the right (0.0217)** - rank 1 becomes rank 7, and it finishes **below the random "
    "floor of 0.0604**. Everything else keeps roughly its order: SVD-64 0.7594 -> 0.4437, "
    "item-item top-15 0.6533 -> 0.4156, popularity 0.5713 -> 0.2947. Only one model inverts, "
    "and it is the one that was winning.",
    "**Protocol** - the pair of decisions that turns a ranking into a score: what counts as a "
    "correct answer, and which products the model was allowed to offer. A leaderboard without "
    "its protocol written on it is not a result.",
    "Both tables are real and they disagree, so at most one of them is answering the question "
    "the business is paying for. If you report only the left panel you ship a reorder strip "
    "and call it personalization. If you report only the right panel you hide that most of "
    "this retailer's revenue is replenishment. The rule for the rest of this notebook is that "
    "both are always reported together.",
    "The right panel is **not** a better measurement than the left. It is a different "
    "question. Neither panel is evidence of revenue - both are hit rates against one 13-week "
    "window of one retailer's history.",
)

md(r"""
## 3.3 Why it lands *below* random, which is a different question

Scoring badly is unsurprising: the reorder baseline has nothing to say about products the
customer has never bought. But random guessing gets **0.0604** and the reorder baseline gets
**0.0217**. Being worse than a coin needs an explanation, and it is a mechanical one.

The reorder model's score for a (customer, product) pair is *the number of training baskets
that product appeared in for that customer*. For a product the customer has never bought,
that number is **exactly zero**. Mask the history and every remaining score is zero: the
model has no opinion at all about the 4,443 minus history products left standing.

`argsort` still returns ten of them. What you are looking at is not a ranking - it is a
**tie-break**, and the tie-break resolves toward low column indices. Column order here is
sorted stock code, which correlates with the least-bought tail of the catalog.
""")

code(r"""
# ===============================================================
# 3.3 THE DIAGNOSIS: AN ALL-ZERO SCORE VECTOR
# ===============================================================
zero = evaluate.zero_score_diagnosis(split, fitted[config.REORDER_LABEL])
print(f"Customers scored under discovery                   : {zero['customers']:,}")
print(f"  ... with ANY product scoring above zero          : "
      f"{zero['customers_with_any_positive_score']:,}")
print(f"  ... whose entire score vector is zero            : "
      f"{zero['share_with_all_zero_scores']:.1%}")
print(f"Mean popularity rank of the ten slots it fills     : "
      f"{zero['mean_popularity_rank_of_slots']:,.0f} of {zero['catalog_size']:,}")
print(f"\n{zero['explanation']}")
""")

md(r"""
**100% of the 2,168 scored customers get an all-zero score vector.** The ten products it
"recommends" sit at a mean popularity rank of **2,703 out of 4,443** - deep in the tail. Ten
uniformly random products average rank 2,247, so the tie-break is *systematically worse than
chance*, which is why the bar is shorter than the dashed line.

The lesson generalizes past this baseline: **any model that produces a constant score vector
is being ranked by its tie-break.** A cold customer hitting item-item CF gets an all-zero row
too, and Stage 5 has to decide what to show them instead of rendering an arbitrary list with
a confident heading on it.

## 3.4 The incoherent middle: the protocol most teams ship by accident

There is a third combination, and it is the one that gets written when the two protocol
decisions are made in different sprints by different people:

> **Ground truth:** everything bought after the cut, repeats included - the *standard* truth.
> **Candidates:** the catalog minus the customer's history - the *discovery* candidate set.

The model is forbidden from offering the products it is being graded on. **38.4% of the
correct answers are structurally unreachable**, and no model can score them however good it
is. The table below still computes. It still sorts. It still has a winner. It is not
answering any question.
""")

code(r"""
# ===============================================================
# 3.4 THE PROTOCOL BUG, RUN ON PURPOSE SO IT CAN BE RECOGNIZED
# ===============================================================
incoherent = evaluate.leaderboard(split, fitted, config.PROTOCOL_INCOHERENT)
print(show_board(incoherent))
print(f"\nCeiling on this table: {1 - repeat['repeat_share']:.1%} of the truth is reachable; "
      f"the other {repeat['repeat_share']:.1%} was masked out of the candidate set.")
""")

md(r"""
Its numbers sit just under the discovery table - 0.4287 for SVD-64 against 0.4437 - because
the extra 76 customers and the unreachable repeats drag every row down by a similar amount.
Nothing about it looks broken. That is exactly the problem: **a silently incoherent protocol
does not raise an exception, it just quietly reports a number nobody can act on.**

The check that catches it is one sentence: *can the truth I am scoring against appear in the
candidate set I allowed?* Here, for 38.4% of it, no.

---

### Stage 3 conclusion

**The same seven models, on the same data, on the same day, produced two leaderboards that
disagree about first place.** Reorder (already-bought) is rank 1 at 0.7995 under the standard
protocol and rank 7 at 0.0217 under discovery - below ten products drawn at random, because
masking the customer's history leaves it with an identically zero score vector and a biased
tie-break.

The metric did not measure the model. It measured the question. From here on, both tables are
reported together, with their protocols and their denominators attached, and the deployed
choice is argued on the discovery table because that is the one that matches the slot.
""")
# ---------------------------------------------------------------------------

# ═══════════════════════════════════════════════════════════════════════════
# Stage 4
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 4 - Popularity Bias, Leaks and the Loop

**Question:** What is a model that scores well actually putting in front of people, and what
does the evaluation you chose hide from you?

**What to expect in this stage:** what each model recommends rather than how well it scores -
coverage, novelty, and the share of slots that come from the hundred most popular products.
Then two measured warnings: a leave-one-out split, held to identical targets, inflates the
most expressive model's hit rate by more than a hundred percent; and ten rounds of a
popularity model retrained on its own recommendations collapse the catalog to ten products,
with every accuracy metric improving throughout.

**Why this stage exists:** accuracy metrics are computed only over products customers
actually interacted with, and customers interacted with popular products partly because they
were shown popular products. Coverage and novelty beside every accuracy number is the only
thing that makes that visible.

**What passes to stage 5:** the evidence that the deployed model has to be chosen on more
than one number, and a labeled classroom assumption that must stay labeled everywhere it
appears.
""")

# ---------------------------------------------------------------------------
md(r"""
## 4.1 Stop asking how well it scores. Ask what it shows.

Accuracy answers *were we right about the products customers bought*. It cannot answer *what
did we put on the page*. Two models can post the same hit rate while one of them has shown 80
products and the other 1,145.

The table below is computed on the **discovery protocol**, over the same 2,168 customers and
the same ten slots each, and it reports only what was shown:

- **Coverage** - distinct products that reached anyone's slots, over the **4,443** in the
  catalog.
- **Recommendation Gini** - how unequally the 21,680 slots were shared out across products.
  0 = every product shown equally often, 1 = one product takes every slot.
- **% of slots from the top 100** - denominator: all 21,680 slots filled.
- **% of slots from the less-popular half** - the 2,222 products below median popularity.
- **Top product's share of all slots** - how much of the page one single product owns.
""")

code(r"""
# ===============================================================
# 4.1 WHAT EACH MODEL ACTUALLY PUTS IN FRONT OF PEOPLE
# ===============================================================
exposure = evaluate.exposure_profile(split, fitted)
view = exposure.copy()
for column in ["Coverage", "% of slots from the top 100",
               "% of slots from the less-popular half",
               "Top product's share of all slots"]:
    view[column] = view[column].map("{:.2%}".format)
view["Recommendation Gini"] = view["Recommendation Gini"].map("{:.3f}".format)
view["Median popularity rank"] = view["Median popularity rank"].map("{:.0f}".format)
print(view.to_string(index=False))
print(f"\nDenominator: {len(sorted(split.truth_discovery)) * config.SLOTS:,} slots "
      f"({len(sorted(split.truth_discovery)):,} customers x {config.SLOTS} slots), "
      f"catalog = {split.n_items:,} products")
""")

md(r"""
Read the popularity row. Under the discovery protocol it fills 21,680 slots from **80
distinct products - 1.80% of the catalog** - and **0.00% of those slots come from the
less-popular half**. Not "few". None. In 21,680 opportunities it never once recommended a
product from the bottom 2,222.

Under the standard protocol, where nothing is masked, it is starker still: popularity shows
**the same ten products to all 2,244 customers**, which is **0.23% of the catalog**, and
still scores HR@10 0.5713.

**Term - popularity bias:** the tendency of a recommender to concentrate its slots on
already-popular items. It is not a bug in the code. Accuracy metrics are computed only over
products customers actually interacted with, and customers interacted with popular products
partly *because they were shown popular products*. The metric rewards the concentration it
helped create.

Item-item top-15 is the row to compare against: **25.77% coverage, 1,145 distinct products,
53% of slots from the top 100** instead of 99.9%, and a median popularity rank of 82 instead
of 7. It is also more accurate. That is not the usual trade, and Stage 5 measures why.
""")

code(r"""
# ===============================================================
# 4.2 ACCURACY AND COVERAGE ON THE SAME AXES
# ===============================================================
charts.coverage_vs_accuracy(discovery).show()
""")

guide(
    "Which models are worth deploying once you refuse to look at accuracy on its own?",
    "One labeled dot per model. Horizontal: catalog coverage - the share of the 4,443 "
    "products that reached at least one customer's ten slots. Vertical: discovery HR@10. "
    "Color identifies the model. Hover carries novelty and mean popularity rank as well.",
    "Coverage divides by the **4,443 products** in the catalog. HR@10 divides by the **2,168 "
    "customers** scorable under the discovery protocol.",
    "**Random 10 is far right at 99.21% coverage and flat on the floor** - showing everything "
    "is trivially easy and worth nothing. **Popularity is far left at 1.80%** with a "
    "respectable 0.2947. The two models near the top - SVD-64 at 0.4437 / 19.49% and "
    "item-item top-15 at 0.4156 / 25.77% - are close in accuracy and **six points apart in "
    "coverage**. Reorder sits in the bottom-left corner: accurate at nothing, and shows almost "
    "nothing.",
    "**Catalog coverage** - the share of the catalog a model is capable of putting in front "
    "of anyone. Numerator: distinct products appearing in any customer's ten slots. "
    "Denominator: all 4,443 products.",
    "This is where the deployed model gets argued rather than picked. SVD-64 wins discovery "
    "accuracy by 0.028 and shows 279 fewer products; it also cannot answer *why am I seeing "
    "this?* with the name of something the customer bought. Item-item top-15 is the choice, "
    "and the reason is on this chart plus the explainability argument, not on the leaderboard "
    "alone.",
    "High coverage is not a goal in itself - the random model proves that. This chart "
    "supports a trade-off argument between two models that are already accurate. It is not a "
    "ranking, and neither axis is revenue.",
)

md(r"""
## 4.3 The other split, and exactly how much it flatters you

**Term - leave-one-out (LOO):** the most common recommender split in tutorials and papers.
Hold out one purchase per customer - usually their most recent - and train on everything
else. It is popular because it gives every customer a test case and produces big, quotable
numbers.

It also leaves **every other customer's post-cut behavior in the training data**, and often
the same customer's later baskets too. In production you cannot train on next month.

Comparing a global-time table against a published LOO table proves nothing, because the two
have different target sets. So this experiment **fixes the targets** - exactly one held-out
product per customer, the same product in both runs - and changes only what the model is
allowed to train on:

- **A - honest:** nothing after the cut, for anybody.
- **B - leave-one-out:** all history except that one held-out purchase.

The gap between A and B is the leak, with nothing else moving.
""")

code(r"""
# ===============================================================
# 4.3 IDENTICAL TARGETS, TWO TRAINING SETS
# ===============================================================
inflation = evaluate.loo_inflation(interactions, split)
view = inflation.copy()
for column in view.columns[1:3]:
    view[column] = view[column].map("{:.4f}".format)
view["Inflation"] = view["Inflation"].map("{:+.1%}".format)
print(view.to_string(index=False))

charts.loo_inflation(inflation).show()
""")

guide(
    "How much does a leave-one-out split inflate a model's hit rate, and does it inflate all "
    "models equally?",
    "Two bars per model. Green is training set A - honest, nothing after the cut for anyone. "
    "Red is training set B - leave-one-out, everything except the held-out purchase. Bar "
    "height is HR@10 against **one** held-out product per customer, so the absolute numbers "
    "are much lower than the ten-target leaderboards and are not comparable to them. The red "
    "figure above each pair is the relative inflation.",
    "HR@10 here divides by the customers who have a usable held-out first purchase, and each "
    "one has a truth set of size **1**. Both bars in a pair use the identical target set.",
    "**The leak scales with model capacity.** Popularity gains **+8.6%** (0.0161 -> 0.0175) - "
    "it barely reads the extra data. Item-item CF gains **+89.5%** (0.0351 -> 0.0664). "
    "TruncatedSVD-64 gains **+104.3%** (0.0429 -> 0.0876) - it more than doubles.",
    "**Data leakage** - information that would not exist at prediction time reaching the model "
    "during training. Here it is future co-purchase: the leaked matrix knows which products "
    "were bought together in October when it is asked to predict September.",
    "The models that gain most from the leak are exactly the ones a team is hoping to "
    "justify. If you evaluate under leave-one-out you will conclude that matrix factorization "
    "roughly doubles your simple baseline. Under the honest split it is a much smaller "
    "improvement, and the gap between them is not a modeling result - it is the split.",
    "This does **not** say leave-one-out is always wrong; it is a reasonable protocol for "
    "questions where time order genuinely does not matter. It says that on a next-purchase "
    "question it is measuring something you cannot sell. And these absolute numbers are "
    "one-target hit rates - do not quote them beside the Stage 3 leaderboards.",
)

md(r"""
## 4.4 What ten rounds of deployment do to a catalog

The last warning is not about evaluation. It is about what happens after the model ships.

Deploy the popularity model. Some shoppers buy what they are shown. Those purchases go into
the log. Retrain on the enlarged log. Show again. The products it promoted now have more
purchases *because it promoted them*, so it promotes them harder.

**This simulation is a labeled classroom assumption, not a measurement.** It assumes **5% of
shown slots convert**, over **10 rounds**. That number is not measured from this retailer's
data; it was chosen so the mechanism is visible in ten rounds instead of two hundred. The
figure carries the caption on the chart itself, and so does every artifact that stores it.
""")

code(r"""
# ===============================================================
# 4.4 A POPULARITY MODEL RETRAINED ON ITS OWN RECOMMENDATIONS
# ===============================================================
loop = evaluate.exposure_loop(split)
print(config.FEEDBACK_ASSUMPTION_NOTE)
print()
view = loop.copy()
view["Top-10 share"] = view["Top-10 share"].map("{:.2%}".format)
view["Top-100 share"] = view["Top-100 share"].map("{:.2%}".format)
view["Gini"] = view["Gini"].map("{:.4f}".format)
print(view.to_string(index=False))

charts.exposure_loop(loop).show()
""")

guide(
    "If a recommender is retrained on the behavior it caused, what happens to the catalog?",
    "Top panel: two lines against the round number. Red is the share of all interactions held "
    "by the ten most-bought products; orange dotted is the share held by the top 100. Bottom "
    "panel: grey bars counting the distinct products the system has **ever** shown, across "
    "every round. Round 0 is before deployment.",
    "Both lines divide by **all interactions in the training matrix at that round**, which "
    "grows each round as simulated purchases are added. The bars are raw counts of products, "
    "out of 4,443.",
    "The top-10 share climbs from **2.38% to 6.26% in ten rounds - a 163% relative increase** "
    "- and the Gini rises from 0.610 to 0.626. The bottom panel is the sharper fact: it "
    "reaches **10** in round 1 and never moves again. Across ten rounds and 496,200 slot-fills, "
    "the system showed **10 of 4,443 products**. Nothing about the products changed; the "
    "model manufactured the evidence that those ten are the best.",
    "**Feedback loop** - when a system's outputs become its future training inputs, so its "
    "own behavior is fed back to it as evidence about the world.",
    "Every accuracy metric in this simulation *improves* round over round, because the model "
    "is being graded on behavior it caused. This is why an offline hit rate cannot be the "
    "only gate on a deployed recommender, and why coverage is monitored in production and not "
    "just at training time.",
    "The 5% conversion rate is **assumed, not measured** - the speed of the collapse is an "
    "artifact of that choice. What the assumption does not control is the direction, which "
    "follows from retraining on your own output. Do not quote 163% as a property of this "
    "retailer.",
)

md(r"""
---

### Stage 4 conclusion

Three measurements, each one invisible on an accuracy table.

**What the models show:** popularity fills 21,680 discovery slots from 80 products and takes
**none of them** from the less-popular half of the catalog. Item-item top-15 reaches 1,145
products and is *more* accurate.

**What the split hides:** with targets held identical and only the training data changed,
leave-one-out inflates popularity by **+8.6%**, item-item CF by **+89.5%** and SVD-64 by
**+104.3%**. The leak flatters exactly the model whose complexity you were trying to justify.

**What deployment does:** under a labeled 5%-conversion assumption, ten rounds of retraining
on its own recommendations move the top-10 share from 2.38% to 6.26% while the system shows
ten distinct products, ever.

The deployed model therefore cannot be chosen on one number. Stage 5 chooses it, writes the
rule a merchandiser would read, and then prices the whole thing honestly.
""")
# ---------------------------------------------------------------------------

# ═══════════════════════════════════════════════════════════════════════════
# Stage 5
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 5 - Policy, Cold Start and Handoff

**Question:** What does a shopper actually see, who gets nothing, and what leaves this
notebook?

**What to expect in this stage:** the written operating rule a merchandiser could read - ten
slots, discovery-only eligibility, reorders moved to a separate "Buy it again" strip - and
the two populations that are both called cold start and are not the same thing. A fallback
list chosen by measuring five candidates against what cold customers really bought next, and
labeled "Popular right now" rather than "Recommended for you". The upper bound on incremental
revenue. Then the six exported files, and a reload check that re-ranks 200 customers from
the artifacts alone.

**Why this stage exists:** the model produces a ranking; the policy decides what a person is
shown. Roughly one shopper in four gets no personalization at all here, and the honest system
is the one that says so on screen instead of rendering a ranked list built from a vector of
zeros.

**What passes out of this notebook:** six files totaling under half a megabyte, and a model
card that states what this system will not do.
""")

# ---------------------------------------------------------------------------
md(r"""
## 5.1 The rule, written so a merchandiser could argue with it

A model produces a ranking. A **policy** decides what a person is actually shown. The
difference matters here more than usual, because the model's ranking is defensible and
several of the things a shopper sees are not decided by it at all.

The rule below is frozen, exported to the service as `operating_policy.json`, and readable by
someone who has never opened a notebook.
""")

code(r"""
# ===============================================================
# 5.1 THE OPERATING POLICY
# ===============================================================
print(policy.policy_statement())
""")

md(r"""
Three things in that rule are ethical choices, not technical ones.

**Eligibility is discovery-only.** Products the shopper already owns are never eligible for
these ten slots. That is the Stage 3 protocol turned into a production rule, so the thing we
measured is the thing we ship.

**Reorders keep their own strip, honestly labeled.** "Buy it again" is genuinely useful - it
is 38.4% of what customers buy next. It is a replenishment reminder, it needs no model, and
it is never counted, measured or reported as personalization. Merging it into "Recommended
for you" would let us quote HR@10 0.7995 on a slide.

**The fallback gets a different heading.** A shopper we know nothing about sees "Popular
right now", not "Recommended for you". The second is a claim about them; the first is a claim
about the shop.

## 5.2 Who cannot be served, counted in separate columns

Two populations get called "cold start" in retail. They are not the same thing and they have
different denominators:

- **Cold registered customer** - a customer id that bought nothing before the cut. Denominator:
  the 2,893 registered customers active after it.
- **Guest checkout** - a transaction with no customer id at all. Denominator: the 199,180
  invoice lines in the test window.

A sentence that says "cold start" without saying which one it means is not a measurement.
There is also a third: **cold products**, new to the catalog, which no collaborative model can
rank because no customer has bought them yet.
""")

code(r"""
# ===============================================================
# 5.2 THE COLD-START CENSUS, KEPT IN SEPARATE COLUMNS
# ===============================================================
cold = policy.cold_start_census(interactions, split)
print(f"Registered customers active after the cut : "
      f"{cold['registered_customers_active_in_test']:,}")
print(f"  cold - never seen before the cut        : {cold['cold_registered_customers']:,} "
      f"= {cold['cold_registered_share']:.1%}  ({cold['cold_registered_revenue_share']:.1%} "
      "of test revenue)")
print(f"  thin - seen, but under 5 products       : {cold['thin_history_customers']:,} "
      f"= {cold['thin_history_share']:.1%}")
print(f"  cannot be personalized at all           : {cold['unservable_customers']:,} "
      f"= {cold['unservable_share']:.1%}")
print(f"\nGuest rows in the test window (DIFFERENT denominator) : "
      f"{cold['guest_rows_in_test']:,} of {cold['all_rows_in_test']:,} "
      f"= {cold['guest_row_share']:.1%}, {cold['guest_revenue_share']:.1%} of test revenue")
print(f"Products new to the catalog after the cut             : {cold['cold_products']:,} "
      f"of {cold['products_sold_in_test']:,} = {cold['cold_product_share']:.1%}, "
      f"{cold['cold_product_revenue_share']:.1%} of test revenue")
print(f"\n{cold['warning']}")

charts.cold_start_share(cold).show()
""")

guide(
    "How much of the audience can this system personalize for at all, and who is left over?",
    "Two panels that deliberately refuse to stack. Left: registered customers active after "
    "the cut, split into a green servable bar and two unservable bars - red for cold (never "
    "seen) and orange for thin (seen, but under five products). Right: guest checkouts, as a "
    "share of test-window rows and of test-window revenue.",
    "The left panel divides by **2,893 registered customers active in the test window**. The "
    "right panel divides by **199,180 invoice lines** and by test-window revenue. These are "
    "different denominators and the shares must never be added together.",
    "**22.4% of registered test customers cannot be personalized** - 20.7% cold plus 1.7% "
    "thin - and they carry 11.4% of test revenue. Separately, **21.3% of test-window rows "
    "have no customer id at all**, worth 14.6% of test revenue. Roughly one shopper in four, "
    "on either count, gets no personalization from this system.",
    "**Cold start** - having no history to personalize from. It is not one condition: a cold "
    "*customer*, a *guest*, and a cold *product* each break a different part of the system and "
    "each needs a different answer.",
    "This is the single biggest constraint on what the slot can be worth, and no amount of "
    "modeling touches it. It is also why the fallback list is a first-class artifact rather "
    "than an afterthought: it is what 22.4% of registered customers and 100% of guests "
    "actually see.",
    "These bars do not say the unservable customers are worth less. They say the system has "
    "nothing personal to offer them. And do not read the two panels as one number - a guest "
    "row and a cold customer are different units counted against different totals.",
)

md(r"""
It is worth being precise about **what each model does when it is handed an empty history**,
because three of them return something rather than failing, and what they return is not a
recommendation.
""")

code(r"""
# ===============================================================
# 5.2b WHAT EACH MODEL RETURNS ON AN EMPTY HISTORY
# ===============================================================
print(policy.cold_user_behavior().to_string(index=False))
""")

md(r"""
This is the Section 3.3 failure again, in production clothes. An all-zero score vector
produces ten products in index order, and a page that renders them under "Recommended for
you" is making a claim it cannot support. The policy's answer is to detect the condition and
change the heading, not to render the list.

## 5.3 The fallback, chosen by measurement rather than taste

The fallback is what one shopper in four sees, so it gets measured like a model. Five
plausible generic lists are scored against **what the 599 cold registered customers actually
bought in the test window** - not against the servable population, and not against guests.
""")

code(r"""
# ===============================================================
# 5.3 FIVE CANDIDATE FALLBACKS, SCORED ON COLD CUSTOMERS
# ===============================================================
sweep = policy.fallback_sweep(split)
view = sweep.copy()
view["HR@10"] = view["HR@10"].map("{:.4f}".format)
view["Precision@10"] = view["Precision@10"].map("{:.4f}".format)
print(view.to_string(index=False))
print(f"\nDenominator: {int(sweep['Cold customers scored'].iloc[0]):,} cold registered "
      "customers who bought something after the cut")
""")

md(r"""
**Recent revenue over the last 28 training days wins at HR@10 0.4624**, ahead of all-time
popularity at **0.4391** and well ahead of recent *basket-count* trending at 0.3439-0.4090.

The margin over all-time popularity is small but the direction is the interesting part. This
retailer sells to wholesale buyers, and revenue-weighting picks the products a buyer opens an
account with, while basket-count weighting picks cheap items that appear in many orders. The
narrower 14-day windows are worse than the 28-day one: too little data, and too much of a
single week's promotion.

Here is the list a cold shopper would actually see, under the heading **"Popular right
now"**.
""")

code(r"""
# ===============================================================
# 5.3b THE TEN PRODUCTS A COLD SHOPPER SEES
# ===============================================================
fallback = policy.fallback_list(split, descriptions)
print(f'Module heading: "{config.FALLBACK_TITLE}"  (not "{config.MODULE_TITLE}")\n')
print(fallback.to_string(index=False,
      formatters={"Revenue in the last 28 training days": "{:,.0f}".format}))
""")

md(r"""
## 5.4 What the policy does to the whole test window
""")

code(r"""
# ===============================================================
# 5.4 EVERY SHOPPER IN THE TEST WINDOW, ROUTED
# ===============================================================
outcomes = policy.policy_outcomes(interactions, split, deployed)
print(f"Customers in the test window          : {outcomes['test_window_customers']:,}")
print(f"  personalized                        : {outcomes['personalized_customers']:,} "
      f"= {outcomes['personalized_share']:.1%}")
print(f"  fallback list instead               : {outcomes['fallback_customers']:,} "
      f"= {outcomes['fallback_share']:.1%}")
print(f"  needing a partial backfill          : "
      f"{outcomes['customers_needing_partial_backfill']:,} "
      f"= {outcomes['partial_backfill_share']:.1%}")
print(f"\nSlots filled                          : {outcomes['slots_total']:,}")
print(f"  from the fallback list              : {outcomes['slots_from_fallback']:,} "
      f"= {outcomes['fallback_slot_share']:.1%}")
print(f"\nGuest baskets in the test window      : {outcomes['guest_baskets_in_test']:,} "
      f"- 100% fallback, by construction")
""")

md(r"""
**No customer needs a partial backfill.** Every one of the 2,245 personalized shoppers has at
least ten eligible products scoring above zero, which is what a 98.2%-empty matrix and a
4,443-product catalog guarantee. The backfill branch in the policy is still written, because
a narrower catalog or a heavier exclusion list would trigger it, and a rule that only works
on this quarter's data is not a rule.

## 5.5 One customer the model serves badly, on purpose

Customer **17841** is packaged into the demo manifest deliberately. It is the clearest
argument in the notebook against reading a leaderboard as a statement about people.
""")

code(r"""
# ===============================================================
# 5.5 THE DISCUSSION CASE: CUSTOMER 17841
# ===============================================================
row = split.user_index[config.DISCUSSION_CUSTOMER]
person = interactions[interactions["customer_id"] == config.DISCUSSION_CUSTOMER]
before = person[person["invoice_ts"] <= split.cut]
after = person[person["invoice_ts"] > split.cut]

cf_slots = evaluate.ranked_lists(split, deployed, config.PROTOCOL_DISCOVERY, [row])[row]
reorder_slots = evaluate.ranked_lists(split, fitted[config.REORDER_LABEL],
                                      config.PROTOCOL_STANDARD, [row])[row]

print(f"Customer {config.DISCUSSION_CUSTOMER}")
print(f"  training baskets                        : {before['invoice'].nunique():,}")
print(f"  distinct products bought before the cut : "
      f"{before['stock_code'].nunique():,} "
      f"({split.R[row].nnz / split.n_items:.1%} of the {split.n_items:,}-product catalog)")
print(f"  distinct products bought after the cut  : {after['stock_code'].nunique():,}")
print(f"  ... of those, new to this customer      : "
      f"{len(split.truth_discovery.get(row, ())):,}")
print()
print(f'  "{config.MODULE_TITLE}" ({config.DEPLOYED_MODEL_LABEL}, discovery) : '
      f"{len(set(cf_slots.tolist()) & split.truth_discovery.get(row, set()))}/10 correct")
print(f'  "{config.REORDER_TITLE}" ({config.REORDER_LABEL}, standard)  : '
      f"{len(set(reorder_slots.tolist()) & split.truth_standard.get(row, set()))}/10 correct")
print()
print(pd.DataFrame({
    "Slot": np.arange(1, config.SLOTS + 1),
    config.MODULE_TITLE: [str(descriptions.get(split.items[int(i)], ""))[:44]
                          for i in cf_slots],
    config.REORDER_TITLE: [str(descriptions.get(split.items[int(i)], ""))[:44]
                           for i in reorder_slots],
}).to_string(index=False))
""")

md(r"""
**Zero out of ten on discovery. Ten out of ten on reorder.**

This account holds **1,934 distinct products - 43.5% of the entire catalog - across 167
baskets**, and bought **893 distinct products** in the next thirteen weeks, of which 153 were
new to it. Collaborative filtering has almost nothing left to offer: the customer has already
bought nearly everything the model would suggest, and the products it can still legally
recommend are the ones nobody like this customer buys.

The account is a **wholesaler restocking inventory, not a shopper browsing**. For this
customer the honest product is the "Buy it again" strip, and the personalization slot is
close to worthless - which the discovery number says clearly and the standard number hides
completely.

This is the discussion prompt for the classroom: *what does a hit rate of 0.4156 mean for a
specific person, and how many customers on this account list are actually this one?*
""")

md(r"""
## 5.6 The number nobody puts on a slide

Every table so far has been a hit rate. A hit rate is not money. So: of the revenue customers
spent in the test window **on products that were new to them**, how much sits on a product
the model actually ranked into a slot?

**This is an upper bound and it is not a measurement of value.** It credits the model in full
for revenue the customer would have generated anyway - nobody ran an experiment here, there
is no control group, and a purchase that follows a recommendation was not necessarily caused
by it.
""")

code(r"""
# ===============================================================
# 5.6 AN UPPER BOUND ON WHAT PERSONALIZATION IS WORTH HERE
# ===============================================================
revenue = evaluate.incremental_revenue(split, fitted)
view = revenue.copy()
view["Revenue reached"] = view["Revenue reached"].map("{:,.0f}".format)
view["Share of available new-product revenue"] = \
    view["Share of available new-product revenue"].map("{:.2%}".format)
view["Discovery hits per customer"] = \
    view["Discovery hits per customer"].map("{:.3f}".format)
print(view.to_string(index=False))
print(f"\nAvailable new-product revenue: {revenue.attrs['available_revenue']:,.0f} "
      f"across {revenue.attrs['customers']:,} customers")

charts.incremental_revenue(revenue).show()
""")

guide(
    "How much of the money that was actually on the table does the best model reach?",
    "One bar per model. Height is the share of available new-product revenue that sits on a "
    "product that model ranked into one of ten slots. The dashed orange line marks the "
    "no-personalization fallback list. The annotation on the deployed model measures the gap "
    "between them.",
    "Every bar divides by the same **1,105,276 of test-window revenue** - the money customers "
    "spent on products that were new to them - across the **2,168** customers scorable under "
    "the discovery protocol. It does **not** divide by all test revenue.",
    "**The best personalized model reaches 3.53%. A ten-product list with no personalization "
    "in it at all reaches 2.81%.** The entire measured gain from collaborative filtering is "
    "**0.7 percentage points**, and that is an upper bound. SVD-64 reaches 3.47%, less than "
    "item-item top-15 despite winning the discovery hit rate, because its hits land on "
    "cheaper products.",
    "**Upper bound** - the largest value a quantity could take under the most generous "
    "assumptions available. Here the generous assumption is attributing 100% of a purchase to "
    "the recommendation that preceded it.",
    "This is the number that sets expectations before a project starts. A ten-slot module on "
    "this catalog is worth single-digit percentages of new-product revenue at absolute best, "
    "and most of that is reachable with a generic list. It is still worth building - but the "
    "business case is 0.7 points, not 3.53%.",
    "This is **not** incremental revenue and must never be quoted as such. Measuring "
    "incremental revenue needs a holdout group and a live experiment, neither of which exists "
    "in this dataset. Read it only as a ceiling that the real number sits under.",
)

md(r"""
## 5.7 Two engineering findings that survived being checked

Both of these are the sort of thing a team believes on Monday and ships on Friday. Both were
measured instead.

**Finding one: throwing away 99% of the similarity matrix makes it more accurate.**

Item-item cosine gives every product a similarity to all 4,442 others. Almost all of those
links are noise from one or two accidental co-purchases in a 98.2%-empty matrix. Keeping only
each product's strongest neighbours removes the noise. The usual expectation is that a
smaller artifact costs accuracy, so the only honest way to report it is with all three
columns on one row - accuracy, coverage, and megabytes.
""")

code(r"""
# ===============================================================
# 5.7 TRUNCATION: ACCURACY, COVERAGE AND SIZE IN ONE TABLE
# ===============================================================
truncation = evaluate.truncation_trade(split, [3, 5, 10, 15, 20, 30, 40])
view = truncation.copy()
view["Discovery HR@10"] = view["Discovery HR@10"].map("{:.4f}".format)
view["Coverage"] = view["Coverage"].map("{:.2%}".format)
view["Novelty"] = view["Novelty"].map("{:.2f}".format)
view["Stored megabytes"] = view["Stored megabytes"].map("{:.3f}".format)
view["Shrink vs the full matrix"] = view["Shrink vs the full matrix"].map("{:.0f}x".format)
print(view.to_string(index=False))
""")

md(r"""
**Keeping 15 neighbours per product raises discovery HR@10 from 0.3644 to 0.4156, raises
coverage from 15.46% to 25.77%, and shrinks the artifact from 78.96 MB to 0.55 MB - about
143x.** More accurate, more of the catalog, and small enough to load in a web service. The
peak is real but shallow: 20 neighbours gives 0.4073 and 10 gives 0.4054, so 15 is a measured
choice rather than a magic number, and coverage keeps climbing all the way down to 3
neighbours while accuracy starts to fall.

**Finding two: the popularity-damping knob is wired to nothing.**

The standard advice for popularity bias in item-item CF is to divide each product's column by
its popularity raised to some alpha before taking the cosine, and tune alpha. Here is the
arithmetic. Scaling column *i* of R by a constant multiplies row *i* of R-transpose by that
same constant. The cosine then **L2-normalizes every row to unit length**, which divides the
constant straight back out. The similarity matrix is unchanged for every alpha.
""")

code(r"""
# ===============================================================
# 5.7b THREE DAMPING VALUES, MEASURED TO FOUR DECIMALS
# ===============================================================
damping = evaluate.damping_no_op_table(split, [0.0, 0.25, 0.5])
print(damping.to_string(index=False))
print("\nIdentical to four decimals, and the similarity matrices are bit-identical.")
""")

md(r"""
**Three alphas, four-decimal-identical results, and a maximum absolute difference of 0.0
between the similarity matrices.** A student who does not check this can tune alpha for a
week and report the noise between runs as a finding. The fix for popularity bias in this
model is not damping the cosine - it is the truncation above, which raised coverage from
15.46% to 25.77% for free.

## 5.8 What leaves this notebook

Six files, and nothing else. Three things are deliberately **not** exported:

- **The customer x product matrix.** It is 390,571 cells of last quarter's purchase history
  and it is stale the day after it is written. The service owns its own customer history and
  multiplies it against the similarity matrix at request time.
- **The full dense similarity matrix**, for the reason measured in 5.7.
- **The SVD model.** It wins discovery HR@10 by 0.028 and cannot answer *why am I seeing
  this?* with the name of a product the customer bought. It stays in the leaderboard, where
  the comparison is the point, and out of the service.
""")

code(r"""
# ===============================================================
# 5.8 ASSEMBLE THE EVIDENCE AND WRITE THE SIX-FILE CONTRACT
# ===============================================================
reload_customers = handoff.reload_users(split)
reload_check = {
    "customers": len(reload_customers),
    "selection": (f"the discovery-protocol population sorted by customer id, "
                  f"first {config.RELOAD_CHECK_USERS}"),
    "protocol": config.PROTOCOL_DISCOVERY,
    "baseline_top10": handoff.baseline_top10(split, deployed, reload_customers),
    "similarity_digest": handoff.similarity_digest(deployed.payload),
}

catalog = handoff.build_catalog(split, descriptions)
samples = handoff.build_samples(split, descriptions, fitted)
evidence = handoff.assemble_evidence(
    split=split, ledger=ledger, repeat_profile=repeat, concentration=skew,
    standard=standard, discovery=discovery, comparison=comparison,
    zero_diagnosis=zero, revenue=revenue, cold=cold, outcomes=outcomes,
    reload_check=reload_check, incoherent=incoherent, exposure=exposure,
    loop=loop, inflation=inflation, truncation=truncation, damping=damping,
    fallback_sweep=sweep,
)
model_card = handoff.build_model_card(evidence, catalog)
operating_policy = handoff.build_policy(evidence, fallback)

exported = handoff.export(deployed.payload, catalog, evidence, model_card,
                          operating_policy, samples)
print(exported.to_string(index=False))
""")

md(r"""
The model card is the file a reviewer reads instead of this notebook, and the part that
matters most is the part that says what the system will not do.
""")

code(r"""
# ===============================================================
# 5.8b WHAT THE MODEL CARD REFUSES TO CLAIM
# ===============================================================
print(model_card["boundary"])
print()
for claim in model_card["prohibited_claims"]:
    print(f"  - {claim}")
""")

md(r"""
## 5.9 Reload the artifacts and prove they stand on their own

The last cell throws away everything in memory. It reads the similarity matrix and the
catalog **back from disk**, rebuilds the customer matrix from the committed interaction log
the way the service would rebuild it from its own history store, and re-ranks **200
customers** under the discovery policy.

The test is not "does it look similar". It is **all ten stock codes identical, in the same
order, for all 200 customers**, plus a SHA-256 over the stored similarity arrays matching the
digest recorded at export. Anything else raises.
""")

code(r"""
# ===============================================================
# 5.9 RELOAD IDENTITY CHECK
# ===============================================================
identity = handoff.verify()
print(f"Status                  : {identity['status']}")
print(f"Identical top-10 lists  : {identity['identical_top10']} customers")
print(f"Products reloaded       : {identity['products_reloaded']:,}")
print(f"Stored links            : {identity['stored_links']:,} "
      f"({identity['neighbours_kept']} neighbours per product)")
print(f"Similarity digest       : {identity['similarity_digest'][:32]}...")
print(f"Recorded at export      : {identity['digest_recorded_at_export'][:32]}...")
print(f"Customer matrix         : {identity['customer_matrix']}")

assert identity["status"] == "identical"
assert identity["identical_top10"] == f"{config.RELOAD_CHECK_USERS}/{config.RELOAD_CHECK_USERS}"
assert identity["similarity_digest"] == identity["digest_recorded_at_export"]
print("\nReload identity assertions passed.")
""")

code(r"""
# ===============================================================
# 5.9b WHAT THIS LAB ASKS A STUDENT TO CLONE
# ===============================================================
print(handoff.committed_size().to_string(index=False))
""")

md(r"""
---

### Stage 5 conclusion

The policy fills **ten discovery-only slots** with item-item cosine truncated to 15
neighbours, keeps reorders in a separate strip that is never reported as personalization, and
hands **22.4% of registered test customers** - plus every guest - a list headed "Popular
right now", chosen by measuring five candidates against what cold customers really bought
(recent revenue over 28 days, HR@10 **0.4624**, against **0.4391** for all-time popularity).

Two engineering findings survived checking: truncating to 15 neighbours **raised** discovery
accuracy from 0.3644 to 0.4156 **and** coverage from 15.46% to 25.77% while shrinking the
artifact ~143x, and popularity damping is a mathematical no-op that three alphas confirm to
four decimals.

And the honest price of all of it: **3.53% of available new-product revenue against 2.81%
with no personalization - 0.7 percentage points, as an upper bound.**

Six files, under half a megabyte, reload byte-identical.

---

## What this notebook is asking you to take away

**The two tables are the lesson.** Reorder (already-bought) is rank 1 at HR@10 **0.7995** on
the standard protocol and rank 7 at **0.0217** on discovery - below ten products drawn at
random. Same model, same day, same data, opposite verdicts, decided entirely by what the
analyst counted as a hit. A leaderboard without its protocol written on it is not a result.

**Coverage and novelty are not decoration.** Popularity scores 0.5713 while showing 0.23% of
the catalog to everybody and never once recommending from its less-popular half.

**The split is the experiment.** Leave-one-out inflates SVD-64 by +104.3% and popularity by
+8.6% with the targets held identical. Choose the split before you choose the model.

**And the claim boundary holds everywhere.** An offline ranking score is not evidence of
revenue. The best personalized model here reaches 3.53% of available new-product revenue
against 2.81% for a generic list, and even that gap is an upper bound. Merchandisers own
placement and exclusions; the model ranks within their rules. A recommendation is not a
statement about what the shopper needs, and nothing here describes any real retailer's
current operations.
""")
# ---------------------------------------------------------------------------

notebook["cells"] = cells
notebook["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}

if __name__ == "__main__":
    nbf.validate(notebook)
    identifiers = [cell["metadata"]["id"] for cell in notebook["cells"]]
    assert len(identifiers) == len(set(identifiers)), "duplicate cell id"
    assert all(cell["metadata"].get("language") for cell in notebook["cells"]), \
        "missing language"
    with OUTPUT.open("w", encoding="utf-8") as handle:
        nbf.write(notebook, handle)
    markdown_cells = sum(1 for cell in notebook["cells"] if cell["cell_type"] == "markdown")
    code_cells = len(notebook["cells"]) - markdown_cells
    guides = sum(1 for cell in notebook["cells"]
                 if cell["cell_type"] == "markdown"
                 and cell["source"].startswith("### How to read this plot"))
    figures = sum(cell["source"].count(".show()") for cell in notebook["cells"]
                  if cell["cell_type"] == "code")
    print(f"Wrote {OUTPUT.name}: {len(notebook['cells'])} cells "
          f"({code_cells} code, {markdown_cells} markdown), "
          f"{figures} figures, {guides} reading guides")
