"""Output formatters for human and JSON output."""

import json
from typing import Any

from .lint import LintResult
from .validate import ValidationResult


def format_human_lint(result: LintResult) -> str:
    """Format lint result for human output."""
    lines = []

    if result.ok:
        lines.append(f"✓ Lint passed ({result.checks_passed} checks)")
    else:
        lines.append("✗ Lint failed")
        for w in result.warnings:
            line_info = f"line {w['line']}: " if w.get("line") else ""
            lines.append(f"  {line_info}{w['msg']}")

    return "\n".join(lines)


def format_human_validate(result: ValidationResult) -> str:
    """Format validation result for human output."""
    lines = []

    if result.ok:
        lines.append("✓ Validation passed")
        if result.contract_name:
            lines.append(f"  Contract: {result.contract_name}")
        if result.schema:
            methods = result.schema.get("methods", {})
            view_count = sum(1 for m in methods.values() if m.get("readonly", False))
            write_count = len(methods) - view_count
            lines.append(f"  Methods: {len(methods)} ({view_count} view, {write_count} write)")
    else:
        lines.append("✗ Validation failed")
        for e in result.errors:
            line_info = f"line {e['line']}: " if e.get("line") else ""
            lines.append(f"  {line_info}{e['msg']}")

    return "\n".join(lines)


def format_human_schema(result: ValidationResult) -> str:
    """Format schema output for human display."""
    if not result.ok or not result.schema:
        return format_human_validate(result)

    lines = []
    schema = result.schema

    lines.append(f"Contract: {result.contract_name}")
    lines.append("")

    # Constructor
    ctor = schema.get("ctor", {})
    ctor_params = ctor.get("params", [])
    lines.append(f"Constructor ({len(ctor_params)} params):")
    for param in ctor_params:
        # Params are [name, type] tuples
        name = param[0] if isinstance(param, list) else param.get("name", "?")
        ptype = param[1] if isinstance(param, list) else param.get("type", "?")
        lines.append(f"  - {name}: {_format_type(ptype)}")

    lines.append("")

    # Methods
    methods = schema.get("methods", {})
    lines.append(f"Methods ({len(methods)}):")
    for name, info in methods.items():
        readonly = "[view]" if info.get("readonly") else "[write]"
        params = info.get("params", [])
        # Params are [name, type] tuples
        param_names = [p[0] if isinstance(p, list) else p.get("name", "?") for p in params]
        param_str = ", ".join(param_names)
        lines.append(f"  - {name}({param_str}) {readonly}")

    return "\n".join(lines)


def format_json(data: dict[str, Any]) -> str:
    """Format data as compact JSON."""
    return json.dumps(data, separators=(",", ":"))


def format_json_pretty(data: dict[str, Any]) -> str:
    """Format data as pretty JSON."""
    return json.dumps(data, indent=2)


def format_vscode_json(lint_result: LintResult, validate_result: ValidationResult | None = None) -> str:
    """
    Format results for VS Code extension consumption.

    Expected format:
    {
        "results": [{"rule_id": "W001", "message": "...", "severity": "warning", "line": 1, "column": 0}],
        "summary": {"total": 1, "by_severity": {"error": 0, "warning": 1, "info": 0}}
    }
    """
    results = []
    error_count = 0
    warning_count = 0
    info_count = 0

    # Convert lint warnings
    for w in lint_result.warnings:
        code = w.get("code", "W000")
        severity = "error" if code.startswith("E") else "warning"

        if severity == "error":
            error_count += 1
        else:
            warning_count += 1

        results.append({
            "rule_id": code,
            "message": w.get("msg", "Unknown issue"),
            "severity": severity,
            "line": w.get("line", 1),
            "column": w.get("col", 0),
        })

    # Convert validation errors
    if validate_result and not validate_result.ok:
        for e in validate_result.errors:
            error_count += 1
            results.append({
                "rule_id": e.get("code", "E000"),
                "message": e.get("msg", "Validation error"),
                "severity": "error",
                "line": e.get("line", 1),
                "column": 0,
            })

    output = {
        "results": results,
        "summary": {
            "total": len(results),
            "by_severity": {
                "error": error_count,
                "warning": warning_count,
                "info": info_count,
            }
        }
    }

    return json.dumps(output)


def _format_type(type_info: Any) -> str:
    """Format a type for display."""
    if isinstance(type_info, str):
        return type_info
    if isinstance(type_info, dict):
        if "$ref" in type_info:
            return type_info["$ref"]
        if "$or" in type_info:
            return " | ".join(_format_type(t) for t in type_info["$or"])
        if "type" in type_info:
            return type_info["type"]
    return str(type_info)
