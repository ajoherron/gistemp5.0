'''
Execute steps of the GISTEMP algorithm.

(Not including all steps for development)
'''


# Standard library imports
import sys
import os

# 3rd-party library imports
import pandas as pd

# Add the parent folder to sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

# Local imports
from steps import step0, step1

# Formatting for stdout
num_dashes: int = 25
dashes: str = '-' * num_dashes

# Step 0
print(f'|{dashes} Running Step 0 {dashes}|')
step0_output: pd.DataFrame = step0.step0()
# print(step0_output)

# Step 1
print(f'|{dashes} Running Step 1 {dashes}|')
step1_output: pd.DataFrame = step1.step1(step0_output)
# print(step1_output)

# Step 2
# print(f'|{dashes} Running Step 2 {dashes}|')
# step2_output = step2.step2(step1_output)

# Step 3
#print(f'|{dashes} Running Step 1 {dashes}|')
#step3_output = step3.step3(step1_output)