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

As of 2026-08-17, `npm audit` reports **no advisories at any severity**.

The two moderate Mermaid advisories previously recorded here have been resolved:
the fixed releases are now available from the registry and the lockfile has been
updated to `mermaid` 11.16.1 and `dompurify` 3.4.13. The upgrade is non-breaking —
the full test and build gate passes on it. A separate high-severity advisory in
`nanoid` (GHSA-2v37-7h3g-55p8, reached transitively through Vite and PostCSS) was
fixed in the same pass by moving to 3.3.18.

The defence-in-depth measures below predate those upgrades and remain in force:

- Mermaid runs with `securityLevel: "strict"`.
- HTML labels are disabled.
- Diagram source is generated from validated workflow objects; arbitrary Mermaid
  syntax is not accepted from users or Copilot.
- Node IDs are restricted to alphanumeric and underscore characters.
- Labels remove quote and angle-bracket characters and are length-limited.

Re-run `npm audit --audit-level=high` together with `npm run check` before every
release, and update the date above with the result.
