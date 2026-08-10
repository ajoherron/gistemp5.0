.PHONY: install run test clean

install:
	uv sync --group dev

run:
	uv run python main/run.py

test:
	uv run pytest testing/ -v

clean:
	rm -rf results/ logs/*.log __pycache__ .pytest_cache
