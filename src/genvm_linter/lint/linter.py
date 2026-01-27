"""Main linter combining all AST-based checks."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .safety import check_safety
from .structure import check_structure


@dataclass
class LintResult:
    """Result of linting a contract."""

    ok: bool = True
    checks_passed: int = 0
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result: dict[str, Any] = {
            "ok": self.ok,
            "passed": self.checks_passed,
        }
        if self.warnings:
            result["warnings"] = self.warnings
        return result


def lint_contract(contract_path: Path | str) -> LintResult:
    """
    Run all AST-based lint checks on a contract.

    Args:
        contract_path: Path to the contract file

    Returns:
        LintResult with warnings
    """
    contract_path = Path(contract_path)

    if not contract_path.exists():
        return LintResult(
            ok=False,
            warnings=[{"code": "E100", "msg": f"Contract not found: {contract_path}"}],
        )

    source = contract_path.read_text()
    all_warnings: list[dict[str, Any]] = []
    checks_passed = 0

    # Run safety checks
    safety_warnings = check_safety(source)
    if safety_warnings:
        for w in safety_warnings:
            all_warnings.append({
                "code": w.code,
                "msg": w.msg,
                "line": w.line,
            })
    else:
        checks_passed += 1

    # Run structure checks
    structure_warnings = check_structure(source)
    if structure_warnings:
        for w in structure_warnings:
            all_warnings.append({
                "code": w.code,
                "msg": w.msg,
                "line": w.line,
            })
    else:
        checks_passed += 1

    # Syntax check (via ast.parse)
    try:
        import ast
        ast.parse(source)
        checks_passed += 1
    except SyntaxError as e:
        all_warnings.append({
            "code": "E001",
            "msg": f"Syntax error: {e.msg}",
            "line": e.lineno or 1,
        })

    return LintResult(
        ok=len(all_warnings) == 0,
        checks_passed=checks_passed,
        warnings=all_warnings,
    )
