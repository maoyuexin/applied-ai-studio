# From a complaint letter to the right specialist team

Teaching notebook for **ITAI 2372 · Module 4**. It follows the same five-stage structure as
the fraud, pneumonia, and credit-risk labs, on a new modality: real consumer complaints
written in English, routed to one of eight specialist queues.

| | Stage | What happens |
|---|---|---|
| 1 | **Ingestion and Provenance** | Where the complaints come from, what one row means, what was sampled |
| 2 | **EDA and Text Preparation** | Team imbalance, the duplicate-letter discovery, and TF-IDF by hand |
| 3 | **Model Training** | Baseline, the deployed model, and a matched comparison against a transformer |
| 4 | **Validation and Operating Policy** | Per-team results, the confidence rule, one frozen test scoring |
| 5 | **Prediction, Routing Words and Handoff** | Three complaints end to end, then the exported contract |
| 6 | **Optional LLM comparison** | Two examples, then a matched 32-complaint comparison using a captured Copilot run |

## Boundary

**The model routes; it never judges whether a complaint is valid.** It decides which queue a
complaint enters first. It does not decide whether the consumer is right, what the company
owes, or how the case ends. A wrong route costs days on a regulatory clock; a person still
reads every complaint, and complaints the model is unsure about go to a human triage queue
rather than to a guess.

## Run it

In a Codespace, open `01_complaint_build.ipynb`, select `.venv/bin/python`, and run all
cells. Everything it needs is committed: the complaint splits, the precomputed transformer
embeddings, and the screened demo complaints. **No download, no API key, no network** — the
transformer comparison in stage 3 reads embeddings from a parquet rather than loading a
model.

Locally, from the repository root:

```bash
npm run setup:notebook
node scripts/venv-python.mjs -m pip install -r notebooks/complaint-routing/requirements-visuals.txt
```

The second command installs `wordcloud==1.9.4` for generating the word-cloud images.
Run it once in an existing Codespace too. Viewing the saved notebook or HTML needs no
new package installation; the PNG images are embedded.

Then open the notebook with the `.venv` interpreter. A full run takes about **40 seconds**
on CPU, including training, the representation comparison, artifact export, and the reload
check.

## Simple teaching visuals

Section 2.6 shows two dense word clouds for real training complaint **10158370**,
labeled Credit cards. The consumer describes a canceled flight and a refund that the
card company has not returned. This fixed example was selected for an understandable
issue, not for a model-performance comparison. The first cloud sizes terms by count; the second
uses TF-IDF weights fitted on the 40,729 training complaints with the existing vectorizer
settings. No validation or test text is used. Both show the union of the top 40 count
terms and top 40 weighted terms (50 distinct terms in this example). `refund` leads
the counts; `airline`, `flight`, and `card company` receive strong TF-IDF weights.

The display hides filler words, numbers, and `XXXX` redactions only; the classifier's
preprocessing is unchanged. `WordCloud.generate_from_frequencies` packs the terms into
PNG images with seed 42. Text size is approximate, since layout also affects it; position
and color have no data meaning. These are not classifier confidence scores or reasons.
The source values are retained in the Plotly figure's metadata for inspection, not printed
over the cloud. No model or LLM artifacts are altered when generating this illustration.

Section 4.3 contrasts **coverage** with **recall** using 20 invented complaints:
16 automatic routes / 20 arrivals = 80% coverage, whereas 3 correctly labeled mortgage
complaints / 5 actual mortgage complaints = 60% recall. The example uses the existing
policy and metric functions. Recall is computed on model labels before the confidence
cutoff, just like the per-team table. Changing only the cutoff changes coverage, not
those fixed labels. All complaints still receive human handling after the routing step.

The frozen test output prints the actual arithmetic: 6,833 / 8,728 = 78.3% coverage,
with 1,895 sent to human triage. The 89.7% accuracy among automatic routes answers a
different question. No trained models, policies, data splits, or LLM captures changed.

Run the visual checks with:

```bash
node scripts/venv-python.mjs -m pytest notebooks/complaint-routing/tests/test_teaching_visuals.py -q
```

## Optional LLM comparison

The notebook now has **109 cells, 51 code cells, and 11 charts**. Stage 6 is separate
from the deployed TF-IDF classifier and 0.55 policy. It compares `gpt-5.4` with that
classifier on 32 fixed test complaints, four per recorded team. Both receive the full
narrative; the LLM receives team definitions but no known label or baseline answer.

Leave `LIVE_LLM = False` for the captured, offline run. It needs no SDK authentication.
Replay checks prompt/sample fingerprints and the baseline's class-ordered predictions,
so an equivalent regenerated model is accepted even if joblib bytes differ.

For live mode, install the optional dependency from the repository root:

```bash
node scripts/venv-python.mjs -m pip install "github-copilot-sdk==1.0.8"
```

Authenticate the GitHub Copilot CLI and ensure `gpt-5.4` is available, then set
`LIVE_LLM = True`. Each run sends 32 public publisher-redacted narratives to Copilot
and consumes plan usage. Never substitute private complaints. Each request has a fresh,
no-tools session; no workspace context, memory, or persistent session store is used.
Missing credentials or model access produce an error; individual failed/invalid answers
are counted, not silently replaced with successful captured responses.

To explicitly replace the saved capture, from the repository root:

```bash
node scripts/venv-python.mjs notebooks/complaint-routing/scripts/capture_llm_comparison.py
```

This writes only `data/llm_comparison.json`, never the deployed artifacts. Preserve an
earlier capture before replacing it when comparing runs. The saved first run is
`data/llm_comparison_first_run.json`. The current two-run history is disclosed in the
notebook: first 22/32 usable correct answers with 4 rejections, then 25/32 with 2
rejections after adding raw-response logging; the prompt/sample/checks stayed fixed.
TF-IDF matched 24/32 in both runs. The second run returned the recorded team for 26/32
before quotation checks. Median second-run time was about 2.46 seconds for the LLM
versus 0.00083 seconds for TF-IDF, excluding SDK startup/model loading.

These are small-sample results, not proof of superiority. Invalid quotations can reflect
spacing changes rather than invented information. Raw answers, rejection reasons, and
available token counts are retained in the current capture. Token counts are not dollar
costs. Label-only accuracy is distinguished from usable-answer accuracy, and a generated
rationale is not a verified explanation of the LLM's internal computation.

Focused offline tests:

```bash
node scripts/venv-python.mjs -m pytest notebooks/complaint-routing/tests/test_llm_comparison.py -q
```

To regenerate the notebook source, or to produce the app artifacts without touching the
notebook outputs:

```bash
node scripts/venv-python.mjs notebooks/complaint-routing/scripts/build_notebook.py
node scripts/venv-python.mjs notebooks/complaint-routing/scripts/prepare_app_artifacts.py
```

## Package layout

```text
01_complaint_build.ipynb   Executed teaching notebook
complaintlab/              Shared config, data, text prep, models, metrics, charts, handoff
  config.py                paths, the frozen spike decisions, and every constant
  data.py                  loading the committed splits, provenance, the dedupe evidence
  text_prep.py             TF-IDF settings and the worked example that explains them
  models.py                baseline, the deployed pipeline, the matched comparison
  metrics.py               per-team tables, confusion, and the confidence policy
  charts.py                every Plotly figure
  explain.py               routing words, team probabilities, the per-complaint card
  handoff.py               the five artifacts a service consumes, and the reload check
data/                      Committed parquet: 3 complaint splits + 2 embedding files
artifacts/                 Written by the notebook, gitignored
backup/                    Standalone offline HTML
scripts/                   Dataset, embedding, notebook, artifact, and backup builders
```

**Every visible notebook cell is short.** Anything longer lives in `complaintlab`. The course
is about business judgement, not programming.

## The data

**58,185 real consumer complaints** from the
[CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/),
a US federal agency's public record of complaints against financial companies. Complaints
received 2023 or later, each carrying a narrative the consumer wrote. US Government public
data — no copyright, free to use and redistribute.

Split 70 / 15 / 15 stratified by team with seed 42: 40,729 train, 8,728 validation, 8,728
test.

Three properties of this data are teaching material in their own right:

- **Narratives are opt-in.** Only about 22% of complaints carry one, because the consumer
  must consent to publication. The model learned the language of that minority.
- **Personal details were removed by the publisher**, not by us — the `XXXX` blocks visible
  in every narrative are the CFPB's redactions.
- **41.5% of narratives in the window were exact duplicates.** Credit-repair services file
  the same template letter for thousands of consumers; one letter appears 27,496 times. They
  are removed *before* the split is drawn. The first build of this dataset skipped that step
  and reported 84.3% test accuracy where the honest number was 81.9%.

Credit reporting was capped at 1.5× the second-largest team before sampling. In the real
window it is 4.8× debt collection, and without the cap the smaller teams never get enough
examples. That is a disclosed classroom choice: the team shares in this lab are not the
real-world mix.

To rebuild the splits from a bulk file you downloaded yourself (the 1.42 GB zip is never
fetched at setup or in class):

```bash
python scripts/build_dataset.py /path/to/complaints.csv.zip   # rebuild
python scripts/build_dataset.py                               # verify what is committed
```

Rebuilding against a newer bulk file will not reproduce the committed rows — the CFPB adds
hundreds of thousands of complaints a month.

## The transformer comparison, offline by construction

Stage 3 compares two ways of turning a complaint into numbers, on **matched data**: the same
15,000 training complaints (stratified, seed 42) and the same 8,728 validation complaints,
with the same `LogisticRegression`. Only the representation changes.

The MiniLM (`all-MiniLM-L6-v2`) embeddings are precomputed and committed as float16 parquet,
so class needs no 183 MB download and no GPU:

```bash
python scripts/build_embeddings.py           # regenerate (downloads the model once)
python scripts/build_embeddings.py --check   # verify the committed files
```

On matched data the transformer does **not** win here. Long domain-specific complaints get
truncated at 256 tokens, and routing hinges on vocabulary that word counts capture directly.
The lab teaches it as a representation trade, not an upgrade — and the deployed model is the
one that can show a triage clerk which words caused each route.

## What the notebook exports

```text
artifacts/
  model.joblib             the fitted TF-IDF + logistic regression pipeline
  model_card.json          intended use, provenance, measured results, limitations
  evaluation.json          split counts, dedupe stats, both leaderboards, sweep, frozen test
  operating_policy.json    the 0.55 confidence rule, both routes, the boundary statement
  sample_manifest.parquet  60 held-out complaints with predictions, routes, routing words
```

The final cells reload `model.joblib` from disk and require the probabilities to match **bit
for bit** — on the 60 manifest complaints and on a fixed 500-complaint slice of the test
split, checked against a SHA-256 digest recorded in `evaluation.json`.

## Measured results

Frozen model and threshold, test split scored once:

| Measure | Value |
|---|---|
| Accuracy | 82.1% |
| Macro-F1 | 0.810 |
| Coverage (auto-routed share) | 78.3% |
| Accuracy among auto-routed | 89.7% |
| Sent to human triage | 1,895 of 8,728 (21.7%) |

Against a majority-class baseline of 30.5% accuracy and 0.059 macro-F1.
