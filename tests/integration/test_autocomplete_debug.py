# { "Depends": "py-genlayer:test" }

from genlayer import *

class DebugTest(gl.Contract):
    
    def __init__(self):
        pass
    
    @gl.public.view
    def test_all_cases(self) -> int:
        # Test Case 1: gl. (should show modules + root methods + properties)
        gl.
        
        # Test Case 2: gl.eq (partial - should show eq_principle)
        gl.eq
        
        # Test Case 3: gl.eq_principle. (should show methods)
        gl.eq_principle.
        
        # Test Case 4: gl.nondet.web. (should show web methods)
        gl.nondet.web.
        
        # Test Case 5: gl.message. (should show message properties)
        gl.message.
        
        # Test Case 6: Address constructor
        Address
        
        # Test Case 7: Variable autocomplete
        addr = Address("0x123...")
        addr.
        
        # Test Case 8: Signature help
        result = gl.eq_principle.prompt_comparative(  # Should show signature help
        
        return 42