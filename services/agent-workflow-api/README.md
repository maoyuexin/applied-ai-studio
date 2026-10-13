# Agent workflow service

Runs, records and streams multi-agent workflows for the **Agent Workflows** tab
(`/agent-workflows`). Built on Microsoft Agent Framework (Python) with a Microsoft Foundry
model. The page replays recorded runs without this service; the service is only needed for
**Live** runs.

| Scenario | Pattern | Tools behind it |
|---|---|---|
| Card Alert | Single agent | Fraud service (score + reasons), hold action with approval |
| Trial Finder | Single agent | Trial Finder MCP server (ClinicalTrials.gov), referral with approval |
| Machine Alert to Work Order | Sequential, with a plain-code check | Maintenance + procedures services, work order with approval |
| Coding Team | Handoff | Hosted code interpreter (Foundry sandbox), merge with approval |
| Holiday Promotion | Group chat with a chair | Forecast service, claims rules in code, brief with approval |

Every action tool requires a person's approval and only writes to a per-run outbox.

## Run it

```bash
npm run setup:agent-workflows        # own .venv in this folder
cp services/agent-workflow-api/settings.example.json services/agent-workflow-api/settings.local.json
# edit endpoint + model; sign in with `az login` (AzureCliCredential, no keys stored)
npm run dev:agent-workflows          # http://127.0.0.1:4440, proxied at /api/agent-workflows
```

Live runs also need the model services each scenario uses (`npm run dev:fraud`, `dev:pdm`,
`dev:procedures`, `dev:forecast`). The page shows which ones are missing.

## Record replays

```bash
npm run record:agent-workflows       # scripts/record_all.py, then export_specs.py
npm run test:agent-workflows         # unit tests + checks that the web data is current
```

Recorded runs live in `data/agent-workflows/recordings/` and are committed; the page imports
them directly. Live runs are saved to `data/agent-workflows/live-runs/` (git-ignored) and can be
replayed from the run list.

## Add a scenario

Create `app/scenarios/<name>.py` with a `Scenario` (agents, tools, layout, tasks) plus a
`build(ctx)` that returns an Agent Framework workflow, register it in `app/scenarios/__init__.py`,
then run `scripts/export_specs.py`. Approval-required tools use `@tool(approval_mode="always_require")`
and `ctx.file_action(...)`.

### Business view

Set `SCENARIO.business` to a `BusinessSpec` so people without a technical background can follow
the case: the question, situation, stakes, who decides, today versus with agents, the actors
(swimlanes) and the business stages. Each `StageSpec` lists event matchers (`type`, `agent`,
`tool`, `node`, `target`, plus `nth` or `last`) and a `visual` rendered by
`apps/web/src/agentWorkflows/visuals.tsx`. The tests check that every recording reaches every
non-optional stage.

The service binds to 127.0.0.1 and has no authentication; put it behind an authenticated proxy
before exposing it anywhere else.
