"""Contract validation using SDK reflection."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .sdk_loader import find_contract_class, load_contract_module, load_sdk


@dataclass
class ValidationResult:
    """Result of contract validation."""

    ok: bool = False
    contract_name: str | None = None
    schema: dict[str, Any] | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result: dict[str, Any] = {"ok": self.ok}
        if self.contract_name:
            result["contract"] = self.contract_name
        if self.schema:
            methods = self.schema.get("methods", {})
            result["methods"] = len(methods)
            result["view_methods"] = sum(
                1 for m in methods.values() if m.get("readonly", False)
            )
            result["write_methods"] = sum(
                1 for m in methods.values() if not m.get("readonly", False)
            )
            ctor = self.schema.get("ctor", {})
            result["ctor_params"] = len(ctor.get("params", []))
        if self.errors:
            result["errors"] = self.errors
        return result


def validate_contract(
    contract_path: Path | str,
    progress_callback: Callable[[int, int], None] | None = None,
) -> ValidationResult:
    """
    Validate a GenLayer contract using SDK reflection.

    Args:
        contract_path: Path to the contract file
        progress_callback: Optional callback for download progress

    Returns:
        ValidationResult with schema or errors
    """
    contract_path = Path(contract_path)

    if not contract_path.exists():
        return ValidationResult(
            ok=False,
            errors=[{"code": "E100", "msg": f"Contract not found: {contract_path}"}],
        )

    # Load SDK
    try:
        get_schema = load_sdk(contract_path, progress_callback)
    except Exception as e:
        return ValidationResult(
            ok=False,
            errors=[{"code": "E101", "msg": f"Failed to load SDK: {e}"}],
        )

    # Load contract module
    try:
        module = load_contract_module(contract_path)
    except SyntaxError as e:
        return ValidationResult(
            ok=False,
            errors=[
                {
                    "code": "E102",
                    "msg": f"Syntax error: {e.msg}",
                    "line": e.lineno,
                }
            ],
        )
    except ImportError as e:
        return ValidationResult(
            ok=False,
            errors=[{"code": "E103", "msg": f"Import error: {e}"}],
        )
    except Exception as e:
        return ValidationResult(
            ok=False,
            errors=[{"code": "E104", "msg": f"Failed to load contract: {e}"}],
        )

    # Find contract class
    contract_class = find_contract_class(module)
    if contract_class is None:
        return ValidationResult(
            ok=False,
            errors=[{"code": "E105", "msg": "No contract class found"}],
        )

    # Extract schema
    try:
        schema = get_schema(contract_class)
    except TypeError as e:
        # SDK type errors include location info
        error_msg = str(e)
        error: dict[str, Any] = {"code": "E106", "msg": f"Type error: {error_msg}"}

        # Try to extract line number from error
        if "line" in error_msg:
            import re

            match = re.search(r"'line':\s*(\d+)", error_msg)
            if match:
                error["line"] = int(match.group(1))

        return ValidationResult(ok=False, errors=[error])
    except Exception as e:
        return ValidationResult(
            ok=False,
            errors=[{"code": "E107", "msg": f"Schema extraction failed: {e}"}],
        )

    return ValidationResult(
        ok=True,
        contract_name=contract_class.__name__,
        schema=schema,
    )


def extract_schema(
    contract_path: Path | str,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any] | None:
    """
    Extract ABI schema from a contract.

    Args:
        contract_path: Path to the contract file
        progress_callback: Optional callback for download progress

    Returns:
        Schema dict or None if validation failed
    """
    result = validate_contract(contract_path, progress_callback)
    return result.schema if result.ok else None
