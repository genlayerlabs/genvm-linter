# { "Depends": "py-genlayer:test" }

from genlayer import *

class TestContract(gl.Contract):
    """Test intelligent contract."""
    
    def __init__(self):
        """Initialize the contract."""
        pass
    
    @gl.public.view
    def test_method(self, value: int):
        """Test method."""
        x = gl.ContractAt("dasdasdasda")  # Should error - needs Address
        y = Address("invalid_address")     # Should error - invalid format
        pass
