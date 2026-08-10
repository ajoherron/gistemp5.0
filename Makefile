UV := $(shell which uv 2>/dev/null || echo $(HOME)/.local/bin/uv)

.PHONY: install venv run test clean compare test-step0

install:
	$(UV) sync --group dev

venv:
	$(UV) venv

run:
	$(UV) run python main/run.py

test:
	$(UV) run pytest testing/ -v

compare:
	$(UV) run python testing/compare_step0.py

clean:
	rm -rf results/ logs/*.log __pycache__ .pytest_cache

# ── Step-by-step validation ───────────────────────────────────────────────────

test-step0:
	$(UV) run pytest testing/test_step0.py -v
