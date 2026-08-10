.PHONY: install venv run test clean compare

install:
	uv sync --group dev

venv:
	uv venv

run:
	uv run python main/run.py

test:
	uv run pytest testing/ -v

compare:
	uv run python testing/compare_step0.py

clean:
	rm -rf results/ logs/*.log __pycache__ .pytest_cache
