# { "Depends": "py-genlayer:test" }

from genlayer import *

class UserContract(gl.Contract):
    
    def __init__(self):
        self.balance: int = 0
    
    @gl.public.view
    def get_balance(self) -> int:
        # Type error: returning string instead of int
        return "not a number"
    
    @gl.public.view  
    def calculate_fee(self, amount: int) -> int:
        # Type error: passing string to int parameter
        fee_rate = self.get_fee_rate("invalid")
        return amount * fee_rate
        
    def get_fee_rate(self, category: str) -> float:
        if category == "premium":
            return 0.1
        return 0.05