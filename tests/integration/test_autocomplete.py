# { "Depends": "py-genlayer:test" }

from genlayer import *

class TestContract(gl.Contract):
    counter: u64
    
    def __init__(self):
        self.counter = u64(0)
    
    @gl.public.write  
    def test_methods(self) -> int:
        # Test autocomplete for gl.eq_principle.
        result1 = gl.eq_principle.strict_eq(lambda: "test").get()
        
        # Test autocomplete for gl.nondet.
        result2 = gl.nondet.exec_prompt("What is 2+2?").get()
        
        # Test autocomplete for gl.nondet.web.
        response = gl.nondet.web.get("https://example.com").get()
        
        # Test autocomplete for gl.storage.
        data = gl.storage.inmem_allocate(TestContract)
        
        return 42