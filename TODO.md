# Onboarding polish checklist

Ordered by impact for a science-first, less-technical audience (e.g. GISS researchers).

## Critical — would stop someone cold

- [x] **Quick Start section in README** — 3 commands at the very top: install, run, see output
- [x] **Explain `uv` and provide a `pip` fallback** — most scientists use pip or conda; `uv sync` is opaque without context or install instructions
- [x] **Describe the output** — what files are produced, where they land, what format, what they mean

## Significant — friction but surmountable

- [x] **Fix stale repo structure in README** — lists `parameters/` directory that doesn't exist; `utils/config.py` does that job
- [x] **Describe visualization output** — `make viz` / `run_all.py` produces PNGs but README doesn't say where or what they show
- [x] **Remove `requests` from `pyproject.toml`** — listed as a dependency but unused (switched to `urllib.request`)

## Nice-to-have

- [x] **Add `make help`** — one-line descriptions of every Makefile target
- [x] **Friendly error on wrong Python version** — currently fails with a cryptic library error; a clear message pointing to Python 3.11+ would help
