"""AST-based safety checks for GenLayer contracts."""

from .linter import lint_contract, LintResult

__all__ = ["lint_contract", "LintResult"]
