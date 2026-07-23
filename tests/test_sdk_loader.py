"""Unit tests for SDK layout compatibility."""

import sys
from types import ModuleType

from genvm_linter.validate import sdk_loader


def _package(name: str) -> ModuleType:
    package = ModuleType(name)
    package.__path__ = []
    return package


def _clear_genlayer_modules(monkeypatch):
    for name in list(sys.modules):
        if name == "genlayer" or name.startswith("genlayer."):
            monkeypatch.delitem(sys.modules, name)


def test_import_get_schema_prefers_current_sdk_layout(monkeypatch):
    _clear_genlayer_modules(monkeypatch)

    def expected(contract):
        return {"contract": contract}

    module = ModuleType("genlayer._internal.get_schema")
    module.get_schema = expected
    monkeypatch.setitem(sys.modules, "genlayer", _package("genlayer"))
    monkeypatch.setitem(sys.modules, "genlayer._internal", _package("genlayer._internal"))
    monkeypatch.setitem(sys.modules, "genlayer._internal.get_schema", module)

    assert sdk_loader._import_get_schema() is expected


def test_import_get_schema_falls_back_to_legacy_sdk_layout(monkeypatch):
    _clear_genlayer_modules(monkeypatch)

    def expected(contract):
        return {"contract": contract}

    module = ModuleType("genlayer.py.get_schema")
    module.get_schema = expected
    monkeypatch.setitem(sys.modules, "genlayer", _package("genlayer"))
    monkeypatch.setitem(sys.modules, "genlayer.py", _package("genlayer.py"))
    monkeypatch.setitem(sys.modules, "genlayer.py.get_schema", module)

    assert sdk_loader._import_get_schema() is expected


def test_broken_new_sdk_is_not_masked_by_legacy_fallback(monkeypatch):
    """A new-layout SDK whose own imports are broken must surface that error.

    Falling back to the legacy path here would hide a genuinely broken SDK
    behind a confusing 'no module named genlayer.py' error.
    """
    _clear_genlayer_modules(monkeypatch)

    genlayer = _package("genlayer")
    internal = _package("genlayer._internal")

    def _explode():
        raise ModuleNotFoundError(
            "No module named 'genlayer._internal.calldata'",
            name="genlayer._internal.calldata",
        )

    get_schema_mod = ModuleType("genlayer._internal.get_schema")
    get_schema_mod.__getattr__ = lambda _name: _explode()

    monkeypatch.setitem(sys.modules, "genlayer", genlayer)
    monkeypatch.setitem(sys.modules, "genlayer._internal", internal)
    # Importing the module raises a ModuleNotFoundError for a DIFFERENT module.
    monkeypatch.setitem(sys.modules, "genlayer._internal.get_schema", None)

    def _fake_import(name, *args, **kwargs):
        if name == "genlayer._internal.get_schema":
            _explode()
        raise AssertionError(f"legacy fallback must not be reached (tried {name})")

    monkeypatch.setattr("builtins.__import__", _fake_import)

    try:
        sdk_loader._import_get_schema()
    except ModuleNotFoundError as exc:
        assert exc.name == "genlayer._internal.calldata"
    else:
        raise AssertionError("expected the underlying ModuleNotFoundError to propagate")
