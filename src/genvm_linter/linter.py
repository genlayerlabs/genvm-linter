"""Main linter implementation for GenVM contracts."""

import ast
from pathlib import Path
from typing import List, Optional, Union

from .rules import Rule, ValidationResult
from .rules.contract import MagicCommentRule, ImportRule, ContractClassRule
from .rules.decorators import DecoratorRule
from .rules.types import TypeSystemRule
from .rules.genvm_patterns import GenVMApiUsageRule, LazyObjectRule, StoragePatternRule
from .rules.python_types import PythonTypeCheckRule, GenVMTypeStubRule
from .rules.genvm_dataclasses import DataclassValidation


class GenVMLinter:
    """Main linter class for GenVM intelligent contracts."""
    
    def __init__(self):
        """Initialize the linter with default rules."""
        self.rules: List[Rule] = [
            MagicCommentRule(),
            ImportRule(),
            ContractClassRule(),
            DecoratorRule(),
            TypeSystemRule(),
            GenVMApiUsageRule(),
            LazyObjectRule(),
            StoragePatternRule(),
            PythonTypeCheckRule(),
            GenVMTypeStubRule(),
            DataclassValidation(),
        ]
    
    def add_rule(self, rule: Rule) -> None:
        """Add a custom rule to the linter."""
        self.rules.append(rule)
    
    def lint_file(self, filepath: Union[str, Path]) -> List[ValidationResult]:
        """Lint a single Python file.
        
        Args:
            filepath: Path to the Python file to lint
            
        Returns:
            List of validation results
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            from .rules.base import ValidationResult, Severity
            return [ValidationResult(
                rule_id="file-not-found",
                message=f"File not found: {filepath}",
                severity=Severity.ERROR,
                line=1,
                column=0,
                filename=str(filepath)
            )]
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except Exception as e:
            from .rules.base import ValidationResult, Severity
            return [ValidationResult(
                rule_id="file-read-error", 
                message=f"Error reading file: {e}",
                severity=Severity.ERROR,
                line=1,
                column=0,
                filename=str(filepath)
            )]
        
        return self.lint_source(source_code, str(filepath))
    
    def lint_source(self, source_code: str, filename: Optional[str] = None) -> List[ValidationResult]:
        """Lint Python source code.
        
        Args:
            source_code: The Python source code to lint
            filename: Optional filename for error reporting
            
        Returns:
            List of validation results
        """
        results: List[ValidationResult] = []
        
        # First, run string-based rules that need to check the raw source
        for rule in self.rules:
            if hasattr(rule, 'needs_source_code') and rule.needs_source_code:
                results.extend(rule.check(source_code, filename))
        
        # Try to parse the AST
        try:
            tree = ast.parse(source_code, filename=filename)
        except SyntaxError as e:
            from .rules.base import ValidationResult, Severity
            results.append(ValidationResult(
                rule_id="syntax-error",
                message=f"Syntax error: {e.msg}",
                severity=Severity.ERROR,
                line=e.lineno or 1,
                column=e.offset or 0,
                filename=filename
            ))
            return results
        
        # Run AST-based rules
        for rule in self.rules:
            if not (hasattr(rule, 'needs_source_code') and rule.needs_source_code):
                results.extend(rule.check(tree, filename))
        
        return results
    
    def lint_directory(self, directory: Union[str, Path], pattern: str = "*.py") -> List[ValidationResult]:
        """Lint all Python files in a directory.
        
        Args:
            directory: Path to the directory to lint
            pattern: File pattern to match (default: "*.py")
            
        Returns:
            List of validation results
        """
        directory = Path(directory)
        results: List[ValidationResult] = []
        
        if not directory.exists():
            from .rules.base import ValidationResult, Severity
            return [ValidationResult(
                rule_id="directory-not-found",
                message=f"Directory not found: {directory}",
                severity=Severity.ERROR,
                line=1,
                column=0
            )]
        
        for filepath in directory.rglob(pattern):
            if filepath.is_file():
                results.extend(self.lint_file(filepath))
        
        return results