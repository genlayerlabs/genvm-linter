"""Intentionally failing regressions for bugs found on v0.11-dev."""

from genvm_linter.lint.safety import check_safety
from genvm_linter.lint.structure import check_structure


def test_array_rejects_negative_literal_size():
    source = """# { "Depends": "py-genlayer:test" }
from typing import Literal
from genlayer import *

class NegativeArray(Contract):
    values: Array[u256, Literal[-1]]
"""

    warnings = check_structure(source)

    assert any(warning.code == "E017" for warning in warnings), (
        "Array sizes must be positive, but Literal[-1] is represented as an "
        "ast.UnaryOp and bypasses the current E017 constant-only check"
    )


def test_nondet_storage_mutator_call_is_rejected():
    source = """# { "Depends": "py-genlayer:test" }
from genlayer import *

class MutatingNondet(Contract):
    values: DynArray[u256]

    def leader(self):
        self.values.append(u256(1))
        return gl.nondet.exec_prompt("pick a value")

    @gl.public.write
    def run(self):
        return gl.eq_principle.prompt_non_comparative(self.leader)
"""

    warnings = check_safety(source)

    assert any(warning.code == "E026" for warning in warnings), (
        "Calling a mutating storage method is a storage write, but E026 only "
        "visits Assign and AugAssign nodes"
    )
