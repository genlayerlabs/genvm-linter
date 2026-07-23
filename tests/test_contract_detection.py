"""Regression tests for contract base detection across SDK eras."""

import ast

import pytest

from genvm_linter.lint.ast_utils import is_contract_subclass
from genvm_linter.lint.safety import check_safety
from genvm_linter.lint.structure import check_structure


@pytest.mark.parametrize(
    "base",
    [
        "Contract",
        "gl.Contract",
        "gl.contract.Contract",
        "genlayer.Contract",
        "genlayer.contract.Contract",
    ],
)
def test_all_contract_base_spellings_enable_contract_scoped_rules(base):
    source = f"""# {{ "Depends": "py-genlayer:test" }}
class StoredValue:
    pass

class Storage({base}):
    count: int
    value: StoredValue

    def missing_self():
        raise ValueError("bad")
"""

    structure_codes = {warning.code for warning in check_structure(source)}
    safety_codes = {warning.code for warning in check_safety(source)}

    assert {"E014", "E015", "E022"} <= structure_codes
    assert "W004" in safety_codes


class TestNonContractBases:
    """Guards against future over-broadening of CONTRACT_BASE_NAMES."""

    @pytest.mark.parametrize(
        "source",
        [
            "class C(object): pass",
            "class C: pass",
            "class C(foo.bar.Baz): pass",
            "class C(gl.contract.Other): pass",
            "class C(other.contract.Contract): pass",
            "class C(Contractish): pass",
        ],
    )
    def test_unrelated_bases_are_not_contracts(self, source):
        node = ast.parse(source).body[0]
        assert is_contract_subclass(node) is False
