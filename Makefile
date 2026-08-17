UV := $(shell which uv 2>/dev/null || echo $(HOME)/.local/bin/uv)

.PHONY: help install run run-fresh clean \
        compare compare-step0 compare-step1 compare-step2 compare-step3 compare-step4 compare-step5 \
        viz

help:
	@echo "gistemp5.0 — available targets:"
	@echo ""
	@echo "  install          Install Python dependencies"
	@echo "  run              Run the full pipeline (uses cached steps when available)"
	@echo "  run-fresh        Re-run all steps, ignoring any cached intermediate outputs"
	@echo "  viz              Generate comparison figures for all steps (saves to visualization/)"
	@echo "  clean            Delete cached intermediate outputs"
	@echo ""
	@echo "  compare          Validate all steps against gistemp4.0 (runs steps 0-5)"
	@echo "  compare-step0    Validate step 0 only"
	@echo "  compare-step1    Validate step 1 only"
	@echo "  compare-step2    Validate step 2 only"
	@echo "  compare-step3    Validate step 3 only"
	@echo "  compare-step4    Validate step 4 only"
	@echo "  compare-step5    Validate step 5 only"

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
