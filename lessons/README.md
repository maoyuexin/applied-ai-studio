# Lesson library

Each lesson pairs an industry story with one or more worked cases. The slides frame the business
workflow, an executed notebook shows the technical evidence in five stages, and the Studio app
shows where the model's output changes a real decision and where a person keeps authority.

**Browse everything in the browser, with no installation:**
<https://maoyuexin.github.io/applied-ai-studio/>

| # | Lesson | Cases | Slides |
|---|---|---|---|
| 01 | [How Work Happens, and Where AI Fits](01-work-processes/README.md) | One online order | [PDF](01-work-processes/M1_Deck_How_Work_Happens.pdf) |
| 02 | [From Data to Decision](02-data-to-decision/README.md) | Card transaction fraud | [PDF](02-data-to-decision/S2_Deck_AI_Across_Industries.pdf) |
| 03 | [AI in Healthcare](03-healthcare/README.md) | Pediatric chest X-ray prioritization | [PDF](03-healthcare/M3_Deck_AI_in_Healthcare.pdf) |
| 04 | [AI in Finance and Risk Management](04-finance-risk/README.md) | Credit risk review; complaint routing | [PDF](04-finance-risk/M4_Deck_AI_in_Finance.pdf) |
| 05 | [AI in Manufacturing](05-manufacturing/README.md) | Compressor predictive maintenance | [PDF](05-manufacturing/M5_Deck_AI_in_Manufacturing.pdf) |
| 06 | [AI in Retail and Supply Chain](06-retail-supply-chain/README.md) | Demand forecasting; next best product; catalog onboarding | [PDF](06-retail-supply-chain/M6_Deck_AI_in_Retail.pdf) |

## Three ways to use a lesson

1. **Read**: slides and short readings are PDFs in each lesson folder. GitHub previews them.
2. **Open in the browser**: notebook reports and interactive demos are self-contained HTML files.
   The [lesson site](https://maoyuexin.github.io/applied-ai-studio/) opens them directly; nothing
   loads from the network and nothing is sent anywhere.
3. **Run it**: open the repository in GitHub Codespaces
   ([quickstart](../docs/student-quickstart.md)) to rerun any notebook or use the full Studio app.
   The lesson site can remember your Codespace address so its Studio links open your running app.

## Teach with it

- Lessons are ordered as a sequence, but each one stands alone after lesson 02 introduces the
  five-stage notebook pattern.
- Course-specific schedules live under [`courses/`](../courses/README.md). A course maps its own
  modules to these lessons, so several courses can share one library.
- Slides carry the course they were first taught in; the notebooks, demos and Studio app are
  course-neutral.

## Add or update a lesson

1. Put the PDFs in `lessons/<number>-<topic>/` with a short `README.md`.
2. Add the lesson to [`lessons.json`](lessons.json): slides and readings (`.pdf`), notebook reports
   and demos (`.html` already in the repository), and Studio routes. Use `publishAs` when the slides
   link to a file by a different name.
3. Check and preview:

   ```bash
   npm run test:lessons
   npm run build:site   # writes _site/; open _site/index.html
   ```

Merging to `main` republishes the site through `.github/workflows/pages.yml`.

Do not add material you do not have the right to redistribute. In particular, merchant product
photographs stay out of public copies.
