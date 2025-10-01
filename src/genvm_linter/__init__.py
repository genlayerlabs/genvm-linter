"""GenVM Linter - A Python linter for GenLayer GenVM intelligent contracts with version awareness."""

__version__ = "0.2.0"
__author__ = "GenLayer Labs"
__email__ = "dev@genlayer.com"

from .linter import GenVMLinter, VersionAwareGenVMLinter
from .rules import Rule, ValidationResult, Severity
from .version import Version, VersionParser
from .rule_registry import RuleRegistry

__all__ = [
    "GenVMLinter",
    "VersionAwareGenVMLinter",  # Alias for backward compatibility
    "Rule",
    "ValidationResult",
    "Severity",
    "Version",
    "VersionParser",
    "RuleRegistry"
]