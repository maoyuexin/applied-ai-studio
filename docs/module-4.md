# Module 4: AI in Finance

## Open in Codespaces

Select the **feat/module-4-finance** branch before creating a Codespace. The release
is not on `main` until merged. Setup installs the dependencies, verifies the included
model bundles, and starts the app on port 5173. Open that port from the Ports panel;
do not start a second app process in Codespaces.

Existing Codespaces must check out the release branch and rebuild the container to
install the new services. Commit or preserve your own work before switching branches.

## Two Complete Cases

| Case | Notebook | Offline report | Demo path | Workflow path |
|---|---|---|---|---|
| Credit-account review | [Credit notebook](../notebooks/credit-risk/01_credit_build.ipynb) | [Credit HTML](../notebooks/credit-risk/backup/01_credit_build.html) | `/credit` | `/workflow?courseCase=financial-credit-risk` |
| Complaint routing | [Complaint notebook](../notebooks/complaint-routing/01_complaint_build.ipynb) | [Complaint HTML](../notebooks/complaint-routing/backup/01_complaint_build.html) | `/complaints` | `/workflow?courseCase=financial-complaint-routing` |

The Industry Workflows catalog has a Workflow button and a Demo button for each case.
GitHub may not render Plotly outputs in its notebook preview. Open the notebook in
Codespaces or open the downloaded HTML locally to use its interactive figures.

The credit notebook includes five real data rows and the simplified remove-columns,
retrain, compare lesson. The complaint notebook includes two complete narratives and
optional Section 6 comparing an LLM with TF-IDF on 32 fixed test complaints.

## Reproducible Defaults

Each lab includes its five validated model artifacts. `npm run prepare:credit` and
`npm run prepare:complaints` verify and reuse a complete bundle; neither silently
retrains it. The recorded model-loading library versions are pinned in each API's
Python project. An incompatible or corrupted bundle fails verification.

To intentionally retrain, use `npm run prepare:credit -- --force` or
`npm run prepare:complaints -- --force`. Running all notebook cells also rebuilds the
artifacts. Preserve the published versions before doing an experiment. Missing bundles
are rebuilt from the included data by the preparation commands.

The demo APIs listen locally on ports 4360 (credit) and 4370 (complaints). Vite proxies
both, including through the private Codespaces browser URL. No live external service
or credentials are needed for these demos, workflows, or default notebook execution.

## Optional LLM Experiment

Keep `LIVE_LLM = False` to replay the captured results offline. Live mode uses the
GitHub Copilot SDK, requires an authenticated Copilot account with access to `gpt-5.4`,
and sends the public redacted narratives to that service. It consumes plan usage.
Do not substitute private customer complaints.

Both recorded runs are included. The latest run matched 26/32 team labels, with 25/32
usable correct answers after strict quotation checks; TF-IDF matched 24/32. The first
LLM run produced 22/32 usable correct answers. The notebook explains the variability,
latency, usage, label-quality limits, and why this does not establish superiority.
The LLM is not connected to the demo's routing policy or deployed model.

## Checks

```bash
npm run prepare:credit
npm run prepare:complaints
npm run test:credit
npm run test:complaints
npm run check
```

These labs are educational. A credit score routes an account for analyst review; it
does not approve, deny, or change anyone's credit. Complaint classification selects
the first team; it does not decide whether an allegation is true or how to resolve it.