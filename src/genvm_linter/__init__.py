"""GenLayer contract validation and schema extraction."""

from importlib.metadata import version as _get_version

__version__ = _get_version("genvm-linter")

# Backwards-compatible exports for studio integration
from .linter import GenVMLinter
from .rules import Severity, ValidationResult

__all__ = ["GenVMLinter", "Severity", "ValidationResult", "__version__"]
