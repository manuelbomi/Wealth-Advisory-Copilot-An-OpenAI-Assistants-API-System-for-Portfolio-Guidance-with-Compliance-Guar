# Contributing

This is a personal portfolio project, but it's built to normal open-source
contribution standards.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
make install
make test
```

## Before opening a PR

```bash
make lint        # ruff check .
make typecheck    # mypy app
make test          # pytest -v
```

CI (`.github/workflows/ci.yml`) runs the same three steps plus a Docker build on
every push and PR, all with no `OPENAI_API_KEY` set -- if it doesn't pass fully
offline, it isn't done.

## Code style

- Layered architecture (`app/api` / `app/service` / `app/domain` /
  `app/infrastructure`) -- new code should go in the layer that matches its
  responsibility; avoid reaching across layers (e.g. API routes must not import
  `openai` directly).
- Type hints on all new public functions; `mypy app` must stay clean.
- Comment the *why*, not the *what* -- see existing modules for the expected
  level of docstring/comment detail.
- No real employer or bank names anywhere in this repository. Use "Northbridge
  Financial Group" (fictional) for any example bank branding.

## Tests

New tools, guardrail rules, or service-layer behavior should ship with a unit
test in `tests/`, following the existing fixtures in `tests/conftest.py`.
