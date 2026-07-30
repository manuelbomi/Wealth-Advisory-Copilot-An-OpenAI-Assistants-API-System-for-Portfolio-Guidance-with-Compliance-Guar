# Security

This is a portfolio/demo project, not a production system, but it follows
production-minded security practices so it's representative of real engineering
work.

## Reporting

This repository has no real users or production deployment. If you spot a
security issue in the code as a reviewer, please open a GitHub issue describing
it -- there is no bug bounty or formal disclosure process for a demo project.

## Secrets handling

- `OPENAI_API_KEY` (and any other secret) is loaded only from environment
  variables / `.env` (see `.env.example`), never hardcoded.
- `Settings.openai_api_key` is typed as `pydantic.SecretStr` specifically so it
  cannot be accidentally logged or included in a `repr()`.
- The structured JSON logging formatter (`app/core/logging_config.py`) redacts a
  fixed set of key names (`api_key`, `authorization`, `password`, `secret`, ...)
  from any `extra=` fields as defense in depth.
- `.env` is git-ignored; only `.env.example` (with blank/placeholder values) is
  committed.

## Untrusted content

Content retrieved via the File Search tool (synthetic fund fact sheets, see
`app/infrastructure/fund_factsheet_store.py`) is treated as **untrusted data**,
not instructions: it is only ever surfaced to the model/user as quoted reference
material with a citation, never interpolated into system instructions or
executed. In a real deployment, any user- or third-party-supplied document
ingested via File Search should be handled the same way -- this matters because
retrieval-augmented tool content is a known prompt-injection vector.

## Dependencies

- All Python dependencies are pinned to exact versions in `requirements.txt` /
  `requirements-dev.txt` for reproducible builds.
- The Docker base image is pinned to a specific tag
  (`python:3.11.10-slim-bookworm`), not a floating `latest`.
- CI (`.github/workflows/ci.yml`) runs `ruff` and `mypy` on every push/PR.

## Container hardening

- Multi-stage Docker build; the runtime image contains no build toolchain.
- The container runs as a fixed non-root user (uid 1000), not root.
- Kubernetes manifests (`deploy/k8s/deployment.yaml`) set
  `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, and drop all Linux
  capabilities.

## Known non-goals of this demo

- No authentication/authorization is implemented on the API (`client_id` is an
  unauthenticated path parameter). A real deployment must add this.
- The audit log is a local append-only file, not a tamper-evident store (see
  `GOVERNANCE.md`).
- Rate limiting / abuse protection on the chat endpoint is out of scope for this
  demo beyond basic input-length validation.
