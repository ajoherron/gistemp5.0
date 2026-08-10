UV := $(shell which uv 2>/dev/null || echo $(HOME)/.local/bin/uv)

.PHONY: install venv run test clean compare

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
