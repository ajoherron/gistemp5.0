"""
Execute the gistemp5 pipeline.
"""

import argparse
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import logger
from utils import cache as step_cache
from steps import step0, step1, step2, step3, step4, step5
from utils.config import (GHCN_TEMP_URL, GHCN_META_URL, STRANGE_URL,
                              BRIGHTNESS_URL, SBBX_PATH, SBBX_INPUT_DIR)
from utils.config import START_YEAR, END_YEAR


def parse_args():
    parser = argparse.ArgumentParser(description="gistemp5 pipeline")
    parser.add_argument("--start_year", type=int, default=START_YEAR)
    parser.add_argument("--end_year", type=int, default=END_YEAR)
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached step outputs")
    return parser.parse_args()


def main():
    start = time.time()
    args = parse_args()
    sy, ey = args.start_year, args.end_year
    use_cache = not args.no_cache

    results_dir = "results"
    if os.path.exists(results_dir):
        shutil.rmtree(results_dir)
    os.makedirs(results_dir)

    sep = "-" * 25

    logger.info(f"|{sep} Step 0 {sep}|")
    df0 = step_cache.load('step0', sy, ey) if use_cache else None
    if df0 is None:
        df0 = step0.step0(GHCN_TEMP_URL, GHCN_META_URL, sy, ey)
        step_cache.save(df0, 'step0', sy, ey)
    else:
        logger.info("  Loaded step0 from cache.")
    df0.to_csv(os.path.join(results_dir, "step0_output.csv"))

    logger.info(f"|{sep} Step 1 {sep}|")
    df1 = step_cache.load('step1', sy, ey) if use_cache else None
    if df1 is None:
        df1 = step1.step1(df0, STRANGE_URL, sy, ey)
        step_cache.save(df1, 'step1', sy, ey)
    else:
        logger.info("  Loaded step1 from cache.")
    df1.to_csv(os.path.join(results_dir, "step1_output.csv"))

    logger.info(f"|{sep} Step 2 {sep}|")
    df2 = step_cache.load('step2', sy, ey) if use_cache else None
    if df2 is None:
        df2 = step2.step2(df1, GHCN_META_URL, BRIGHTNESS_URL, sy, ey)
        step_cache.save(df2, 'step2', sy, ey)
    else:
        logger.info("  Loaded step2 from cache.")
    df2.to_csv(os.path.join(results_dir, "step2_output.csv"))

    logger.info(f"|{sep} Step 3 {sep}|")
    df3 = step_cache.load('step3', sy, ey) if use_cache else None
    if df3 is None:
        df3 = step3.step3(df2, sy, ey)
        step_cache.save(df3, 'step3', sy, ey)
    else:
        logger.info("  Loaded step3 from cache.")
    df3.to_csv(os.path.join(results_dir, "step3_output.csv"))

    logger.info(f"|{sep} Step 4 {sep}|")
    df4 = step_cache.load('step4', sy, ey) if use_cache else None
    if df4 is None:
        df4 = step4.step4(SBBX_PATH, sy, ey, input_dir=SBBX_INPUT_DIR)
        step_cache.save(df4, 'step4', sy, ey)
    else:
        logger.info("  Loaded step4 from cache.")

    logger.info(f"|{sep} Step 5 {sep}|")
    # Step 5 produces two analyses (land, mixed), each with annual + monthly DataFrames.
    # Cached under separate keys: step5_land_annual, step5_land_monthly, etc.
    def _load_step5(sy, ey):
        dfs = {}
        for mode in ('land', 'mixed'):
            ann = step_cache.load(f'step5_{mode}_annual',  sy, ey)
            mon = step_cache.load(f'step5_{mode}_monthly', sy, ey)
            if ann is None or mon is None:
                return None
            dfs[mode] = {'annual': ann, 'monthly': mon}
        return dfs

    df5 = _load_step5(sy, ey) if use_cache else None
    if df5 is None:
        df5 = step5.step5(df3, df4, sy, ey)
        for mode in ('land', 'mixed'):
            step_cache.save(df5[mode]['annual'],  f'step5_{mode}_annual',  sy, ey)
            step_cache.save(df5[mode]['monthly'], f'step5_{mode}_monthly', sy, ey)
    else:
        logger.info("  Loaded step5 from cache.")

    elapsed = round(time.time() - start)
    h, rem = divmod(elapsed, 3600)
    m, s = divmod(rem, 60)
    logger.info(f"Done in {h}h {m}m {s}s")


if __name__ == "__main__":
    main()
