"""Build 01_complaint_build.ipynb in the five Module 4 teaching stages.

This file is the canonical source of the notebook. Never hand-edit the .ipynb:
change a cell here and regenerate, then execute the notebook so its committed
outputs match the code that produced them.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import nbformat as nbf


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_DIR / "01_complaint_build.ipynb"

notebook = nbf.v4.new_notebook()
cells: list = []


def cell_metadata(language: str) -> tuple[str, dict[str, str]]:
    cell_number = len(cells) + 1
    if cell_number >= 11:
        cell_number += 2
    cell_id = f"complaint-build-{cell_number:03d}"
    return cell_id, {"id": cell_id, "language": language}


def md(text: str) -> None:
    cell_id, metadata = cell_metadata("markdown")
    cells.append(nbf.v4.new_markdown_cell(text.strip("\n"), id=cell_id, metadata=metadata))


def code(text: str) -> None:
    cell_id, metadata = cell_metadata("python")
    cells.append(nbf.v4.new_code_cell(text.strip("\n"), id=cell_id, metadata=metadata))


# ═══════════════════════════════════════════════════════════════════════════
# Header
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
# From a complaint letter to the right specialist team

**ITAI 2372 - Module 4 - AI in Finance and Risk**

The credit case scored a table of numbers. This one reads English. A consumer writes a
paragraph about what a bank did to them, and the workflow has to decide which of eight
specialist teams should answer it - before anyone has read it.

| | Stage | What happens |
|---|---|---|
| **1** | **Ingestion and Provenance** | Where the complaints come from, what one row means, what was sampled |
| **2** | **EDA and Text Preparation** | The team imbalance, the duplicate-letter discovery, and turning words into numbers |
| **3** | **Model Training** | A baseline, then the deployed model, then a measured comparison against a transformer |
| **4** | **Validation and Operating Policy** | Per-team results, the confidence rule, and one frozen test scoring |
| **5** | **Prediction, Routing Words and Handoff** | Three complaints end to end, then the exported contract |

> **The model routes; it never judges whether a complaint is valid.** It decides which
> queue a complaint enters first. It does not decide whether the consumer is right, what
> the company owes, or how the case ends. A wrong route costs days on a regulatory clock;
> a person still reads every complaint.

### The case

A bank's complaint-handling office receives consumer complaints forwarded by the Consumer
Financial Protection Bureau. Federal rules give the company a short, fixed window to
respond, and the clock starts when the complaint arrives - not when the right team finally
sees it. Today a clerk reads each complaint and forwards it. The narrow question is:

> **Which specialist team should read this complaint first?**

Eight teams answer complaints here: bank accounts, credit cards, credit reporting, debt
collection, loans, money transfers, mortgages, and student loans.

### The data

- **58,185 real consumer complaints** published by a US federal agency
- Complaints received **2023 or later**, each with a narrative the consumer wrote
- **8 specialist teams**, consolidated from the agency's own product labels
- Narratives are **opt-in** and the agency scrubs personal details before publishing
- Split 70 / 15 / 15, stratified by team, seed 42

The parquet files are committed beside this notebook. Running it needs no download, no
API key, and no network - including for the transformer comparison in stage 3.
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
from plotly.offline import init_notebook_mode
from IPython.display import display

from complaintlab import charts, config, data, explain, handoff, metrics, models, presentation, text_prep

warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 160)
init_notebook_mode(connected=False)
pio.renderers.default = "notebook"
print(config.describe())
""")

# ═══════════════════════════════════════════════════════════════════════════
# Stage 1
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 1 - Ingestion and Provenance

**Question:** Where did these complaints come from, who is in them, and what is one row?

**What to expect in this stage:** the publisher and the exact file, an honest statement of
who is missing from the data, two real complaints printed in full, and the split counts the
rest of the notebook uses.

**Why this stage exists:** a text dataset arrives looking finished. Someone still chose
which complaints get published, which fields survive, and which words were removed. If we
skip that, we will read the model's mistakes as the world's behaviour instead of the
sample's.

**What passes to stage 2:** three loaded splits - train, validation, test - and the
provenance facts that constrain what any of them can prove.
""")

md(r"""
## 1.1 What the CFPB Consumer Complaint Database is

The **Consumer Financial Protection Bureau (CFPB)** is a US federal agency. When a consumer
complains about a bank, a lender, a debt collector, or a credit bureau, the CFPB forwards
the complaint to the company, gives the company a fixed window to respond, and then
publishes the complaint in a public database.

Two properties of that database shape everything below.

**Narratives are opt-in.** The complaint record always exists, but the consumer's own
description of what happened is published only if the consumer ticks a consent box. About
**22% of complaints** carry one. So this model learned from the language of the minority
who consented to publication - not from every complainant.

**Personal details are removed at the source.** Before publishing, the CFPB replaces names,
account numbers, dates, and addresses with runs of **`XXXX`**. We do not de-identify
anything here; the publisher did it first. Those `XXXX` blocks are visible in every
narrative below, and the model treats them as ordinary text.

**Source:** [CFPB Consumer Complaints](https://www.consumerfinance.gov/data-research/consumer-complaints/) ·
bulk file `complaints.csv.zip`, retrieved 2026-09-01 · US Government public data.
""")

code(r"""
# ===============================================================
# 1.1 PROVENANCE OF THE COMMITTED FILES
# ===============================================================
splits = data.load_splits()
data.provenance_summary(splits)
""")

md(r"""
## 1.2 What one row means

**One row is one complaint that one consumer submitted about one company.** Not one
consumer, not one account, not one company. The same person can appear twice if they
complained twice, and a large bank appears thousands of times.

The model reads exactly one field: the **narrative**. It never sees the company name, the
state, the date, or the CFPB's own `issue` label. Those columns are kept for context in
this notebook and are deliberately withheld from the model, because at routing time in a
real intake queue they either do not exist yet or are the very thing we are trying to
predict.

Below are **two actual training complaints from different teams**, each 400-900 characters
long so we can read it in full. The recorded team is the label the model learns to predict;
it is shown for us, not given to the model. The `XXXX` redactions are kept as published.
These are reading examples, not a test of model accuracy.
""")

code(r"""
# ===============================================================
# 1.2 TWO REAL COMPLAINTS, IN FULL
# ===============================================================
import textwrap

train = splits["train"]
examples = (
  train.loc[train[config.TEXT_COLUMN].str.len().between(400, 900)]
  .drop_duplicates(subset="team")
  .head(2)
)
example = examples.iloc[0]
for example_number, complaint in enumerate(examples.to_dict("records"), start=1):
  print(f"EXAMPLE {example_number} | Complaint ID: {complaint['complaint_id']}")
  print(f"Recorded team: {complaint['team']} (label, not a model input)")
  print("Narrative the model reads:")
  for paragraph in complaint[config.TEXT_COLUMN].splitlines():
    print(textwrap.fill(paragraph, width=72))
  print()
""")

md(r"""
## 1.3 Why we sample, and what the sample costs

The full database holds **17.5 million complaints**, of which **3.85 million** carry a
narrative. That is far more than a laptop can hold in memory during a class, and it is far
more than a model needs to learn eight teams.

So the build script sampled. Three choices were made once, written down, and frozen:

1. **Complaints received 2023 or later.** The agency renamed its product categories in
   2023, and volume roughly quadrupled between 2022 and 2025. Older complaints describe a
   different mix of companies and a different vocabulary.
2. **Exact-duplicate narratives removed before splitting.** Stage 2 is about why.
3. **The largest team capped.** Also stage 2.

The split below is the result. **Stratified** means each split holds the same proportion of
every team, so validation and test are not accidentally easier than training.
""")

code(r"""
# ===============================================================
# 1.3 THE THREE SPLITS
# ===============================================================
data.split_summary(splits).style.format({"Share of sample": "{:.1%}"}).hide(axis="index")
""")

code(r"""
# ===============================================================
# 1.4 HOW OFTEN THE PUBLISHER REDACTED SOMETHING
# ===============================================================
text_prep.redaction_profile(train[config.TEXT_COLUMN])
""")

md(r"""
### Stage 1 conclusion

We have 58,185 real complaints from a named federal publisher, already de-identified at the
source, split 70/15/15 by team with seed 42. The one field the model reads is the
consumer's own paragraph, and the population behind it is *complainants who consented to
publication since 2023* - which is the population every number in this notebook describes.
""")

# ═══════════════════════════════════════════════════════════════════════════
# Stage 2
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 2 - EDA and Text Preparation

**Question:** what is actually in these complaints, and how does a paragraph of English
become something a model can add up?

**What to expect in this stage:** the team mix; a short flow showing how we prepared
the data before splitting; complaint length; and one sentence turned into numbers.

**Why this stage exists:** the two biggest decisions in this whole lab - deduping and
capping - came out of looking at the data, not out of modelling. Both were invisible until
someone counted.

**What passes to stage 3:** a training split we trust, and a defined way of turning its
narratives into numbers.
""")

md(r"""
## 2.1 The teams, and how unequal they are

The label the model predicts is the **team**: one of eight standing queues in the
complaint-handling office. Each team owns a family of products.

| Team | Owns complaints about |
|---|---|
| Bank accounts | checking and savings accounts, overdraft fees, closures |
| Credit cards | credit cards, prepaid and gift cards, card billing |
| Credit reporting | credit reports, disputes, inaccurate items, inquiries |
| Debt collection | collectors, validation of debts, collection lawsuits |
| Loans | vehicle, payday, title, and personal loans |
| Money transfers | payment apps, wire transfers, virtual currency |
| Mortgages | mortgage servicing, escrow, modification, foreclosure |
| Student loans | federal and private student loans, forbearance, servicers |

In the real 2023+ window, credit reporting is not merely the largest team - it is
**4.8 times** larger than debt collection and **31 times** larger than student loans. A
model trained on that mix can score 65% accuracy while never learning what a student-loan
complaint looks like.

So the build script **capped credit reporting at 1.5 times the second-largest team** before
sampling. That is a disclosed classroom choice, and it has a cost: the team shares below
are *not* the real-world mix, so nothing here estimates how much of a bank's real complaint
volume is credit reporting.
""")

code(r"""
# ===============================================================
# 2.1 COMPLAINTS PER TEAM PER SPLIT
# ===============================================================
counts = data.team_counts(splits)
counts.style.format({"share of sample": "{:.1%}"}).hide(axis="index")
""")

code(r"""
# ===============================================================
# 2.1b TEAM DISTRIBUTION ACROSS THE THREE SPLITS
# ===============================================================
charts.team_distribution(counts).show()
""")

md(r"""
### How to read this plot

- **Question:** after the cap, how uneven are the eight teams, and does any split get an
  easier mix than the others?
- **Marks and axes:** one bar per team, tallest team on the left. The bar is stacked into
  its three splits - blue training, orange validation, green test - and the number above
  each bar is the team's total. Colour is not doing the work alone: the segments are always
  in the same order and the totals are printed.
- **Denominator:** the 58,185 complaints in the committed sample. Not the source database.
- **What to notice:** the cap did its job on the runner-up - credit reporting is now 1.5
  times debt collection - and did much less at the bottom: it still holds 17,758 complaints
  against student loans' 2,000, about 9 to 1. Every team's three segments keep the same
  70/15/15 proportions, which is what stratification bought us.
- **Term:** **class imbalance** means some labels appear far more often than others. In the
  real 2023+ window the biggest team is 31 times the smallest; in this capped sample it is
  8.9 times.
- **Why it matters:** accuracy alone will flatter any model on this data. A model that
  always answers "credit reporting" is right 30.5% of the time without reading a word.
  Stage 3 makes that baseline explicit, and stage 4 reports each team separately.
- **Boundary:** these heights are a sampling decision, not a measurement of the world. Do
  not read "credit reporting is 30% of complaints" off this chart - in the real window it
  is closer to 72%.
""")

md(r"""
## 2.2 Prepare the data before splitting

**About 42 out of every 100 rows repeated text already in the data.** Removing those
extra copies is called **deduplication**: keep one copy of each identical complaint text.

The files we loaded were already prepared in this order:

```text
Complaint text from 2023 onward
             |
             v
Group product names into 8 team labels
             |
             v
Keep one copy of each identical text
             |
             v
Apply the team cap and select our sample
             |
             v
Split into training / validation / test
```

**How much was repeated?** These recorded build counts cover the **2,634,602 rows
mapped to our eight teams**, before sampling. They are not percentages of the final
58,185-complaint classroom sample.
""")

code(r"""
# ===============================================================
# 2.2 EXACT REPEATS REMOVED BEFORE SAMPLING AND SPLITTING
# ===============================================================
duplicate_share = config.DEDUPE_ROWS_REMOVED / config.DEDUPE_ROWS_IN_WINDOW
print(f"Rows before deduplication: {config.DEDUPE_ROWS_IN_WINDOW:,}")
print(f"Extra copies removed:      {config.DEDUPE_ROWS_REMOVED:,} ({duplicate_share:.1%})")
print(f"Different texts kept:      {config.DEDUPE_DISTINCT_NARRATIVES:,} ({1 - duplicate_share:.1%})")
""")

md(r"""
**What if we skip this?** Imagine the same letter appears in both training and testing.
The model has already practiced on the test wording, so its test score can look better
than its ability to route a new complaint. This is **data leakage**, like practicing
with questions that later appear on the exam. Remove copies **before** splitting;
removing them separately inside each split can leave the same text on both sides.

**Why group product names?** The agency changed some category names over time. We map
related names to one classroom team, such as "Credit card" and "Prepaid card" to
**Credit cards**. The small "Debt or credit management" category has no team in this
exercise and is left out: 5,545 rows, about 0.2% of the original 2023+ text window.

**Two limits:** slightly reworded copies can remain; identical wording does not mean a
complaint is invalid. This step cleans the training data, not the real complaint queue.
""")

md(r"""
## 2.3 How long is a complaint?

Length matters twice in this lab. It decides how much evidence the word-count model has to
work with, and it decides how much of a complaint the transformer in stage 3 can even read
before it stops.
""")

code(r"""
# ===============================================================
# 2.3 NARRATIVE LENGTH IN THE TRAINING SPLIT
# ===============================================================
charts.narrative_length(train).show()
""")

md(r"""
### How to read this plot

- **Question:** how much text does the model actually get per complaint?
- **Marks and axes:** the horizontal axis is characters in the narrative, in 150-character
  bins; the vertical axis counts training complaints in each bin. The green line marks the
  median. The display is capped at 6,000 characters and the labelled annotation states how
  many complaints were folded into that last bar.
- **Denominator:** the 40,729 training complaints. Validation and test look the same, as
  the table below confirms.
- **What to notice:** the distribution is strongly right-skewed. Half of all complaints are
  under 870 characters - roughly a long paragraph - while the longest runs to 32,609
  characters, about twelve pages.
- **Term:** a **right-skewed** distribution has most of its mass at low values and a long
  thin tail at high ones. The median (870) is far below the mean (1,246) precisely because
  of that tail.
- **Why it matters:** short complaints carry few words, so the word-count model has little
  to weigh and its confidence tends to be lower - which is exactly the population the
  triage queue in stage 4 will catch.
- **Boundary:** longer is not more serious. A two-line complaint about a wrongly closed
  account and a twelve-page dispute letter can both be routine or both be urgent. This
  chart measures typing, not severity.
""")

code(r"""
# ===============================================================
# 2.3b LENGTH, SPLIT BY SPLIT
# ===============================================================
text_prep.length_profile(splits)
""")

md(r"""
## 2.4 Turning one sentence into numbers

A model cannot add up English. Something has to convert a paragraph into a row of numbers,
and *what* it converts to is the central choice of this lab.

The deployed model uses **TF-IDF**, which stands for term frequency-inverse document
frequency. Two ideas, one per half of the name:

- **Term frequency:** how often a word or 2-word phrase appears in *this* complaint. A
  complaint that says "mortgage" five times is more about mortgages than one that says it
  once.
- **Inverse document frequency:** how rare that word is across *all* complaints. "The"
  appears everywhere and carries nothing. "Escrow" appears in few complaints and carries a
  great deal. IDF divides by how common a word is, so rare words get large weights and
  common words get small ones.

Multiply the two, and every word in a complaint gets a number: high when the word is
frequent here and rare elsewhere.

Below, three one-sentence complaints are turned into numbers so that every value can be
checked by eye. Watch what happens to "my", which appears in all three, versus "credit
card", which appears in one.
""")

code(r"""
# ===============================================================
# 2.4 A WORKED TF-IDF EXAMPLE ON THREE TINY COMPLAINTS
# ===============================================================
for i, sentence in enumerate(text_prep.WORKED_EXAMPLE_CORPUS, start=1):
    print(f"{i}. [{text_prep.WORKED_EXAMPLE_TEAMS[i - 1]:16s}] {sentence}")
print("\nComplaint 1 as numbers (only its non-zero columns are shown):")
text_prep.worked_example()
""")

md(r"""
Rows are sorted by **how many complaints contain the term, highest first**. This count
is across the three complaints, not repetitions within complaint 1.

"my" appears in all **three** complaints and has the lowest weight. "credit" and
"my credit" appear in **two**, so their weights are higher. "card" and "credit card"
appear in **one**, so their weights are higher still. **A higher complaint count does
not mean a higher TF-IDF weight.**

TF-IDF keeps words and neighboring two-word phrases, but it does not understand the
whole sentence.
""")

md(r"""
### Word clouds: which words stand out?

**The story: a canceled flight and a missing refund.** The consumer says the credit-card
company received the refund but did not return it. These clouds use that real training
complaint, selected because the problem is easy to recognize, not to evaluate the model.

- **Word frequency:** words used more often in this complaint appear larger.
- **TF-IDF:** combines frequency here with rarity across the training complaints.

Look for **refund**, **flight**, **airline**, and **credit card**. Compare what stands
out when we count repeated words with what stands out after TF-IDF weighting.
""")

code(r"""
# ===============================================================
# 2.4b ONE REAL COMPLAINT, TWO WAYS TO SIZE ITS WORDS
# ===============================================================
word_clouds = charts.tfidf_word_clouds(train)
print(f"Real complaint #{word_clouds.layout.meta['complaint_id']} | {word_clouds.layout.meta['team']}")
print(f"IDF uses {word_clouds.layout.meta['training_complaints']:,} training complaints.")
""")

md(r"""
**Read the size, not the location or color.** Both clouds use the same selected terms,
including two-word phrases. Larger words have higher values within that cloud; sizes
are approximate because the words must fit together.

Filler words, numbers, and `XXXX` redactions are hidden **only in this picture**.
This is not a model-confidence score or proof of the correct team. The classifier and
its preprocessing are unchanged.
""")

code(r"""
# ===============================================================
# 2.4c FREQUENCY CLOUD AND TF-IDF CLOUD
# ===============================================================
word_clouds.show()
""")

md(r"""
### Stage 2 conclusion

We grouped labels into eight teams, removed repeated text **before splitting**, and
selected the classroom sample. Near-duplicates can still remain. Next, TF-IDF turns
complaint words and short phrases into numbers the model can use.
""")

# ═══════════════════════════════════════════════════════════════════════════
# Stage 3
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 3 - Model Training

**Question:** how much of the routing can a model actually do, and does a modern
transformer do it better?

**What to expect in this stage:** a baseline that reads nothing, the deployed TF-IDF model,
and then a carefully matched comparison against sentence embeddings from a small
transformer - same complaints, same classifier, only the representation swapped.

**Why this stage exists:** "we used AI" is not a result. A number only means something
against a number you could have had for free, and a comparison only means something when
everything except the thing being compared is held still.

**What passes to stage 4:** one fitted model, chosen with a stated reason, and its
probabilities on the validation split.
""")

md(r"""
## 3.1 The baseline that reads nothing

Before any model, the number to beat: always answer with the biggest team, ignore the text
entirely. **Majority-class baseline.** It costs nothing, it needs no data science, and any
model that cannot beat it is not earning its place.
""")

code(r"""
# ===============================================================
# 3.1 BASELINE AND THE DEPLOYED MODEL, ON THE SAME SPLIT
# ===============================================================
X_train, y_train = train[config.TEXT_COLUMN], train[config.TARGET]
validation, test = splits["validation"], splits["test"]
X_val, y_val = validation[config.TEXT_COLUMN], validation[config.TARGET]
X_test, y_test = test[config.TEXT_COLUMN], test[config.TARGET]

baseline = models.majority_baseline(y_train, len(y_val))
tfidf = models.fit_tfidf(X_train, y_train, X_val)
leaderboard = models.leaderboard([baseline, tfidf], y_val)
leaderboard.style.format({
    "Trained on": "{:,}",
    "Validation accuracy": "{:.4f}",
    "Validation macro-F1": "{:.4f}",
}).hide(axis="index")
""")

md(r"""
**Accuracy** is correct routes divided by all complaints in the validation split - 8,728
complaints. **Macro-F1** averages each team's F1 score with equal weight, so a team with
300 complaints counts as much as one with 2,664. That is the metric that notices when a
model quietly abandons the small teams: the baseline's accuracy of 30.5% comes with a
macro-F1 of 0.059, because seven of its eight teams get nothing right at all.

The fitted model looks at 50,000 columns of words and phrases. One setting decides how many
words survive: `min_df`, the number of complaints a word must appear in before it is kept
at all. It is worth checking, and worth reporting honestly when it turns out not to matter.
""")

code(r"""
# ===============================================================
# 3.2 THE ONE HYPER-PARAMETER THIS LAB TUNES
# ===============================================================
models.min_df_tuning(X_train, y_train, X_val, y_val).style.format({
    "Columns kept": "{:,}",
    "Validation accuracy": "{:.4f}",
    "Validation macro-F1": "{:.4f}",
}).hide(axis="index")
""")

md(r"""
All three settings land within 0.001 accuracy of each other, because the 50,000-column cap
binds before `min_df` does: the vocabulary is already truncated to the 50,000 most useful
columns whichever threshold we pick. **`min_df=2` is kept**, and the honest report is that
this hyper-parameter did not matter here. Reporting that is more useful than pretending a
tuning run bought something.
""")

md(r"""
## 3.2 A fair comparison against a transformer

The obvious question in 2026 is whether a transformer would do better. Answering it
carelessly is easy and worthless, so the comparison here is **matched**:

- **Same complaints in:** a fixed subsample of **15,000 training complaints**, stratified by
  team with seed 42, identical for both representations.
- **Same complaints out:** the full **8,728-complaint validation split**, identical for both.
- **Same classifier:** `LogisticRegression(C=1.0, max_iter=1000, random_state=42)`, the
  identical object in both cases.
- **Only one thing differs:** how the complaint became numbers.

The subsample exists because embedding 40,729 complaints takes about four minutes of CPU
time; 15,000 keeps the comparison honest and the notebook fast. The TF-IDF side is refitted
on those same 15,000 rows so neither side gets more data than the other.

The MiniLM embeddings are **read from a committed parquet**. The notebook downloads no
model and touches no network. They were produced once by `scripts/build_embeddings.py` and
stored as float16, which is why both files together are about 18 MB instead of 76.
""")

code(r"""
# ===============================================================
# 3.3 MATCHED COMPARISON: SAME 15,000 ROWS, TWO REPRESENTATIONS
# ===============================================================
subsample = models.comparison_subsample(train)
E_train = models.load_embeddings(config.EMBEDDINGS_TRAIN_PARQUET, subsample["complaint_id"])
E_val = models.load_embeddings(config.EMBEDDINGS_VAL_PARQUET, validation["complaint_id"])
print(f"comparison training rows : {len(subsample):,}  (same ids for both representations)")
print(f"TF-IDF row width         : {config.TFIDF_MAX_FEATURES:,} sparse columns")
print(f"embedding row width      : {E_train.shape[1]} dense numbers")

tfidf_matched = models.fit_tfidf(
    subsample[config.TEXT_COLUMN], subsample[config.TARGET], X_val,
    name=f"TF-IDF + logistic regression ({config.COMPARE_TRAIN_ROWS:,} rows)",
)
minilm = models.fit_embedding_model(
    E_train, subsample[config.TARGET], E_val,
    name=f"MiniLM embeddings + logistic regression ({config.COMPARE_TRAIN_ROWS:,} rows)",
)
comparison = models.leaderboard([tfidf_matched, minilm], y_val)
comparison.style.format({
    "Trained on": "{:,}",
    "Validation accuracy": "{:.4f}",
    "Validation macro-F1": "{:.4f}",
}).hide(axis="index")
""")

md(r"""
## 3.3 What the transformer actually is

Before reading that table's verdict, it is worth knowing what the losing - or winning -
model actually contains. These numbers were read out of the loaded model, not from
marketing material.

| Fact about `all-MiniLM-L6-v2` | Value |
|---|---|
| Transformer layers | **6** |
| Attention heads per layer | **12** |
| Hidden size (numbers carried per token) | **384** |
| Feed-forward size inside a layer | 1,536 |
| Vocabulary | 30,522 wordpieces |
| Parameters | **22,713,216 (~22.7M)** |
| Output vector per complaint | **384 numbers** (mean-pooled, normalized) |
| Longest input it reads | **256 wordpiece tokens** - the rest is cut off |
| Download size | **183.2 MB** |
| Measured speed on a classroom CPU | 211 complaints per second |

**What it does, at recognition level.** The complaint is first cut into **tokens** -
wordpieces, so "escrow" may be one token and "forbearance" may be three. Each token starts
as a list of 384 numbers. Then, in each of the 6 layers, **every token looks at every other
token** and updates its own 384 numbers based on what it found. That is **attention**: the
numbers standing for "closed" come out different when "account" is nearby than when "case"
is nearby. After 6 rounds of that, the model averages all the token vectors into **one
vector of 384 numbers** for the whole complaint.

That single vector is the representation. Complaints that talk about similar things land
near each other in those 384 dimensions, whether or not they share any words.

**What is learned and what is configured.** The 22.7 million parameters were learned, once,
by the model's authors on general web and forum text - not on complaints, and not by us. The
6 layers, 12 heads, 384 dimensions, and 256-token limit are configuration, fixed before any
training. We did not fine-tune anything here: we used the model as a fixed converter from
text to 384 numbers.

**What the 384-number summary does NOT prove.** It does not show that the model understood
the complaint. It carries no fact about the company, no legal judgement, and no evidence
that the consumer is right. It is a position in a space where similar language sits nearby -
useful for grouping, silent about truth. And it cannot tell a triage clerk *which words*
caused a route, because no dimension of it corresponds to a word.

One more configured number matters here: **256 tokens**. Anything past that is discarded
before the model reads it.
""")

code(r"""
# ===============================================================
# 3.4 HOW MUCH OF A COMPLAINT FITS IN 256 TOKENS
# ===============================================================
text_prep.token_truncation_profile(train[config.TEXT_COLUMN])
""")

md(r"""
Wordpiece tokens are always at least as numerous as words - names, brands, and rare legal
terms split into several - so the truly truncated share is higher than the 27.1% above.
Better than a quarter of these complaints get cut off before the transformer finishes
reading them, while TF-IDF reads every word of every complaint.
""")

code(r"""
# ===============================================================
# 3.5 EVERY CANDIDATE ON THE SAME VALIDATION SPLIT
# ===============================================================
all_candidates = models.leaderboard([baseline, tfidf, tfidf_matched, minilm], y_val)
charts.leaderboard_chart(all_candidates).show()
""")

md(r"""
### How to read this plot

- **Question:** which representation routes complaints better, and by how much?
- **Marks and axes:** one pair of bars per model. Blue is accuracy, orange is macro-F1;
  every bar is labelled with its own value, so the comparison does not depend on colour.
  The two middle bars are the matched pair - same 15,000 complaints, same classifier.
- **Denominator:** every bar is scored on the identical 8,728 validation complaints. The
  models differ in what they were trained on and how text was represented, never in what
  they were tested on.
- **What to notice:** on matched data the two representations tie. TF-IDF takes accuracy by
  0.35 of a point (80.83% against 80.48%) and MiniLM takes macro-F1 by 0.004 (0.7957 against
  0.7918). Neither margin is a win. The right-hand pair also shows what the deployed model
  gains from the other 25,729 training complaints the matched pair does not get: 82.87%.
- **Term:** a **representation** is the recipe for turning input into numbers. Both middle
  bars use the same learning algorithm; only the recipe changed.
- **Why it matters:** this decides which model ships. A tie means the extra machinery bought
  nothing measurable here, so it cannot justify the explainability it costs.
- **Boundary:** this is not a verdict on transformers. It is one 22.7M-parameter general
  sentence encoder, used frozen, on long domain-specific complaints it truncates at 256
  tokens. A larger model, or a fine-tuned one, or shorter inputs, could easily reverse it.
""")

md(r"""
### Stage 3 conclusion: a representation trade, not an upgrade

The matched comparison came out a **tie**, and a tie is the most useful result this stage
could have produced - because it forces the decision onto something other than the accuracy
number. Read the two middle bars as a trade rather than a ranking:

| | TF-IDF | MiniLM embeddings |
|---|---|---|
| Matched accuracy / macro-F1 | 80.83% / 0.7918 | 80.48% / 0.7957 |
| Row width | 50,000 sparse columns | 384 dense numbers |
| Reads | every word of the complaint | the first 256 tokens |
| Words it has never seen | nothing to say about them | can still place them by context |
| Explanation for one route | the weighted words themselves | none at word level |
| Cost to run in class | seconds, no download | 183 MB model, minutes of CPU |

The embedding is 130 times narrower and carries meaning across different wordings - real
advantages on other tasks. What it does not do here is *beat* word counts, because routing
hinges on domain vocabulary that TF-IDF captures directly: *escrow*, *forbearance*,
*chargeback*, *Cash App*, *1681*. The 384-dimension summary spends its capacity on general
meaning, and general meaning is not the scarce thing in this task.

One more thing that comparison shows. The deployed model, trained on all 40,729 complaints,
reaches 82.87% - about two points above its own 15,000-row version. The word-count model
keeps improving as complaints are added, because every new complaint can add vocabulary. The
embedding's 384 dimensions were fixed before it ever saw a complaint.

**The deployed model is TF-IDF plus logistic regression.** The argument is not the accuracy
number, which is a tie. It trains in about 11 seconds, needs no download, and - decisively
for a workflow where a person receives every route - it can show which words caused each
decision. Here accuracy and explainability point the same way, so the choice is easy. When
they do not, this is the stage where you have to say out loud which one you are buying and
what you are giving up for it.
""")

code(r"""
# ===============================================================
# 3.6 WHAT THE DEPLOYED MODEL LEARNED, PER TEAM
# ===============================================================
explain.signature_table(tfidf.estimator)
""")

# ═══════════════════════════════════════════════════════════════════════════
# Stage 4
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 4 - Validation and Operating Policy

**Main idea: let the model suggest a team, but ask a clerk to choose when the score is low.**

We will check three things: how well it finds each team's complaints, when routing goes
to a person, and what happens on a separate test set. **A specialist still reads and
handles every complaint**, including those whose team was chosen automatically.
""")

md(r"""
## 4.1 How well does it find the right team?

First let the model choose a team for **every validation complaint**, before applying
any confidence cutoff. Overall accuracy can hide a weak result for one team.

For each row below, ask: **of the complaints labeled for this team, how many did the
model find?** That percentage is called **recall**. The labels come from the source
product categories, not a new expert review of each letter.
""")

code(r"""
# ===============================================================
# 4.1 ONE SIMPLE CHECK FOR EACH TEAM
# ===============================================================
val_per_team = metrics.per_team_table(y_val, tfidf.val_predictions)
val_scores = metrics.classification_scores(y_val, tfidf.val_predictions)
print(f"Right team overall: {val_scores['accuracy']:.1%} of {len(y_val):,} validation complaints.")
val_per_team.loc[val_per_team["Team"].isin(config.TEAMS),
                 ["Team", "Complaints in the split", "Recall"]].rename(columns={
    "Complaints in the split": "Labeled for this team",
    "Recall": "Correct team found",
}).style.format({
    "Labeled for this team": "{:,}", "Correct team found": "{:.1%}",
}).hide(axis="index")
""")

md(r"""
**Example: Loans.** Of 505 loan complaints, the model found 325 and sent 180 elsewhere:
**64.4% found**, roughly 64 out of 100. This is a weakness even though overall accuracy
is about 83%.

Some complaints involve overlapping topics, such as debt collection and credit reporting.
That can help explain a wrong team choice, but it does not make the mistake harmless.
The receiving specialist needs a way to redirect it.
""")

md(r"""
## 4.2 When should a clerk choose the team?

**Confidence** is the model's highest score among the eight teams. Our cutoff is **0.55
(55%)**. It is a routing rule, not a claim that 55% of routes are correct.

```text
Complaint arrives
  |
  v
Model suggests a team
  |
  v
Confidence at least 0.55?
  Yes: use suggested team
   No: clerk chooses team
  |
  v
Specialist handles complaint
```

**Three made-up scores:** the middle row shows that exactly 0.55 qualifies. A high score
can still be wrong; a low score asks for help, not dismissal of the complaint.
""")

code(r"""
# ===============================================================
# 4.2 THREE PRACTICE SCORES THROUGH THE SAME RULE
# ===============================================================
practice_confidence = np.array([0.90, 0.55, 0.40])
pd.DataFrame({
    "Made-up confidence": [f"{score:.0%}" for score in practice_confidence],
    "Who chooses the team?": metrics.routes(practice_confidence),
}).replace({
    config.ROUTE_AUTO: "Model sends to its suggested team",
    config.ROUTE_TRIAGE: "Clerk reads and chooses a team",
})
""")

md(r"""
**Why 0.55?** On validation, the goal was to auto-route as many complaints as possible
while getting at least **90% of those routes right**. Among the tested cutoffs, 0.55
met that goal with the highest automatic-routing share. At 0.50, accuracy among
auto-routes was only 88.7%. The detailed comparison stays in the saved evidence.

**Try one change:** raising the cutoff sends more complaints to the clerk; lowering it
lets the model route more. Neither change retrains the model, and neither guarantees
better results on future complaints. We keep 0.55 for the final test.
""")

md(r"""
## 4.3 What happened on the final test?

Freeze the model and cutoff, then score **8,728 separate test complaints**. Do not change
the rule to improve the test result. Validation also has 8,728 complaints, but they are
different rows.

The table separates **how much routing is automatic** from **how often those automatic
routes are right**. No score below measures the clerk's decisions or the final response
to the consumer.
""")

code(r"""
# ===============================================================
# 4.3 THE FROZEN RULE ON VALIDATION AND TEST
# ===============================================================
val_policy = metrics.policy_eval(y_val, tfidf.val_predictions, tfidf.val_confidence)
pipeline = tfidf.estimator
test_probabilities = pipeline.predict_proba(X_test)
classes = pipeline.named_steps["lr"].classes_
test_predictions = classes[np.argmax(test_probabilities, axis=1)]
test_confidence = test_probabilities.max(axis=1)
test_scores = metrics.classification_scores(y_test, test_predictions)
test_policy = metrics.policy_eval(y_test, test_predictions, test_confidence)

routing_summary = pd.DataFrame([{
    "Check": label,
    "Complaints checked": f"{result['complaints']:,}",
    "Team chosen automatically": f"{result['auto_routed']:,} ({result['coverage']:.1%})",
    "Clerk chooses the team": f"{result['triage_rows']:,} ({result['triage_share']:.1%})",
    "Right team among automatic routes": f"{result['accuracy_among_auto_routed']:.1%}",
} for label, result in [("Validation", val_policy), ("Test", test_policy)]]).set_index("Check").T
print(f"If the model chose every test route: {test_scores['accuracy']:.1%} would match the recorded team.")
routing_summary
""")

md(r"""
### Read the result in everyday terms

- **About 78 out of 100** test complaints get their team automatically. This share is
  called **coverage**: 6,833 out of 8,728, not the percentage routed correctly.
- **About 22 out of 100** go to a clerk for team selection: 1,895 complaints. The clerk
  needs time to handle this queue; these complaints are not rejected.
- **About 90 out of 100 automatic routes** match the recorded team. This uses a different
  group: only the auto-routed complaints. Confident mistakes still remain.

**Did we meet the target?** Validation reached **90.2%**, but test reached **89.7%**,
slightly below the 90% target. Similar numbers are not a guarantee. Report the shortfall
without retuning on the test set; this classroom result is not production approval.

### Stage 4 conclusion

**Suggest a team -> check confidence -> auto-route or ask a clerk -> specialist handles
the complaint.** Keep the 0.55 rule and these test results fixed for the walkthroughs.
The full precision, recall, F1, threshold comparison, and test confusion counts remain
in the app's supporting evidence, not extra tables to read here.
""")

# ═══════════════════════════════════════════════════════════════════════════
# Stage 5
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 5 - Prediction, Routing Words and Handoff

**Question:** what does one complaint actually look like going through this, and what
exactly does the service receive?

**What to expect in this stage:** three real held-out complaints walked end to end -
narrative, team probabilities, route, routing words, and what the person on the other end
does - including one the model got confidently wrong. Then the exported artifacts and a
reload check.

**Why this stage exists:** a metric is an average over 8,728 complaints. Nobody in the
complaints office experiences an average; they experience one complaint at a time.

**What passes out of this notebook:** five files, and nothing else.
""")

md(r"""
## 5.1 Three complaints, read one at a time

These three come from the test split and from a set of twelve complaints that were read in
full and screened before being packaged: no distressing content, no template letters, all
eight teams covered, confidence spanning 0.363 to 0.996.

Each walkthrough separates four things that are easy to blur together: **what the consumer
wrote**, **what the model output**, **what the policy did with it**, and **what actually
turned out to be true**.
""")

code(r"""
# ===============================================================
# 5.1 WALKTHROUGH 1 - CONFIDENT AND CORRECT
# ===============================================================
test_scored = test.reset_index(drop=True).assign(
    predicted_team=test_predictions, confidence=test_confidence
)

# one scored test complaint, by its id
def pick(complaint_id):
    return test_scored.loc[test_scored["complaint_id"] == complaint_id].iloc[0]

first = pick(config.WALKTHROUGH_IDS[0])
presentation.complaint_excerpt(first, 1, "Confident and correct", limit=1100)
""")

code(r"""
# ===============================================================
# 5.2 WHAT THE MODEL SAID ABOUT IT
# ===============================================================
presentation.routing_decision(pipeline, first)
""")

code(r"""
# ===============================================================
# 5.3 ALL EIGHT TEAM PROBABILITIES
# ===============================================================
presentation.probability_bars(pipeline, first[config.TEXT_COLUMN])
""")

code(r"""
# ===============================================================
# 5.4 THE WORDS THAT CAUSED THE ROUTE
# ===============================================================
words = explain.routing_words(pipeline, first[config.TEXT_COLUMN], first["predicted_team"])
charts.routing_words_bar(words, first["predicted_team"], config.WALKTHROUGH_IDS[0]).show()
""")

md(r"""
### How to read this plot

- **Question:** which words in this one complaint pushed it toward the team the model chose?
- **Marks and axes:** one horizontal bar per word or 2-word phrase, strongest at the top.
  Bar length is that word's push toward the chosen team, and each bar prints its own value.
  The bar colour is just the team's colour, carrying no extra meaning.
- **Denominator:** none - these are contributions, not shares. Each is the complaint's
  TF-IDF value for that word multiplied by the chosen team's weight for the same word.
  They add into a score, not into 100%.
- **What to notice:** the top words are the ones a human router would circle. The 2-word
  phrase carries independent weight from its parts, which is why the model keeps bigrams.
- **Term:** a **coefficient** is the weight logistic regression learned for one word and one
  team. Positive means "this word is evidence for this team"; the bars are those
  coefficients scaled by how strongly the word appears here.
- **Why it matters:** this is the whole explainability argument from stage 3, made concrete.
  A clerk who disagrees with a route can see what drove it in one glance. The embedding
  model has no equivalent picture.
- **Boundary:** these are the model's arithmetic, not the consumer's reasoning and not a
  finding about the company. A word appearing here does not make it important to the case -
  only to this model's score.
""")

code(r"""
# ===============================================================
# 5.5 WALKTHROUGH 2 - BELOW THE THRESHOLD, SO A PERSON READS IT
# ===============================================================
second = pick(config.WALKTHROUGH_IDS[1])
display(presentation.complaint_excerpt(second, 2, "A clerk chooses the team", limit=900))
presentation.routing_decision(pipeline, second)
""")

code(r"""
# ===============================================================
# 5.6 WHY THE MODEL HESITATED
# ===============================================================
display(presentation.routing_word_bars(pipeline, second[config.TEXT_COLUMN], second["predicted_team"]))
presentation.probability_bars(pipeline, second[config.TEXT_COLUMN])
""")

md(r"""
This is the abstention path working exactly as designed. The complaint is about the
**complaint process itself** - the consumer is unhappy that a company's response cannot be
answered - rather than about a product. There is almost no product vocabulary in it, so no
team's words dominate and the top probability lands at 0.363, well under 0.55.

Look at what the model had left to go on: the routing words are the company's name. That is
a thin reason to send a complaint anywhere, and the threshold is what stops it from being
acted on. The model does not guess; a triage clerk reads it and decides.

Notice what the low confidence did **not** do: it did not close the complaint, delay it, or
mark it unimportant. The regulatory clock runs the same either way. All that changed is who
picks the team.
""")

md(r"""
## 5.2 The complaint the policy let through, and got wrong

The next one is included on purpose. It is **auto-routed and wrong** - above the threshold,
so no person saw it before it moved.
""")

code(r"""
# ===============================================================
# 5.7 WALKTHROUGH 3 - CONFIDENT AND WRONG
# ===============================================================
third = pick(config.MISROUTE_EXAMPLE_ID)
display(presentation.complaint_excerpt(third, 3, "Confident and wrong", limit=1100))
presentation.routing_decision(pipeline, third)
""")

code(r"""
# ===============================================================
# 5.8 THE WORDS THAT CAUSED THE WRONG ROUTE
# ===============================================================
display(presentation.probability_bars(pipeline, third[config.TEXT_COLUMN]))
presentation.routing_word_bars(pipeline, third[config.TEXT_COLUMN], third["predicted_team"])
""")

md(r"""
The CFPB filed this one under *checking or savings account*, so the bank-accounts team owns
it. Read the complaint and you can see why the model disagreed: the consumer writes about a
charge, a cancelled card, a fraud investigation, and a refund that never came. Every one of
those is credit-card vocabulary. The word "checking" never appears, and neither does
"debit" - the only thing that makes this a bank-accounts complaint is a fact the narrative
never states.

The model reached 0.666 confidence, cleared 0.55, and sent it to credit cards. Nobody looked
at it first.

**This is what a threshold does and does not buy you.** It removes the model's weakest
guesses. It does not remove confident mistakes, and the routing words above show why this
one never looked weak: the evidence really was card-shaped. A threshold manages errors; it
does not eliminate them. On the test split, 10.3% of auto-routed complaints are wrong - 706
of the 6,833 that moved without review - and this is one of them.

**Discussion: what monitoring would catch this?** The complaint itself is recoverable - a
credit-card specialist reads two sentences, sees "debit card", and forwards it. The
question is whether anyone ever finds out it happened. Four things would:

1. **A reassignment log.** Every time a specialist forwards a complaint out of their queue,
   record the original route, the new team, and the confidence. That log is a stream of
   labelled errors arriving for free, and the debit-versus-credit confusion would surface in
   it within a week.
2. **Rate monitoring per team pair.** Watch the reassignment rate for each origin-destination
   pair against its historical level. Bank accounts to credit cards has a known base rate
   here - 99 of 1,184 test complaints. A jump in it is a signal something changed upstream.
3. **Confidence drift.** Track the share of complaints landing under 0.55. If it moves, the
   incoming language has changed and the model's training window is ageing.
4. **Sampled review above the threshold.** Pull a small random sample of auto-routed
   complaints each week and check them by hand. Without this, the auto-routed stream is the
   one part of the workflow nobody is looking at - which is precisely where a confident
   error like this one hides.

None of these are model changes. They are workflow design, and they are what makes a 90%
policy safe to run.
""")

md(r"""
## 5.3 What leaves this notebook

Five files, and nothing else. The service that consumes them never re-trains, never
re-derives a threshold, and never sees the training data.

| File | What it carries |
|---|---|
| `model.joblib` | the fitted TF-IDF + logistic regression pipeline |
| `model_card.json` | intended use, provenance, measured results, limitations |
| `evaluation.json` | split counts, dedupe stats, both leaderboards, the sweep, frozen test results |
| `operating_policy.json` | the 0.55 rule, both routes, and the boundary statement |
| `sample_manifest.parquet` | 60 held-out complaints with predictions, routes, and routing words |
""")

code(r"""
# ===============================================================
# 5.9 ASSEMBLE THE EVIDENCE AND EXPORT
# ===============================================================
sweep = metrics.threshold_sweep(y_val, tfidf.val_predictions, tfidf.val_confidence)
test_per_team = metrics.per_team_table(y_test, test_predictions)
test_confusion = metrics.confusion_frame(y_test, test_predictions)
reload_rows = handoff.reload_slice(test)
reload_probabilities = pipeline.predict_proba(reload_rows[config.TEXT_COLUMN].tolist())
reload_check = {
    "complaints": handoff.RELOAD_CHECK_ROWS,
    "selection": "test split sorted by complaint_id, sampled with seed 42",
    "probability_sha256": handoff.probability_digest(reload_probabilities),
    "predictions": list(classes[np.argmax(reload_probabilities, axis=1)]),
}

evidence = handoff.assemble_evidence(
    splits, leaderboard, comparison, sweep, val_policy, val_per_team,
    test_scores, test_policy, test_per_team, test_confusion, reload_check,
)
manifest = handoff.build_manifest(test, test_predictions, test_confidence, pipeline)
sizes = handoff.export(pipeline, evidence, manifest)
for name, size in sizes.items():
    print(f"  {name:<26} {size}")
""")

code(r"""
# ===============================================================
# 5.10 WHAT THE MANIFEST HOLDS
# ===============================================================
print(f"{len(manifest)} complaints | "
      f"{int((manifest['route'] == config.ROUTE_TRIAGE).sum())} triage | "
      f"{int(manifest['curated'].sum())} screened for teaching | "
      f"{int(manifest['is_misroute_example'].sum())} flagged misroute example")
manifest[["complaint_id", "team", "predicted_team", "confidence", "route",
          "correct", "curated", "is_misroute_example"]].head(12).style.format(
    {"confidence": "{:.3f}"}
).hide(axis="index")
""")

md(r"""
## 5.4 Does the saved model still say the same thing?

An exported model is only useful if it behaves identically after being written to disk and
read back somewhere else. The check below reloads `model.joblib` and
`sample_manifest.parquet` from the artifacts directory, re-scores them, and requires the
probabilities to match **bit for bit** - not "close enough", the identical float64 bytes.

It repeats the check on a fixed 500-complaint slice of the test split by comparing a SHA-256
digest of the raw probability bytes against the one recorded in `evaluation.json`. If a
library version shifts and changes a result in the twelfth decimal place, this fails loudly
instead of silently shipping a different model.
""")

code(r"""
# ===============================================================
# 5.11 RELOAD IDENTITY
# ===============================================================
identity = handoff.verify(test)
identity
""")

code(r"""
# ===============================================================
# 5.12 THE EXPORTED POLICY, AS THE SERVICE WILL READ IT
# ===============================================================
policy = json.loads((config.ARTIFACT_DIR / "operating_policy.json").read_text())
print(json.dumps({k: policy[k] for k in ["rule", "confidence_threshold", "fallback", "boundary"]}, indent=2))
""")

md(r"""
### Stage 5 conclusion

One complaint at a time, the workflow reads: narrative in, eight probabilities out, one
route chosen by a fixed rule, and - when the model acts - a short list of words that caused
it. The saved artifacts reproduce every one of those numbers bit for bit in a fresh process.

### What this notebook did and did not build

**It built** a routing model measured once on untouched data: 82.1% accuracy, 89.7% of
auto-routed complaints reaching the right team, 21.7% going to a person, and a word-level
reason for every automatic decision.

**It did not build** a judgement about any complaint. The model routes; it never decides
whether a complaint is valid, what a company owes, or how a case ends. Its worst realistic
failure is a complaint arriving in the wrong queue and losing a day - which is exactly why
the reassignment log in section 5.2 matters more than the next accuracy point.
""")

md(r"""
---
# 6 - Optional: can an LLM route the same complaints?

The five-stage build is finished. **Nothing below changes its model, 0.55 rule, app,
or reported test results.** This is a separate comparison with a pretrained large
language model (LLM), using the GitHub Copilot SDK pattern from the healthcare notebook.

| Existing classifier | New experiment |
|---|---|
| TF-IDF counts words and word pairs; logistic regression learns from labeled complaints | An instruction-following LLM receives a complaint and eight team definitions |
| We trained a task-specific classifier | No task-specific training or labeled examples in the prompt |
| Local, offline prediction | Live prediction needs Copilot access; a captured run works offline |

MiniLM in Stage 3 produced **embeddings for logistic regression**. Here the LLM itself
chooses the team. The question is whether this different approach improves routing,
not whether it writes a more convincing explanation.
""")

md(r"""
## 6.1 Same inputs, same labels, a small fixed sample

Use **32 test complaints: four from each of the eight recorded teams**, chosen with
seed 42 before any LLM answers are inspected. Both models read each full narrative.
Neither gets the recorded team, company field, issue field, or the other model's answer.

We score **team predictions**, not the existing 0.55 auto-routing policy. An invalid
or failed LLM answer counts as incorrect. This balanced sample differs from the original
test distribution; do not compare its percentage directly with Stage 4's 82.07%.

First read two shorter complaints from this fixed sample. Their labels are revealed later.
They are selected for readable length, not because either model got them right.
""")

code(r"""
from complaintlab import data, llm_comparison
import pandas as pd
import textwrap

llm_sample = llm_comparison.select_sample(data.load_splits()["test"])
llm_examples = (
  llm_sample.assign(length=llm_sample["narrative"].str.len())
  .sort_values(["length", "complaint_id"]).drop_duplicates("team").head(2)
)
for complaint in llm_examples.to_dict("records"):
  print(f"COMPLAINT {complaint['complaint_id']} | narrative only")
  for paragraph in complaint["narrative"].splitlines():
    print(textwrap.fill(paragraph, width=72))
  print()
""")

md(r"""
## 6.2 Ask the LLM to choose a team

The instruction is: **choose one of the eight teams, give a short reason, and quote
the words in the complaint supporting that choice.** The exact prompt and team
definitions are in `llm_comparison.SYSTEM_PROMPT` and `llm_comparison.TEAM_DEFINITIONS`.

Each complaint gets a fresh session with no tools, memory, or access to files. Complaint
text is treated as untrusted data, not instructions. Responses must be valid JSON with
a known team and a quotation that actually appears in the narrative. These checks catch
format errors and invented quotations, not every wrong classification. A generated
reason is **not proof of how the LLM reached its answer**.

**Default: replay a real captured run without network access.** Set `LIVE_LLM = True`
only to make 32 new requests using `github-copilot-sdk==1.0.8` and authenticated Copilot
CLI access to `gpt-5.4`. This sends the public, publisher-redacted narratives to Copilot
and consumes your plan's usage. Do not substitute private customer complaints.
Live errors are counted, not silently replaced with captured successes.
""")

code(r"""
LIVE_LLM = False
llm_result = await llm_comparison.run_comparison(llm_sample, live=LIVE_LLM)
print(f"Mode: {llm_result['mode']}")
print(f"Model: {llm_result['model']} | Captured: {llm_result['generated_at']}")
""")

code(r"""
llm_rows = {row["complaint_id"]: row for row in llm_result["rows"]}
for complaint_id in llm_examples["complaint_id"]:
  answer = llm_rows[int(complaint_id)]
  print(f"COMPLAINT {complaint_id}")
  print(f"Recorded team : {answer['recorded_team']}")
  print(f"TF-IDF choice : {answer['tfidf_team']}")
  print(f"LLM choice    : {answer['llm_team'] or 'Invalid / failed'}")
  print("LLM reason:", textwrap.fill(answer["explanation"], width=72))
  print("Quoted words:", textwrap.fill(answer["evidence_quote"], width=72))
  print()
""")

md(r"""
## 6.3 Compare all 32, not just the two examples

**Usable accuracy** requires the recorded team and a valid answer. An LLM answer with
a matching team but a non-verbatim quote is rejected by this strict contract. We also
report label-only accuracy separately. **Macro-F1** combines precision
and recall for each team, then gives all eight teams equal weight. With only four
complaints per team, one mistake can move the results substantially.

The recorded team comes from the source product category, not an independent expert
review of the text. Some letters could reasonably involve several teams. Inspect
disagreements before calling every label mismatch a reasoning failure.

Time is measured per complaint. TF-IDF time covers local prediction; LLM time includes
session creation, the network request, output checks, and closing the session. Model
loading and SDK startup are excluded. Token usage is not a dollar bill; Copilot plan
rules and pricing determine the cost. Captured timings describe that run, not replay speed.
""")

code(r"""
llm_scorecard = llm_comparison.summary_table(llm_result)
llm_scorecard["Usable accuracy"] = llm_scorecard["Usable accuracy"].map("{:.1%}".format)
llm_scorecard["Macro-F1"] = llm_scorecard["Macro-F1"].map("{:.3f}".format)
llm_scorecard["Median seconds / complaint"] = (
    llm_scorecard["Median seconds / complaint"].map("{:.3f}".format)
)
display(llm_scorecard.set_index("Model").T.rename_axis("Measure"))
display(llm_comparison.per_team_table(llm_result).style.hide(axis="index"))
print(textwrap.fill(llm_comparison.label_only_summary(llm_result), width=72))
for token_field in ("input_tokens", "output_tokens"):
  reported = [row[token_field] for row in llm_result["rows"] if row.get(token_field) is not None]
  print(f"{token_field}: {sum(reported):,} reported across {len(reported)}/32 requests")
print("Dollar cost is not reported here; these token counts are not a billing estimate.")
""")

md(r"""
## 6.4 Inspect mistakes, then decide what the evidence says

The table shows up to five complaints where either model disagrees with the recorded
label, in complaint-ID order. All mistakes still count in the scorecard above.
Rejected quotations may differ only in spacing; rejection does not necessarily mean
invented content. Raw responses and rejection reasons remain in the capture.
""")

code(r"""
llm_mistakes = pd.DataFrame(llm_result["rows"])
llm_mistakes = llm_mistakes.loc[
  (llm_mistakes["tfidf_team"] != llm_mistakes["recorded_team"])
  | (llm_mistakes["llm_team"] != llm_mistakes["recorded_team"])
]
display(llm_mistakes[["complaint_id", "recorded_team", "tfidf_team", "llm_team", "status"]]
    .head(5).fillna("Invalid / failed"))
print(textwrap.fill(llm_comparison.conclusion(llm_result), width=72))
""")

md(r"""
### What this changes, and what it does not

An LLM can attempt classification **without us building a vocabulary or training a
separate classifier**. That is a real change in the development process. It does not
mean the model was never trained: it brings substantial prior pretraining.

**Replacement is an evidence-based decision, not the starting conclusion.** This small
sample does not establish statistical superiority, and public complaints may have
appeared in a pretrained model's data. A stronger evaluation would use a larger,
independently reviewed, newly collected set, a frozen prompt, and repeated checks of
quality, latency, failures, and cost. Rerunning the LLM may produce different answers.

**Run history:** the first capture produced 22/32 usable correct answers and four
rejections. After adding raw-response logging, a second run of the same prompt and
sample produced 25/32 and two rejections. The notebook replays the second run, not a
best-of selection. The first capture is retained as `data/llm_comparison_first_run.json`.
Neither run alone establishes superiority; the variation is part of the finding.

For this lesson, the original classifier remains the deployed system. The LLM section
is a separate experiment. A specialist still owns the complaint and the final response.
""")

notebook["cells"] = cells
notebook["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}

if __name__ == "__main__":
    previous = nbf.read(OUTPUT, as_version=4).cells if OUTPUT.exists() else []
    previous_cells = {(cell.cell_type, cell.source): cell for cell in previous}
    for index, cell in enumerate(notebook.cells):
        saved = previous_cells.get((cell.cell_type, cell.source))
        if saved is not None:
            notebook.cells[index] = saved
        else:
            digest = sha256(f"{cell.cell_type}:{cell.source}".encode()).hexdigest()[:12]
            cell.id = f"complaint-build-{digest}"
            cell.metadata["id"] = cell.id
    identifiers = [cell.id for cell in notebook.cells]
    assert len(identifiers) == len(set(identifiers)), "duplicate cell id"
    assert all(cell.metadata.get("id") == cell.id for cell in notebook.cells), "mismatched cell id"
    assert all(cell.metadata.get("language") for cell in notebook.cells), "missing language"
    nbf.validate(notebook)
    nbf.write(notebook, OUTPUT)
    code_count = sum(cell.cell_type == "code" for cell in notebook.cells)
    print(f"Wrote {OUTPUT.name}: {len(notebook.cells)} cells ({code_count} code)")
