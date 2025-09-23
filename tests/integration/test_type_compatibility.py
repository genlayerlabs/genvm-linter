# { "Depends": "py-genlayer:test" }
from genlayer import *

class Contract(gl.Contract):
    nums: DynArray[u256]
    
    @gl.public.write  
    def set_nums(self, values: list[int]):
        # Should accept list[int] -> DynArray[u256]
        self.nums = values
        
    @gl.public.write
    def direct_assign(self):
        # Should accept literal list
        self.nums = [1, 2, 3]
        
    @gl.public.view
    def get_nums(self) -> list[int]:
        # Should accept DynArray[u256] -> list[int]
        return self.nums
