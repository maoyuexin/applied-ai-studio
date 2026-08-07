# ADR-0001: Aspire orchestration with separate catalog and agent services

## Status

Proposed

## Context

The workflow application needs multiple independently observable capabilities,
and the OGE demo already establishes Aspire as a useful local orchestrator. The
Copilot runtime has a broader security boundary than deterministic catalog and
fit logic.

## Decision

Use .NET Aspire to host a React/Vite web resource, a Node catalog API, and a Node
Copilot agent API. Keep catalog facts and deterministic scoring in the catalog
service. The agent obtains data only through bounded HTTP-backed custom tools.

## Alternatives considered

- **One Express process:** simpler startup, but couples deterministic behavior to
  SDK lifecycle and makes the agent's trust boundary less visible.
- **Backend per industry:** visually impressive but premature; most initial cases
  are catalog records, not independent domain engines.
- **Foundry-hosted agents:** does not test the requested GitHub Copilot SDK model
  and adds a separate deployment dependency.

## Consequences

- Positive: clear failure isolation, explicit data ownership, OGE-like Aspire
  observability, and simple addition of a real vertical backend later.
- Negative: three local processes and a .NET prerequisite for the preferred host.
- Mitigation: retain `npm run dev` as the no-.NET local fallback.

## Revisit when

- a real vertical module needs its own compute or dependencies;
- the application moves beyond one local operator;
- deployment rather than local orchestration becomes the primary concern.