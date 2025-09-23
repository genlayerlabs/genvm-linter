# { "Depends": "py-genlayer:test" }
from genlayer import *

class TestContract(gl.Contract):
    values: DynArray[u256]
    items: DynArray[int]
    
    def __init__(self):
        self.values = DynArray()
        self.items = DynArray()
    
    @gl.public.write
    def test_assignments(self):
        # This should work - assigning list[int] to DynArray[u256]
        self.values = [1, 2, 3, 4, 5]
        
        # This should also work - list[int] to DynArray[int]
        self.items = [10, 20, 30]
        
        # This should work too - DynArray to DynArray
        temp: DynArray[int] = DynArray()
        self.items = temp
        
        # And this - list comprehension
        self.values = [x * 2 for x in range(10)]
