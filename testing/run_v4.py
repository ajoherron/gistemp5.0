"""
Run the gistemp4.0 pipeline and cache all step outputs.

Used by `make run-v4`. Must be run after `make install-v4`.
Run from repo root:
    python testing/run_v4.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import compare_step0
import compare_step1
import compare_step2
import compare_step3
import compare_step4
import compare_step5

print("=== Running gistemp4.0 pipeline ===\n")

print("-- Step 0 --")
compare_step0.fetch_v4_inputs()
compare_step0.run_v4_step0()

print("\n-- Step 1 --")
compare_step1.fetch_v4_inputs()
compare_step1.run_v4_step1()

print("\n-- Step 2 --")
compare_step2.fetch_v4_inputs()
compare_step2.run_v4_step2()

print("\n-- Step 3 --")
compare_step3.run_v4_dump()

print("\n-- Step 4 --")
compare_step4.run_v4_sbbx_dump()

print("\n-- Step 5 --")
compare_step5.ensure_v4_cache()

print("\n=== gistemp4.0 pipeline complete ===")
