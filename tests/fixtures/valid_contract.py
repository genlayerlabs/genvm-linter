# { "Depends": "py-genlayer:test" }

from genlayer import *
from dataclasses import dataclass

@allow_storage
@dataclass
class UserData:
    name: str
    balance: u256
    is_active: bool

class ValidContract(gl.Contract):
    owner: Address
    users: TreeMap[Address, UserData]
    balances: DynArray[u256]
    total_supply: u256

    def __init__(self, initial_supply: int):
        self.owner = gl.message.sender_address
        self.total_supply = initial_supply

    @gl.public.view
    def get_balance(self, user: str) -> int:
        address = Address(user)
        user_data = self.users.get(address)
        if user_data:
            return user_data.balance
        return 0

    @gl.public.write
    def set_balance(self, user: str, amount: int):
        address = Address(user)
        user_data = UserData(name="", balance=amount, is_active=True)
        self.users[address] = user_data
        self.total_supply = amount  # Modify state to avoid warning

    @gl.public.view
    def get_total_supply(self) -> int:
        return self.total_supply

    def _private_helper(self) -> str:
        return "helper"