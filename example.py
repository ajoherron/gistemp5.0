'''
This file is an example of how Python files should be laid out.
Start with a descriptive docstring at the top.
'''

# Standard library imports first
import os
import sys

# 3rd-party library imports second
import numpy as np
import pandas as pd

# Local imports third
from steps import step0

# Global constants and variables (all caps)
FOO: int = 13
BAR: int = 1738

# Classes
class Hello:
    def __init__(self, name: str):
        self.name = name
    
    def greet(self) -> str:
        return f'Hello, {self.name}!'
    
# Functions
def square(x: int) -> int:
    '''
    Function that squares the input value.

    Input:
        x (int): Integer to be squared.

    Output:
        x**2 (int): Squared integer (x^2).
    '''
    return x**2

# Script logic
if __name__ == '__main__':

    # Print greeting from class
    obj = Hello('Alex')
    greeting = obj.greet()
    print(greeting)

    # Calculate square using function
    result = square(FOO)
    print(f'{FOO} squared is {result}')
