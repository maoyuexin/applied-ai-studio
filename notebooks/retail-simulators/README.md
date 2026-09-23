# Retail Decision Simulators

Two single-file HTML simulators with Applied AI Studio's dark palette. Open either file directly;
no server, network, account, or runtime Python is needed.

## Public Release Images

The public repository omits merchant photographs, including images embedded in generated HTML.
Normal Git is used; Git LFS is neither needed nor configured. Public demos retain all product
names, model payloads, charts, controls and scoring. They display Photo unavailable where an
image would appear; the visual walkthrough uses lettered product labels. Local classroom builds
may contain photographs and therefore look different without changing the learned model.

Both builders omit product photographs by default. Only after obtaining permission, populate the
ignored local `product-images/` cache and explicitly pass `--include-product-photos` to
`build_simulators.py` or `build_story.mjs`. Such generated outputs must not be committed without
reviewing distribution rights. Source URLs and matching notes remain in `product-images.json`.

`build_simulators.py --reuse-export` repackages the existing saved model data without fitting it
again. Rebuilding the walkthrough also refreshes its same-folder notebook companion HTML files.

## Saved Demos and Notebook Reruns

The committed HTML exports freeze the teaching run. Browser tests check their exact score
vectors, predictions, and replay fixtures; these demos do not retrain in Codespaces.
Fresh Python notebook fits are not guaranteed to reproduce those numbers across platforms,
even with identical input files and package versions. Histogram boosting and arbitrary
ranking ties can produce different fitted trees, example predictions, or catalog coverage.
For example, the verified Linux rerun produced forecast test MAE 47.94 instead of 47.97,
the worked forecast 890.48 instead of 824.15, and recommendation coverage 25.57% instead
of 25.77%. These are rerun results, not changes to the saved classroom evidence.

Teaching tests check the input counts, model settings, calculations, and comparative lesson
claims for fresh fits. Use `--reuse-export` to preserve the published model when repackaging;
a new fit needs a new evidence review before replacing the classroom exports.

- [Next Best Product](../product-recommendations/backup/02_recommendation_simulator.html)
- [Demand Forecasting](../demand-forecasting/backup/02_forecast_simulator.html)
- [How Recommendations Are Learned](../product-recommendations/backup/03_recommendation_story.html)

## Recommendation Workflow

Three numbered steps: choose one of 13 real customers, choose one of their purchases, press
Recommend top 10. The browser ranks the full 4,443-product training catalog using the notebook's
item-item cosine model (15 outgoing neighbors). Each selected slot has a purchase-to-product
diagram and an exact contribution ledger: similarity links from distinct purchased products sum
to its score. When the whole history ranks, each slot also reports the share of its score coming
from the selected purchase.

The rank-products-by control offers the same customer three ways. *Everything this customer
bought* is the personalized ranking. *Only the purchase above* ranks that one product's nearest
neighbours: a product-page "customers who bought this" list, deliberately not a personalized
claim, so it sidesteps rather than violates the five-product eligibility policy. *Popular with
everyone* is the training-popularity baseline and ignores the customer entirely.

The 13 customers are chosen deterministically in `build_simulators.py`: two per history-size band
(5-8, 9-14, 15-24, 25-40, 41-80, 81-200 distinct products), ordered by how many of their products
have a photograph, tie-broken by customer id, plus customer 12349. Selection never inspects whether
the model ranks a customer well; the roster hits in 5 of 13, against the 41.6% population rate.

Each customer carries their `truth_discovery` set: products bought after the 2011-09-09 cut that
they had never bought before it. That is the right ground truth here because the ranking hides a
customer's own purchases, which is the discovery protocol the 41.6% (item-item) and 29.5%
(popularity) classroom figures come from. `truth_standard` would count repeat purchases the ten
slots can never contain. Revealing it marks the slots the customer really bought later, and says
plainly when none of the ten were, with the population rate for context.

A new visitor receives generic fallback until five distinct products are recorded, matching the
existing eligibility policy. Adding to the basket alone does not change history. Repeat purchases
do not add weight to binary history. Purchased and excluded items never fill discovery slots.
Catalog search, category filters, basket, exclusions, undo, reset and JSON session export live in
the collapsed Build your own shopper panel.

Similarity weights stay fixed: a purchase changes history, not the learned model. Generic slots
have no personalized score. Fallback uses recent-revenue products, followed by training popularity
if necessary. Score ties use stock-code order, which can differ from the notebook's arbitrary
tie ordering. No discount or offer-response data are available: this ranks products, not offers.

## Recommendation Walkthrough

The separate `03_recommendation_story.html` is a 2-minute, 53-second visual lesson with on-screen
explanations, not a narrated MP4. Seven scenes show invented purchases for five customers and six
products, the binary matrix, a countable cosine calculation, saved neighbors, summed scores,
purchase masking and re-ranking, and the connection to the real notebook. Existing simulators,
notebooks, and model artifacts are unchanged.

Playback starts paused. Play/pause, previous/next, chapter selection, seeking, speed, and replay
are available. **All steps** shows the complete figure sequence; printing produces seven A4 pages.
The source-product selector exposes retained and discarded links. The cake-stand purchase toggle
recomputes the top two using the existing `engine.js`, without modifying the learned similarities.
Reduced-motion preferences are respected and hidden tabs pause playback.

The toy policy uses up to three neighbors, one purchase for personalization, and two slots.
The final scene explicitly distinguishes the real 15-neighbor, five-purchase, ten-slot policy.
Real catalog size, split date, and settings come from the existing recommendation simulator export.
Public builds use lettered product labels. Permissioned local builds can embed six cached
stock-code-matched photographs with credits; neither kind of label is a model feature.

Build from the repository root after the recommendation simulator export exists:

```sh
node notebooks/retail-simulators/build_story.mjs
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
  node notebooks/retail-simulators/test_story.mjs
```

`build_story.mjs --check` runs the arithmetic assertions without generating HTML. Browser checks
cover all seven scenes at 375, 390, 768, and 1440 pixels, exact model calculations, photo parity,
playback timing, keyboard navigation, purchase changes, seven-page printing, and offline loading.
Screenshots and a print preview go to `/tmp/m6-recommendation-story-tests` by default.

## Forecast Workflow

Choose one of ten example products and press Play. The replay walks all 26 held-out weeks in two
beats each: the model forecasts the week against the eight-week average, then the week is revealed
and the running average miss updates for both methods. Step advances one beat, the slider scrubs,
Reset parks the replay before week one, and the speed control runs 0.7 to 3.2 seconds per week.
The Shapley waterfall follows the playhead and a scoreboard accumulates every scored week. The
what-if editor (edit the latest eight values, or use the scale controls) is a collapsed panel.

Every forecast is one week ahead of recorded history. Revealing a week hands the *real* number to
the next week's feature row, so the model is never fed its own predictions and the displayed errors
do not compound. A genuine multi-week-out forecast would have to reuse predictions as inputs, and
this model was neither trained nor validated that way. The model beats the eight-week average on
5 of these 10 products; the scoreboard names the winner per product rather than assuming one.

The HTML contains the current pooled HistGradientBoostingRegressor's numeric trees. Browser
inference matches Python, including missing-value branches and clipping at zero. Changing input
history recomputes all dependent lag and rolling features together; it does not retrain.

The explanation is exact Shapley attribution for four feature groups against 16 fixed pre-test
training rows. All 16 group coalitions are evaluated. Reference prediction plus signed group
contributions equals the displayed prediction. It is not per-feature TreeSHAP or a causal claim.
Correlated features can make mixed reference rows unrealistic, and results depend on the chosen
reference and grouping. The original recorded outcome cannot validate a hypothetical edit.

## Build and Test

From the Applied AI Studio repository root, with its Python environment and Node dependencies:

```sh
.venv/bin/python notebooks/retail-simulators/build_simulators.py
node notebooks/retail-simulators/test_simulators.mjs
```

Permissioned local photographs may be cached under the ignored `product-images/` directory and
embedded only with `--include-product-photos`.
To restore missing image files from their recorded sources, run
`.venv/bin/python notebooks/retail-simulators/fetch_product_images.py` once with network access.
Normal builds and the finished simulators need no image downloads.

The first command generates the two standalone files in each lesson's backup folder. It imports
the existing lesson data and models but never writes to their data or application-artifact folders.
The Node test verifies offline packaging, syntax, full recommendation score-vector parity,
88 Python/browser forecast fixtures, masking, repeated history, and attribution additivity.

For the full browser workflow test, supply a Playwright module and installed Chromium executable:

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
CHROMIUM_PATH='/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge' \
  node notebooks/retail-simulators/test_simulators.mjs
```

Browser checks cover purchase, undo, repeat purchase, cold start, exclusions, baseline mode,
export, forecast edits, invalid-input holds, product/week switching, and responsive chart framing.
Screenshots go to `/tmp/m6-retail-simulator-tests` by default. Tested at 390, 768, and 1440 pixels
with reduced motion, zero page/console errors, and all HTTP requests blocked.

### Codespace Verification Notes (2026-09-23)

The existing Codespace was updated and tested, not recreated. Both retail workflows and demos
passed desktop and phone interaction tests against its production build, including byte-for-byte
verification of the saved simulator HTML. Both retail teaching test files also passed on Linux
and macOS. Run those tests with:

```sh
.venv/bin/python -m pytest notebooks/demand-forecasting/tests notebooks/product-recommendations/tests -q
```

The unfiltered repository-wide `npm run check` still has two pre-existing failures, reproduced
on the prior `fc3f229` commit: the predictive-maintenance notebook exceeds its 4,500-word test
limit (4,811 words), and Linux's legacy recommendation API reorder-strip ordering differs from
its saved manifest in `test_slots_reproduce_the_packaged_manifest_exactly`. Neither affects
the current browser-only retail demos. These tests remain unchanged; an explicitly excluded
verification run must not be described as an unfiltered full-suite pass.

## Provenance and Boundaries

Online Retail II, UCI, DOI [10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D), CC BY 4.0.
The six generic category drawings have been removed. The optional local image manifest describes **25 product-specific
photographs**: 23 stock-code matches from Rex London or its retailer Petit Bazaar, plus two
historical name-matched photos labeled **Name-matched reference** (pink polka-dot bag and white
hanging heart tealight holder). Nine of the ten forecast products have stock-code photographs;
the chocolate hot-water bottle has no verified photo and displays **Photo unavailable**.

[product-images.json](product-images.json) records every file, source, credit, and matching basis.
The pictures were checked on a labeled contact sheet. No photo is invented for an unmatched SKU.
Catalog browsing presents photographed products first; the full 4,443-product recommendation
ranking and popularity baseline are unchanged. Images never enter either model.

**Image rights are separate from the UCI data license.** Merchant and Pinterest-hosted photographs
are credited in the UI and manifest; no open redistribution license is claimed. Review image
rights before public distribution. No image assets have been published by this work.

Display categories remain name-based heuristics. Plotly and Lucide utility icons are embedded
from installed libraries. Fonts use the Studio font stack with local fallbacks, not a CDN.

Applied AI Studio now embeds these exact HTML exports at `/forecast` and `/recommendations`,
with **Demo** as the single interactive entry point. Retail showcase cards retain Workflow and
Demo; workflow pages link to Demo; demo pages retain the Workflow link. Duplicate Simulator and
Open simulator buttons have been removed. The `/forecast-simulator` and
`/recommendations-simulator` URLs remain valid for existing bookmarks only. The web build imports
the exports as local assets without copying another editable version or requiring model APIs.
Regenerate the exports before rebuilding the web app when simulator templates change.

The earlier API apps remain at `/forecast-reference` (MA8 intervals and planning policy) and
`/recommendations-reference` (advanced comparison). Their services and model artifacts are
unchanged. The current classroom notebooks and course HTML copies are also unchanged by the
Studio integration. `scripts/test-retail-showcase.mjs` verifies the complete navigation and
embedded workflows against a running Studio; see the root README for its environment options.
Actions remain page-local unless explicitly exported. No customer account, payment, or order is
created. Explanations describe model calculations, not customer intent or causes of demand.