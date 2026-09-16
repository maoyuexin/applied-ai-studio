# Procedure Assistant Lab — Grounded Answers with Citations

ITAI 2372 Module 5, Case 2. Instructor-led demonstration; students rerun later in Codespaces.

## Undergraduate RAG walkthrough (2026-09-16)

The classroom notebook now has **23 cells, 11 code cells, one retrieval chart, and about
1,150 words** of explanation. It follows one permit-retention question through five stages:
choose sources, prepare/index, retrieve, generate, and check.

The teaching path selects **three short public regulatory paragraphs** from the existing
date-pinned corpus. Students see the original text, source citations, searchable chunks,
retrieved passages, the exact LLM instruction and prompt, a generated answer and quote,
then five small example checks. These examples are not a held-out benchmark.

Generation is real: `data/teaching_llm_capture.json` records five tool-disabled **gpt-5.4**
responses. The default is offline replay of those exact responses, with live local retrieval.
Replay verifies the instruction, model, sources, question, retrieved text, and quoted evidence.
A changed question or retrieval result cannot silently reuse an old answer.

Set `LIVE_GENERATION = True` for new questions. This requires internet access, an existing
Copilot sign-in and `github-copilot-sdk==1.0.8`; usage may consume the account's allowance.
Live requests fail explicitly rather than silently substituting a captured response.
The model has no tools, file access, MCP servers, persistent memory, or permission to act.

**App boundary:** the existing app still uses the larger index and its older hand-written
answer pack. The new notebook does not replace any of those files. App/demo redesign is a
separate next step; do not present this notebook as evidence that the app generates live answers.

The previous builder is retained as `scripts/build_reference_notebook.py`, historical
instructor reference, not the default teaching path. Its older narrative has not been
re-reviewed. It generates a separately named notebook in `backup/`; executing that reference
can export app artifacts.

## The case

A maintenance technician has a question before starting work — what the lockout procedure
requires, what a torque figure is, what the rule actually says. This lab searches official
documentation, returns the passages that answer the question, and drafts an answer that cites
them.

**Claim boundary — read this before using anything here.** The assistant **retrieves and
drafts. It never authorizes work, never approves a lockout, and never answers a safety question
from the model's own memory.** A qualified person verifies the cited passage before any work
happens. When the answer is not in the library, the correct behavior is to say so and refuse —
that is a designed outcome, not a failure.

## Original app corpus (not the classroom subset)

| Layer | What it is | Why it is here |
|---|---|---|
| The law | 29 CFR 1910 subparts J, N, O, Q, S (and 30 CFR 56) via the eCFR API | What is legally required |
| The site procedure | US Bureau of Reclamation FIST 1-1, 2-4, 2-6 | How one facility actually implements it |
| The equipment manual | Army TM 9-6115-464-12, generator set | Torque figures and troubleshooting |
| Plain language | OSHA 3120 and 3170 | The same rules written for humans |

13 documents, about 388,000 words, 3,098 retrievable chunks.

**Reference licensing notes.** Public domain does not mean redistributable. A US
Government manual can be free of copyright *and* still carry a DISTRIBUTION STATEMENT that
forbids public release. The vetting rule this lab teaches: check page one and accept
**Statement A** ("approved for public release; distribution is unlimited") only. The manual in
this corpus is Statement A, verified in its own extracted text. iFixit is the opposite trap — an
open-looking license whose terms forbid using the content to train an AI model.

Every eCFR fetch is date-pinned, so the corpus is reproducible across semesters. Nothing is
fetched during the default classroom run. Dependency and embedding-model setup can require downloads.

## How to view or run it

**No installation.** Open `backup/01_procedure_build.html` in any browser. It is self-contained,
works offline, and shows the executed walkthrough with its retrieval chart and captured LLM answers.

**To rerun the source notebook**, from the repository root:

```bash
npm run setup:procedures      # installs the service and lab dependencies
```

Then open `01_procedure_build.ipynb`. It needs no network — the embedding model is cached and
the corpus and actual LLM responses are committed. A fresh environment must cache the embedding
model during setup before using offline mode. `npm run prepare:procedures` rebuilds the original
app artifacts; it is not part of this shorter classroom path.

From the repository root, rebuild and execute the default offline notebook with:

```bash
node scripts/venv-python.mjs notebooks/procedure-assistant/scripts/build_notebook.py
node scripts/venv-python.mjs -m nbconvert --to notebook --execute --inplace notebooks/procedure-assistant/01_procedure_build.ipynb
node scripts/venv-python.mjs notebooks/procedure-assistant/scripts/make_backup.py
```

To deliberately record a new live set of the five examples:

```bash
node scripts/venv-python.mjs notebooks/procedure-assistant/scripts/capture_teaching_answers.py
```

This sends only the public excerpts and questions to the selected model and replaces the teaching
capture, not app artifacts. The exporter requires successful execution and rejects progress
widgets that would try to fetch browser scripts. The shared teaching regression checks cover both
Module 5 notebook builders and the RAG capture:

```bash
node scripts/venv-python.mjs -m pytest notebooks/procedure-assistant/tests/test_teaching.py -q
```

## Original app measurements (reference only)

Retrieval, on 45 scored questions phrased the way a technician would ask them:

| Retriever | hit@1 | hit@5 | Query time |
|---|---|---|---|
| TF-IDF word counts | 0.311 | 0.578 | 0.9 ms |
| MiniLM sentence embeddings | 0.467 | 0.822 | 3.0 ms |

**Why that comparison matters.** An earlier measurement put keyword search at 90% — but those
questions had been generated *from the passage text*, which hands a keyword matcher the answer.
Rewritten as a technician would ask them, the ranking reverses. Your benchmark number depends on
how you wrote the questions, and this is the opposite of what Module 4's text case found.

## Advanced findings retained for instructor reference

- **A plausible citation to a rule that does not exist is the real danger.** A naive chunker
  produced wrong citations 82.3% of the time, 77.4% of them pointing at paragraphs that are not
  in the regulation. The fix was a parsing change, not a better model.
- **A self-check can pass while being wrong.** The structural validator accepted a citation that
  looked well-formed and was not. Only an independent ground truth — the regulation's own
  internal cross-references — exposed it.
- **"Zero unsupported claims" is not "zero hallucinations."** The numeric check catches invented
  figures but not a real figure copied from the wrong passage.
- **A near-duplicate corpus destroys citations while retrieval looks fine.** Adding a nearly
  identical regulation left the right *text* being found while the cited *rule* was wrong on
  half the questions.
- Whole-section chunks would silently discard about two thirds of their tokens past the model's
  input limit — silent truncation, with no error message.

## Attribution

US Government works: eCFR/OSHA (29 CFR, 30 CFR), US Bureau of Reclamation FIST volumes, US Army
technical manual. This lab is educational. It is not an approved source of safety procedure for
any real equipment, and no answer it produces authorizes work.
