# Applied AI Studio MVP Delivery Plan

**Status:** In progress

**Created:** 2026-08-05
**Target:** Locally hosted applied AI workflow MVP

## Phase 0 - Architecture and safety boundary

- [x] Select the `applied-ai-studio` project identity.
- [x] Define single-operator local scope.
- [x] Separate deterministic catalog/scoring from Copilot reasoning.
- [x] Define public-synthetic-only data policy.
- [x] Define Aspire web, catalog, and agent resources.
- [x] Record the Copilot SDK sandbox decision.

**Gate:** Architecture has no path from the model to host filesystem, shell,
browser, or write operations.

## Phase 1 - Executable application foundation

- [x] Create npm workspace and shared contract package.
- [x] Add 13 use cases across retained industries.
- [x] Build deterministic fit-scoring API and focused tests.
- [x] Build Copilot SDK agent API with read-only tools and SSE.
- [x] Build Industry Cases, AI Fit Analyzer, and Ask Studio routes.
- [x] Add deterministic Mermaid and interactive React SVG workflow rendering.
- [x] Model the retail workflow, six decisions, baseline, and Data/Method/Metric/Human drill-down.
- [x] Add readable diagram typography, 80-180% zoom, reset, and full-viewport presentation mode.
- [x] Move detailed workflows behind use-case cards and keep primary navigation focused.
- [x] Add Workflow and planned Demo actions to every use-case card.
- [x] Generalize the detailed Map, Judge, and Design workbench beyond Retail.
- [x] Retain five comprehensive workflows and defer the eight shallow catalog cases from the visible UI.
- [x] Add deep Maintenance, KYC, Resident Intake, and Fleet workflows with decisions, exceptions, baselines, and human boundaries.
- [x] Add plain-language business context, workflow scope, process boundaries, and participants to every retained workflow.
- [x] Add automation as a distinct least-expensive intervention alongside rules, optimization, AI, and humans.
- [x] Add schema-constrained five-stage Copilot drafting before deterministic AI fit scoring.
- [x] Add an exact 75-point gate for detailed AI solution design.
- [x] Add schema-validated AI method, solution pattern, data, paired metrics, human authority, components, risks, PoC plan, and second workflow.
- [x] Reject below-threshold blueprint requests at the agent API boundary.
- [x] Add Aspire AppHost source based on the OGE pattern.
- [x] Add the FastAPI Online Order vertical with a project-local Python environment.
- [x] Add SQLAlchemy models, Alembic migration, SQLite ownership, and deterministic product seed.
- [x] Persist one happy-path order through seven workflow events and three decision methods.
- [x] Add synchronized Customer, Merchant Operations, and Scenario Control workspaces.
- [x] Add SSE synchronization across separate customer and merchant windows.
- [x] Route the Online Order Demo action to the executable application.
- [x] Persist detailed payment-classification and delivery-prediction impact.
- [x] Add Merchant decision history and Scenario AI causal-impact comparison.
- [x] Add double-click algorithm drill-downs for all four decision engines.
- [x] Include features, training/configuration, test strategy, metrics,
  monitoring, limitations, and synthetic-versus-production labeling.
- [x] Pass `npm audit`, focused scoring tests, and all Node/TypeScript builds.
- [ ] Install .NET 9 and compile the AppHost on the target Mac.

**Gate:** `npm run check` passes and Aspire starts all four resources.

## Phase 2 - Workflow content and UX hardening

- [x] Review all twelve non-reference scenarios and record the retained/deferred rationale.
- [x] Align the primary UI to Map → Judge AI Fit → Design What Survives.
- [x] Align industry coverage to the retained scenario set.
- [ ] Add one slide-ready architecture summary per scenario.
- [ ] Add facilitator notes and common design mistakes.
- [ ] Add filtering by capability, risk, and architecture pattern.
- [ ] Add a print/export view for fit-analysis results.
- [ ] Add deep links for selected showcase cases.
- [ ] Add loading, empty, signed-out, quota, and service-failure acceptance tests.
- [ ] Verify 375, 768, 1024, and 1440 pixel layouts.
- [ ] Run keyboard and automated accessibility audits.

**Gate:** Every workflow is usable without developer tools and no page
requires live Copilot except Ask Studio.

## Phase 3 - Live Copilot SDK evaluation

- [x] Verify the local operator account can start and ping the SDK runtime in the current session.
- [ ] Create a frozen 20-question evaluation set.
- [ ] Include lookup, comparison, fit explanation, unanswerable, and injection cases.
- [ ] Record resolved model, first-token latency, completion time, and failures.
- [ ] Run 10 consecutive conversations and one process restart test.
- [ ] Confirm all attempted shell, file, URL, memory, and unknown tools are rejected.
- [x] Verify a direct prompt-injection request for a local `.env` is refused without disclosure.
- [ ] Confirm no customer or local project content appears in responses.
- [ ] Review premium-request usage against the operating budget.
- [ ] Add a visible signed-out recovery state.

**Gate:** At least 17 of 20 answers are acceptable, all unanswerable cases state
the evidence limit, and there are zero critical unsupported claims or executed
unauthorized operations.

## Phase 4 - Product release

- [ ] Decide local-only versus authenticated remote interaction.
- [ ] Keep services on loopback for local-only use.
- [ ] If network access is required, add authentication and a non-personal identity design first.
- [ ] Freeze package and Copilot SDK versions.
- [ ] Add a one-command preflight for ports, catalog health, CLI sign-in, and model access.
- [ ] Prepare an offline mode where Industry Workflows and AI Fit Analyzer remain fully usable.
- [ ] Produce an operator runbook and a five-minute recovery procedure.
- [ ] Tag the tested product release after user approval.

**Gate:** A clean-machine rehearsal can start the app, complete all four
demonstrations, recover from Copilot failure, and shut down cleanly.

## Phase 5 - Optional executable vertical demos

Add vertical services one at a time after the shared workbench is stable.

- [x] Select Online Order as the first workflow-relevant vertical.
- [x] Define its deterministic happy-path engine and evaluation criteria.
- [x] Add a dedicated Aspire backend because mutable order state justifies it.
- [ ] Add payment-review, oversell, carrier-delay, and remedy exception scenarios.
- [ ] Separate the background worker when asynchronous progression requires failure isolation.
- [ ] Move SQLite to PostgreSQL before running concurrent cloud instances.
- [ ] Expose it to Copilot through bounded custom tools.
- [ ] Add a standalone failure mode so the rest of Studio remains usable.
- [ ] Repeat security, quality, latency, and release-rehearsal gates.

Good first candidates are document-package review, maintenance triage, or a
synthetic visual-analysis workflow. Avoid adding several shallow backends merely
to demonstrate microservices.

## Definition of done

- [x] `npm run check` and `npm audit` pass.
- [ ] Aspire AppHost compiles and runs on the target Mac.
- [ ] Live Copilot evaluation gate passes.
- [ ] Accessibility and four-width responsive checks pass.
- [ ] All data is public or synthetic and no secret is committed.
- [ ] Offline degradation and operator recovery are rehearsed.
- [ ] Workflow content and release scope are approved by Yuexin.