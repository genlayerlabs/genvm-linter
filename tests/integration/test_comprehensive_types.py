# { "Depends": "py-genlayer:test" }
from genlayer import *
from dataclasses import dataclass

@dataclass
class Item:
    id: u64
    values: DynArray[u256]

class AdvancedContract(gl.Contract):
    items: DynArray[Item]
    numbers: DynArray[u256]
    mappings: TreeMap[str, DynArray[int]]
    
    def __init__(self):
        self.items = DynArray()
        self.numbers = DynArray()
        self.mappings = TreeMap()
    
    @gl.public.write
    def add_numbers(self, nums: list[int]):
        # Should work: list[int] -> DynArray[u256]
        self.numbers = nums
        
        # Should work: literal list
        self.numbers = [1, 2, 3, 4, 5]
        
        # Should work: list comprehension
        self.numbers = [x * 2 for x in range(10)]
    
    @gl.public.view
    def get_numbers(self) -> list[int]:
        # Should work: DynArray[u256] -> list[int]
        return self.numbers
    
    @gl.public.write
    def process_items(self):
        # Complex nested type
        item = Item(
            id=42,  # int -> u64: should work
            values=[100, 200, 300]  # list[int] -> DynArray[u256]: should work
        )
        self.items.append(item)
        
        # Store in map
        self.mappings["key"] = [1, 2, 3]  # list[int] -> DynArray[int]
    
    @gl.public.view
    def get_item_values(self, index: int) -> list[int]:
        if index < len(self.items):
            # DynArray[u256] -> list[int]
            return self.items[index].values
        return []
