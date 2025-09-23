# { "Depends": "py-genlayer:test" }

from genlayer import *
from dataclasses import dataclass

@dataclass
@allow_storage
class Account:
    balance: u256

class TestContract(gl.Contract):
    accounts: TreeMap[str, Account]  # Should work now
    users: DynArray[str]  # Should work now
    
    def __init__(self):
        self.accounts = TreeMap()
        self.users = DynArray()
    
    @gl.public.write
    def test_address(self):
        # Should work now - Address accepts string
        addr = Address("0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6")
        return addr.as_b64
    
    @gl.public.write  
    def test_sized_int_constructor(self):
        # Should work - u256 accepts int
        val = u256(1000)
        return int(val)
    
    # This should still error - sized int in parameter
    @gl.public.view
    def bad_param(self, amount: u256) -> int:
        return int(amount)
