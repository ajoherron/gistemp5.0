"""
Logging configuration for gistemp5.
"""

import logging
import sys

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)
