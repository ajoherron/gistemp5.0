UV := $(shell which uv 2>/dev/null || echo $(HOME)/.local/bin/uv)

.PHONY: install venv run clean compare compare-step0

install:
	$(UV) sync --group dev

venv:
	$(UV) venv

run:
	$(UV) run python main/run.py

clean:
	rm -rf results/ logs/*.log __pycache__ .pytest_cache

# ── Step-by-step comparison against gistemp4.0 ───────────────────────────────

compare-step0:
	$(UV) run python testing/compare_step0.py

compare: compare-step0
