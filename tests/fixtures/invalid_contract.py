# Missing magic comment
from genlayer import *

class InvalidContract(gl.Contract):
    balance: int  # Should use u256
    users: dict[str, int]  # Should use TreeMap
    items: list[str]  # Should use DynArray

    def __init__(self, initial_balance: int):
        self.balance = initial_balance

    # Missing decorator
    def get_balance(self) -> u256:  # Should return int
        return self.balance

    @gl.public.view
    def set_balance(self, amount: int):  # View decorator but modifies state
        self.balance = amount

    @gl.public.write
    @gl.public.view  # Multiple decorators
    def double_decorated(self):
        pass

    @gl.public.view
    def __init__(self, value: int):  # Constructor with public decorator
        pass