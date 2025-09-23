# { "Depends": "py-genlayer:test" }

from genlayer import *

class TestContract(gl.Contract):
    value: u256  # This is OK - sized integers are allowed in storage
    
    def __init__(self):
        self.value = u256(0)
    
    @gl.public.view
    def method_with_u64_param(self, param: u64) -> int:  # Should be error: u64 in parameter
        return int(param)
    
    @gl.public.view
    def method_with_u256_param(self, x: u256, y: i128) -> int:  # Should be error: u256, i128 in parameters
        return int(x + y)
    
    @gl.public.view
    def method_with_u64_return(self) -> u64:  # Already caught as error
        return u64(123)
    
    @gl.public.view
    def valid_method(self, x: int, y: str) -> int:  # This is OK
        return x

@dataclass
class MyData:
    id: u64  # This is OK - sized integers allowed in dataclasses
    value: u256  # This is OK
    name: str
