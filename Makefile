UV := $(shell which uv 2>/dev/null || echo $(HOME)/.local/bin/uv)

.PHONY: install run run-fresh clean \
        compare compare-step0 compare-step1 compare-step2 compare-step3 compare-step4 compare-step5 \
        viz

install:
	$(UV) sync

run:
	$(UV) run python main/run.py

run-fresh:
	rm -f cache/*.parquet
	$(UV) run python main/run.py

clean:
	rm -rf cache/*.parquet __pycache__ .pytest_cache

# ── Step-by-step comparison against gistemp4.0 ───────────────────────────────

compare-step0:
	$(UV) run python testing/compare_step0.py

compare-step1:
	$(UV) run python testing/compare_step1.py

compare-step2:
	$(UV) run python testing/compare_step2.py

compare-step3:
	$(UV) run python testing/compare_step3.py

compare-step4:
	$(UV) run python testing/compare_step4.py

compare-step5:
	$(UV) run python testing/compare_step5.py

compare: compare-step0 compare-step1 compare-step2 compare-step3 compare-step4 compare-step5

# ── Visualisations ────────────────────────────────────────────────────────────

viz:
	$(UV) run python visualization/run_all.py
