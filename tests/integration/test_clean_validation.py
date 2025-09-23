# { "Depends": "py-genlayer:test" }
from genlayer import *
from dataclasses import dataclass

@allow_storage
@dataclass
class Account:
    address: str
    balance: u256
    age: u8

class CleanContract(gl.Contract):
    accounts: DynArray[Account]
    balances: TreeMap[str, u256]
    
    def __init__(self):
        self.accounts = DynArray()
        self.balances = TreeMap()
    
    @gl.public.write
    def add_account(self, address: str, initial_balance: int, age: int):
        # This should work - passing int to u256/u8 fields
        account = Account(
            address=address,
            balance=initial_balance,  # int -> u256: OK
            age=age  # int -> u8: OK  
        )
        self.accounts.append(account)
        self.balances[address] = u256(initial_balance)
        
        # Address constructor should work
        addr = Address(address)
        return True
    
    @gl.public.view
    def get_balance(self, address: str) -> int:
        if address in self.balances:
            return int(self.balances[address])
        return 0
    
    # This should still error - u256 in parameter
    @gl.public.view
    def bad_method(self, amount: u256) -> int:
        return int(amount)
