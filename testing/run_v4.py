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
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V4_DIR    = os.path.join(REPO_ROOT, '..', 'gistemp4.0')
zon_land  = os.path.join(V4_DIR, 'tmp', 'result', 'landZON.Ts.GHCN.CL.PA.1200.npz')
zon_mixed = os.path.join(V4_DIR, 'tmp', 'result', 'mixedZON.Ts.ERSSTV5.GHCN.CL.PA.1200.npz')

if not os.path.exists(zon_land) or not os.path.exists(zon_mixed):
    print("  Running full gistemp4.0 pipeline to generate step5 ZON files (this takes several minutes) …")
    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join('tool', 'run.py')],
        cwd=V4_DIR,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("gistemp4.0 full pipeline failed")
else:
    print("  ZON files already present, skipping.")

compare_step5.ensure_v4_cache()

print("\n=== gistemp4.0 pipeline complete ===")
