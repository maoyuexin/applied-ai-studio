# Module 3 instructor run guide

## What is ready

- Executed five-stage CNN notebook plus optional multimodal Stage 6: `01_pneumonia_build.ipynb`
- Offline fallback: `backup/01_pneumonia_build.html`
- Captured multimodal response: `artifacts/multimodal_demo_response.json`
- Checksum-verified committed data: `data/pneumoniamnist_128.npz`
- Artifact-backed service: `services/pneumonia-api`
- Applied AI Studio route: `http://127.0.0.1:5173/pneumonia`

The build accepts no arbitrary image uploads and needs no API key, clinical data access,
Kaggle account, or cloud model credential. The optional live Stage 6 call uses the signed-in
GitHub Copilot user; captured mode needs no authentication.

## Fresh Codespace

Codespaces setup installs the notebook and API dependencies, prepares the fraud and
pneumonia artifacts, and starts all six services automatically. Open forwarded port 5173,
choose **Healthcare**, and launch **Pediatric Chest X-ray Prioritization**.

## Local run

One-time setup from the repository root:

```bash
python3.11 -m venv .venv
npm ci
npm run setup:orders
npm run setup:notebook
npm run setup:fraud
npm run prepare:fraud
npm run setup:pneumonia
npm run prepare:pneumonia
```

Start the complete studio:

```bash
npm run dev
```

Open `http://127.0.0.1:5173/pneumonia`.

## Notebook demonstration

The notebook follows the same visible structure as Session 2:

1. Data Ingestion and Provenance
2. Image EDA and Preparation
3. Model Training
4. Model Validation and Operating Policy
5. Model Prediction and Handoff

After those five measured stages finish, Stage 6 demonstrates what a multimodal LLM may
attempt with one fixed priority-review thumbnail. It is a separate capability experiment,
not part of the CNN pipeline or app.

For the most reliable live class:

1. Open the executed notebook before class and verify the figures are present.
2. Explain Stages 1 and 2 from saved output.
3. Run the compact training cell; the validated CPU run is about 2.3 minutes.
4. Run the remaining validation and handoff cells.
5. In Stage 6, keep `LIVE_MULTIMODAL_DEMO = False` for the reliable captured response.
6. Read the generated language before revealing the CNN score, route, and dataset label.
7. If notebook execution fails, open the offline HTML and continue without changing the lesson.

### Optional live multimodal run

Before class, verify GitHub Copilot authentication and run Stage 6 once with
`LIVE_MULTIMODAL_DEMO = True`. The selected model must report vision support. The helper
uses an isolated one-turn session with no tools or memory. If the request fails, the cell
shows captured mode and continues.

Use this voiceover whether the result looks strong or weak:

> The model generated plausible image-based medical language. Our binary label cannot
> validate its detailed findings or locations. Generation capability is not clinical
> reliability, and the radiologist remains the accountable interpreter.

## Business workflow demonstration

1. Open **Industry Workflows**, filter to **Healthcare**, and choose **Workflow** on the
   Pediatric Chest X-ray Prioritization card.
2. In **Map the process**, compare the documented path with identity correction, image
   recapture, and priority-routing exceptions.
3. In **Judge AI fit**, select the diamonds to contrast rules, policy automation, learned
   image classification, radiologist interpretation, and clinician authority.
4. In **Design what survives**, select the pneumonia-pattern decision and connect Data,
   Method, Metric, and Human to the notebook evidence.
5. Return to the Healthcare catalog and choose **Demo** to run the packaged model.

## App demonstration

1. **Scoring workbench:** choose a packaged study and separate score, cutoff, and route.
2. Move exposure to `-100`, run the workflow, and show quality hold with no score or label.
3. Reset, run the original, and toggle the influence overlay.
4. **Review queue:** compare 397 priority-review and 227 standard-review studies; inspect
   false positives and false negatives.
5. **Model card:** connect the confusion matrix, quality limits, intended use,
   limitations, and authority chain.

## What the instructor still needs to decide

No input is required to finish the technical notebook or app. Before publication or class,
the instructor should:

1. Review the clinical wording and decide whether to request a qualified clinical-language
   review later. The current language intentionally remains conservative.
2. Decide whether to retrain live or use the executed outputs and run only selected cells.
3. Decide when to publish the current branch and whether to update the Module 3 slide deck
   with the measured metrics and validated app screenshots.

Do not provide real patient images. The app intentionally has no upload path.