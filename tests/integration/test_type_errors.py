# { "Depends": "py-genlayer:test" }

from typing import Union
from genlayer import *

class TypeErrorContract(gl.Contract):
    
    def __init__(self):
        self.value: int = 0
    
    @gl.public.view
    def get_value(self) -> int:
        # Type error: returning str instead of int
        return "hello world"
    
    @gl.public.view  
    def wrong_parameter_type(self, num: int) -> str:
        # Type error: passing str to int parameter
        result = self.process_number("not a number")
        return result
        
    def process_number(self, n: int) -> str:
        return f"Number: {n}"
    
    @gl.public.view
    def mixed_return_type(self, flag: bool) -> int:
        if flag:
            return 42  # Correct: int
        else:
            return "error"  # Type error: str instead of int
            
    @gl.public.view  
    def sized_integer_return(self) -> u64:  # Should be error: sized int in return type
        return u64(123)