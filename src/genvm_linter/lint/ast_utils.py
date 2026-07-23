"""Shared AST helpers for lint checks."""

import ast

CONTRACT_BASE_NAMES = frozenset(
    {
        "Contract",
        "gl.Contract",
        "gl.contract.Contract",
        "genlayer.Contract",
        "genlayer.contract.Contract",
    }
)


def dotted_name(node: ast.expr) -> str | None:
    """Return a dotted name for Name/Attribute expressions."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def is_contract_subclass(node: ast.ClassDef) -> bool:
    """Return whether a class uses a supported GenLayer Contract base spelling."""
    return any(dotted_name(base) in CONTRACT_BASE_NAMES for base in node.bases)
