# Catalog Onboarding: LLM Extraction with Human Review

Retail lesson, case 3. A non-chatbot workflow: **source evidence -> LLM field proposals -> checks -> listing draft -> human review**.
The default is a self-contained offline demo in `backup/M6_Demo_Catalog_Onboarding.html`.
It contains actual captured GPT-5.4 responses, not hand-authored responses presented as model output.
No additional notebook or application service is required.

## Evidence and Results

`evidence.json` contains three dated factual transcriptions from official Rex London pages and two
independent fictional supplier stress tests. Public product pages stand in for supplier evidence;
these are not internal supplier documents. Facts were reviewed September 22, 2026. The source
transcriptions omit marketing copy, reviews, price and stock; full pages are not redistributed.

| Record | Provenance | Teaching result |
|---|---|---|
| 47566 bunting | Real public facts | Approximate 800 cm, 15 pennants, wash at 30 C, fire warning; human review |
| 85099B storage bag | Real public facts | Recycled plastic and wipe-clean care; explicit selling unit absent; hold |
| 22084 paper-chain kit | Real public facts | One kit, approximately 200 links, 1,000 cm assembled length; human review |
| B17 bottle | Fictional | Six per shipping carton does not establish customer selling pack; hold |
| C24 mug | Fictional | Two undated capacity statements disagree; preserve conflict and hold |

The actual saved run produced **24 supported, 8 missing and 1 conflicting field** across 33 requests.
All 33 agreed with the selected-example reference checks. Two records advanced to human review;
three remained on hold. These five hand-selected examples are **not a representative benchmark**.
The red-bag hold reflects the deliberately strict explicit-selling-unit classroom policy, not a
claim that the retailer's live listing is defective.

Expected values are never included in the LLM prompt. Evaluation uses an independently authored
key after generation. Some string comparisons check required phrases; they are not semantic
entailment proofs. Matching an exact quote proves location, not meaning. All five captured drafts
were inspected during creation, but future outputs still require review. The bottle draft includes
a logistics fact that a merchandiser may prefer to omit from customer copy; the original wording
is retained and flagged in the demo.

## Offline Classroom Route

1. Open the standalone HTML. Start with bunting and inspect both source excerpts.
2. In Extraction, inspect approximate length and the missing waterproof claim; open source evidence.
3. In Checks, distinguish valid references, reference agreement and required-field completeness.
4. In Draft, read the actual captured wording beside its linked fields.
5. In Review, acknowledge source review and make a simulated approval or hold decision.
6. Repeat with the fictional bottle and conflicting mug. Approval remains disabled for holds.
7. Open Batch evidence for stacked status counts, reference counts and the field-status heatmap.

Review decisions are local and resettable. Export downloads a JSON teaching record; nothing is
written to a real product-information system. The browser never calls the LLM or any HTTP API.
Photographs are only visual labels and are never model inputs. Merchant image rights are separate
from the UCI license, so the default (public) build omits them and shows a neutral placeholder.
Add `--include-product-photos` to `build` only when you have permission to distribute the cached
photos; that option reads the local `notebooks/retail-simulators/product-images/` cache.

## Optional Live LLM Implementation

From the Applied AI Studio repository root, using its existing Python 3.11+ environment:

```sh
.venv/bin/python notebooks/catalog-onboarding/catalog_demo.py check
.venv/bin/python notebooks/catalog-onboarding/catalog_demo.py capture
```

`capture` requires an authenticated Copilot environment and model access. It creates a timestamped
file under `captures/`; it refuses to overwrite existing files. No secrets belong in the script or
CLI arguments. Complete any sign-in privately in your terminal. The validated SDK version is
`github-copilot-sdk==1.0.8`; the default requested model is `gpt-5.4`, with no silent substitution.
Five calls were actually executed to produce the bundled capture on September 22, 2026.

To inspect and build an HTML replay from a new capture:

```sh
.venv/bin/python notebooks/catalog-onboarding/catalog_demo.py check --capture /path/to/new-capture.json
.venv/bin/python notebooks/catalog-onboarding/catalog_demo.py build \
  --capture /path/to/new-capture.json --output /tmp/catalog-new-run.html
```

The model session has no tools, MCP servers, memory, custom instructions, file access or store
actions enabled. Each product uses a fresh session. Only the selected public facts or fictional
documents are sent. Raw responses, exact prompts, model usage, timing and fingerprints are saved.
Malformed model output is preserved and shown as a hold, not replaced with a fabricated answer.
Transport/authentication failures stop the capture explicitly. Editing evidence or prompts makes
an old capture fail fingerprint validation and requires a new run.

Offline build also uses the repository's installed React/Lucide Node dependencies and Plotly 6.9.0.
No image download is required.
The finished HTML has no such runtime dependencies.

## Validation

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest notebooks/catalog-onboarding/test_catalog_demo.py -q
.venv/bin/python notebooks/catalog-onboarding/catalog_demo.py build
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
  node notebooks/catalog-onboarding/test_demo.mjs
```

Python checks cover schema, wrong units, lost qualifiers, false evidence, unsupported draft terms,
pack ambiguity, conflicts, and capture tampering. Fixture-based validator mutations are synthetic
tests, not additional LLM accuracy results. Browser tests cover every record and stage at
1440/768/390 pixels, real response parity, all three plots, source drilldown, approval gates,
hold/reset/undo/export, and zero HTTP requests or browser errors. Screenshots are written to
`/tmp/m6-catalog-demo-tests`.

## Files

- `evidence.json`: attributed factual transcriptions, field schemas and separate reference key.
- `catalog_demo.py`: actual LLM capture, validation, replay and HTML build.
- `capture.json`: immutable default captured run; never silently overwritten.
- `demo.html`: editable standalone UI template.
- `test_catalog_demo.py`, `test_demo.mjs`: calculation/validation and browser checks.
- `backup/M6_Demo_Catalog_Onboarding.html`: generated offline classroom artifact (public, photo-free).

No existing forecasting/recommendation models, datasets, notebooks, simulators or application
services are modified by this case.