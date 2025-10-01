"""
Example contracts showing version-specific features and requirements.
"""

# ==============================================================================
# Example 1: v0.1.0 Contract (Original version)
# ==============================================================================

EXAMPLE_V010 = """# v0.1.0
# { "Depends": "py-genlayer:test" }

from genlayer import *  # Star import required in v0.1.0

class SimpleStorage(gl.Contract):
    def __init__(self):  # __init__ required in v0.1.0
        self.value = 0

    @gl.public.write
    def set_value(self, val: int) -> None:
        self.value = val

    @gl.public.view
    def get_value(self) -> int:
        return self.value
"""

# ==============================================================================
# Example 2: v0.2.0 Contract (Enhanced imports and optional init)
# ==============================================================================

EXAMPLE_V020 = """# v0.2.0
# { "Depends": "py-genlayer:test" }

from genlayer import gl, TreeMap, u32  # Specific imports allowed in v0.2.0+

class EnhancedStorage(gl.Contract):
    # No __init__ required in v0.2.0+
    storage: TreeMap[str, u32]

    @gl.public.write
    def store(self, key: str, value: u32) -> None:
        self.storage[key] = value

        # Lazy object support in v0.2.0+
        lazy_storage = self.storage.lazy()

    @gl.public.view
    def retrieve(self, key: str) -> u32:
        return self.storage.get(key, u32(0))
"""

# ==============================================================================
# Example 3: v0.3.0 Contract (Dataclasses and events)
# ==============================================================================

EXAMPLE_V030 = """# v0.3.0
# { "Depends": "py-genlayer:test" }

from genlayer import gl, TreeMap, u32
from dataclasses import dataclass

@dataclass
class UserData:
    name: str
    balance: u32
    active: bool

class ValueChanged(gl.Event):
    def __init__(self, old_value: u32, new_value: u32):
        self.old_value = old_value
        self.new_value = new_value

class AdvancedContract(gl.Contract):
    users: TreeMap[str, UserData]
    total_balance: u32

    @gl.public.write  # At least one public method required in v0.3.0+
    def add_user(self, address: str, name: str, initial_balance: u32) -> None:
        user = UserData(
            name=name,
            balance=initial_balance,
            active=True
        )
        self.users[address] = user

        # Non-deterministic storage access patterns
        old_total = self.total_balance
        self.total_balance = old_total + initial_balance

        # Emit event
        ValueChanged(old_total, self.total_balance).emit()

    @gl.public.view
    def get_user(self, address: str) -> UserData:
        return self.users.get(address)
"""

# ==============================================================================
# Example 4: Latest version (All features)
# ==============================================================================

EXAMPLE_LATEST = """# { "Depends": "py-genlayer:latest" }

from genlayer import (
    gl, TreeMap, DynArray,
    u32, u256, i32,
    eq_principle_prompt_comparative as eq_prompt
)
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class Transaction:
    sender: str
    recipient: str
    amount: u256
    timestamp: u32
    metadata: Dict[str, str]

class TransactionEvent(gl.Event):
    def __init__(self, tx: Transaction, status: str):
        self.transaction = tx
        self.status = status

class ModernContract(gl.Contract):
    # Advanced storage with generic types
    transactions: TreeMap[str, List[Transaction]]
    balances: TreeMap[str, u256]
    pending: DynArray[Transaction]
    config: Dict[str, str]

    def __init__(self):
        # Optional init with setup logic
        self.config = {
            "version": "latest",
            "features": "all"
        }

    @gl.public.write
    async def process_transaction(self, tx: Transaction) -> bool:
        # Async support for non-deterministic operations
        validation = await self.validate_transaction(tx)
        if not validation:
            return False

        # Advanced storage operations
        self.pending.append(tx)

        # Update balances with locking
        sender_balance = self.balances.get(tx.sender, u256(0))
        if sender_balance < tx.amount:
            TransactionEvent(tx, "failed").emit()
            return False

        self.balances[tx.sender] = sender_balance - tx.amount
        recipient_balance = self.balances.get(tx.recipient, u256(0))
        self.balances[tx.recipient] = recipient_balance + tx.amount

        # Store transaction
        if tx.sender not in self.transactions:
            self.transactions[tx.sender] = []
        self.transactions[tx.sender].append(tx)

        TransactionEvent(tx, "success").emit()
        return True

    @gl.public.view
    def get_balance(self, address: str) -> u256:
        return self.balances.get(address, u256(0))

    @gl.public.view
    def get_transactions(self, address: str) -> List[Transaction]:
        return self.transactions.get(address, [])

    async def validate_transaction(self, tx: Transaction) -> bool:
        # Complex validation logic
        return tx.amount > u256(0) and tx.sender != tx.recipient
"""

# ==============================================================================
# Example 5: Complex dependencies with version
# ==============================================================================

EXAMPLE_COMPLEX_DEPS = """# v0.3.0
# {
#   "Seq": [
#     { "Depends": "py-lib-genlayer-embeddings:09h0i209wrzh4xzq86f79c60x0ifs7xcjwl53ysrnw06i54ddxyi" },
#     { "Depends": "py-genlayer:1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379" }
#   ]
# }

from genlayer import gl, TreeMap
from genlayer.embeddings import create_embedding, cosine_similarity

class EmbeddingContract(gl.Contract):
    embeddings: TreeMap[str, List[float]]

    @gl.public.write
    def store_embedding(self, key: str, text: str) -> None:
        # Using external dependency
        embedding = create_embedding(text)
        self.embeddings[key] = embedding

    @gl.public.view
    def compare_similarity(self, key1: str, key2: str) -> float:
        emb1 = self.embeddings.get(key1)
        emb2 = self.embeddings.get(key2)
        if emb1 and emb2:
            return cosine_similarity(emb1, emb2)
        return 0.0
"""

# ==============================================================================
# Utility function to validate contracts
# ==============================================================================

def validate_contract_examples():
    """Validate all example contracts with version-aware linter."""
    from genvm_linter import GenVMLinter

    linter = GenVMLinter()

    examples = [
        ("v0.1.0", EXAMPLE_V010),
        ("v0.2.0", EXAMPLE_V020),
        ("v0.3.0", EXAMPLE_V030),
        ("latest", EXAMPLE_LATEST),
        ("complex", EXAMPLE_COMPLEX_DEPS)
    ]

    for name, source in examples:
        print(f"\n=== Validating {name} contract ===")
        results = linter.lint_source(source, f"{name}_contract.py")

        errors = [r for r in results if r.severity.value == "error"]
        warnings = [r for r in results if r.severity.value == "warning"]
        info = [r for r in results if r.severity.value == "info"]

        print(f"Errors: {len(errors)}, Warnings: {len(warnings)}, Info: {len(info)}")

        for error in errors:
            print(f"  ERROR: {error.message}")

        # Get version info
        version_info = linter.get_version_info(source)
        print(f"  Version: {version_info['version']}")
        print(f"  Features: {list(version_info['features'].keys())[:5]}...")


if __name__ == "__main__":
    validate_contract_examples()