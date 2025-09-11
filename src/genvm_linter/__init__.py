"""GenVM Linter - A Python linter for GenLayer GenVM intelligent contracts."""

__version__ = "0.1.0"
__author__ = "GenLayer Labs"
__email__ = "dev@genlayer.com"

from .linter import GenVMLinter
from .rules import Rule, ValidationResult, Severity

__all__ = ["GenVMLinter", "Rule", "ValidationResult", "Severity"]