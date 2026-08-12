"""
Logging configuration for gistemp5.
"""

import logging
import datetime
import sys

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = f"logs/gistemp_{timestamp}.log"

console_handler = logging.StreamHandler(sys.stdout)
file_handler = logging.FileHandler(log_filename)

console_handler.setLevel(logging.INFO)
file_handler.setLevel(logging.DEBUG)

file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)

logger = logging.getLogger(__name__)
logger.addHandler(console_handler)
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)
