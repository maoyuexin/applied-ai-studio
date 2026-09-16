"""Build the five-stage anomaly notebook; do not replace the separate app model."""
from __future__ import annotations

import hashlib
from pathlib import Path
import nbformat as nbf

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_DIR / "01_pdm_build.ipynb"
cells = []


def add(language: str, text: str) -> None:
    source = text.strip()
    identity = "pdm-" + hashlib.sha256((language + source).encode()).hexdigest()[:12]
    constructor = nbf.v4.new_markdown_cell if language == "markdown" else nbf.v4.new_code_cell
    cells.append(constructor(source, id=identity, metadata={"id": identity, "language": language}))


def md(text: str) -> None:
    add("markdown", text)


def code(text: str) -> None:
    add("python", text)


def guide(read: str, notice: str, meaning: str) -> None:
    md(f"### How to read this plot\n- **Read:** {read}\n- **Notice:** {notice}\n- **Why it matters:** {meaning}")


md("""
# How an anomaly detector gets built
**ITAI 2372 | Module 5 | From industrial sensor data to a maintenance review**

We built a fraud classifier from transaction records and a pneumonia-label classifier from
images. This time the data scientist faces a different problem: **we have lots of equipment
readings but very few confirmed failures. How can we find unusual operation?**

| Stage | What happens |
|---|---|
| 1. Data Ingestion | Load, profile, inspect, and separate the time periods |
| 2. EDA and Feature Engineering | Turn sensor minutes into meaningful hourly inputs |
| 3. Model Training | Fit two anomaly detectors without failure labels and compare them |
| 4. Model Validation | Freeze the cutoff, check later data, and inspect mistakes |
| 5. Model Prediction | Score a new hour, explain the review request, and define the handoff |

### The case
A compressor supplies compressed air. Leaks can make it work harder and run hotter. A
maintenance planner wants to inspect unusual operation without sending technicians to every
ordinary fluctuation. We use a train compressor; factories face a similar equipment-monitoring task.

### The data
- **MetroPT-3:** real sensor readings from one Metro do Porto train compressor in 2020.
- Roughly **1.5 million raw readings**, summarized into a local one-minute file.
- **Four reported air-leak events**, not a reliable normal/fault label for every reading.
- Public dataset, **CC BY 4.0**; no downloads during the notebook run.

> An **anomaly** is unusual relative to the pattern a detector learned. It might be a fault,
> a workload change, or a sensor problem. **Anomaly does not mean confirmed failure.**
> The model requests human review. It does not diagnose a leak, stop equipment, or certify safety.
""")
code("""
import json
import joblib
import numpy as np
import pandas as pd
from IPython.display import display
from plotly.offline import init_notebook_mode
from sklearn.ensemble import IsolationForest
from pdmlab import config, data, detect, features, metrics, policy, teaching

init_notebook_mode(connected=False)
pd.set_option("display.max_columns", 8)
print("Local data ready. Models will learn from February-March; later periods stay separate.")
""")
md("""
---
# 1 - Data Ingestion
**Question:** What data do we have, what does one row mean, and what can we trust?

As in the fraud notebook, start with real rows and a column inventory. Here the sources
are a sensor archive and maintenance reports, not transactions and customers. We do not join
failure outcomes into the model inputs. Reports are evidence for later evaluation.

## 1.1 Load the sensor archive
The original readings are irregular, typically about ten seconds apart. The committed file
contains one-minute averages. The loader restores missing minutes to the timeline as empty
rows, so a gap does not disappear when we plot or summarize the data.

Source: [UCI MetroPT-3](https://archive.ics.uci.edu/dataset/791/metropt+3+dataset),
Veloso and colleagues, 2022, [dataset DOI](https://doi.org/10.24432/C5VW3R), CC BY 4.0.
""")
code("""
minutes = data.load_minutes()
recorded_minutes = int(minutes["Motor_current"].notna().sum())
print(f"Recorded minutes: {recorded_minutes:,}; full timeline: {len(minutes):,} minutes")
print(f"From {minutes.index.min()} to {minutes.index.max()}")
display(minutes.loc["2020-02-15 08:00":"2020-02-15 08:05",
                    ["Motor_current", "Oil_temperature", "TP3"]].round(2))
""")
md("""
Read across a row: motor electricity use, oil temperature, and air pressure at the same
minute. Read down a column to see changes. The timestamp matters because an equipment
problem unfolds over time. These rows are minute averages, not individual raw sensor readings.

## 1.2 Profile the available columns
**Data profiling** checks what fields mean, how much is missing, and how the model will use
them. Having a column does not mean we should feed it into a model. Three sensor columns
produce our six model features; the others remain available for investigation.
""")
code("""
display(teaching.source_profile(minutes).style.hide(axis="index"))
""")
md("""
### What is different about the labels?
Fraud had a target such as `is_fraud`; the image case had normal/pneumonia labels. This
archive does **not** label every hour as normal or faulty. It has four separate event reports.
No report means "not documented," not "confirmed healthy."

We will fit the detectors without an answer column. This is an **unsupervised anomaly-detection**
approach, using an earlier reference period with no documented failures. Reports will help
compare models and inspect their later alerts, so they still influence our development choices.
""")
code("""
reports = data.failure_table()[["Failure", "Documented start", "Documented end", "Hours"]]
display(reports)
""")
md("""
## 1.3 Check whether the input is usable
Missing readings and anomalous readings are different problems. Missing data means we lack
evidence; an anomaly is an unusual pattern **in data we actually observed**.
Our classroom quality gate requires at least 30 recorded minutes in a clock hour. It does
not validate every possible sensor fault, but prevents scoring an almost-empty hour as normal.
""")
code("""
display(data.coverage_summary(minutes))
teaching.coverage_plot(minutes).show()
""")
guide("Each bar counts clock hours in a coverage category.",
      "Only the usable group reaches feature preparation. The other hours are not assigned a reassuring score.",
      "Replacing missing readings with zeros invents an equipment state. Missing hours need a separate data-quality route.")
md("""
## 1.4 First EDA: what does motor current look like?
**Exploratory data analysis (EDA)** means inspecting the data before fitting the model.
Use the training months here, not future test outcomes. Current gives us a readable first
view of when the motor is off, idling, or working hard.
""")
code("""
teaching.current_distribution(minutes).show()
""")
guide("Horizontal position is motor current; bar height counts recorded training minutes in that range. The dashed line is 4.75 A.",
      "The readings cluster around low current, an idling range, and a higher working range. One low reading is not automatically a failure.",
      "We can summarize time spent working instead of asking a model to interpret every minute. The 4.75 A feature setting is specific to this dataset, not a safety limit.")
md("""
## 1.5 Separate training, validation, and test periods
Keep the same separation used in the earlier notebooks, but split **by time**. Nearby hours
resemble each other; shuffling them could let later operating patterns leak into training.

| Period | Role | What it may influence |
|---|---|---|
| February-March | Training/reference | The patterns the detector learns |
| April-June | Validation | Model comparison and the operating cutoff |
| July-September | Test | Evaluation after choices are fixed |

This is a reproducible replay of historical data, not a new prospective trial. We will not
show test scores during model choice. The reference months may contain unreported problems.
""")
md("""
**Stage 1 conclusion:** we have a time-indexed sensor table, a quality gate, four event
reports, and three distinct periods. We do not have enough labels to treat every unreported
hour as a confirmed normal training example.

---
# 2 - EDA and Feature Engineering
**Question:** Which measurements should describe one hour to the anomaly detector?

Like the fraud case, we create human-named features. Unlike the CNN, this model does not
learn directly from pixels or the raw time series. **One model row will be one usable hour.**

Choosing which source columns to transform is part of **feature engineering**. All stored
columns are numeric; `COMP`, `LPS`, and `Oil_level` are averaged on/off signals. This version
uses motor current, oil temperature, and TP3 pressure to create six understandable features.
The other columns are not used by this model; they remain available for future experiments.

## 2.1 Turn minute readings into six features
""")
code("""
hourly = features.hourly_features(minutes)
matrix = features.model_matrix(hourly)
training = matrix.loc[(matrix.index >= config.TRAIN_START) & (matrix.index < config.TRAIN_END)]
validation = matrix.loc[(matrix.index >= config.DEV_START) & (matrix.index < config.DEV_END)]
test_matrix = matrix.loc[(matrix.index >= config.TEST_START) & (matrix.index < config.TEST_END)]
print(f"{recorded_minutes:,} recorded minutes -> {len(matrix):,} usable hours -> {matrix.shape[1]} inputs")
display(pd.DataFrame({"Period": ["Training", "Validation", "Test"],
                      "Usable hours": [len(training), len(validation), len(test_matrix)]}))
""")
md("""
| Input feature | What it describes |
|---|---|
| Compressor working (%) | Percentage of recorded minutes spent working hard |
| Starts per hour | Transitions into working hard, not total running time |
| Rest per start | Nonworking time estimated from working share and starts |
| Oil temperature | Average oil temperature during the hour |
| Pressure variation | How much panel pressure varies during the hour |
| Pressure change | Magnitude of average panel-pressure change during nonworking minutes |

The last feature is named `pressure_fall_rate` in code, but the implementation takes an
absolute change: it does not independently prove that pressure was falling. When no rest
was observed it uses zero, meaning no observed rest-period change, not proof of no leak.
""")
code("""
feature_preview = matrix.loc["2020-02-15 08:00":"2020-02-15 12:00"].copy()
feature_preview["load_share"] *= 100
display(feature_preview.rename(columns=teaching.FEATURE_LABELS).rename(
    columns={"Compressor working": "Compressor working (%)"}).round(3))
""")
md("""
## 2.2 Follow one feature from readings to a number
Count recorded minutes with average motor current above 4.75 A, then divide by recorded
minutes. Compare the same February and April hours throughout this example.

**What does "working time %" mean?** It is the **compressor's time working hard**, not a
technician's work time, output productivity, or the chance of a fault.
Calculate **working minutes / recorded minutes x 100**. For an illustrative complete hour:
30 working minutes out of 60 = 50%; 60 out of 60 = 100%. The motor may idle or be off in the
remaining minutes. If only 40 minutes were recorded and 20 were working, the share is still
50%, but we do not know what happened in the missing 20 minutes. Coverage is checked separately.
""")
code("""
feature_figure, feature_summary = teaching.feature_example(minutes, matrix)
feature_figure.show()
display(feature_summary)
""")
guide("Each point is one minute's current. Both panels use the same scale; minutes above the dashed line count as working hard.",
      "The February hour has 4/60 working minutes, or 6.7%; the April failure hour has 60/60, or 100%.",
      "That working pattern becomes one feature. Zero starts can occur during continuous operation, so starts alone do not tell us whether the motor is off.")
md("""
## 2.3 Look at combinations, not one cutoff per sensor
The pneumonia notebook plotted brightness against contrast. Here plot working share against
temperature: **one point is one hour**. Show the training reference and the April event as
an exploratory validation example. The six-dimensional model will see more than these two inputs.
""")
code("""
teaching.feature_cloud(training, validation).show()
""")
guide("Each dot is one hour. Moving right means the compressor worked hard for a larger percentage of its recorded minutes; moving up means hotter oil. For a complete hour, 50% means 30 of 60 minutes. Symbols distinguish reference hours from reported-event hours.",
      "Many reference hours gather in common operating regions. The April hours sit near continuous operation at high temperatures, but there can be overlap.",
      "Anomaly detection asks whether a combination is unusual relative to the reference. These two axes do not establish a fault boundary, and the report labels are not supplied during fitting.")
md("""
### What EDA decided for us
| Observation | Modeling decision |
|---|---|
| The motor moves between operating ranges | Summarize working share and starts |
| Several measurements describe an hour | Fit a multivariable anomaly detector |
| Missing hours are not normal observations | Keep a separate quality gate |
| Labels are sparse and incomplete | Fit without failure labels; evaluate cautiously against reports |

Hourly aggregation loses short spikes and is available only after the hour finishes. This
is a maintenance-analysis example, not emergency equipment protection. The six features are
calculated consistently in every period. Neither event dates nor future outcomes enter the inputs.

---
# 3 - Model Training
**Question:** Can a detector learn useful structure without examples labeled "failure"?

Fit a simple baseline and a standard anomaly-detection algorithm on the **same six features
and training hours**. Compare their validation results using the same review allowance.
Unlike the CNN, neither model trains by repeatedly correcting a labeled prediction error.

## 3.1 Fit a simple statistical baseline
The **robust-score baseline** learns a median and a variation scale for each feature.
It measures movement in configured trouble directions, then averages the contributions.
This is itself an anomaly detector: training learns its reference values rather than an
operator specifying every numeric limit. It also embeds human choices about which direction matters.
""")
code("""
baseline = detect.RobustZDetector().fit(training)
baseline_validation_scores = baseline.score(validation)
display(pd.DataFrame({"Feature": list(teaching.FEATURE_LABELS.values()),
                      "Learned middle": baseline.median_.round(3).to_numpy(),
                      "Learned scale": baseline.scale_.round(3).to_numpy()}))
""")
md("""
For temperature, the learned middle is about 58.48 C and scale about 4.17 C. An hour at
74.27 C contributes about `(74.27 - 58.48) / 4.17 = 3.79` before averaging with other features.
That is a relative unusualness measure, not a safe-temperature rating or a probability.

## 3.2 Train Isolation Forest
**Isolation Forest** repeatedly partitions reference samples using randomly chosen features
and split values. A point that is separated in relatively few splits is treated as more unusual;
a point embedded among many similar examples tends to require more splits.

Imagine separating one isolated point from a crowded group on the feature plot. The real
model repeats this across many trees and all six inputs. No tree is told "this is a leak."

On the earlier two-feature plot, a point sitting away from the main cloud can often be
separated with few cuts. A point surrounded by many similar hours takes more cuts. The
forest averages that idea across many random trees and all six features.

- **300 trees:** combine many random partitions rather than trusting one.
- **Up to 256 training rows per tree:** small samples keep fitting practical.
- **Fixed seed:** reproduce this classroom run.

There is no CNN-style loss curve here: training constructs a forest, not gradient-based
epochs. The evidence comes from how its scores behave on separate observations.
""")
code("""
forest = IsolationForest(n_estimators=300, max_samples=256,
                         random_state=config.RANDOM_STATE, contamination="auto")
forest.fit(training)
forest_training_scores = pd.Series(-forest.score_samples(training), index=training.index)
forest_validation_scores = pd.Series(-forest.score_samples(validation), index=validation.index)
print(f"Fitted {len(forest.estimators_)} trees on {len(training):,} reference hours, with no target column.")
""")
md("""
Scikit-learn's `score_samples` uses lower values for more unusual points. We negate it so
**higher means more anomalous** throughout the notebook. These values are not probabilities.
`contamination="auto"` does not tell us the real fault rate; we set our own review cutoff
from validation scores rather than use the library's default binary prediction.

## 3.3 Compare the two detectors fairly
The two models use different score scales, so cutoff 6 or cutoff 0.68 cannot mean the same
thing for both. Give each approximately the **highest-scoring 2% of validation hours**.
This is a classroom comparison allowance, not an estimated failure rate or real staffing commitment.
Ties at the cutoff can slightly change the actual share.

Judge reported-event detection first, then false callouts. An event counts as detected if
an alert occurs from 24 hours before its start through six hours after its end. For false
callouts, omit the uncertain buffer from 72 hours before through 24 hours after each event.
Group alert hours no more than six hours apart into one callout. These are evaluation rules,
not recorded technician visits or confirmed diagnoses.
""")
code("""
comparison = teaching.compare_models({
    "Robust-score baseline": baseline_validation_scores,
    "Isolation Forest": forest_validation_scores,
})
display(comparison.round(4))
selected_name = teaching.choose_model(comparison)
assert selected_name == "Isolation Forest", "Review model choice if the comparison changes."
print("Continue with:", selected_name)
""")
md("""
**Read the comparison:** both flag 36 validation hours. Isolation Forest finds three reported
events versus two for the baseline, but creates seven false callouts versus zero. We continue
with Isolation Forest because the stated priority is event detection; the extra review work
is a real trade-off, not something to hide.

**Stage 3 conclusion:** Isolation Forest is the candidate for this worked example, not a
universal winner. The baseline can behave differently at another allowance. Three validation
events on one compressor are far too little evidence for a broad performance claim.

---
# 4 - Model Validation
**Question:** Which anomaly scores trigger review, and what happens on the later test period?

The fraud and image cases turned a model score into an action with a cutoff. We do the same,
but **anomaly score is not failure probability**. A 2% validation review allowance does not
guarantee that 2% of future hours will be flagged.

## 4.1 Draw the cutoff for the selected detector
Every validation hour receives an anomaly score. **Higher means more unusual.** A score by
itself does not trigger anything until we draw a cutoff line. The model comparison already
selected Isolation Forest and the 2% validation review allowance. Now turn that allowance
into one fixed line:

```text
score < cutoff   -> 0, no additional model flag
score >= cutoff  -> 1, flag for human review
```
""")
code("""
cutoff = float(comparison.loc[comparison["Model"] == selected_name, "Comparison cutoff"].iloc[0])
cutoff_figure, cutoff_summary = teaching.score_cutoff_plot(forest_validation_scores, cutoff)
cutoff_figure.show()
display(cutoff_summary)
""")
guide("The x-axis is the actual date in the April-June validation period. The blue line gives one anomaly score for each usable hour. The dashed horizontal line is the cutoff. Red dots are hours at or above it.",
    "Any score above the line becomes model flag 1 and requests review. A score below it becomes flag 0. The table gives the exact rule and counts.",
    "The line converts a score into a review decision. It does not make the score a probability or prove a red point is faulty. Gaps mean that hour lacked a usable score.")
md("""
**Example:** score **0.70** is above cutoff **0.679284**, so it becomes flag 1 and requests
review. Score **0.60** is below the line, so it becomes flag 0. Neither number is a percent.
Choosing another review allowance would move the line. That requires a decision about
maintenance capacity; the test data must not be used to move it.

## 4.2 Check the final rule on later data
We already used February-March to train the models and April-June to select Isolation Forest
and its cutoff. Now apply that finished rule to **July-September** without changing it.

This later period is called the **test period**. It gives a more honest check because the
model and cutoff were decided before these results were viewed. If we changed them after
seeing this table, July-September would become another practice period rather than a final check.

There is only one reported event in this period, so the result is limited evidence.
""")
code("""
test_scores = pd.Series(-forest.score_samples(test_matrix), index=test_matrix.index)
test_result = metrics.evaluate(test_scores, cutoff, (config.TEST_START, config.TEST_END))
display(pd.DataFrame([
    ["Reported event detected", "Yes" if test_result["failures_detected"] else "No"],
    ["Hours flagged for review", f"{test_result['alert_hours']} of {test_result['scored_hours']}"],
    ["Extra grouped alerts against reports", test_result["false_callouts"]],
], columns=["Later-data check", "Result"]))
""")
md("""
**Read the result:** the finished rule detects the one reported event and flags 27 of 1,224
usable hours. Four groups of alerts do not match a nearby event report. Because reports may
be incomplete, those are unmatched alerts to investigate, not proven healthy-machine mistakes.

Do not report overall accuracy: most hours have no event report, so a model that never flags
anything would appear correct most of the time while missing the maintenance purpose.

## 4.3 Read an alert-versus-report table
The earlier classifiers used confusion matrices because they had a label for each example.
Here we can compare flags with report timing, but must not call every unreported hour a
verified true negative. This four-box view is **agreement with reports, not diagnostic accuracy**.

The first row counts usable hours overlapping the reported event. The second counts hours
outside the uncertainty buffer. Other near-event hours are excluded, not quietly labeled normal.
""")
code("""
agreement_figure, excluded_hours = teaching.hourly_agreement(
    test_scores, cutoff, (config.TEST_START, config.TEST_END))
agreement_figure.show()
print(f"Excluded ambiguous near-event hours: {excluded_hours}")
""")
guide("Columns are model flag/no flag; rows are hours overlapping a reported event or outside its uncertainty buffer. Numbers count hours, not separate failures.",
      "A flag outside the buffer is a false alert against the available reports, but might still deserve investigation. No flag during an event is a missed event hour.",
      "Do not calculate a reassuring fault-accuracy percentage from incomplete labels. The event-level check and the workload counts answer different questions.")
md("""
## 4.4 Does the alert help a person?
Two practical questions matter after checking the model:

- **Is there time to respond?** An alert after the problem is over cannot help with that event.
- **Is the extra work manageable?** Too many unnecessary inspections can make people ignore alerts.

For the one reported test event, put the times in order:
""")
code("""
timing = teaching.event_table(test_scores, cutoff, (config.TEST_START, config.TEST_END)).iloc[0]
flagged_hour = pd.Timestamp(timing["First flagged hour"])
display(pd.DataFrame([
    ["First flagged hour begins", flagged_hour],
    ["That hour's score can be available", flagged_hour + pd.Timedelta(hours=1)],
    ["Reported event begins", pd.Timestamp(timing["Reported onset"])],
], columns=["What happened", "Date and time"]))
print(f"Potential notice: {timing['Lead after hour ends (h)']:g} hours, before processing and response delays.")
""")
md("""
**The lesson:** this example leaves **13.5 hours of potential notice** after the hour finishes,
before communication or response delays. It does not prove that every failure can be forecast.
The test also produced **four false callouts against the reports** over about two months.
A maintenance manager must decide whether that review workload is acceptable.

Later, keep checking the number of alerts. A busier operating schedule or changed equipment
can change the data pattern (**drift**). Investigate before changing the cutoff; more alerts
do not by themselves prove more faults.

**Stage 4 takeaway:** an anomaly detector must give useful notice without overwhelming the
people who review its flags. Section 5.1 shows the predictions and reports on one timeline.

---
# 5 - Model Prediction
**Question:** How does one incoming hour become a review request somebody can investigate?

## 5.1 Compare predictions and reported anomalies over time
Use the **same date-and-time axis** to connect the model's score, its prediction, and the
maintenance evidence. This is the fixed Isolation Forest applied to the test period.

The rule is **model flag = 1 when score >= cutoff**, otherwise 0. The cutoff is approximately
**0.679284**, chosen from the validation scores. It is **not a standard-deviation threshold**
and does not mean a 67.9% chance of failure. Missing scores produce no prediction, not zero.

The first view includes both the July 8 high-score example and the July 15 reported event.
"Full test" shows the entire test period. All panels stay aligned when you change the view.
""")
code("""
prediction_figure, prediction_table = teaching.prediction_timeline(
    test_scores, cutoff, (config.TEST_START, config.TEST_END))
prediction_figure.show()
display(prediction_table.loc["2020-07-15 12:00":"2020-07-15 19:00"].round(4))
""")
guide("Top: anomaly score with the dashed cutoff. Middle: predicted flag (1) or no flag (0). Bottom: reported-event overlap (1) or no report for that hour (0). The faint green band is the exact reported event period.",
      "When both lower panels are at 1, the model flags an hour overlapping a reported event. A model flag of 1 with report 0 is an unmatched flag for that hour: it could be advance warning, another problem, or a false alert. Report 1 with model 0 is a missed event hour.",
      "The reports are incomplete labels, not proof of health everywhere they show 0. A gap in the score and prediction panels means no usable score, even if a report exists. This separates what the model predicted from what was documented.")
md("""
**Read the hourly table:** each row uses the same timestamp in all columns. Values are rounded
for display, but the flag is calculated from the full-precision score. Report 1 means the
hour overlaps an event: the July 15 event starts at 14:30, so the 14:00-14:59 row is marked 1.
The score for that hour is only available after 15:00. The report labels are added afterward
for comparison; they are not model inputs. A blank/NaN score means no prediction was made.

### Three example predictions
All examples below are from the test period, unseen during fitting and model choice.
They were selected retrospectively to illustrate behavior, not to estimate accuracy.
""")
code("""
examples = teaching.prediction_examples(test_matrix, test_scores, cutoff)
display(examples[["Example", "Hour", "Anomaly score", "Flag", "Report overlaps hour"]].round(4))
""")
md("""
Keep **score**, **policy decision**, and **observed evidence** separate, just as in the fraud
and pneumonia examples. An unreported high-score hour is not automatically a healthy machine;
an unflagged hour is not certified safe. The detector has found unusualness, not a cause.

## 5.2 Score one hour through the complete pipeline
Replay the highest-scoring test hour. Supply its recorded sensor minutes, compute the same
features, score it with the fitted model, then apply the frozen cutoff. Include one previous
minute so the pressure-change calculation has its usual context. No future hour is used.
""")
code("""
incoming_hour = test_scores.idxmax()
incoming_minutes = minutes.loc[incoming_hour - pd.Timedelta(minutes=1):incoming_hour + pd.Timedelta(minutes=59)]
incoming_features = features.model_matrix(features.hourly_features(incoming_minutes)).loc[[incoming_hour]]
np.testing.assert_allclose(incoming_features, test_matrix.loc[[incoming_hour]], rtol=0, atol=1e-12)
incoming_score = float(-forest.score_samples(incoming_features)[0])
np.testing.assert_allclose(incoming_score, test_scores.loc[incoming_hour], rtol=0, atol=1e-12)
print("Hour:", incoming_hour, "| Score available after:", incoming_hour + pd.Timedelta(hours=1))
print(f"Anomaly score: {incoming_score:.6f}; cutoff: {cutoff:.6f}")
print("Decision:", "Request human review" if incoming_score >= cutoff else "No extra model flag")
""")
md("""
## 5.3 What looked different in this flagged hour?
Isolation Forest combines all six measurements to produce the score. It does not return a
probability or a simple statement that one measurement "caused" the flag. We can still show
the technician what was measured in **real units** and compare it with typical training hours.

The typical range below contains the middle half of training-hour values: after sorting the
training values, 25% are below the range and 25% are above it. It is a descriptive reference,
not an engineering safety limit.
""")
code("""
feature_review = teaching.feature_comparison(training, incoming_features.iloc[0])
display(feature_review)
""")
md("""
**Read the table:** this hour shows 66.7% compressor working time versus a typical training
range of 5.0%-10.0%; six starts versus a typical two to three; only 3.3 minutes of rest per
start versus 18.3-28.5; and 75.7 C oil temperature versus 56.3-62.3 C. Pressure variation
is also higher, while pressure change is within its typical range.

**Key message:** several measurements look different at the same time, so the model requests
review. That combination might come from a leak, heavier workload, a sensor problem, or another
cause. The table helps a technician decide what to inspect; it does not explain the forest's
internal calculation or diagnose the machine.
""")
md("""
## 5.4 What if the hour has almost no readings?
Like the image notebook's quality hold, this path stops ordinary prediction. Removing
readings is a clearly labeled simulation of a recorder problem, not another failure example.
""")
code("""
incomplete_hour = incoming_minutes.loc[incoming_hour:].iloc[:10]
usable_incomplete = features.hourly_features(incomplete_hour)
assert usable_incomplete.empty
print("Only ten minutes supplied: HOLD for data-quality review. No anomaly score produced.")
""")
md("""
## 5.5 Is finding the anomaly worth the review cost?
The model's usefulness is not the same as its event-detection count. Here is a compact
scenario calculation using **invented classroom costs**, not the operator's bills:
400 USD per visit, 1,200 USD per unaddressed fault hour, 22,000 USD interruption after
12 hours, and four hours to respond. Intervention is assumed to shorten a fault, not prevent it.
The calculation uses the selected forest and its cutoff, not the older app's detector.
""")
code("""
later_matrix = matrix.loc[matrix.index >= config.DEV_START]
later_scores = pd.Series(-forest.score_samples(later_matrix), index=later_matrix.index)
cost_rows = []
for label, window in [("Validation + test (retrospective)", (config.DEV_START, config.TEST_END)),
                      ("Test period only", (config.TEST_START, config.TEST_END))]:
    with_alerts = policy.policy_cost(later_scores, cutoff, window)
    no_alerts = policy.never_alert(window)
    cost_rows.append({"Period": label, "Detector (assumed USD)": with_alerts["total_cost_usd"],
                      "No alerts (assumed USD)": no_alerts["total_cost_usd"]})
display(pd.DataFrame(cost_rows))
""")
md("""
Read both rows, not just whichever favors the detector. These estimates depend on assumptions
about response and downtime, plus only four events. They do not establish annual savings.
Scheduled maintenance is another alternative; a real pilot should compare it using measured
visits, outcomes, and costs before any wider rollout.

## 5.6 Hand off the measured model, not just a notebook
| What the application needs | Why |
|---|---|
| Fitted forest and exact feature order | Reproduce the learned scores |
| Minute-to-hour preparation and quality gate | Give the model the same kind of inputs |
| Frozen cutoff and review rule | Keep model output separate from action |
| Evaluation and limitations | State where evidence exists and where it does not |
| Human review process | Confirm faults and record inspection outcomes |

**This notebook now teaches Isolation Forest. The existing app still uses its earlier
robust-score model and policy.** We have not replaced app artifacts or claimed its screens
show this model. That change belongs to the next demo review. The check below verifies the
original saved baseline remains intact while this notebook holds the new forest in memory.
""")
code("""
saved_baseline = joblib.load(config.ARTIFACT_DIR / "model.joblib")
np.testing.assert_allclose(saved_baseline.score(matrix), baseline.score(matrix), rtol=0, atol=0)
teaching_result = {"model": selected_name, "cutoff": cutoff,
                   "validation": comparison.to_dict("records"), "test": test_result}
print("Verified: incoming-hour prediction matches batch scoring; original app baseline unchanged.")
print("Teaching model and its evaluation are ready for the separate demo-design review.")
""")
md("""
### The five stages, and who must be involved
| Stage | Evidence produced | People needed |
|---|---|---|
| Data Ingestion | Profile, missingness, time split | Data engineer and equipment specialist |
| Feature Engineering | Consistent hourly measurements | Data scientist and maintenance planner |
| Model Training | Fitted detectors and validation comparison | Data scientist |
| Model Validation | Event checks, false reviews, timing | Data scientist and maintenance manager |
| Model Prediction | Reviewable alert with measurements | Application engineer and technician |

**What transfers from the earlier cases:** inspect data, build suitable inputs, train on
earlier evidence, validate separately, and keep human authority explicit.
**What changes here:** we learn a reference pattern without failure labels during fitting;
an anomaly flag is a request to investigate, never the answer to "is this machine broken?"
""")


def build() -> nbf.NotebookNode:
    notebook = nbf.v4.new_notebook(cells=cells, metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    })
    if OUTPUT.exists():
        previous = nbf.read(OUTPUT, as_version=4)
        saved = {(cell.cell_type, cell.source): cell for cell in previous.cells}
        for position, cell in enumerate(notebook.cells):
            if (cell.cell_type, cell.source) in saved:
                notebook.cells[position] = saved[(cell.cell_type, cell.source)]
    nbf.validate(notebook)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            compile(cell.source, "notebook cell", "exec")
    return notebook


if __name__ == "__main__":
    notebook = build()
    nbf.write(notebook, OUTPUT)
    print(f"Wrote {OUTPUT.name}: {len(notebook.cells)} cells; "
          f"{sum(cell.cell_type == 'code' for cell in notebook.cells)} code cells")