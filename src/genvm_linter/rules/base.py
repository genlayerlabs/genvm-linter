"""Base classes for linting rules."""

import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Union


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


class Rule(ABC):
    """Base class for all linting rules."""
    
    def __init__(self, rule_id: str, description: str):
        self.rule_id = rule_id
        self.description = description
    
    @abstractmethod
    def check(self, node: Union[ast.AST, str], filename: Optional[str] = None) -> List[ValidationResult]:
        """Check the given AST node or source code for violations of this rule.
        
        Args:
            node: The AST node or source code string to check
            filename: Optional filename for error reporting
            
        Returns:
            List of validation results
        """
        pass
    
    def create_result(
        self, 
        message: str, 
        severity: Severity, 
        line: int = 1, 
        column: int = 0,
        filename: Optional[str] = None,
        suggestion: Optional[str] = None
    ) -> ValidationResult:
        """Create a validation result for this rule."""
        return ValidationResult(
            rule_id=self.rule_id,
            message=message,
            severity=severity,
            line=line,
            column=column,
            filename=filename,
            suggestion=suggestion
        )