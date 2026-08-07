# Security Policy

## Reporting a Vulnerability

Use GitHub's private vulnerability reporting for this repository when available.
Do not post credentials, tokens, private prompts, customer data, or exploit
details in a public issue.

If private reporting is unavailable, contact the repository owner through their
GitHub profile before sharing sensitive details.

## Credential Policy

This project does not require checked-in credentials.

- GitHub Copilot authentication is handled by the local Copilot CLI.
- `.env`, `.env.local`, `.env.*`, virtual environments, SQLite databases, build
  output, logs, and CLI runtime state are ignored.
- `.env.example` contains only non-secret local defaults.
- Never commit API keys, access tokens, client secrets, private keys, passwords,
  connection strings containing credentials, or customer data.
- Never paste credentials into an issue, pull request, screenshot, test fixture,
  or synthetic-data file.

If a credential is committed accidentally, revoke or rotate it immediately,
remove it from Git history, and notify affected owners. Deleting the latest line
is not sufficient because the value remains in repository history.

## Deployment Boundary

The current application is designed for loopback, single-operator use. Exposing
it to a shared network or cloud environment requires authentication,
authorization, TLS, request limits, and a non-personal Copilot identity design.

## Known Dependency Advisories

As of 2026-08-07, `npm audit` reports two moderate advisories in the Mermaid
rendering dependency chain and no high or critical advisories. The advisory-fixed
versions identified by npm (`mermaid` 11.16.1 and `dompurify` newer than 3.4.12)
are not yet available from the configured package registry. npm's automated
alternative is a breaking Mermaid downgrade that does not remove the DOMPurify
advisory.

Current mitigations:

- Mermaid runs with `securityLevel: "strict"`.
- HTML labels are disabled.
- Diagram source is generated from validated workflow objects; arbitrary Mermaid
  syntax is not accepted from users or Copilot.
- Node IDs are restricted to alphanumeric and underscore characters.
- Labels remove quote and angle-bracket characters and are length-limited.

Upgrade Mermaid and DOMPurify as soon as non-breaking fixed releases are
available, then rerun the complete browser and security test gate.
