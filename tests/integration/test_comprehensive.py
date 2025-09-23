# { "Depends": "py-genlayer:test" }

from genlayer import *
from typing import List, Dict
from dataclasses import dataclass

# Test proper usage in dataclasses
@dataclass
@allow_storage
class ValidDataClass:
    id: u64  # OK - sized integers allowed in dataclasses  
    value: u256  # OK
    name: str
    count: int  # OK - regular int is fine too

@dataclass
class DataClassWithoutStorage:
    id: u64  # Should warn about missing @allow_storage
    value: u256

class TestContract(gl.Contract):
    # Storage fields - sized integers are OK here
    balance: u256  # OK
    user_count: u64  # OK
    active: bool
    name: str
    users: DynArray[str]  # OK - GenVM collection
    balances: TreeMap[str, u256]  # OK - GenVM collection
    
    def __init__(self):
        self.balance = u256(0)
        self.user_count = u64(0)
        self.active = True
        self.name = "Test"
        self.users = DynArray()
        self.balances = TreeMap()
    
    # ERROR: sized integers in method parameters
    @gl.public.view
    def bad_param_u64(self, amount: u64) -> int:
        return int(amount)
    
    @gl.public.view
    def bad_param_u256(self, value: u256) -> int:
        return int(value)
    
    @gl.public.view
    def bad_param_i128(self, signed: i128) -> int:
        return int(signed)
    
    # ERROR: sized integers in return types
    @gl.public.view
    def bad_return_u64(self) -> u64:
        return u64(123)
    
    @gl.public.view
    def bad_return_u256(self) -> u256:
        return self.balance
    
    @gl.public.view
    def bad_return_i256(self) -> i256:
        return i256(-123)
    
    # OK: proper method signatures
    @gl.public.view
    def good_method(self, x: int, y: str) -> int:
        return x * 2
    
    @gl.public.view
    def good_method_no_return(self, data: str):
        self.name = data
    
    @gl.public.write
    def good_method_write(self, amount: int) -> bool:
        self.balance = u256(amount)  # OK - can convert int to u256 internally
        return True
    
    # OK: bigint is allowed (special case)
    @gl.public.view
    def method_with_bigint(self, big: bigint) -> bigint:
        return big * bigint(2)
    
    # Method with complex types
    @gl.public.view
    def method_with_list_param(self, items: List[int]) -> Dict[str, int]:
        result = {}
        for i, item in enumerate(items):
            result[str(i)] = item
        return result
    
    # Internal method - still should follow rules
    def internal_bad_param(self, val: u128) -> int:
        return int(val)
    
    def internal_bad_return(self) -> u64:
        return self.user_count

# Another class that's not a contract
class HelperClass:
    # These should be OK - not in a contract
    value: u256
    
    def process(self, amount: u64) -> u256:  # Should still error in methods
        return u256(amount * 2)

# Test dataclass in contract context
@dataclass
@allow_storage  
class UserData:
    user_id: u64
    balance: u256
    username: str

class AnotherContract(gl.Contract):
    users: TreeMap[str, UserData]
    
    def __init__(self):
        self.users = TreeMap()
    
    @gl.public.write
    def add_user(self, username: str, initial_balance: int):
        user = UserData(
            user_id=u64(len(self.users)),
            balance=u256(initial_balance),
            username=username
        )
        self.users[username] = user
    
    @gl.public.view
    def get_user_balance(self, username: str) -> int:  # OK - returns int
        if username in self.users:
            return int(self.users[username].balance)
        return 0