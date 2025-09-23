# { "Depends": "py-genlayer:test" }
from genlayer import *

class TestContract(gl.Contract):
    
    def __init__(self):
        self.value = 0
    
    # Public method with decorator - OK
    @gl.public.view
    def get_value(self) -> int:
        return self.value
    
    # Method without decorator - should be WARNING (not ERROR)
    def get_unified_score_for_tweet(self, tweet_id: str) -> int:
        # This could be intentionally private or just missing decorator
        return self._calculate_score(tweet_id)
    
    # Private method with underscore - OK
    def _calculate_score(self, tweet_id: str) -> int:
        # Private helper method - no decorator needed
        return 42
    
    # Another method without decorator
    def process_data(self, data: str):
        # Should suggest adding decorator or underscore
        self.value = len(data)
    
    # Properly decorated write method
    @gl.public.write
    def set_value(self, new_value: int):
        self.value = new_value
