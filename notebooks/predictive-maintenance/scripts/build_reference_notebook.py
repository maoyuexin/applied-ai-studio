"""Build 01_pdm_build.ipynb in the five Module 5 teaching stages.

This file is the canonical source of the notebook. Never hand-edit the
generated JSON: change the text here and regenerate, so the notebook, the
``pdmlab`` package, and the exported artifacts can never drift apart.

    node scripts/venv-python.mjs notebooks/predictive-maintenance/scripts/build_notebook.py

Monetary amounts in markdown are written inside backticks (`$25,200`). A bare
pair of dollar signs in one paragraph is read as inline math by both
JupyterLab and nbconvert, which silently swallows the text between them.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_DIR / "backup" / "02_pdm_reference.ipynb"

notebook = nbf.v4.new_notebook()
cells: list = []


def cell_metadata(language: str) -> tuple[str, dict[str, str]]:
    cell_id = f"pdm-build-{len(cells) + 1:03d}"
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
# From a compressor's sensor stream to a maintenance work order

**ITAI 2372 - Module 5 - AI in Manufacturing and Industrial Operations**

Modules 2, 3 and 4 built a fraud model, an image model and a credit model in the same five
stages. Tonight we use those stages on **industrial sensor data**, and add the two things
the factory floor brings that none of the earlier cases did: **time**, and **a machine that
changes while you are watching it**.

| | Stage | What happens |
|---|---|---|
| **1** | **Data Ingestion and Provenance** | Verify the source, the license, the sampling rate, and the holes in the record |
| **2** | **EDA and Feature Preparation** | Read the sensors in plain language, state the leak physics, build 6 features |
| **3** | **Detection** | Why there is no supervised model here, and why the simplest detector won |
| **4** | **Operating Policy, Alert Fatigue and Drift** | Price every threshold, then watch the world move under a fixed rule |
| **5** | **Prediction, Work Order and Handoff** | Walk packaged windows end to end, then say plainly what this cannot do |

### The case

A metro operator runs compressors on its passenger trains. When one develops an air leak it
runs almost continuously, wastes energy, wears out early, and can eventually take the train
out of service. A maintenance planner has a handful of technician-hours a week. The narrow
question is:

> **Which hours of this compressor's sensor stream deserve a technician's attention today?**

### The authority boundary, stated once and enforced throughout

```text
sensor hour  ->  score  ->  policy decision  ->  work order  ->  technician inspects
```

**The model never stops the compressor, never locks out equipment, and never certifies that
a machine is safe for a person to work on.** It produces a number per hour. A written policy
turns that number into "raise a work order", "watch", or "no action". A technician decides
what is actually wrong and what to do about it.

Three words that are not synonyms, and that this notebook keeps apart on purpose:

| Word | What it is here |
|---|---|
| **Score** | How far this hour sits from the machine's own quiet-months normal |
| **Decision** | What the written policy does with that score: work order, watch, or nothing |
| **Outcome** | What the maintenance report says actually happened, recorded after the fact |

### The claim we are allowed to make, and the one we are not

This system **detects a developing air leak within roughly an hour of its documented onset.**
It **does not forecast**. Stage 5 shows the measurement behind that sentence: three of the
four documented failures give **zero** advance warning, and we will look at the flat line
that proves it rather than talking around it.

### The data

- **MetroPT-3**: one Air Production Unit on a real Metro do Porto passenger train
- **1,516,948 raw sensor readings**, 2020-02-01 to 2020-09-01, CC BY 4.0
- One committed row is **one minute** of averaged sensor readings; one modeled row is **one clock hour**
- **Four documented air-leak failures**, taken from the operator's own maintenance reports

Nothing downloads while this notebook runs. Every dollar figure in Stage 4 is a **synthetic
classroom assumption**, labeled as such wherever it appears.
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

from pdmlab import charts, config, data, detect, features, handoff, metrics, policy

warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 140)
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

**Question:** Do we know exactly where this sensor stream came from, what one row means, how
often it was actually sampled, and where it is missing?

**What you should expect to see:** a table of verified facts - source, license, checksum,
row count - then six real minutes of raw sensor readings, then the four documented failures,
then an honest accounting of the holes.

**Why this stage exists in a real workflow:** a maintenance team cannot act on an alert from
a model whose input it cannot trace. In industrial monitoring the provenance question that
bites hardest is not "where did the file come from" but **"how often was this actually
measured, and when was the recorder off?"** Both answers change what the model is allowed
to claim.

**Output passed to Stage 2:** one validated 1-minute sensor grid, with recorder gaps visible
as missing values rather than quietly closed.
""")

md(r"""
## 1.1 The source file, and a correction we are obliged to make

The original is a single CSV published by the UCI Machine Learning Repository: **MetroPT-3
(Air Compressor)**, dataset id 791, 218 MB, released under **CC BY 4.0**. It records the Air
Production Unit - the compressor that makes the compressed air a train needs for its brakes
and doors - on **one real Metro do Porto passenger train**, from 2020-02-01 to 2020-09-01.

Two things were done to it before it reached this folder, and nothing else:

1. **The checksum was verified.** A **SHA-256** is a file fingerprint: change one byte
   anywhere and the fingerprint changes completely. Recording it means anyone can prove they
   have the same file we used, not a lookalike.
2. **It was averaged to one row per minute** and stored as Parquet, so a 4.9 MB file sits
   beside this notebook and a classroom with no network still works. `scripts/build_dataset.py`
   documents that conversion and can redo it from a raw CSV you already have.

**The correction.** The UCI page states the readings were "collected at 1Hz". **They were
not.** Measured on the raw timestamps: the spacing between consecutive readings is irregular
with a **median of 10 seconds**, and 1,337,521 of the 1,516,947 intervals are exactly 10
seconds. At a true 1 Hz the seven-month span would hold roughly 18 million rows, not 1.5
million. This matters beyond pedantry - if you believed 1 Hz you would size buffers, set
alert latencies and design features for a stream that does not exist. **We do not repeat the
1 Hz claim anywhere in this lab.**

**Term - provenance:** the traceable record of where data came from and what was done to it
between there and here. Not a formality: it is the only thing that lets a second person
reproduce a number you are asking them to act on.
""")

code(r"""
# ===============================================================
# 1.1 LOAD THE COMMITTED FILE AND VERIFY WHAT IT IS
# ===============================================================
minutes = data.load_minutes()
print(data.provenance_summary(minutes).to_string(index=False))
""")

md(r"""
## 1.2 What one row actually means

The committed file stores **one row per minute**, and each value in that row is the **mean of
the roughly six raw readings taken during that minute**. Ten sensors survive the conversion;
five that the model never reads were dropped.

Below are six consecutive minutes from a quiet February morning. Read the `Motor_current`
column down the page: `3.73`, `2.49`, `0.04`, `0.04`, `0.04`, `0.04`. That is the compressor
finishing a working burst and switching off. The whole of Stage 2 is built on being able to
read that column.
""")

code(r"""
# ===============================================================
# 1.2 SIX REAL MINUTES, AND WHAT EACH SENSOR MEASURES
# ===============================================================
print(data.one_hour_of_minutes(minutes, "2020-02-15 08:00", hours=1).head(6).round(3).to_string())
print()
print(data.sensor_dictionary().to_string(index=False))
""")

md(r"""
## 1.3 The ground truth: four documented failures

There is no label column in this dataset. The ground truth is **four air-leak failures
written down by the operator's maintenance staff**, published alongside the sensor data.

That is the entire labeled evidence base for this lab: **four events**. Hold that number.
Everything Stage 3 and Stage 4 measure is anecdotal evidence about one machine, and no
confidence interval is possible from four events. We will say so again where it matters.
""")

code(r"""
# ===============================================================
# 1.3 THE FOUR DOCUMENTED FAILURES
# ===============================================================
print(data.failure_table().to_string(index=False))
""")

md(r"""
## 1.4 The holes, counted before anything else

A sensor archive is not a spreadsheet: the recorder stops. The committed file keeps only the
minutes that carry a reading, and `load_minutes()` puts them back onto a **regular 1-minute
grid**, so a gap appears as rows of missing values instead of silently closing up.

That distinction is the whole point. If the gaps closed themselves, a two-day outage would
look like two days of a machine behaving normally.

**Term - coverage:** the share of a clock hour's 60 minutes that carries a reading.
Denominator: 60. An hour under **50%** coverage is **not scored at all** - it is reported as
"no data" and routed to a person, never treated as normal.
""")

code(r"""
# ===============================================================
# 1.4 HOW MUCH OF THE RECORD IS SIMPLY NOT THERE
# ===============================================================
gaps = data.gap_facts(minutes)
print(data.coverage_summary(minutes).to_string(index=False))
print(f"\nRecorder gaps: {gaps['gap_count']} separate stretches, "
      f"{gaps['missing_hours']:,.0f} hours in total, longest {gaps['longest_gap_hours']:.1f} h.")
print()
print(data.largest_gaps(minutes).to_string(index=False))

charts.coverage_timeline(
    data.daily_coverage_frame(minutes), gaps["gap_count"], gaps["missing_hours"]
).show()
""")

md(r"""
### How to read this plot

- **Question:** Is the sensor record continuous, or does it have holes big enough to change
  what we are allowed to conclude?
- **Marks and axes:** one bar per calendar day. Bar height is the share of that day's 1,440
  minutes that carry a reading. Blue days are at least half covered; orange days fall below
  half. The dashed line marks half a day. The four red bands are the documented failures,
  labeled F1 to F4.
- **Denominator:** each bar divides by **1,440 minutes**, the full length of that day - not
  by the minutes that happen to exist.
- **What to notice:** the record is mostly complete and then abruptly is not. **331 separate
  recorder gaps** remove **904 hours** of readings - **17.7%** of the 306,960-minute grid.
  **700 clock hours carry no reading at all**, and another **200** are under half covered and
  get dropped. **4,216 of 5,116 clock hours (82.4%)** survive to be scored. Look at late
  April: a **48-hour** hole, one week after F1.
- **Term - missingness:** data absent from a record, and the pattern of that absence. Missing
  *at random* is survivable. Missing *where the interesting thing happens* is not, and the
  next cell shows which kind this is.
- **Why it matters:** every hour without data is an hour the detector cannot alert on. A
  system that goes quiet during an outage and a system that goes quiet because the machine is
  healthy look identical from the outside. That is why coverage is checked before scoring,
  not after.
- **Boundary:** a bar at 100% means the recorder was running, **not** that the readings are
  correct. Coverage measures presence, never quality.
""")

md(r"""
## 1.5 Where the holes fall, which is worse than how many there are

Now the question that decides what Stage 5 may claim: **how much data exists in the 24 hours
before each documented failure began?** That is the window in which advance warning would
have to appear.
""")

code(r"""
# ===============================================================
# 1.5 COVERAGE IN THE 24 HOURS BEFORE EACH ONSET
# ===============================================================
print(data.pre_onset_coverage(minutes).to_string(index=False))
""")

md(r"""
**Read that table carefully.** F4 - the single failure that turns out to give real advance
warning - has **18 of its 24 pre-onset hours** present, the thinnest coverage of the four. Its
six missing hours are **consecutive**: they are the tail of a **14.2-hour recorder gap** that
ran from 07:17 to 21:27 on July 14.

F3 is the mirror image: **24 of 24 hours present**, complete coverage. In Stage 5 we will see
that F3's pre-onset score is perfectly flat. That combination is the strongest evidence we
have that the missing warning is **real physics and not a data artifact** - the one failure
where we could have seen a warning coming is the one where there was nothing to see.

This caveat rides along with every lead-time number in this notebook.
""")

md(r"""
## 1.6 Three windows, in time order, frozen before anything is measured

Sensor data cannot be split at random. Shuffling hours would let the model learn from June to
score April, which is a form of looking at the answer. The split is **by time**, and it is
fixed here, before any threshold is chosen.
""")

code(r"""
# ===============================================================
# 1.6 THE TIME-ORDERED SPLITS
# ===============================================================
print(data.split_windows().to_string(index=False))
""")

md(r"""
**Stage 1 conclusion.** The file is traceable, its sampling rate is **10 seconds and not the
1 Hz the source claims**, one row is one minute of averaged readings, the ground truth is
**four maintenance reports**, and **904 hours of readings are missing in 331 gaps that land
in exactly the windows we would most want to inspect**. Those four facts constrain every
claim in the rest of this notebook.
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 2 - EDA and Feature Preparation

**Question:** What does this compressor actually do minute to minute, what does an air leak
do to it, and which six numbers per hour capture that in language a maintenance planner
already uses?

**What you should expect to see:** the motor-current meter read in plain language, a healthy
week beside a leaking one, six features each introduced by the question a planner asks, and
then **a bug** - a feature that is undefined exactly when the machine is broken.

**Why this stage exists in a real workflow:** raw sensor channels are not features. A model
fed 10 raw columns at 1-minute resolution learns the duty cycle, not the fault. The
engineering work is turning "pressure, current, temperature" into "how hard did it work, how
often did it start, how long did it rest" - quantities a technician can argue with.

**Output passed to Stage 3:** 4,216 scorable hours x 6 features, with no missing values and
no silently deleted rows.
""")

md(r"""
## 2.1 Reading the motor-current meter

Everything downstream rests on one column. `Motor_current` is the current the compressor
motor draws, in **amperes**. It has three regimes, and you can see all three in the data:

| Reading | What the machine is doing |
|---|---|
| about **0 A** | Off. Not spinning. |
| about **4 A** | Spinning, but not compressing - idling, or spinning down |
| about **6-7 A** | **Working hard**: actually compressing air |

Two cut points follow from that: **1.0 A** separates off from running at all, and **4.75 A**
separates idling from compressing. Both are read off the histogram below rather than guessed.
""")

code(r"""
# ===============================================================
# 2.1 THE THREE REGIMES OF THE COMPRESSOR MOTOR
# ===============================================================
charts.motor_current_regimes(data.motor_current_histogram(minutes)).show()
""")

md(r"""
### How to read this plot

- **Question:** Does the motor current actually separate "off", "idling" and "working hard",
  or are we imposing categories the machine does not have?
- **Marks and axes:** one bar per 0.1-ampere bin of 1-minute mean motor current. Bar height
  is the number of minutes in the seven-month record that landed in that bin, on a **log
  scale** - without the log, the enormous "off" peak would flatten everything else to
  invisibility. Blue is below 1.0 A, orange between 1.0 and 4.75 A, red above 4.75 A. The two
  dashed lines are the cut points.
- **Denominator:** none - these are raw counts of minutes, out of 252,720 minutes that carry
  a reading.
- **What to notice:** three distinct humps, not a smooth spread. A very tall spike at ~0 A, a
  clear bump around 4 A, and a broad population from 6 to 7 A. The valleys between them are
  where the cut points sit, which is why 1.0 and 4.75 are defensible rather than arbitrary.
- **Term - operating regime:** a distinct mode a machine spends time in, visible as a separate
  peak in a sensor's distribution. Finding the regimes first is what lets a feature say
  "working hard" instead of "current was 6.2".
- **Why it matters:** every feature in this stage is defined against these two cut points. If
  4.75 were wrong, "share of the hour working hard" would count idling as work and the
  detector would fire on a machine that is merely warm.
- **Boundary:** a log scale makes rare values look far more common than they are. The 4 A
  bump is genuinely small - it is thousands of minutes against hundreds of thousands at 0 A.
  Do not read equal bar heights as equal amounts of time.
""")

md(r"""
## 2.2 The physics of an air leak, stated once

This is the sentence the entire feature set comes from:

> **If air escapes, the compressor has to work more often and for longer to hold the same
> pressure in the panel.**

Everything follows from that. A leaking machine **rests less**, **starts more often at
first and then simply never stops**, **runs hotter** because it is compressing continuously,
and its panel pressure **swings less** - it stays pinned near the top instead of rising and
falling - while **bleeding away faster** during whatever rest it does get.

None of that is a spike. It is the absence of the machine's normal rhythm. The chart below
puts a healthy February week above the longest documented leak, F3.
""")

code(r"""
# ===============================================================
# 2.2 WHAT A LEAK LOOKS LIKE: A HEALTHY WEEK AGAINST F3
# ===============================================================
hourly = features.hourly_features(minutes)
healthy_week = hourly.loc["2020-02-15":"2020-02-21", "load_share"]
f3_window = hourly.loc["2020-06-05 10:00":"2020-06-07 14:30", "load_share"]
charts.leak_signature(healthy_week, f3_window).show()
""")

md(r"""
### How to read this plot

- **Question:** Does an air leak look like a sudden spike, or like something else entirely?
- **Marks and axes:** two stacked panels sharing a vertical axis. The vertical axis is the
  **share of each clock hour the compressor spent above 4.75 A** - actually compressing. The
  horizontal axis is hours from the start of each window. Blue above is a healthy week in
  February; red below is the F3 leak, 2020-06-05 10:00 to 2020-06-07 14:30.
- **Denominator:** each point divides by the **minutes with data in that hour**, so a value of
  0.50 means the compressor was compressing for half of the readings taken that hour.
- **What to notice:** the healthy week oscillates near the floor, spending most of every hour
  at rest and rising briefly. The leak sits **pinned near 100%** for two and a half days. The
  difference is not amplitude, it is **the disappearance of the rhythm**.
- **Term - duty cycle:** the fraction of time a machine spends actively working. A healthy
  compressor here runs a low duty cycle with regular rests; a leaking one runs near 100%.
- **Why it matters:** this is why the six features below are all about *rhythm* - rests,
  starts, swing - rather than about any single sensor being high. A threshold on raw pressure
  would miss this entirely.
- **Boundary:** these are two hand-picked windows chosen to show the contrast, not a random
  sample. They prove the signature exists; they say nothing about how often a healthy week
  might also look busy. Stage 4 is where that question gets answered, and the answer is
  uncomfortable.
""")

md(r"""
## 2.3 Six features, each answering a question a planner already asks

We aggregate the minute grid into **one row per clock hour**, keeping only hours with at
least 50% coverage. Six of those hourly columns go to the model. Each one exists because a
maintenance planner would ask it out loud:

| Feature | The planner's question | Which direction means trouble |
|---|---|---|
| Share of the hour the compressor is working hard | How much of the hour was it actually compressing? | **higher** |
| Compressor starts per hour | How often did it have to start up again? | **higher** |
| Minutes of rest between working bursts | How long did it get to rest between bursts? | **lower** |
| Average oil temperature (C) | Did it run hotter than usual? | **higher** |
| Swing in panel air pressure (bar) | Did panel pressure rise and fall normally, or sit pinned? | **lower** |
| How fast pressure falls while resting (bar/min) | How fast did pressure bleed away while it rested? | **higher** |

**Term - feature engineering:** turning raw measurements into quantities that carry meaning
for the decision at hand. The input here is 60 rows of 10 sensor channels; the local operation
is an aggregation over one clock hour (a share, a count, a mean, a standard deviation, a
slope); what is *configured* is the two current cut points and the hour grain; what is
*learned* is nothing at all - features are arithmetic, and no data is fitted here. The output
is one row of six numbers per hour. What it does **not** prove: that these six are sufficient.
Stage 5 shows a case where they are not.
""")

code(r"""
# ===============================================================
# 2.3 BUILD THE HOURLY FEATURE MATRIX
# ===============================================================
matrix = features.model_matrix(hourly)
print(f"{len(minutes):,} minutes  ->  {len(hourly):,} scorable hours  ->  "
      f"{matrix.shape[1]} model features")
print(f"Hours dropped for coverage below {config.MIN_HOUR_COVERAGE:.0%}: "
      f"{5116 - len(hourly):,} of 5,116 clock hours")
print()
print(matrix.loc["2020-02-15 08:00":"2020-02-15 12:00"].round(3).to_string())
""")

md(r"""
## 2.4 The bug: a feature that is undefined exactly when the machine is broken

This is the most important five minutes in Stage 2, and it is a bug we actually shipped
before catching it.

Two of the six features are about **rest**: minutes of rest between working bursts, and how
fast pressure falls **while resting**. The natural way to compute both is to take the resting
samples and average them.

Now read that back against the physics. **A badly leaking compressor never rests.** So in the
worst failure hours there are no resting samples, and both features come out as **NaN** -
"not a number", the marker for a value that does not exist.

The next line most people write is `dropna()`. It removes rows with missing values, it looks
like hygiene, and it prints nothing. Here is what it removes.
""")

code(r"""
# ===============================================================
# 2.4 WHAT A NAIVE dropna() SILENTLY DELETES
# ===============================================================
naive = features.naive_model_matrix(hourly)
fixed = features.model_matrix(hourly)
print(f"Rows with at least one NaN - naive definition : {int(naive.isna().any(axis=1).sum()):>5,} "
      f"of {len(naive):,}")
print(f"Rows with at least one NaN - fixed definition : {int(fixed.isna().any(axis=1).sum()):>5,} "
      f"of {len(fixed):,}")
print()
print(features.dropna_damage(hourly).to_string(index=False))
""")

md(r"""
**Read the "Hours silently deleted" column.** F3 - the year's longest documented failure, 52.5
hours of continuous running - loses **all 47** of its scorable hours. F1 loses **23 of 24**.
The two worst failures are erased from the dataset by one line of cleanup.

A detector trained and evaluated on what survives scores **0 of 4 failures detected**, and
every symptom points at the model: bad features, wrong algorithm, not enough signal. The
model was never the problem. **The rows were gone before the model saw them.**

**The fix is a definition, not an imputation.** We do not fill the missing values in; we
define the features so that "no rest" is a *number* rather than an absence:

- **rest minutes per cycle** = the part of the hour *not* spent compressing, divided by the
  number of starts (at least one). A fully loaded hour now scores **0 minutes of rest** -
  which is true - instead of "unknown".
- **pressure fall rate** = **0 bar/min** when there was no resting stretch to measure,
  because no rest means no observed decay.

After the fix, **0 of 4,216 rows** carry a missing value, and NaN can only ever mean "no
sensor data", which Stage 1 already handles by refusing to score the hour.

**The transferable lesson:** when a value is missing, ask *why* before you drop it. Missing
because nobody measured it and missing because the quantity does not exist in that state are
different problems, and only one of them is safe to delete. Here the absence **was** the
signal.
""")

md(r"""
## 2.5 How separable are failures - and how separable are the hours before them?

Two questions, deliberately measured side by side, because the answers are opposite.

**Term - Cohen's d:** the gap between two group means expressed in pooled standard
deviations. `d = 1` means the groups sit one standard deviation apart; `d` above 2 is a very
large separation. **Term - AUC:** the probability that a randomly chosen failure hour scores
higher than a randomly chosen baseline hour. `0.5` is a coin flip; `1.0` is perfect ordering.

Denominator for both: baseline = the **1,398** hours from 2020-02-01 to 2020-04-10 that carry
data; "during" = the **83** hours inside a documented failure window; "24 h before" = the
**82** hours in the day preceding an onset.
""")

code(r"""
# ===============================================================
# 2.5 EFFECT SIZES: DURING A FAILURE, AND THE DAY BEFORE IT
# ===============================================================
effects = features.effect_sizes(hourly, matrix)
print(effects[["display", "baseline_mean", "during_mean",
               "cohens_d_during", "auc_during", "cohens_d_24h_before"]].round(3).to_string(index=False))
charts.effect_size_chart(effects).show()
""")

md(r"""
### How to read this plot

- **Question:** Do the features that separate a failure while it is happening also separate
  the hours *before* it happens?
- **Marks and axes:** one row per feature, two bars each. The red bar is **|Cohen's d| during
  a documented failure**; the grey bar is **|Cohen's d| in the 24 hours before onset**. Longer
  is more separated. The number is printed on each bar, so the comparison does not rely on
  color or on bar length alone.
- **Denominator:** both bars compare against the **same 1,398 baseline hours**. The red bar's
  other group is 83 failure hours; the grey bar's is 82 pre-onset hours.
- **What to notice:** the red bars are enormous - **5.77** for working-hard share, **3.88**
  for oil temperature, and every feature above 2.0. The grey bars are **near zero**: the
  largest is **0.62**, and two are negative. Working-hard share separates failures at AUC
  **0.983** and the day before at `d = 0.30`.
- **Term - effect size:** how far apart two groups are, independent of how many observations
  you have. A large sample can make a meaningless difference "statistically significant";
  effect size asks whether the difference is big enough to act on.
- **Why it matters:** this single chart is the claim boundary, drawn in advance. **The
  features scream during a failure and are silent the day before.** That is a detector, not a
  forecaster, and Stage 5 will show the hour-by-hour trace that makes it concrete.
- **Boundary:** these effect sizes come from **four events, 83 hours**. They describe this
  compressor over these seven months. They are not an estimate of how well this would work on
  another machine, and no confidence interval is quoted because four events cannot support
  one.
""")

md(r"""
**Stage 2 conclusion.** Six features, each traceable to a question a planner asks and to the
same one-sentence leak physics. One bug found and fixed by **defining** the missing case
rather than deleting it - a fix that recovered **77 failure hours** the naive version threw
away. And a measurement that fences the claim before any model is fitted: **enormous
separation during a failure, essentially none the day before.**
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 3
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 3 - Detection

**Question:** With four labeled events and seven months of unlabeled hours, what kind of model
is even possible here - and does a more sophisticated one beat the simplest thing that works?

**What you should expect to see:** an argument for why supervised learning is off the table, a
detector whose entire fitted state is **twelve numbers**, and a fair head-to-head against
three fancier models on an identical alerting budget.

**Why this stage exists in a real workflow:** industrial monitoring almost never has enough
labeled failures to train a classifier. The question shifts from "what does a failure look
like" - unanswerable from four examples - to **"what does normal look like, and how far from
it is this hour"**. That reframing is the whole of anomaly detection.

**Output passed to Stage 4:** one score per scorable hour, and the six per-feature
contributions that explain each score.
""")

md(r"""
## 3.1 Why there is no supervised model here

Module 4 trained a classifier on 24,000 labeled accounts. Here we have **four labeled
failures**. You cannot fit a decision boundary to four points and expect it to mean anything -
and you certainly cannot hold some of them out to test it.

So we change the question:

| Supervised framing (impossible here) | Anomaly-detection framing (what we do) |
|---|---|
| Learn what a failure looks like from labeled failures | Learn what **normal** looks like from unlabeled quiet months |
| Needs hundreds of positive examples | Needs **zero** failure examples to fit |
| Outputs "probability this is a failure" | Outputs "how far this hour sits from normal" |
| Labels used for training | Labels used **only** to check the result afterwards |

**Term - anomaly detection:** fitting a description of ordinary behavior, then scoring new
observations by their distance from it. The four documented failures are never used to fit
anything in this notebook. They are held back entirely, as the only honest check we have.

The baseline is fitted on **February and March only** - 1,227 hours in which no failure is
documented - and nothing after March 31 is ever seen by the fit.
""")

md(r"""
## 3.2 The detector: twelve numbers

**One-sided robust z-score, averaged over six features.** In full:

1. For each feature, take the **median** of the 1,227 training hours as "normal".
2. Take the **MAD** - median absolute deviation - times **1.4826**, as "how much normal
   varies". **Term - MAD:** the median of the absolute distances from the median. The 1.4826
   makes it comparable to a standard deviation for normally distributed data. Unlike a
   standard deviation, a handful of extreme hours barely move it.
3. For a new hour, compute `(value - median) / scale` per feature.
4. **Flip the sign** so the direction that means trouble is always positive, then **clip at
   zero**, so a feature that is *better* than normal contributes nothing rather than
   cancelling out a feature that is worse.
5. **Average the six.**

A score of **6** means the average feature sits six robust standard deviations into the
trouble direction. The entire fitted model is **six medians and six scales** - twelve numbers
you can read with your eyes, print on a page, and hand to a technician who wants to know what
the machine is being compared against.
""")

code(r"""
# ===============================================================
# 3.2 FIT ON FEBRUARY-MARCH ONLY, AND PRINT THE WHOLE MODEL
# ===============================================================
detector = detect.fit_detector(matrix)
score = detector.score(matrix)
contributions = detector.score_frame(matrix)

training = detect.training_slice(matrix)
print(f"Fitted on {len(training):,} training hours "
      f"({config.TRAIN_START.date()} to {(config.TRAIN_END - pd.Timedelta(days=1)).date()}), "
      f"{int(features.failure_mask(training.index).sum())} of them inside a documented failure.\n")
print(pd.DataFrame({
    "planner question": [config.FEATURE_QUESTION[f] for f in config.MODEL_FEATURES],
    "trouble is": ["higher" if config.FEATURE_DIRECTION[f] > 0 else "lower"
                   for f in config.MODEL_FEATURES],
    "training median": detector.median_.round(4),
    "training scale (MAD x 1.4826)": detector.scale_.round(4),
}).to_string())
print(f"\nScored {len(score):,} hours. The fitted model is {2 * len(config.MODEL_FEATURES)} numbers.")
""")

md(r"""
## 3.3 Does anything fancier beat it?

Four model families, **the same six features**, **the same training months**, and - this is
the part that makes the comparison fair - **the same alerting budget**.

Different models emit numbers on completely different scales, so a shared numeric threshold
would be meaningless. Instead each model's cut is placed at the **98th percentile of its own
scores**, so every model alerts on the **top 2% of hours** and the comparison is purely about
*which* hours each one picks.

**Term - technician callout:** the unit of work, and the thing we count. Alert hours within
**6 hours** of each other are **one trip** to the machine, because that is what actually
happens. Counting alert hours instead would inflate a single 52-hour event into fifty
"alerts". **Term - false callout:** a callout on a **clean** hour - one outside
`[onset - 72 h, end + 24 h]` for every documented failure. Hours inside that band are neither
credited nor penalized, because we genuinely do not know whether the machine was already
degrading before someone wrote the report.
""")

code(r"""
# ===============================================================
# 3.3 FOUR MODEL FAMILIES AT AN IDENTICAL ALERT BUDGET
# ===============================================================
comparison = metrics.compare_models(detect.candidate_scores(matrix))
print(comparison.to_string(index=False))
charts.model_comparison(comparison).show()
""")

md(r"""
### How to read this plot

- **Question:** When every model is allowed to alert on exactly the same number of hours, how
  much technician time does each one waste for the failures it catches?
- **Marks and axes:** one bar per model. Bar height is **false technician callouts per
  month**. Green bars caught all four documented failures; orange bars did not. The label
  above each bar states how many of four it caught, so the detection result never depends on
  color.
- **Denominator:** false callouts are counted on **clean hours only** over the 5.0-month
  scored period (2020-04-01 to 2020-09-02), then divided by that period in months.
- **What to notice:** **the simplest model wins outright.** Robust z, mean of six, catches
  **4 of 4** at **0.60** false callouts per month. IsolationForest also catches 4 of 4 but
  needs **2.39** - roughly **four times the wasted trips for the same detection**. PCA
  reconstruction error catches only **2 of 4** while generating **4.38**. Robust Mahalanobis
  matches the winner's 0.60 but catches only **3 of 4**. Taking the **worst** of the six
  features instead of the mean more than doubles false callouts, from 3 to 7.
- **Term - IsolationForest:** an ensemble that scores a point by how few random splits are
  needed to isolate it. It is a strong general-purpose anomaly detector, and here it is beaten
  by an average of six z-scores.
- **Why it matters:** four times the false callouts is not a rounding error to a team with a
  handful of technician-hours a week. And the winner has a second advantage the chart cannot
  show: when it alerts, you can point at **which of the six features** drove the number.
  IsolationForest cannot tell a technician why.
- **Boundary:** "wins" means **on this machine, these seven months, these four events**. This
  is not evidence that robust z beats IsolationForest in general. It is evidence that
  reaching for the complicated model first was not justified here.
""")

md(r"""
## 3.4 The other choice that mattered: MAD, not standard deviation

Same features, same direction rules, same training months - only the definition of "how far"
changes. Centering on the **mean** and scaling by the **standard deviation** is the textbook
z-score. Here it fails, and the failure has a specific shape.

The compressor **idles most nights**. That normal on/off swing is enormous, so the standard
deviation it produces is enormous, so every real fault gets divided down into invisibility.
The MAD, being a median of distances, barely notices the idle hours.
""")

code(r"""
# ===============================================================
# 3.4 MAD SCALING AGAINST SD SCALING - FAILURES CAUGHT AT EACH THRESHOLD
# ===============================================================
print(metrics.scaling_comparison(detect.scaling_variants(matrix)).to_string(index=False))
""")

md(r"""
**Read the rows across.** MAD scaling catches **4 of 4 at every threshold from 2 to 10** - a
wide band in which the operating threshold can sit. Standard-deviation scaling catches 4 of 4
at threshold 2, then **falls off a cliff**: 1 of 4 at threshold 3, and **0 of 4 from
threshold 5 onward**. Centering on the median instead of the mean does not rescue it.

**Term - operating band:** the range of thresholds over which a detector still does its job.
A wide band means the exact threshold is a business decision about workload. A narrow band
means the threshold is load-bearing, and any drift in the data will knock the system out of
it. MAD gives us a band. SD gives us a knife edge.
""")

md(r"""
## 3.5 Seven months of scores, all at once

Before we price anything, look at the whole record. This is every scorable hour, the two
policy lines Stage 4 will justify, the training months, and the four documented failures.
""")

code(r"""
# ===============================================================
# 3.5 THE FULL SCORE TIME SERIES
# ===============================================================
charts.score_timeline(score).show()
print(f"Scored hours: {len(score):,}   median score: {score.median():.2f}   "
      f"max: {score.max():.2f} at {score.idxmax()}")
""")

md(r"""
### How to read this plot

- **Question:** Where do the documented failures sit in the score distribution, and is
  anything else up there with them?
- **Marks and axes:** one point per scored clock hour, joined into a line. The vertical axis
  is the detector score - robust standard deviations from the February-March normal. The red
  dashed line at **6.0** is where a work order gets raised; the orange dotted line at **3.0**
  is the watch band. The grey band on the left is the **training months**; the four red bands
  labeled F1-F4 are the documented failures.
- **Denominator:** none - this is a score per hour, not a rate. 4,216 hours are plotted; the
  gaps in the line are the hours Stage 1 refused to score.
- **What to notice:** three things. First, the failure bands **do** contain tall spikes -
  the detector is not blind. Second, **the spikes are not confined to the failure bands**:
  there are peaks of comparable height in mid-May, and inside the grey training months. Third,
  the baseline **creeps upward** from June onward - the whole line sits higher in summer than
  in February, and no failure is documented there.
- **Term - drift:** a change in the data's ordinary behavior over time, unrelated to the thing
  being detected. That upward creep is drift, and Stage 4 is about what it costs.
- **Why it matters:** the tall spikes outside the red bands are the entire alert-fatigue
  problem, visible before a single dollar is assigned. Every one of them would have been a
  technician driving to a healthy machine.
- **Boundary:** a spike inside a red band does **not** mean the detector predicted that
  failure. Most of these spikes sit *during* the documented window, not before it. Height on
  this chart says nothing about timing, and timing is what Stage 5 measures.
""")

md(r"""
**Stage 3 conclusion.** Four labeled events forced an anomaly-detection framing, and within
that framing **the simplest model won on both axes that matter** - a quarter of
IsolationForest's false callouts at identical detection, and a fitted state small enough to
print. The scaling choice mattered more than the model family: **MAD keeps a usable operating
band from 2 to 10 where a standard deviation collapses at 5.** And the full time series
already shows the two problems Stage 4 has to price: spikes on healthy hours, and a baseline
that will not stay still.
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 4
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 4 - Operating Policy, Alert Fatigue and Drift

**Question:** What threshold should this system run at - and what happens to that threshold
three months later, when the machine is the same but the summer is not?

**What you should expect to see:** a policy defined **before** any sweep, that sweep priced as
a cost table, comparison against doing nothing and against calendar maintenance, and then the
headline of this entire module: **a drift experiment in which nothing about the equipment
changes and the alert load grows tenfold.**

**Why this stage exists in a real workflow:** this is where predictive-maintenance projects
actually die. Not at model accuracy - at the moment the maintenance team stops opening the
alerts. Alert fatigue and drift are usually discussed as separate risks. They are the same
table, and we are going to look at it.

**Output passed to Stage 5:** one frozen threshold, one three-way routing rule, and one
scoring of the untouched July-September window.
""")

md(r"""
## 4.1 The policy, written down before the sweep

Defining the rule before looking at the numbers is what keeps this from being a search for
the threshold that flatters us.

```text
score >= 6.0   ->  work_order   raise a maintenance work order; a technician inspects within 4 hours
3.0 <= score < 6.0  ->  watch    log it to the shift report, no callout
score < 3.0    ->  no_action    nothing happens
```

Plus one fallback that is part of the policy, not an implementation detail: **an hour with
under 50% sensor coverage is not scored.** It is reported as "no data" and routed to a person.
It is never silently treated as normal.

### Every dollar below is a synthetic classroom assumption

They are anchored on the published fact that air-production-unit faults caused Metro do Porto
to cancel more than 170 trips in 2017. **They are not that organization's real figures**, and
nothing measured here transfers to another fleet. They exist so the trade-off has units.

One modeling choice inside them deserves calling out, because it is what near-zero lead time
actually buys. Catching a fault at its onset does **not** avoid the fault. It produces a
**shorter fault**. A detected fault is charged for the hours from its documented onset to the
first alert, **plus the four hours a technician takes to arrive**. An undetected one is
charged for its full documented length.
""")

code(r"""
# ===============================================================
# 4.1 THE SYNTHETIC COST ASSUMPTIONS
# ===============================================================
print(policy.cost_assumptions_table().to_string(index=False))
print(f"\nRouting rule: {json.dumps(config.ROUTES, indent=2)}")
""")

md(r"""
## 4.2 The threshold sweep, priced

Now the sweep - as a **cost table**, not an accuracy table. Each row is one candidate
threshold over 2020-04-01 to 2020-09-02, and each row answers: how many technician trips, how
many of those were wasted, how many failures caught, and what does the whole thing cost.

Against it we price the two policies a maintenance team would actually propose instead:
**never alert** - do nothing, let faults run - and **calendar maintenance**, a technician
walking the machine every N days at 09:00.
""")

code(r"""
# ===============================================================
# 4.2 WHAT EACH THRESHOLD COSTS, AND WHAT DOING IT THE OLD WAY COSTS
# ===============================================================
full_window = (config.SCORED_START, config.SCORED_END)
sweep = policy.threshold_sweep(score, full_window)
baselines = policy.baseline_table(full_window)
print("Detector, by threshold (SYNTHETIC dollars):")
print(sweep.to_string(index=False))
print("\nThe alternatives, priced over the same window:")
print(baselines.to_string(index=False))

never_cost = float(baselines.loc[baselines["policy"] == "never alert", "total_cost_usd"].iloc[0])
daily_cost = float(baselines.loc[baselines["policy"] == "scheduled inspection every 1 d",
                                 "total_cost_usd"].iloc[0])
charts.cost_curve(sweep, never_cost, daily_cost).show()
""")

md(r"""
### How to read this plot

- **Question:** Which threshold costs least, and how much does that choice cost a technician
  in trips?
- **Marks and axes:** two stacked panels sharing a horizontal axis, the alert threshold. The
  top panel is **total synthetic cost** on a **log scale** - callout cost plus fault cost. The
  red dashed line is **never alert** (`$148,980`); the orange dotted line is **inspect daily**
  (`$167,200`). The green diamond marks the chosen threshold, 6.0. The bottom panel is
  **technician callouts per month** as bars.
- **Denominator:** costs are totals over the 5.0-month window, not rates. Callouts per month
  divides total callouts by that same 5.0 months.
- **What to notice:** the curve is **flat from 6 to 10** - `$25,200`, `$25,200`, `$25,800`,
  `$25,000`, `$24,600` - and then **falls off a cliff at 12**, jumping to `$58,200` because
  the detector finally arrives too late on F3 and the 12-hour interruption charge lands. Below
  6 the cost climbs for the opposite reason: threshold 3 catches the same 4 failures but takes
  **92 callouts** instead of 15, at `$56,000`. **Doing nothing costs `$148,980`. Inspecting
  daily costs more than doing nothing** - `$167,200` for 155 visits that catch 2 of 4.
- **Term - operating threshold:** the number the written policy compares the score against. It
  is a **business decision about workload**, not a model parameter, which is why it is chosen
  on a cost table and not by the model.
- **Why it matters:** the flat region is the real finding. Anywhere from 6 to 10 buys
  essentially the same outcome, so the choice can be made on **technician workload** -
  2.98 callouts a month at threshold 6 - rather than on a decimal place. We take **6.0**, the
  low end of the flat region, because it keeps the most lead time on F4.
- **Boundary:** "optimal" here means optimal **under four events and these synthetic costs**.
  Change the interruption charge and the cliff moves. Add a fifth failure and every row shifts.
  This chart argues about a trade-off shape; it does not certify a dollar figure.
""")

md(r"""
## 4.3 What the threshold buys in warning time - and what it costs

The same sweep, viewed as **lead time**: hours between the first alert and the documented
onset. Positive means the alert came **before** the failure was written down. Zero means the
alert landed in the onset hour itself. Negative means we caught it late.
""")

code(r"""
# ===============================================================
# 4.3 LEAD TIME PER FAILURE, BY THRESHOLD
# ===============================================================
print(metrics.lead_time_table(score).to_string(index=False))
""")

md(r"""
**The trap is the top row.** At threshold 2 every failure shows 14 to 22 hours of "lead time",
which looks like the forecasting result we wanted. It is not. At threshold 2 the system is
alerting on **1,695 hours** and generating **13.1 false callouts a month**. It is not
detecting anything - **it is always on**, and an alarm that is always on is right before every
failure by construction.

At the thresholds anyone would actually run, F1, F2 and F3 collapse to **0.0 hours of
warning** or worse. Only **F4** holds a real lead - **14.5 hours** at threshold 6 - and Stage
1 already told us that 6 of F4's 24 pre-onset hours are a recorder gap.

This is the sentence to carry out of Stage 4: **the threshold that buys lead time is the
threshold that floods the queue.** The next two cells measure exactly how badly.
""")

md(r"""
## 4.4 Drift, part one: the rule a first team actually writes

Before anyone builds a six-feature detector, somebody writes the obvious rule. It usually
looks like this:

> *"Alert when rest between working bursts is three robust standard deviations below normal."*

It is a good rule. It encodes real physics - a leaking compressor does not get to rest - and
on the February-March baseline it is nearly silent. Below, each of the six features is turned
into exactly that one-feature rule and run month by month.

**Denominator, stated precisely:** each cell is the share of that month's **clean hours** that
alert - clean meaning outside `[onset - 72 h, end + 24 h]` for every documented failure. April
has **442** clean hours, August **608**. Documented failures are excluded entirely, so **every
alert counted here is a false one.**
""")

code(r"""
# ===============================================================
# 4.4 ONE FEATURE, ONE FIXED THRESHOLD, FIVE MONTHS
# ===============================================================
naive_drift = metrics.naive_single_feature_drift(contributions)
print(naive_drift.to_string(index=False))
charts.naive_rule_drift(naive_drift).show()
""")

md(r"""
### How to read this plot

- **Question:** A single-feature rule that behaves well in spring - does it still behave well
  in summer, on the same healthy machine?
- **Marks and axes:** one line per feature; the horizontal axis is calendar month; the
  vertical axis is the **share of that month's clean hours that alert**. The thick red solid
  line is "minutes of rest between working bursts", the rule a team would most plausibly
  write. The other five are dotted grey, so the headline line is identifiable without relying
  on color.
- **Denominator:** clean hours **within that month** - 442 in April, 502 in May, 502 in June,
  536 in July, 608 in August. Failure windows and their surrounding ambiguous bands are removed
  first.
- **What to notice:** the red line climbs from **18.8% in April** to **43.4%**, **84.7%**,
  **86.0%**, and **86.7% in August**. By August the rule is firing on roughly **six of every
  seven healthy hours**. No documented failure occurs in August. Nothing about the compressor
  broke. "Share of the hour working hard" and "pressure fall rate" drift the same way, more
  gently.
- **Term - alert fatigue:** the point at which the people receiving alerts stop acting on
  them, because the base rate of being wrong has become obvious. A rule at 86.7% is past it.
- **Why it matters:** the rule did not degrade. **The world moved.** The metro ran a heavier
  summer schedule, so the compressor genuinely worked harder, so a threshold calibrated on
  February became a threshold that describes normal June operation. This is the single most
  common way a predictive-maintenance deployment fails, and it needs no bug to happen.
- **Boundary:** this chart indicts a **fixed single-feature threshold**, not the feature. Rest
  between bursts is genuinely one of the strongest failure signals in Stage 2. The problem is
  the constant it is compared against.
""")

md(r"""
## 4.5 Drift, part two: the six-feature detector is not immune

The obvious response is "that is why we built a six-feature detector". So here is the same
experiment run against the real system, at five candidate thresholds, counting **false
technician callouts** - trips to a healthy machine - rather than alert hours.
""")

code(r"""
# ===============================================================
# 4.5 FALSE TECHNICIAN CALLOUTS PER MONTH, BY THRESHOLD
# ===============================================================
detector_drift = metrics.detector_callouts_by_month(score)
print(detector_drift.to_string(index=False))
charts.drift_callout_heatmap(detector_drift).show()
""")

md(r"""
### How to read this plot

- **Question:** Does raising the threshold protect the six-feature detector from drift, and
  what does that protection cost?
- **Marks and axes:** a heatmap. Rows are candidate thresholds, columns are months, and each
  cell holds the **count of false technician callouts** in that month at that threshold. The
  number is printed in every cell, so the reading never depends on the color scale. Darker red
  is more wasted trips.
- **Denominator:** none - these are **counts of trips**, on clean hours only. Alerts within 6
  hours of each other are merged into one trip.
- **What to notice:** read the **threshold 3** row across: **3, 7, 16, 25, 30**. From three
  wasted trips in April to **thirty** in August, on the same machine, with no failure
  documented in either month. Now read down the August column: 30, 8, 3, 1, 0. Raising the
  threshold does control the flood - and Section 4.3 already showed what that costs.
- **Term - the cruel interaction:** **the low threshold that buys lead time is exactly the one
  that floods the queue by summer.** At threshold 3 the detector reaches F2 and F4 more than
  17 hours early - and generates 30 false callouts in August. At threshold 6 it holds at 1 to
  3 callouts a month - and gives real advance warning on **one** of four failures. There is no
  row of this table that gives you both.
- **Why it matters:** alert fatigue and drift are usually managed by different people - one is
  a UX problem, the other a data problem. This table shows they are the same problem, and that
  the threshold is where both of them land.
- **Boundary:** these are counts over one machine and five months. The **direction** is the
  finding; the specific numbers are not a forecast of what any other deployment would see.
""")

md(r"""
## 4.6 What actually moved: the world, not the machine

To be sure the drift is operating conditions rather than a developing fault, look at the
monthly feature means and how far each sits from the training months, measured in **training
standard deviations**.
""")

code(r"""
# ===============================================================
# 4.6 MONTHLY FEATURE MEANS, AND THE SAME DISTANCES IN TRAINING SDs
# ===============================================================
monthly, shifted = features.monthly_means(matrix, detect.training_slice(matrix))
print("Monthly means:")
print(monthly.to_string())
print("\nDistance from the training mean, in training standard deviations:")
print(shifted.to_string())
print("\nAlert load per month at the operating threshold, on clean hours only:")
print(metrics.monthly_alert_load(score, config.THRESHOLD).to_string(index=False))
""")

md(r"""
**Compressor starts per hour** goes from **1.93** in February to **3.18** in July - `+1.11`
training standard deviations. **Pressure fall rate** moves `+1.33`. **Oil temperature** rises
from 56.4 C to 67.1 C. These are the fingerprints of a **heavier summer duty cycle**, spread
across every feature at once. A developing fault looks different: it moves a few features
violently over hours, not all six gently over months.

The monthly alert-load table shows the operating threshold surviving this better than
threshold 3 did - **2.5%, 6.8%, 12.5%, 0.6%, 0.2%** of clean hours, **1 to 3 false callouts a
month**. June is the worst month, not August, because June carried both the heaviest duty
cycle and the longest documented failure.
""")

md(r"""
## 4.7 The mitigation, measured - and rejected as an automatic default

The standard fix is a **rolling baseline**: instead of comparing against a frozen
February-March normal, re-learn "normal" from the last N days, every hour. It is what most
teams reach for, and on the metric everyone looks at first, it works.

So we measured it at **two** thresholds, which is the whole point.
""")

code(r"""
# ===============================================================
# 4.7 ROLLING BASELINE: THE FIX THAT ABSORBS THE FAULT
# ===============================================================
rolling = {f"Rolling {days}-day baseline": detect.rolling_baseline_score(matrix, days)
           for days in (7, 14, 28)}
print(metrics.mitigation_table(score, rolling, threshold=4.0, high_threshold=7.0).to_string(index=False))
""")

md(r"""
**At threshold 4 the rolling baseline is a clear win.** A 14-day window cuts false callouts
from **33 to 15** - a 55% reduction - while still catching **4 of 4**. If we stopped measuring
here we would ship it.

**At threshold 7 it catches 2 of 4 where the fixed baseline still catches 4 of 4.**

The reason is structural, and it is worth stating slowly. A window that keeps re-learning
"normal" from the recent past **eventually learns the fault**. F3 ran for 52.5 hours. A 7-day
window has absorbed a good deal of that into its own idea of normal well before it ends; by
the time the fault is fully developed, the baseline has moved toward it, and the distance the
detector measures shrinks. **The mitigation for drift is also a mechanism for hiding slowly
developing faults** - precisely the faults that would give the most warning.

**What we recommend instead:** keep the **fixed** baseline, and put a **person** on the
recalibration. Review the baseline monthly; refit if any feature's monthly median has moved
more than one training standard deviation. A human reviewing a baseline shift can ask "did the
schedule change, or is the machine getting worse?" A rolling window cannot ask that question,
and answers "the schedule changed" every time.
""")

md(r"""
## 4.8 The threshold is chosen here, and the test window is opened once

Everything above used April through June - the **threshold-selection window**. July onward has
not been looked at. Below, the threshold is chosen on the dev window, and then the held-out
window is scored **once**, with the model, features and policy already frozen.
""")

code(r"""
# ===============================================================
# 4.8 CHOOSE ON APR-JUN, THEN SCORE JUL-SEP EXACTLY ONCE
# ===============================================================
dev_sweep = policy.threshold_sweep(score, (config.DEV_START, config.DEV_END),
                                   [3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
print("Threshold selection on Apr 1 - Jun 30 (F1, F2, F3 live here):")
print(dev_sweep.to_string(index=False))
print(f"\nChosen: {config.THRESHOLD} - cheapest row on the dev window, and the low end "
      "of the flat region.\n")

test_window = (config.TEST_START, config.TEST_END)
test_detection = metrics.evaluate(score, config.THRESHOLD, test_window)
test_policy = policy.policy_cost(score, config.THRESHOLD, test_window)
test_never = policy.never_alert(test_window)

print("FROZEN TEST - Jul 1 to Sep 2, scored once:")
for key in ("scored_hours", "alert_hours", "clean_hours", "false_alarm_hours",
            "false_alarm_rate_on_clean_hours", "false_callouts",
            "false_callouts_per_month", "months", "failures_detected"):
    print(f"  {key:<32} {test_detection[key]}")
print(f"  F4                               {test_detection['per_failure']['F4']}")
""")

md(r"""
**The frozen result.** **1 of 1** failure in the window detected, first alert at
**2020-07-15 00:00**, **14.5 hours** before the documented onset. **4 false-alarm hours out of
1,145 clean hours = a 0.35% false-alarm rate**, which merges into **3 false technician
callouts over 2.04 months = 1.47 a month**.

Those are the numbers on the model card, and they were produced by opening this window one
time.

**Stage 4 conclusion.** The threshold is a **workload decision**, priced on a cost table with
a flat region from 6 to 10. Drift is not a tail risk here - it is the main event: a naive rule
goes from **18.8% to 86.7%** of clean hours alerting, and the real detector at threshold 3
goes from **3 to 30 false callouts a month**, with no change in the equipment. The threshold
that buys warning is the threshold that floods the queue, and no row of that table gives both.
The obvious mitigation works on the metric you check first and **absorbs slow faults** on the
one you check second, so we keep the fixed baseline and put a human on the monthly review.
""")


# ═══════════════════════════════════════════════════════════════════════════
# Stage 5
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 5 - Prediction, Work Order and Handoff

**Question:** What does one hour of sensor data actually turn into on a maintenance planner's
screen - and what are the three things this system cannot do, stated as measurements rather
than as disclaimers?

**What you should expect to see:** eight packaged windows walked from score to work order,
then **three boundary cases** that each take something away from the claim, then the exported
artifacts reloaded from disk in a fresh process and checked.

**Why this stage exists in a real workflow:** the model is one component. What gets deployed
is the **workflow** - and what gets audited later is the artifact plus the written record of
what it could not do. Every limitation below is a measured number, because a limitation
without a number is a disclaimer nobody reads.

**Output:** five artifact files, and a claim boundary this notebook has earned.
""")

md(r"""
## 5.1 The eight packaged windows

The demo ships with eight windows, chosen **by rule, not by taste**: one clean training-era
week, one clean post-drift week, the 24 hours before each documented failure through its
documented end, plus two chosen by measurement - the **strongest drift-induced false alarm on
clean hours** (S6) and the **longest clean stretch that sits in the watch band without ever
crossing** (S7).

Every one of them carries its hour-by-hour scores and routes, so the demo replays a real
decision rather than a screenshot.
""")

code(r"""
# ===============================================================
# 5.1 THE PACKAGED WINDOWS
# ===============================================================
manifest = handoff.build_manifest(score, contributions)
print(manifest[["sample_id", "hours_with_data", "peak_score", "peak_at", "median_score",
                "work_order_hours", "watch_hours", "route_at_peak",
                "covers_documented_failure"]].to_string(index=False))
""")

md(r"""
## 5.2 One window, end to end

Take **S5**, the F4 window - the only failure with genuine advance warning. Below is the whole
path: **score -> policy -> route -> what a technician is told -> what the maintenance report
says happened.**
""")

code(r"""
# ===============================================================
# 5.2 SCORE -> POLICY -> ROUTE -> WORK ORDER
# ===============================================================
row = manifest[manifest["sample_id"] == "S5_F4_real_warning"].iloc[0]
hours = pd.DataFrame(json.loads(row["hourly_scores"]))
first_order = hours[hours["route"] == config.ROUTE_WORK_ORDER].iloc[0]
onset = pd.Timestamp("2020-07-15 14:30")
alert_at = pd.Timestamp(first_order["hour"])
driver, driver_z = detect.top_driver(contributions, alert_at)

print(hours.to_string(index=False))
print()
print("WORK ORDER  (generated by policy v1.0, not by a person)")
print(f"  raised at          {alert_at}")
print(f"  score              {first_order['score']:.2f}   threshold {config.THRESHOLD}")
print(f"  route              {first_order['route']}")
print(f"  strongest driver   {config.FEATURE_DISPLAY_NAMES[driver]} at {driver_z} robust SDs")
print( "  told to technician 'This compressor is working far harder than its February")
print(f"                      baseline. Inspect for an air leak within "
      f"{config.COSTS['response_hours']:.0f} hours.'")
print( "  NOT done by the model: stop the machine, diagnose the cause, or certify it safe")
print(f"  documented onset   {onset}")
print(f"  advance warning    {(onset - alert_at).total_seconds() / 3600:.1f} hours")
print( "  maintenance report 'Short event, and the only one with real advance warning'")
""")

md(r"""
Notice what the work order contains and what it does not. It carries a **score**, the
**feature that drove it**, and an **inspection window**. It does not carry a diagnosis. The
detector knows this hour is far from normal and which measurement made it so; it does not know
that the cause is a leaking fitting rather than a stuck valve, and it does not say so.

Now the three things it cannot do.

---

## 5.3 Boundary one: three of the four failures give zero advance warning

The system detects. It does not forecast. Here is the trace that settles it - F3, the longest
documented failure, hour by hour from 36 hours before onset.
""")

code(r"""
# ===============================================================
# 5.3 BOUNDARY ONE - THE FLAT LINE BEFORE F3
# ===============================================================
f3_trace = metrics.failure_trace(score, "F3")
before = f3_trace[f3_trace["hours_from_onset"] < 0]["score"]
print(f"F3: {len(before)} hours before the documented onset")
print(f"  score range before onset : {before.min():.2f} to {before.max():.2f}")
print(f"  score in the onset hour  : "
      f"{f3_trace.loc[f3_trace['hours_from_onset'] == 0, 'score'].iloc[0]:.2f}")
print(f"  hours above the {config.THRESHOLD} threshold before onset : "
      f"{int((before >= config.THRESHOLD).sum())}")
charts.flat_line_trace(f3_trace).show()
""")

md(r"""
### How to read this plot

- **Question:** In the day and a half before the year's longest air leak, was there anything
  in the score to act on?
- **Marks and axes:** one bar per clock hour. The horizontal axis is **hours from the
  documented onset**, negative meaning before. The vertical axis is the detector score. Red
  bars are at or above the work-order threshold, blue below. The dashed line is 6.0; the solid
  vertical line at 0 is the documented onset.
- **Denominator:** none - one score per hour, 36 hours before through 6 hours after.
- **What to notice:** **36 consecutive hours between 0.19 and 3.36**, every one of them blue,
  not one crossing even the watch line at 3.0. Then the onset hour: **11.63**. The hour
  immediately before onset is **3.36** - the highest of the 36, and still comfortably in the
  watch band. There is no ramp, no shoulder, no gentle climb. **There is nothing, and then
  there is a failure.**
- **Term - lead time:** hours between the first alert and the documented onset. Positive is
  warning; zero means the alert arrived in the onset hour itself. F3's lead time at the
  operating threshold is **0.0 hours**.
- **Why it matters:** this is the difference between the system that was sold and the system
  that exists. **A detector shortens a fault. A forecaster prevents one.** This is the first,
  and pricing it as the second would be the most expensive mistake in this notebook.
- **Boundary:** and here is why this trace is the strongest version of the argument: Stage 1
  showed F3 is the one failure with **24 of 24 pre-onset hours of data**. The flat line is not
  a recorder gap. **There was nothing to see, and we were looking.**

**The same shape holds for F2** - 2 to 4 all day, then a step at the onset hour - and for
**F1**. Only **F4** gives real warning, **14.5 hours**, and six of its prior 24 hours are a
recorder gap. **Three of four failures: zero warning.**

---

## 5.4 Boundary two: the clean training window is not clean

The detector's entire idea of normal comes from 1,227 February-March hours in which **no
failure is documented**. "No failure documented" is not the same claim as "the machine was
healthy". It means **nobody filed a work order.**

So: score the training window with the model that was fitted on it, and see how many of those
"normal" hours the operating policy would have called out.
""")

code(r"""
# ===============================================================
# 5.4 BOUNDARY TWO - SCORING THE 'CLEAN' TRAINING MONTHS
# ===============================================================
training_alerts = metrics.training_window_alerts(score, config.THRESHOLD)
print(f"Training hours                     {training_alerts['training_hours']:,}")
print(f"Hours at or above threshold {config.THRESHOLD}      {training_alerts['hours_above_threshold']}"
      f"  ({training_alerts['share_above_threshold']:.1%})")
print(f"Separate episodes                  {training_alerts['episodes']}")
print(f"Highest score in 'clean' months    {training_alerts['peak_score']}"
      f"  at {training_alerts['peak_at']}")
print()
print(pd.DataFrame(training_alerts["episode_list"]).to_string(index=False))
print(f"\nFor comparison - peak score during documented failures: "
      f"F1 {score['2020-04-18':'2020-04-18 23:59'].max():.2f}, "
      f"F3 {score['2020-06-05 10:00':'2020-06-07 14:30'].max():.2f}")
""")

md(r"""
**44 of 1,227 training hours - 3.6%, in 7 separate episodes - score at or above the operating
threshold.** The highest, on **2020-03-29 15:00**, reaches **12.36**. F1, the year's most
severe documented air leak, peaks at **12.08**. F3, the longest, at **12.18**.

An hour inside our "clean" baseline scores **higher than either of them.**

Three readings are available and we cannot distinguish them from the data:

1. There were undocumented leaks in March that nobody logged.
2. The compressor legitimately worked that hard on those days.
3. The features are wrong in some way we have not found.

**What this does to every number in the notebook:** the baseline is fitted partly on abnormal
hours, which widens the MAD and makes the detector slightly less sensitive than it appears.
And the "false" callouts counted in Stage 4 may include real faults nobody wrote down. **Our
ground truth is the paperwork, not the machine**, and the paperwork is what a maintenance
office had time to file.

---

## 5.5 Boundary three: a healthy machine and the year's worst failure, one hundredth of a point apart

This is the human-in-the-loop argument, as a number rather than as a principle.

**S6** is a healthy compressor on a busy May day. No failure is documented anywhere near it;
it was selected automatically as the strongest drift-induced false alarm on clean hours.
**S2** is F1, the most severe documented air leak of the year.
""")

code(r"""
# ===============================================================
# 5.5 BOUNDARY THREE - S6 AGAINST S2
# ===============================================================
def window_scores(sample_id: str) -> pd.DataFrame:
    record = manifest[manifest["sample_id"] == sample_id].iloc[0]
    return pd.DataFrame(json.loads(record["hourly_scores"])), record

s6, s6_row = window_scores("S6_drift_false_alarm")
s2, s2_row = window_scores("S2_F1_worst_failure")
print(pd.DataFrame([
    {"window": "S6 - healthy, busy May day", "peak": s6_row["peak_score"],
     "median": s6_row["median_score"], "work order hours": s6_row["work_order_hours"],
     "documented failure": bool(s6_row["covers_documented_failure"]),
     "top driver at peak": s6_row["top_driver_at_peak"]},
    {"window": "S2 - F1, worst failure of the year", "peak": s2_row["peak_score"],
     "median": s2_row["median_score"], "work order hours": s2_row["work_order_hours"],
     "documented failure": bool(s2_row["covers_documented_failure"]),
     "top driver at peak": s2_row["top_driver_at_peak"]},
]).to_string(index=False))
print(f"\nDifference in peak score: {abs(s2_row['peak_score'] - s6_row['peak_score']):.2f}")

charts.indistinguishable_pair(s6, s2, s6_row["peak_score"], s2_row["peak_score"]).show()
""")

md(r"""
### How to read this plot

- **Question:** Can any threshold tell a healthy busy day apart from the worst failure of the
  year?
- **Marks and axes:** two panels sharing a vertical axis, the detector score. Left, in blue, is
  **S6** - a healthy compressor, no documented failure. Right, in red, is **S2** - F1. Each
  point is one clock hour; the horizontal axis is hours from the start of each window. The
  dashed line in both panels is the work-order threshold, 6.0.
- **Denominator:** none - scores per hour. S6 covers 29 hours, S2 covers 44.
- **What to notice:** **S6 peaks at 12.07. S2 peaks at 12.08.** One hundredth of a point. Both
  panels sit far above the threshold for most of their length - S6 raises a work order in
  **22 of its 29 hours**, S2 in **24 of 44**. Both are driven by the same feature, "share of
  the hour the compressor is working hard", at the same **37.8** robust standard deviations.
  The shapes differ slightly - F1 is more sustained - but nothing in the *score* separates
  them.
- **Term - human in the loop:** a design in which a person makes the decision the system is
  not equipped to make. Not a safety blanket, and not an apology for model quality - a
  response to a measured fact about what the score can and cannot distinguish.
- **Why it matters:** **no threshold separates these two.** Raise it to 12.075 and you catch
  F1 and drop S6, and you have fitted a threshold to two examples, which is not a policy. The
  thing that tells them apart is a person who knows that the metro ran a heavier May schedule
  that week - context that is nowhere in the sensor stream.
- **Boundary:** this is not a bug to fix in the next iteration. It is what a
  distance-from-normal score **is**. Any detector built on "how far from baseline" will call a
  legitimately busy machine abnormal, because it **is** abnormal relative to the baseline. The
  fix is a person, not a feature.

---

## 5.6 The honest ROI, including the part that does not flatter us

Stage 4's cost curve made the detector look excellent: **`$25,200` against never-alert's
`$148,980`** over the full period. That number is real, and it is **not the number to quote**.
""")

code(r"""
# ===============================================================
# 5.6 ROI ON THE HELD-OUT WINDOW, AND WHY THE GOOD NUMBER IS FRAGILE
# ===============================================================
full_policy = policy.policy_cost(score, config.THRESHOLD, full_window)
full_never = policy.never_alert(full_window)
print(pd.DataFrame([
    {"window": "Full period, Apr 1 - Sep 2", "policy": "detector at 6.0",
     "callouts": full_policy["callouts"], "failures caught": full_policy["failures_caught"],
     "total cost (SYNTHETIC)": full_policy["total_cost_usd"]},
    {"window": "Full period, Apr 1 - Sep 2", "policy": "never alert", "callouts": 0,
     "failures caught": full_never["failures_caught"],
     "total cost (SYNTHETIC)": full_never["total_cost_usd"]},
    {"window": "HELD-OUT, Jul 1 - Sep 2", "policy": "detector at 6.0",
     "callouts": test_policy["callouts"], "failures caught": test_policy["failures_caught"],
     "total cost (SYNTHETIC)": test_policy["total_cost_usd"]},
    {"window": "HELD-OUT, Jul 1 - Sep 2", "policy": "never alert", "callouts": 0,
     "failures caught": test_never["failures_caught"],
     "total cost (SYNTHETIC)": test_never["total_cost_usd"]},
]).to_string(index=False))

print("\nWhere the full-period saving comes from, failure by failure:")
print(pd.DataFrame(full_policy["detail"]).to_string(index=False))
print(f"\nF3 alone, if never caught: {policy.fault_cost(52.5):,.0f} USD of the "
      f"{full_never['total_cost_usd']:,} never-alert total "
      f"({policy.fault_cost(52.5) / full_never['total_cost_usd']:.0%}).")
""")

md(r"""
**On the held-out window alone, the detector loses.** `$6,400` against never-alert's `$5,400`.
It spent `$1,600` on four technician trips to shorten a 4.5-hour fault to 4.0 hours, and the
arithmetic does not work.

**And the favorable full-period figure rests on one event.** F3 ran for 52.5 hours. Left alone
it costs `$85,000` - **57% of the entire `$148,980` never-alert total comes from a single
failure.** Remove F3 and the case largely evaporates.

**What we are allowed to say:** on four events, over five months, on one compressor, under
synthetic costs, this detector caught every documented failure at about three technician trips
a month, and on the two months nobody tuned it on, it cost more than doing nothing.

**What we are not allowed to say:** that it saves `$123,780`, or any annualization of that.
**Four events cannot support an ROI claim**, and a projection resting on one 52.5-hour event is
a projection resting on one event.

If someone needs a business case, the honest version is: *the pilot is cheap, the mechanism is
sound, and the evidence base is four events - so fund another year of instrumented operation
before funding a fleet rollout.*
""")

md(r"""
## 5.7 Export the artifacts, and prove the exported model is the measured model

Five files leave this notebook and nothing else:

| File | What it carries |
|---|---|
| `model.joblib` | the fitted detector - six medians, six scales, six directions |
| `model_card.json` | intended use, provenance, measured results, and every limitation above |
| `evaluation.json` | every table this notebook printed, for the governance view |
| `operating_policy.json` | the threshold, the three routes, the synthetic costs, the boundary |
| `sample_manifest.parquet` | the eight packaged windows with hour-by-hour scores |

The detector is about **two kilobytes**, because it is twelve numbers. In a classroom that is
a feature: you can open the policy JSON and read the entire model.
""")

code(r"""
# ===============================================================
# 5.7 ASSEMBLE THE EVIDENCE AND EXPORT
# ===============================================================
evidence = handoff.assemble_evidence(
    data.coverage_summary(minutes), data.pre_onset_coverage(minutes),
    features.dropna_damage(hourly), effects, comparison,
    metrics.scaling_comparison(detect.scaling_variants(matrix)),
    metrics.lead_time_table(score), sweep, baselines, naive_drift, detector_drift,
    metrics.mitigation_table(score, rolling, threshold=4.0, high_threshold=7.0),
    metrics.monthly_alert_load(score, config.THRESHOLD), training_alerts, dev_sweep,
    test_detection, test_policy, test_never, full_policy, full_never,
    time.time() - NOTEBOOK_STARTED,
)
sizes = handoff.export(detector, evidence, manifest)
for name, size in sizes.items():
    print(f"  {name:<26} {size}")
print(f"\nManifest: {len(manifest)} windows, "
      f"{int(manifest['covers_documented_failure'].sum())} on documented failures.")
""")

md(r"""
## 5.8 Reload in a fresh process and require bitwise-identical scores

The last check is the one that matters, and it is deliberately stronger than reloading in this
kernel. A **separate Python process** starts from nothing, reads the committed parquet,
**recomputes every feature from scratch**, loads `model.joblib` from disk, scores 500 hours,
and has to land on scores that are **bitwise identical** to the ones this notebook produced -
not close, identical - with **zero route changes**.

Bitwise is the right bar. Anything looser hides exactly the problem this check exists to
catch: a service that computes a feature one way while the notebook computed it another,
producing scores that look fine and put a handful of hours on the wrong side of the policy
line.
""")

code(r"""
# ===============================================================
# 5.8 FRESH-PROCESS RELOAD - SCORE AND ROUTE IDENTITY
# ===============================================================
identity = handoff.verify(matrix, detector)
print(identity)
assert identity["scores_bitwise_identical"], "reloaded scores differ from notebook scores"
assert identity["max_abs_difference"] == 0.0, "reloaded scores are not bitwise identical"
assert identity["route_changes"] == 0, "reloaded routes differ from notebook routes"

stored = json.loads((config.ARTIFACT_DIR / "evaluation.json").read_text())
frozen = stored["test_frozen"]
assert frozen["failures_detected"] == test_detection["failures_detected"]
assert frozen["false_callouts_per_month"] == test_detection["false_callouts_per_month"]
assert frozen["per_failure"]["F4"]["lead_hours"] == 14.5
assert frozen["policy"]["total_cost_usd"] == test_policy["total_cost_usd"]
assert frozen["never_alert_baseline"]["total_cost_usd"] == test_never["total_cost_usd"]
assert stored["training_window_not_clean"]["hours_above_threshold"] == 44
assert stored["full_period_policy"]["total_cost_usd"] == full_policy["total_cost_usd"]

print("\nOK - a fresh process reproduces every score bitwise from the committed data.")
print(f"OK - evaluation.json carries the measured frozen test: "
      f"{frozen['failures_detected']}/1 caught, "
      f"{frozen['per_failure']['F4']['lead_hours']} h lead, "
      f"{frozen['false_callouts_per_month']} false callouts per month, "
      f"${frozen['policy']['total_cost_usd']:,} against never-alert's "
      f"${frozen['never_alert_baseline']['total_cost_usd']:,}.")
print(f"\nEnd to end: {time.time() - NOTEBOOK_STARTED:.1f} s.")
""")

md(r"""
## 5.9 Where the handoff ends

```text
sensor minute -> coverage check -> hourly features -> score -> policy decision -> work order
                       |                                                       -> watch log
                       v                                                       -> no action
                 under 50% covered: "no data", routed to a person
```

**The coverage check comes before the model, not after.** An hour with too little data is
never silently scored, because a silently scored empty hour produces a confident number nobody
can trace back to a measurement.

What this system does: **it orders a queue of hours for a technician to look at.** What it does
not do: stop the compressor, lock out equipment, diagnose a fault, certify a machine safe to
work on, or forecast a failure days ahead. Every one of those belongs to a person, and every
one of them stays there.

### The five stages, and who has to be in the room

| Stage | What happened | Who is needed |
|---|---|---|
| **1 - Ingestion** | Source, license, checksum, sampling rate and 904 missing hours verified | Data team **and** the plant engineer who knows when the recorder was down |
| **2 - Features** | Leak physics stated, six features built, one NaN bug found and fixed | ML team **and** a maintenance planner who can say whether a feature is meaningful |
| **3 - Detection** | Anomaly framing argued; simplest model beat three fancier ones | ML team **and** whoever will explain an alert to a technician |
| **4 - Policy and drift** | Threshold priced on workload; drift measured; rolling baseline rejected | ML team **and** the maintenance manager who owns the technicians' time |
| **5 - Handoff** | Boundaries measured, artifacts exported and verified from a fresh process | Engineering **and** reliability engineering **and** whoever signs the work orders |

**The model is one component. The maintenance workflow is the thing that had to be designed.**

---

### What to take away

1. **Score, decision and outcome are three different things.** S6 scored 12.07, was routed to
   a work order, and the outcome was a healthy machine. All three are correct at once.
2. **Detection is not forecasting, and the difference is measurable.** Three of four failures
   gave zero advance warning, and F3's flat line came with complete pre-onset data.
3. **Drift is the main event, not a tail risk.** Naive rule: 18.8% of clean April hours to
   86.7% of clean August hours. Detector at threshold 3: 3 false callouts to 30. The machine
   did not change.
4. **The obvious mitigation hides the faults you most want to catch.** A rolling baseline cut
   false callouts 55% and dropped detection from 4 of 4 to 2 of 4 at threshold 7.
5. **A missing value can be the signal.** `dropna()` deleted 77 failure hours, including every
   hour of the year's longest leak, and it looked like a modeling problem.
6. **Ground truth is the paperwork, not the machine.** 44 of 1,227 "clean" training hours
   score above the operating threshold, one higher than any documented failure.
7. **Four events cannot support an ROI claim.** On the held-out window the detector cost more
   than doing nothing, and the favorable full-period number is one 52.5-hour event.
8. **The artifact that gets deployed has to be the artifact that was measured**, and the only
   way to know is to reload it in a fresh process and require bitwise-identical scores.
""")


notebook["cells"] = cells
notebook.metadata["kernelspec"] = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}
notebook.metadata["language_info"] = {"name": "python", "version": "3.11"}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, OUTPUT)
print(f"wrote {OUTPUT} with {len(cells)} cells")
