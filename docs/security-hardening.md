# Security Hardening Guide

SellThrough is currently a local CLI + SQLite project. Treat it as
sensitive-by-default anyway: it holds API credentials in the environment and can
store third-party marketplace payloads locally.

## Secrets

- Store eBay credentials only in environment variables or an OS-backed secret
  manager.
- Never commit `.env`, local DBs, tokens, screenshots of keys, or raw auth
  headers.
- Use `python -m sellthrough config check` for redacted diagnostics.
- Do not paste access tokens or client secrets into chat, issues, PRs, or docs.

## Credential Rotation Checklist

Use this if credentials are exposed or when rotating proactively:

1. Revoke or regenerate the affected eBay keyset in the eBay Developer portal.
2. Update local environment variables.
3. Restart shells/tools that need the new environment.
4. Run `python -m sellthrough config check`.
5. Run `python -m sellthrough smoke --query "dewalt drill" --limit 1`.
6. Search the repo and recent PRs for leaked values.

## Raw Payload Storage

- `raw_api_responses.response_json` is sanitized before being stored.
- Sensitive-looking fields are retained with `[REDACTED]` values so source shape
  is still visible without preserving unsafe content.
- Local SQLite files belong under `data/` and are ignored by Git.
- Before sharing any DB export, inspect it as sensitive data.

## Pre-Push Secret Scan

Run this before pushing:

```powershell
rg -n "access_token|client_secret|Authorization|Bearer|gho_|EBAY_CLIENT_SECRET|password|payment|buyer|seller|username" .
```

Expected matches should be code, tests, or docs using placeholders/redacted
examples. Real secret values should never appear.

## Dependency Audit

Install development tools with:

```powershell
python -m pip install -e ".[dev]"
```

Then run:

```powershell
pip-audit
```

## CI Security Workflow Notes

SellThrough currently uses two GitHub Actions workflows for validation and
security checks:

- `.github/workflows/ci.yml` runs unit tests, the offline/mock V1 E2E
  validation test, a high-signal secret scan, and a scoped dependency audit.
- `.github/workflows/security-checks.yml` runs a dedicated high-signal secret
  scan and scoped dependency audit.

The overlap between the CI workflow and the dedicated Security Checks workflow
is intentional for now. It provides defense-in-depth while the project is still
small and easy to audit.

The blocking dependency audit currently covers runtime and web-facing
dependencies. Dev-tooling dependencies are excluded from the blocking audit to
avoid unrelated toolchain advisories blocking application validation. Revisit
this scope if the project becomes production-facing, accepts outside
contributors, or starts distributing packaged releases.

## Future Web/Mobile Rules

- Do not expose SQLite directly.
- Keep eBay credentials server-side only.
- Require authentication for anything beyond localhost.
- Use HTTPS outside local development.
- Add request rate limits.
- Never send unsanitized raw payloads to a browser or mobile client.
