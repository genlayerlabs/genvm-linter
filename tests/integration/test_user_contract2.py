# { "Depends": "py-genlayer:test" }

from genlayer import *

class TestContract(gl.Contract):
    
    @gl.public.view
    def get_value(self) -> int:
        return "string"  # Clear type error
    
    @gl.public.view
    def add_numbers(self, a: int, b: int) -> int:
        return a + b  # This should be fine
        
    @gl.public.view
    def wrong_param(self, num: int) -> str:
        return str(num + "text")  # Type error: can't add int + str
