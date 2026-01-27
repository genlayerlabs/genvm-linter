"""
Backwards-compatible linter API for studio integration.

Wraps the new lint/validate modules with the old GenVMLinter interface.
"""

from pathlib import Path
from typing import List, Optional, Union

from .rules import Severity, ValidationResult
from .lint.safety import check_safety
from .lint.structure import check_structure


class GenVMLinter:
    """Main linter class for GenVM intelligent contracts.

    Provides backwards-compatible API for studio integration.
    Uses fast AST-based checks from lint module.
    """

    def __init__(self):
        """Initialize the linter."""
        pass

    def lint_file(self, filepath: Union[str, Path]) -> List[ValidationResult]:
        """Lint a single Python file.

        Args:
            filepath: Path to the Python file to lint

        Returns:
            List of validation results
        """
        filepath = Path(filepath)

        if not filepath.exists():
            return [
                ValidationResult(
                    rule_id="E100",
                    message=f"File not found: {filepath}",
                    severity=Severity.ERROR,
                    line=1,
                    column=0,
                    filename=str(filepath),
                )
            ]

        try:
            source_code = filepath.read_text(encoding="utf-8")
        except Exception as e:
            return [
                ValidationResult(
                    rule_id="E101",
                    message=f"Error reading file: {e}",
                    severity=Severity.ERROR,
                    line=1,
                    column=0,
                    filename=str(filepath),
                )
            ]

        return self.lint_source(source_code, str(filepath))

    def lint_source(
        self, source_code: str, filename: Optional[str] = None
    ) -> List[ValidationResult]:
        """Lint Python source code.

        Args:
            source_code: Python source code to lint
            filename: Optional filename for error reporting

        Returns:
            List of validation results
        """
        results: List[ValidationResult] = []

        # Syntax check first
        try:
            import ast

            ast.parse(source_code)
        except SyntaxError as e:
            results.append(
                ValidationResult(
                    rule_id="E001",
                    message=f"Syntax error: {e.msg}",
                    severity=Severity.ERROR,
                    line=e.lineno or 1,
                    column=e.offset or 0,
                    filename=filename,
                    suggestion="Fix the syntax error before other checks can run.",
                )
            )
            return results  # Can't continue with syntax errors

        # Safety checks (forbidden imports, non-determinism)
        safety_warnings = check_safety(source_code)
        for w in safety_warnings:
            severity = Severity.ERROR if w.code.startswith("E") else Severity.WARNING
            results.append(
                ValidationResult(
                    rule_id=w.code,
                    message=w.msg,
                    severity=severity,
                    line=w.line,
                    column=w.col,
                    filename=filename,
                    suggestion=_get_suggestion(w.code),
                )
            )

        # Structure checks (contract class, decorators)
        structure_warnings = check_structure(source_code)
        for w in structure_warnings:
            severity = Severity.ERROR if w.code.startswith("E") else Severity.WARNING
            results.append(
                ValidationResult(
                    rule_id=w.code,
                    message=w.msg,
                    severity=severity,
                    line=w.line,
                    column=w.col,
                    filename=filename,
                    suggestion=_get_suggestion(w.code),
                )
            )

        return results


def _get_suggestion(code: str) -> Optional[str]:
    """Get suggestion text for a warning code."""
    suggestions = {
        "W001": "Remove the forbidden import. Use GenLayer SDK equivalents instead.",
        "W002": "Use deterministic alternatives from the GenLayer SDK.",
        "W003": "Use Decimal instead of float for deterministic arithmetic.",
        "S001": "Add a contract header: # { \"Seq\": [{ \"Depends\": \"py-genlayer:...\" }] }",
        "S002": "Ensure your contract class inherits from Contract base class.",
    }
    return suggestions.get(code)


__all__ = ["GenVMLinter"]
