"""E014 must accept the current storage decorator and keep flagging real omissions."""

import pytest

from genvm_linter.lint.structure import check_structure

SOURCE = """# {{ "Depends": "py-genlayer:test" }}
from dataclasses import dataclass
from genlayer import *

{decorators}
class Item:
    name: str

class Store(gl.Contract):
    items: TreeMap[str, Item]
"""


def e014(decorators: str) -> list[str]:
    source = SOURCE.format(decorators=decorators)
    return [w.msg for w in check_structure(source) if w.code == "E014"]


@pytest.mark.parametrize(
    "decorators",
    [
        "@gl.storage.allow",
        "@genlayer.storage.allow",
        "@storage.allow",
        "@gl.storage.allow\n@dataclass",
        "@dataclass\n@gl.storage.allow",
        "@allow_storage",
        "@gl.allow_storage",
        "@allow_storage\n@dataclass",
    ],
)
def test_supported_storage_decorators_are_accepted(decorators):
    assert e014(decorators) == []


@pytest.mark.parametrize(
    "decorators",
    [
        "",
        "@dataclass",
        "@other.storage.allow",
        "@gl.storage.deny",
        "@gl.public.view",
    ],
)
def test_storage_class_without_the_decorator_is_still_flagged(decorators):
    messages = e014(decorators)
    assert len(messages) == 1
    assert "Item" in messages[0]
    assert "@gl.storage.allow" in messages[0]
