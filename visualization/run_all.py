"""
Run all visualization scripts.

    python visualization/run_all.py
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import step0_summary
import step1_summary
import step2_comparison
import step3_comparison
import step4_comparison
import step5_comparison

print("=== Step 0 ===")
df4_0, df5_0 = step0_summary.load_data()
stats_0 = step0_summary.validate(df4_0, df5_0)
print(f"  {stats_0['agreement']}")
step0_summary.plot(df4_0, df5_0, stats_0)

print("\n=== Step 1 ===")
df4_1, df5_1 = step1_summary.load_data()
stats_1 = step1_summary.validate(df4_1, df5_1)
print(f"  {stats_1['agreement']}")
step1_summary.plot(df4_1, df5_1, stats_1)

print("\n=== Step 2 ===")
df4_2, df5_2 = step2_comparison.load_data()
stats_2 = step2_comparison.validate(df4_2, df5_2)
print(f"  {stats_2['agreement']}")
step2_comparison.plot(df4_2, df5_2, stats_2)

print("\n=== Step 3 ===")
df4_3, df5_3 = step3_comparison.load_data()
stats_3 = step3_comparison.validate(df4_3, df5_3)
print(f"  {stats_3['agreement']}")
step3_comparison.plot(df4_3, df5_3, stats_3)

print("\n=== Step 4 ===")
df4_4, df5_4 = step4_comparison.load_data()
stats_4 = step4_comparison.validate(df4_4, df5_4)
print(f"  {stats_4['agreement']}")
step4_comparison.plot(df4_4, df5_4, stats_4)

print("\n=== Step 5 ===")
try:
    data_5 = step5_comparison.load_data()
    step5_comparison.plot(data_5)
except FileNotFoundError as e:
    print(f"  Skipped: {e}")

print("\nDone. Figures saved to visualization/")
