"""Build the five-stage anomaly notebook; do not replace the separate app model.

Revised 2026-09-18 after the instructor's flow review for undergraduates with
little data-science background. Changes against the 2026-09-16 walkthrough:
a physics story opens the feature stage; the seven months are shown as one
timeline with the four leaks marked; a raw-signal day comparison lets students
see a leak before any feature exists; the baseline's internals and the
scikit-learn parameter notes are cut; the review line is named once; a
scorecard adds the practice-month and final-check results together; the cost
check moves into validation and shows the final check only; the worked
prediction scores the F4 warning hour; the app-artifact check is gone.
"""
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

| Stage | Question it answers |
|---|---|
| 1. Data Ingestion | What data do we have, what can we trust, and how are the months split? |
| 2. EDA and Feature Engineering | Which six numbers describe one hour, and why those six? |
| 3. Model Training | Can a detector learn "normal" without failure labels? |
| 4. Model Validation | Where do we draw the review line, and does it hold on later months? |
| 5. Model Prediction | How does one new hour become a review request a person can act on? |

### The case
A compressor supplies compressed air. Leaks can make it work harder and run hotter. A
maintenance planner wants to inspect unusual operation without sending technicians to every
ordinary fluctuation. We use a train compressor; factories face a similar equipment-monitoring task.

### The data
- **MetroPT-3:** real sensor readings from one Metro do Porto train compressor in 2020.
- Roughly **1.5 million raw readings**, summarized into a local one-minute file.
- **Four reported air-leak events**, not a reliable normal/fault label for every reading.
- Public dataset, **CC BY 4.0**; no downloads during the notebook run.

### Three names to keep straight
- **Learn** (February-March, the *training* months): the detector learns what a normal hour looks like.
- **Practice** (April-June, the *validation* months): we compare detectors and choose the review line.
- **Final check** (July-September, the *test* months): the finished rule runs once, unchanged.

> An **anomaly** is unusual relative to the pattern a detector learned. It might be a fault,
> a workload change, or a sensor problem. **Anomaly does not mean confirmed failure.**
> The model requests human review. It does not diagnose a leak, stop equipment, or certify safety.
""")
code("""
import numpy as np
import pandas as pd
from IPython.display import display
from plotly.offline import init_notebook_mode
from sklearn.ensemble import IsolationForest
from pdmlab import config, data, detect, features, metrics, policy, teaching

init_notebook_mode(connected=False)
pd.set_option("display.max_columns", 8)
print("Local data ready. The detector will learn from February-March; later months stay separate.")
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
Use the learning months here, not later outcomes. Current gives us a readable first
view of when the motor is off, idling, or working hard.
""")
code("""
teaching.current_distribution(minutes).show()
""")
guide("Horizontal position is motor current; bar height counts recorded learning-month minutes in that range. The dashed line is 4.75 A.",
      "The readings cluster around low current, an idling range, and a higher working range. One low reading is not automatically a failure.",
      "We can summarize time spent working instead of asking a model to interpret every minute. The 4.75 A feature setting is specific to this dataset, not a safety limit.")
md("""
## 1.5 See one leak with your own eyes
Before any feature or model, look at the raw readings. The left column is an ordinary
February day. The right column is April 18, the first documented air leak. Same three
sensors, same scale, one day each.
""")
code("""
teaching.day_comparison(minutes).show()
""")
guide("Each row is one sensor; each column is one day. The x-axis is the hour of the day. Rows share a vertical scale, so the two days can be compared directly.",
      "On the normal day the current jumps up and drops back all day: short working bursts with rest between them, oil around 57 C. On the leak day the current stays high all day, the oil runs about 74 C, and panel pressure sits low and never climbs back to 10 bar.",
      "A leak does not look like a spike. It looks like a machine that never gets to stop. Every feature we build in Stage 2 is a way of writing that sentence as a number.")
md("""
## 1.6 Split the seven months: learn, practice, final check
Keep the same separation used in the earlier notebooks, but split **by time**. Nearby hours
resemble each other; shuffling them could let later operating patterns leak into learning.

| Months | Plain name | Technical name | What it may influence |
|---|---|---|---|
| February-March | Learn | Training / reference | The patterns the detector learns |
| April-June | Practice | Validation | Detector comparison and the review line |
| July-September | Final check | Test | Evaluation after every choice is frozen |
""")
code("""
teaching.period_timeline().show()
""")
guide("The bar is the seven-month record. Shading marks the three periods. Diamonds mark when each documented air leak was reported.",
      "No leak was reported in the learning months. Three leaks fall in the practice months, so the detector comparison has something to check against. One leak, F4, falls in the final check.",
      "The review line is chosen on the practice months and frozen before July. That is what makes July-September an honest check rather than another round of practice. The learning months may still contain unreported problems.")
md("""
**Stage 1 conclusion:** we have a time-indexed sensor table, a quality gate, four event
reports, and three time periods. We do not have enough labels to treat every unreported
hour as a confirmed normal example, and we have seen with our own eyes what a leak does.

---
# 2 - EDA and Feature Engineering
**Question:** Which measurements should describe one hour to the anomaly detector, and why those?

### The physics first, then the features write themselves
Understand what a leak does and the features follow. Each sentence below becomes a number.

1. **Air escapes.** A leak develops somewhere in the compressed-air system.
2. **Pressure falls faster.** The tank empties sooner than it should after each working burst.
3. **The compressor restarts sooner.** It rests less between bursts and works for longer.
4. **It runs hot.** A machine that never rests heats up and stays hot.

| Sentence in the story | Numbers that measure it |
|---|---|
| Pressure falls faster | Pressure variation, Pressure change |
| The compressor restarts sooner | Compressor working (%), Starts per hour, Rest per start |
| It runs hot | Oil temperature |

Like the fraud case, we create human-named features. Unlike the CNN, this model does not
learn directly from pixels or the raw time series. **One model row will be one usable hour.**
This version uses three source columns, motor current, oil temperature, and TP3 pressure,
to create six understandable features. The other columns remain available for future experiments.

## 2.1 Turn minute readings into six features
""")
code("""
hourly = features.hourly_features(minutes)
matrix = features.model_matrix(hourly)
training = matrix.loc[(matrix.index >= config.TRAIN_START) & (matrix.index < config.TRAIN_END)]
validation = matrix.loc[(matrix.index >= config.DEV_START) & (matrix.index < config.DEV_END)]
test_matrix = matrix.loc[(matrix.index >= config.TEST_START) & (matrix.index < config.TEST_END)]
print(f"{recorded_minutes:,} recorded minutes -> {len(matrix):,} usable hours -> {matrix.shape[1]} inputs")
display(pd.DataFrame({"Period": ["Learn (training)", "Practice (validation)", "Final check (test)"],
                      "Usable hours": [len(training), len(validation), len(test_matrix)]}))
""")
md("""
| Input feature | What it describes | Story step |
|---|---|---|
| Compressor working (%) | Percentage of recorded minutes spent working hard | Restarts sooner |
| Starts per hour | Transitions into working hard, not total running time | Restarts sooner |
| Rest per start | Nonworking time estimated from working share and starts | Restarts sooner |
| Oil temperature | Average oil temperature during the hour | Runs hot |
| Pressure variation | How much panel pressure varies during the hour | Pressure falls faster |
| Pressure change | Size of the average panel-pressure change during nonworking minutes | Pressure falls faster |

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
      "The February hour has 4/60 working minutes, or 6.7%; the April leak hour has 60/60, or 100%.",
      "That working pattern becomes one feature. Zero starts can occur during continuous operation, so starts alone do not tell us whether the motor is off.")
md("""
## 2.3 Look at combinations, not one cutoff per sensor
The pneumonia notebook plotted brightness against contrast. Here plot working share against
temperature: **one point is one hour**. Show the learning months and the April leak as
an exploratory practice-month example. The six-dimensional model will see more than these two inputs.
""")
code("""
teaching.feature_cloud(training, validation).show()
""")
guide("Each dot is one hour. Moving right means the compressor worked hard for a larger percentage of its recorded minutes; moving up means hotter oil. For a complete hour, 50% means 30 of 60 minutes. Symbols distinguish learning-month hours from reported-leak hours.",
      "Many learning-month hours gather in common operating regions. The April hours sit near continuous operation at high temperatures, but there can be overlap.",
      "Anomaly detection asks whether a combination is unusual relative to what was learned. These two axes do not establish a fault boundary, and the report labels are not supplied during fitting.")
md("""
### What EDA decided for us
| Observation | Modeling decision |
|---|---|
| A leak looks like a machine that never stops | Measure working share, starts, and rest |
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
and learning-month hours**. Compare their practice-month results using the same review allowance.
Unlike the CNN, neither model trains by repeatedly correcting a labeled prediction error.

## 3.1 Fit a simple baseline: a ruler
The **robust-score baseline** is a ruler. For each of the six numbers it learns the usual
middle and the usual spread from the learning months, then asks of every new hour: how far
from the middle, in units of spread, in the direction that means trouble? Average the six
answers and that is the score. It is an anomaly detector, and a person can check its arithmetic.
""")
code("""
baseline = detect.RobustZDetector().fit(training)
baseline_validation_scores = baseline.score(validation)
print(f"Baseline learned a middle and a spread for {len(baseline.median_)} features from {len(training):,} learning-month hours.")
""")
md("""
## 3.2 Train Isolation Forest
**Isolation Forest** takes a different route to the same question. Picture the cloud of
learning-month hours from Section 2.3. Draw random cuts across it. A point sitting alone,
away from the crowd, gets separated by a few cuts; a point deep inside the crowd needs many.
The forest repeats that with many random trees across all six features and averages how
easily each hour was isolated. **No tree is ever told "this is a leak."**

There is no CNN-style training curve here: fitting builds the trees, and the evidence comes
from how the scores behave on hours the forest has not seen.
""")
code("""
forest = IsolationForest(n_estimators=300, max_samples=256,
                         random_state=config.RANDOM_STATE, contamination="auto")
forest.fit(training)
forest_training_scores = pd.Series(-forest.score_samples(training), index=training.index)
forest_validation_scores = pd.Series(-forest.score_samples(validation), index=validation.index)
print(f"Fitted {len(forest.estimators_)} trees on {len(training):,} learning-month hours, with no target column.")
""")
md("""
We flip the sign of the library's score so that **higher means more unusual** for both
detectors throughout the notebook. Neither score is a probability.

## 3.3 Compare the two detectors fairly
The two detectors use different score scales, so one number cannot serve as the line for
both. Give each the same allowance instead: the **highest-scoring 2% of practice-month
hours** are flagged. The score at that point is each detector's **review line** (the table
calls it the comparison cutoff). This is a classroom allowance, not a failure rate or a staffing plan.

Judge reported-event detection first, then extra callouts. A leak counts as flagged if any
hour from 24 hours before its reported start through six hours after its end is flagged.
Flagged hours no more than six hours apart are grouped into one callout, and callouts far
from any report count as extra. These are evaluation rules, not technician visits or diagnoses.
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
**Read the comparison:** both flag 36 practice-month hours. Isolation Forest flags all three
reported leaks versus two for the baseline, but creates seven extra callouts versus zero. We
continue with Isolation Forest because the stated priority is finding leaks; the extra review
work is a real trade-off, not something to hide.

**Stage 3 conclusion:** Isolation Forest is the candidate for this worked example, not a
universal winner. The baseline can behave differently at another allowance. Three practice-month
leaks on one compressor are far too little evidence for a broad performance claim.

---
# 4 - Model Validation
**Question:** Which anomaly scores trigger review, and what happens on the final-check months?

The fraud and image cases turned a model score into an action with a cutoff. We do the same,
but **anomaly score is not failure probability**. A 2% practice-month allowance does not
guarantee that 2% of future hours will be flagged.

## 4.1 Freeze the review line for the selected detector
Every practice-month hour has an anomaly score. **Higher means more unusual.** A score by
itself does not trigger anything until a line is drawn. The comparison in 3.3 already gave
Isolation Forest its 2% line. Now it is the one fixed rule:

```text
score < line   -> 0, no model flag
score >= line  -> 1, flag for human review
```
""")
code("""
cutoff = float(comparison.loc[comparison["Model"] == selected_name, "Comparison cutoff"].iloc[0])
cutoff_figure, cutoff_summary = teaching.score_cutoff_plot(forest_validation_scores, cutoff)
cutoff_figure.show()
display(cutoff_summary)
""")
guide("The x-axis is the actual date in the April-June practice months. The blue line gives one anomaly score for each usable hour. The dashed horizontal line is the review line. Red dots are hours at or above it.",
    "Any score above the line becomes model flag 1 and requests review. A score below it becomes flag 0. The table gives the exact rule and counts.",
    "The line converts a score into a review decision. It does not make the score a probability or prove a red point is faulty. Gaps mean that hour lacked a usable score.")
md("""
**Example:** score **0.70** is above the line at **0.679284**, so it becomes flag 1 and requests
review. Score **0.60** is below the line, so it becomes flag 0. Neither number is a percent.
Choosing another allowance would move the line. That requires a decision about maintenance
capacity, and the final-check months must never be used to move it.

## 4.2 Run the frozen rule on the final-check months
February-March taught the detectors and April-June chose Isolation Forest and its line.
Now apply that finished rule to **July-September** without changing anything.

This is the honest check, because the detector and the line were fixed before these results
were viewed. If we changed them after seeing this table, July-September would become another
round of practice. There is only one reported leak in this period, so the result is limited evidence.
""")
code("""
test_scores = pd.Series(-forest.score_samples(test_matrix), index=test_matrix.index)
test_result = metrics.evaluate(test_scores, cutoff, (config.TEST_START, config.TEST_END))
display(pd.DataFrame([
    ["Reported leak flagged", "Yes" if test_result["failures_detected"] else "No"],
    ["Hours flagged for review", f"{test_result['alert_hours']} of {test_result['scored_hours']}"],
    ["Extra callouts (no matching report)", test_result["false_callouts"]],
], columns=["Final check", "Result"]))
""")
md("""
**Read the result:** the frozen rule flags the one reported leak and flags 27 of 1,224
usable hours. Four groups of flagged hours have no matching report. Because reports may
be incomplete, those are extra callouts to investigate, not proven healthy-machine mistakes.

Do not report overall accuracy: most hours have no event report, so a model that never flags
anything would appear correct most of the time while missing the maintenance purpose.

## 4.3 Read an alert-versus-report table
The earlier classifiers used confusion matrices because they had a label for each example.
Here we can compare flags with report timing, but must not call every unreported hour a
verified true negative. This four-box view is **agreement with reports, not diagnostic accuracy**.

The top row counts hours inside the reported leak. The bottom row counts hours well away
from it. Hours close to the leak, where a report might simply be late or early, are left out
rather than quietly labeled normal.
""")
code("""
agreement_figure, excluded_hours = teaching.hourly_agreement(
    test_scores, cutoff, (config.TEST_START, config.TEST_END))
agreement_figure.show()
print(f"Hours left out because they sit close to the reported leak: {excluded_hours}")
""")
guide("Columns are model flag/no flag; rows are hours inside the reported leak or well away from it. Numbers count hours, not separate leaks.",
      "A flag well away from any report is an extra callout against the available reports, but might still deserve investigation. No flag during a leak is a missed leak hour.",
      "Do not calculate a reassuring accuracy percentage from incomplete labels. The leak-level check and the workload counts answer different questions.")
md("""
## 4.4 Does the alert help a person?
Two practical questions matter after checking the model:

- **Is there time to respond?** An alert after the problem is over cannot help with that event.
- **Is the extra work manageable?** Too many unnecessary inspections can make people ignore alerts.

For the one reported leak in the final check, put the times in order:
""")
code("""
timing = teaching.event_table(test_scores, cutoff, (config.TEST_START, config.TEST_END)).iloc[0]
flagged_hour = pd.Timestamp(timing["First flagged hour"])
display(pd.DataFrame([
    ["First flagged hour begins", flagged_hour],
    ["That hour's score can be available", flagged_hour + pd.Timedelta(hours=1)],
    ["Leak reported", pd.Timestamp(timing["Reported onset"])],
], columns=["What happened", "Date and time"]))
print(f"Potential notice: {timing['Lead after hour ends (h)']:g} hours, before processing and response delays.")
""")
md("""
**The lesson:** this example leaves **13.5 hours of potential notice** after the hour finishes,
before communication or response delays. It does not prove that every failure can be forecast.
The final check also produced **four extra callouts** over about two months.
A maintenance manager must decide whether that review workload is acceptable.

## 4.5 The scorecard: add it all up
The practice months held three leaks and the final check held one. Put the two checks
together and read the result as two different questions: did the detector notice each leak
at all, and did it notice before anyone wrote the leak down?
""")
code("""
display(teaching.scorecard(forest_validation_scores, test_scores, cutoff))
""")
md("""
**Read the scorecard:** all four leaks were flagged while they were happening. Only one, F4,
was flagged before it was reported. For F1 and F2 the first flag came about seven hours after
the report; for F3 the flagged hour is the hour the leak was reported, so its score exists
after the report. Finding a leak and warning about a leak are different achievements, and
this detector has strong evidence for the first and one example of the second.

Remember which months are which: F1-F3 sit in the practice months, which were used to choose
the detector and the line, so those three are partly self-fulfilling. F4 is the only leak in
months the detector never saw during selection, which is why it is the number the deck treats as real evidence.

## 4.6 Is finding the anomaly worth the review cost?
The model's usefulness is not the same as its leak count. Here is a compact scenario
calculation on the final-check months using **invented classroom costs**, not the operator's
bills: 400 USD per visit, 1,200 USD per unaddressed fault hour, 22,000 USD interruption after
12 hours, and four hours to respond. Intervention is assumed to shorten a fault, not prevent it.
""")
code("""
final_window = (config.TEST_START, config.TEST_END)
with_alerts = policy.policy_cost(test_scores, cutoff, final_window)
no_alerts = policy.never_alert(final_window)
display(pd.DataFrame([
    ["Run the detector and review its flags", with_alerts["total_cost_usd"]],
    ["Never alert", no_alerts["total_cost_usd"]],
], columns=["Policy on the final-check months", "Assumed cost (USD)"]))
""")
md("""
**Read both rows.** Under these assumptions the detector costs more on the final check than
never alerting, because four extra callouts are priced and only one leak was there to shorten.
That is the honest number and it stays visible. It depends on invented costs and a single leak,
so it does not establish savings or losses; a real pilot would compare scheduled maintenance
too, using measured visits, outcomes, and costs.

Later, keep checking the number of alerts. A busier operating schedule or changed equipment
can change the data pattern (**drift**). Investigate before changing the line; more alerts
do not by themselves prove more faults.

**Stage 4 takeaway:** an anomaly detector must give useful notice without overwhelming the
people who review its flags. Section 5.1 shows the predictions and reports on one timeline.

---
# 5 - Model Prediction
**Question:** How does one incoming hour become a review request somebody can investigate?

## 5.1 Compare predictions and reported anomalies over time
Use the **same date-and-time axis** to connect the model's score, its prediction, and the
maintenance evidence. This is the frozen Isolation Forest applied to the final-check months.

The rule is **model flag = 1 when score >= line**, otherwise 0. The line is approximately
**0.679284**, chosen from the practice-month scores. It is **not a standard-deviation threshold**
and does not mean a 67.9% chance of failure. Missing scores produce no prediction, not zero.

The first view includes both the July 8 high-score example and the July 15 reported leak.
"Full test" shows the entire final-check period. All panels stay aligned when you change the view.
""")
code("""
prediction_figure, prediction_table = teaching.prediction_timeline(
    test_scores, cutoff, (config.TEST_START, config.TEST_END))
prediction_figure.show()
display(prediction_table.loc["2020-07-15 12:00":"2020-07-15 19:00"].round(4))
""")
guide("Top: anomaly score with the dashed review line. Middle: predicted flag (1) or no flag (0). Bottom: reported-leak overlap (1) or no report for that hour (0). The faint green band is the exact reported leak period.",
      "When both lower panels are at 1, the model flags an hour overlapping a reported leak. A model flag of 1 with report 0 is an unmatched flag for that hour: it could be advance warning, another problem, or an extra callout. Report 1 with model 0 is a missed leak hour.",
      "The reports are incomplete labels, not proof of health everywhere they show 0. A gap in the score and prediction panels means no usable score, even if a report exists. This separates what the model predicted from what was documented.")
md("""
**Read the hourly table:** each row uses the same timestamp in all columns. Values are rounded
for display, but the flag is calculated from the full-precision score. Report 1 means the
hour overlaps a leak: the July 15 leak starts at 14:30, so the 14:00-14:59 row is marked 1.
The score for that hour is only available after 15:00. The report labels are added afterward
for comparison; they are not model inputs. A blank/NaN score means no prediction was made.

### Three example predictions
All examples below are from the final-check months, unseen during fitting and model choice.
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
The July 8 hour is the question to leave with students: high score, no report. Advance warning
of something never written down, another problem, or an extra callout? Only an inspection can say.

## 5.2 Score one hour through the complete pipeline
Replay the hour that gave the F4 warning: the 00:00 hour of July 15, the first flagged hour
from Section 4.4. Supply its recorded sensor minutes, compute the same six features, score
them with the fitted forest, then apply the frozen line. Include one previous minute so the
pressure-change calculation has its usual context. No future hour is used.
""")
code("""
incoming_hour = flagged_hour
incoming_minutes = minutes.loc[incoming_hour - pd.Timedelta(minutes=1):incoming_hour + pd.Timedelta(minutes=59)]
incoming_features = features.model_matrix(features.hourly_features(incoming_minutes)).loc[[incoming_hour]]
np.testing.assert_allclose(incoming_features, test_matrix.loc[[incoming_hour]], rtol=0, atol=1e-12)
incoming_score = float(-forest.score_samples(incoming_features)[0])
np.testing.assert_allclose(incoming_score, test_scores.loc[incoming_hour], rtol=0, atol=1e-12)
print("Hour:", incoming_hour, "| Score available after:", incoming_hour + pd.Timedelta(hours=1))
print(f"Anomaly score: {incoming_score:.6f}; review line: {cutoff:.6f}")
print("Decision:", "Request human review" if incoming_score >= cutoff else "No model flag")
""")
md("""
## 5.3 What looked different in this flagged hour?
Isolation Forest combines all six measurements to produce the score. It does not return a
probability or a simple statement that one measurement "caused" the flag. We can still show
the technician what was measured in **real units** and compare it with typical learning-month hours.

The typical range below contains the middle half of learning-month values: after sorting the
values, 25% are below the range and 25% are above it. It is a descriptive reference,
not an engineering safety limit.
""")
code("""
feature_review = teaching.feature_comparison(training, incoming_features.iloc[0])
display(feature_review)
""")
md("""
**Read the table:** at midnight, more than fourteen hours before anyone reported the leak,
this hour shows 35% compressor working time versus a typical 5%-10%; seven starts versus a
typical two to three; only 5.6 minutes of rest per start versus 18.3-28.5; 71.9 C oil
temperature versus 56.3-62.3 C; and pressure changing about four times faster than usual while
the machine rested. Read that against the story in Stage 2: pressure falling faster, restarting
sooner, running hot. All three sentences are already visible in the numbers.

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
## 5.5 Hand off the measured model, not just a notebook
| What the application needs | Why |
|---|---|
| Fitted forest and exact feature order | Reproduce the learned scores |
| Minute-to-hour preparation and quality gate | Give the model the same kind of inputs |
| Frozen review line and rule | Keep model output separate from action |
| Evaluation and limitations | State where evidence exists and where it does not |
| Human review process | Confirm faults and record inspection outcomes |

### The five stages, and who must be involved
| Stage | Evidence produced | People needed |
|---|---|---|
| Data Ingestion | Profile, missingness, time split | Data engineer and equipment specialist |
| Feature Engineering | Consistent hourly measurements | Data scientist and maintenance planner |
| Model Training | Fitted detectors and practice-month comparison | Data scientist |
| Model Validation | Leak checks, extra callouts, timing, scorecard | Data scientist and maintenance manager |
| Model Prediction | Reviewable alert with measurements | Application engineer and technician |

**What transfers from the earlier cases:** inspect data, build suitable inputs, learn from
earlier evidence, check separately, and keep human authority explicit.
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
