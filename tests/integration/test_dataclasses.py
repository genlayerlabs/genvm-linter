# { "Depends": "py-genlayer:test" }
"""Integration tests for dataclass validation in GenVM contracts."""

from genlayer import *
from dataclasses import dataclass

# Test basic dataclass with GenVM types
@dataclass
class UserProfile:
    name: str
    age: int
    balance: u256
    scores: DynArray[u64]

# Test nested dataclass
@dataclass
class Transaction:
    amount: u256
    sender: str
    receiver: str

@dataclass
class Block:
    transactions: DynArray[Transaction]
    block_number: u256
    timestamp: u64

# Test dataclass with allow_storage decorator
@dataclass
@allow_storage
class StorageItem:
    id: u256
    data: bytes
    tags: DynArray[str]

class DataclassContract(gl.Contract):
    profiles: DynArray[UserProfile]
    blocks: DynArray[Block]

    def __init__(self):
        self.profiles = DynArray()
        self.blocks = DynArray()

    @gl.public.write
    def test_valid_dataclass_usage(self):
        # Valid usage with explicit types
        profile1 = UserProfile(
            name="Alice",
            age=30,
            balance=u256(1000),
            scores=DynArray([u64(100), u64(200)])
        )

        # Valid usage with type equivalences
        profile2 = UserProfile(
            name="Bob",
            age=25,
            balance=500,  # int -> u256 (valid)
            scores=[50, 75, 100]  # list -> DynArray (valid)
        )

        self.profiles.append(profile1)
        self.profiles.append(profile2)

    @gl.public.write
    def test_nested_dataclasses(self):
        # Valid nested dataclass usage
        tx1 = Transaction(amount=100, sender="Alice", receiver="Bob")
        tx2 = Transaction(amount=200, sender="Bob", receiver="Charlie")

        block = Block(
            transactions=[tx1, tx2],  # list of dataclass instances -> DynArray
            block_number=1,  # int -> u256
            timestamp=1234567890  # int -> u64
        )

        self.blocks.append(block)

    @gl.public.write
    def test_invalid_field_errors(self):
        # This would trigger linting errors:
        # Error: Dataclass 'UserProfile' has no field 'invalid_field'
        # invalid = UserProfile(
        #     name="Test",
        #     age=20,
        #     balance=100,
        #     scores=[],
        #     invalid_field="error"  # LINTING ERROR
        # )
        pass

    @gl.public.write
    def test_type_mismatch_errors(self):
        # These would trigger linting errors if uncommented:

        # Error: Type mismatch for field 'name': expected str, got int
        # wrong_type1 = UserProfile(
        #     name=123,  # LINTING ERROR: int instead of str
        #     age=20,
        #     balance=100,
        #     scores=[]
        # )

        # Error: Type mismatch for field 'age': expected int, got str
        # wrong_type2 = UserProfile(
        #     name="Test",
        #     age="twenty",  # LINTING ERROR: str instead of int
        #     balance=100,
        #     scores=[]
        # )
        pass

    @gl.public.view
    def get_profiles(self) -> DynArray[UserProfile]:
        return self.profiles

    @gl.public.view
    def get_blocks(self) -> DynArray[Block]:
        return self.blocks

# Test various sized integer types
@dataclass
class IntegerTypes:
    small_int: u8
    medium_int: u64
    large_int: u256
    signed_int: i64
    bigint_value: bigint

class IntegerTypesContract(gl.Contract):
    def __init__(self):
        pass

    @gl.public.write
    def test_integer_types(self):
        # All of these should work with int literals
        data = IntegerTypes(
            small_int=255,  # int -> u8
            medium_int=1000000,  # int -> u64
            large_int=999999999,  # int -> u256
            signed_int=500,  # int -> i64 (positive for simplicity)
            bigint_value=bigint(10**30)  # explicit bigint
        )