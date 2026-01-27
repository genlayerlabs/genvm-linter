"""Backwards-compatible rules module for studio integration."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Severity(Enum):
    """Severity levels for validation results."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    """Result of a validation rule check."""

    rule_id: str
    message: str
    severity: Severity
    line: int
    column: int
    filename: Optional[str] = None
    suggestion: Optional[str] = None

    def __str__(self) -> str:
        location = f"{self.filename}:" if self.filename else ""
        location += f"{self.line}:{self.column}"
        return f"{location} {self.severity.value}: {self.message} [{self.rule_id}]"


__all__ = ["Severity", "ValidationResult"]
