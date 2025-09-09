# { "Depends": "py-genlayer:test" }

from genlayer import *

# No contract class - should trigger error

def regular_function():
    pass

class RegularClass:
    pass