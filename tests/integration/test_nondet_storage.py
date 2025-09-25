# { "Depends": "py-genlayer:test" }
"""Integration tests for non-deterministic storage access validation."""

from genlayer import *
from dataclasses import dataclass
import json
import datetime

@allow_storage
@dataclass
class User:
    name: str
    birthday: datetime.datetime
    score: int

@allow_storage
@dataclass
class GameState:
    players: DynArray[User]
    round: int

class StorageAccessContract(gl.Contract):
    # Various storage types
    have_coin: bool
    count: int
    user: User
    game: GameState
    items: DynArray[str]

    def __init__(self):
        self.have_coin = True
        self.count = 100
        self.user = User("Alice", datetime.datetime.now(), 50)
        self.game = GameState(DynArray(), 1)
        self.items = DynArray(["sword", "shield"])

    @gl.public.write
    def test_primitive_copy(self):
        """Test that primitive types can be copied and used in nondet blocks."""
        # These should be OK - primitives are copied by value
        have_coin = self.have_coin  # bool
        count = self.count  # int

        def leader_fn():
            # These should be OK - using local copies
            print(f"Have coin: {have_coin}")
            print(f"Count: {count}")
            return have_coin and count > 0

        def validator_fn(result):
            return True

        gl.vm.run_nondet(leader_fn, validator_fn)

    @gl.public.write
    def test_direct_storage_access_error(self):
        """Test that direct self.attribute access is not allowed."""
        def leader_fn():
            # ERROR: Direct storage access not allowed
            print(self.have_coin)  # Should error
            print(self.count)      # Should error
            print(self.user)       # Should error
            return True

        def validator_fn(result):
            return True

        gl.vm.run_nondet(leader_fn, validator_fn)

    @gl.public.write
    def test_storage_object_reference_error(self):
        """Test that storage object references cannot be accessed."""
        # These create storage references, not copies
        user = self.user  # Storage reference to dataclass
        game = self.game  # Storage reference to dataclass
        items = self.items  # Storage reference to collection

        def leader_fn():
            # ERROR: These are storage references
            print(user)   # Should error
            print(game)   # Should error
            print(items)  # Should error
            return True

        def validator_fn(result):
            return True

        gl.vm.run_nondet(leader_fn, validator_fn)

    @gl.public.write
    def test_copy_to_memory_success(self):
        """Test that explicitly copied objects can be used."""
        # Explicit memory copies
        user_copy = gl.storage.copy_to_memory(self.user)
        game_copy = gl.storage.copy_to_memory(self.game)
        items_copy = gl.storage.copy_to_memory(self.items)

        def leader_fn():
            # These should be OK - explicit memory copies
            print(f"User: {user_copy}")
            print(f"Game: {game_copy}")
            print(f"Items: {items_copy}")
            return True

        def validator_fn(result):
            return True

        gl.vm.run_nondet(leader_fn, validator_fn)

    @gl.public.write
    def test_eq_principle_methods(self):
        """Test storage access in eq_principle methods."""
        have_coin = self.have_coin  # Safe copy

        def get_answer():
            # OK - using local copy
            if have_coin:
                return "yes"
            # ERROR - direct storage access
            if self.count > 0:  # Should error
                return "maybe"
            return "no"

        # strict_eq
        result1 = gl.eq_principle.strict_eq(get_answer)

        # prompt_comparative
        result2 = gl.eq_principle.prompt_comparative(
            get_answer,
            "The answer should be consistent"
        )

    @gl.public.write
    def test_nested_functions(self):
        """Test storage access in nested functions."""
        count = self.count  # Safe copy

        def outer_fn():
            def inner_fn():
                # OK - using local copy
                print(count)
                # ERROR - direct storage access
                print(self.have_coin)  # Should error
                return count > 0

            return inner_fn()

        gl.eq_principle.strict_eq(outer_fn)

    @gl.public.write
    def test_lambda_functions(self):
        """Test storage access in lambda functions."""
        have_coin = self.have_coin

        # Lambda with safe copy - OK
        gl.eq_principle.strict_eq(lambda: have_coin)

        # Lambda with direct access - ERROR
        gl.eq_principle.strict_eq(lambda: self.count)  # Should error

    @gl.public.write
    def test_propagated_taint(self):
        """Test that storage taint propagates through assignments."""
        user1 = self.user  # Storage reference
        user2 = user1  # Also tainted
        user_copy = gl.storage.copy_to_memory(user1)  # Safe copy
        user_copy2 = user_copy  # Also safe

        def leader_fn():
            # ERROR - tainted variables
            print(user1)  # Should error
            print(user2)  # Should error
            # OK - safe copies
            print(user_copy)   # OK
            print(user_copy2)  # OK
            return True

        def validator_fn(result):
            return True

        gl.vm.run_nondet(leader_fn, validator_fn)

    @gl.public.write
    def test_mixed_scenario(self):
        """Test a realistic mixed scenario."""
        # Prepare data
        have_coin = self.have_coin  # Safe primitive copy
        user = self.user  # Storage reference
        user_safe = gl.storage.copy_to_memory(self.user)  # Safe copy

        prompt = f"Process this data: coin={have_coin}"

        def process_data():
            # OK - using prompt with safe data
            result = gl.nondet.exec_prompt(prompt)

            # OK - using safe copies
            if have_coin:
                print(f"User safe: {user_safe}")

            # ERROR - trying to use storage reference
            try:
                print(f"User unsafe: {user}")  # Should error
            except:
                pass

            # ERROR - direct storage access
            if self.count > 50:  # Should error
                return "high"

            return "low"

        final_result = gl.eq_principle.prompt_comparative(
            process_data,
            "The result should be consistent"
        )

    @gl.public.view
    def get_have_coin(self) -> bool:
        """Safe view method - not in nondet context."""
        return self.have_coin  # OK - not in nondet block