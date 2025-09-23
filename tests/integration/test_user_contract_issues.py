# v0.1.0
# { "Depends": "py-genlayer:latest" }
from genlayer import *
from dataclasses import dataclass
 
import json
import typing
 
@allow_storage
@dataclass
class User:
    name: str
    age: u8
    balance: u256
 
class UserArrayOperations(gl.Contract):
    users: DynArray[User]
    user_ids: DynArray[str]
    
    def __init__(self):
        pass
    
    @gl.public.write
    def add_user(self, name: str, age: int, balance: int):
        user = User(name=name, age=age, balance=balance)
        self.users.append(user)
        self.user_ids.append(f"user_{len(self.users)}")
        address1 = Address("0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6")
        return address1.as_b64

    
    @gl.public.view
    def find_user_by_name(self, name: u64) -> str:
        for user in self.users:
            if user.name == name:
                return user
        return "acdss"
