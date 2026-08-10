"""
Execute the gistemp5 pipeline.
"""

import argparse
import os
import shutil
import sys
import time

# Allow running from repo root: python main/run.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.logger import logger
from steps import step0
from parameters.data import GHCN_TEMP_URL, GHCN_META_URL
from parameters.constants import START_YEAR, END_YEAR


def parse_args():
    parser = argparse.ArgumentParser(description="gistemp5 pipeline")
    parser.add_argument("--start_year", type=int, default=START_YEAR)
    parser.add_argument("--end_year", type=int, default=END_YEAR)
    return parser.parse_args()


def main():
    start = time.time()
    args = parse_args()

    results_dir = "results"
    if os.path.exists(results_dir):
        shutil.rmtree(results_dir)
    os.makedirs(results_dir)

    sep = "-" * 25

    # Step 0
    logger.info(f"|{sep} Step 0 {sep}|")
    df0 = step0.step0(GHCN_TEMP_URL, GHCN_META_URL, args.start_year, args.end_year)
    df0.to_csv(os.path.join(results_dir, "step0_output.csv"))

    elapsed = round(time.time() - start)
    h, rem = divmod(elapsed, 3600)
    m, s = divmod(rem, 60)
    logger.info(f"Done in {h}h {m}m {s}s")


if __name__ == "__main__":
    main()
