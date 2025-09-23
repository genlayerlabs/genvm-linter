# { "Depends": "py-genlayer:test" }

from genlayer import *
from dataclasses import dataclass

@dataclass
@allow_storage
class Account:
    address: str
    balance: u256  # OK in dataclass

class DemoContract(gl.Contract):
    total_supply: u256  # OK in storage
    accounts: TreeMap[str, Account]  # OK - GenVM collection
    
    def __init__(self):
        self.total_supply = u256(1000000)
        self.accounts = TreeMap()
    
    # ERRORS: sized integers in method signatures
    @gl.public.write
    def transfer_bad(self, to: str, amount: u256) -> u64:
        # Both parameter and return type are wrong
        return u64(0)
    
    # CORRECT: using int in method signatures
    @gl.public.write
    def transfer_good(self, to: str, amount: int) -> bool:
        # Convert to u256 internally for storage
        if to not in self.accounts:
            self.accounts[to] = Account(to, u256(0))
        self.accounts[to].balance += u256(amount)
        return True
    
    # Python type error that mypy should catch
    @gl.public.view
    def get_balance(self, address: str) -> int:
        if address in self.accounts:
            return "wrong type"  # MyPy should catch this
        return 0
