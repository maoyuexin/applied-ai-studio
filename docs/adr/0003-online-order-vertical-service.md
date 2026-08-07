# ADR-0003: One Online Order vertical service with persisted workflow events

## Status

Accepted

## Context

Online Order is the first workflow that must become an executable application.
It crosses address validation, payment screening, inventory allocation,
fulfillment, delivery, and customer communication. Splitting each business step
into a network service would add deployment and consistency costs before any step
has an independent scaling or ownership requirement.

The application also needs repeatable synthetic runs, customer and merchant
views over the same order, durable state, and a database path that can move from
local development to Azure without rewriting the domain.

## Decision

Implement Online Order as one FastAPI vertical service composed by Aspire.

- FastAPI owns the public order API and server-sent event stream.
- SQLAlchemy owns the relational model; Alembic owns every schema change.
- SQLite is the local single-process database. One service owns the file.
- Normal tables store current state; `workflow_events` stores an append-only
  business timeline. This is not full event sourcing.
- The order state machine advances one transaction at a time.
- Rules, AI classifiers, optimizers, and human decisions are explicit decision
  records rather than hidden inside one status value.
- AI decision records include the full impact chain from signals and model output
  through policy threshold, workflow branch, business effect, counterfactual,
  and accountable human authority.
- Every decision engine carries a structured development profile. Rule and
  optimization profiles explicitly use configuration and benchmark validation;
  classification and prediction profiles specify train/validation/test design.
- React exposes Customer, Merchant Operations, and Scenario Control workspaces
  over the same persisted order.
- AI is a bounded decision component. It does not orchestrate order execution.

## Alternatives considered

- **Service per workflow step:** rejected for the MVP. It introduces distributed
  transactions, messaging, tracing, and failure recovery without independent
  business ownership or load.
- **Add order execution to the catalog API:** rejected because mutable commerce
  state and migrations have a different lifecycle from the read-heavy scenario
  catalog.
- **Full event sourcing:** rejected because current-state tables are simpler for
  operations queries; an immutable event timeline provides the required audit and
  visualization behavior.
- **LLM-generated operational truth:** rejected because inventory, fraud labels,
  and delivery outcomes must remain causally consistent and reproducible.

## Consequences

- Positive: one transaction boundary, one schema owner, deterministic tests, and
  a clear extraction seam if a domain later needs independent scale.
- Positive: SQLite can move to PostgreSQL through SQLAlchemy and Alembic.
- Positive: separate browser windows stay synchronized through SSE.
- Negative: the local process owns background progression until a worker is
  separated.
- Negative: SQLite remains suitable for one local writer, not concurrent cloud
  instances.

## Revisit when

- multiple API or worker instances need concurrent writes;
- one business capability requires independent deployment or ownership;
- background jobs need durable cross-process delivery;
- authenticated multi-user operation replaces the local single-operator scope.
