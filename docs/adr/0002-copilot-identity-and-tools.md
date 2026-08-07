# ADR-0002: Local Copilot identity with an empty-mode tool sandbox

## Status

Proposed

## Context

The MVP should use Yuexin's existing GitHub Copilot account and avoid a Foundry
model deployment. The SDK's default CLI mode exposes capabilities that are not
appropriate for the workflow web application.

## Decision

Run the SDK locally with the signed-in operator identity and `mode: "empty"`.
Allow only four custom read-only tools for catalog search, use-case lookup,
comparison, and fit-assessment retrieval. Disable memory, cross-session storage,
and infinite-session files. Reject every other permission request.

## Alternatives considered

- **Default Copilot CLI mode:** rejected because ambient filesystem and shell
  capabilities exceed the application contract.
- **Browser-side SDK:** rejected because it would expose identity and runtime
  control to the client.
- **Shared personal account over a multi-user network:** rejected because it lacks
  user authorization, request attribution, and abuse controls.

## Consequences

- Positive: no model keys, narrow data exposure, and a direct demonstration of
  agent tools and grounded reasoning.
- Negative: the first MVP is tied to the operator's local sign-in and allowance.
- Risk: a future remote release needs per-user OAuth or organization-attributed
  server identity; it cannot reuse this personal-host assumption unchanged.

## Revisit when

- multiple users connect from their own devices;
- the app is hosted in Azure or another remote environment;
- a write-capable demonstration is proposed.