"""GenLayer contract validation and schema extraction."""

__version__ = "0.3.0"

# Backwards-compatible exports for studio integration
from .linter import GenVMLinter
from .rules import Severity, ValidationResult

__all__ = ["GenVMLinter", "Severity", "ValidationResult", "__version__"]
