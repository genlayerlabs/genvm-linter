# { "Depends": "py-genlayer:test" }
from genlayer import *

class BestPracticesContract(gl.Contract):
    """
    Example showing GenVM best practices for method visibility.
    """
    value: u256
    
    def __init__(self):
        self.value = u256(0)
    
    # ✅ GOOD: Public view method with decorator
    @gl.public.view
    def get_value(self) -> int:
        """Public method - accessible from outside."""
        return int(self.value)
    
    # ✅ GOOD: Public write method with decorator
    @gl.public.write
    def set_value(self, new_value: int):
        """Public method - can modify state."""
        self.value = new_value
    
    # ✅ GOOD: Private helper with underscore prefix
    def _validate_input(self, value: int) -> bool:
        """Private method - internal use only, no decorator needed."""
        return 0 <= value <= 1000000
    
    # ✅ GOOD: Another private method
    def _internal_calculation(self, x: int, y: int) -> int:
        """Private helper - underscore indicates it's not public."""
        return x * y + int(self.value)
    
    # ⚠️ WARNING: Missing decorator and no underscore
    def calculate_score(self, data: str) -> int:
        """
        This will show a warning suggesting to either:
        1. Add @gl.public.view/write to make it public, or
        2. Rename to _calculate_score to indicate it's private
        """
        return len(data)
    
    # ⚠️ WARNING: Another ambiguous method
    def process_batch(self, items: list[str]):
        """
        Unclear if this should be public or private.
        Linter will suggest adding decorator or underscore.
        """
        for item in items:
            self._validate_input(len(item))
