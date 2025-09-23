# { "Depends": "py-genlayer:test" }

from genlayer import *

class SimpleContract(gl.Contract):
    value: u256
    
    def __init__(self):
        self.value = u256(0)
    
    @gl.public.view
    def get_value(self) -> int:
        # Type error: returning str instead of int
        return "hello world"  # This should be caught by mypy
    
    @gl.public.view
    def add_numbers(self, a: int, b: int) -> int:
        # Type error: can't add int and str
        return a + "string"  # This should be caught by mypy
    
    @gl.public.view
    def valid_method(self, x: int) -> int:
        return x * 2  # This is OK
