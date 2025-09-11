"""Contract structure validation rules."""

import ast
import re
from typing import List, Optional, Union

from .base import Rule, ValidationResult, Severity


class MagicCommentRule(Rule):
    """Rule to check for the required GenVM magic comment."""
    
    def __init__(self):
        super().__init__(
            rule_id="genvm-magic-comment",
            description="GenVM contracts must have the magic comment '# { \"Depends\": \"py-genlayer:test\" }' before imports"
        )
        self.needs_source_code = True
    
    def check(self, source_code: str, filename: Optional[str] = None) -> List[ValidationResult]:
        """Check for the magic comment anywhere before the first import statement."""
        lines = source_code.splitlines()
        
        if not lines:
            return [self.create_result(
                "Empty file - missing GenVM magic comment",
                Severity.ERROR,
                line=1,
                filename=filename,
                suggestion='Add: # { "Depends": "py-genlayer:test" }'
            )]
        
        expected_pattern = r'#\s*\{\s*"Depends"\s*:\s*"py-genlayer:[^"]+"\s*\}'
        
        # Find the first import line
        first_import_line = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('from '):
                first_import_line = i + 1  # 1-based line numbering
                break
        
        # Check for magic comment before the first import (or anywhere if no imports)
        search_lines = lines[:first_import_line-1] if first_import_line else lines
        
        for i, line in enumerate(search_lines):
            if re.search(expected_pattern, line.strip()):
                return []  # Found the magic comment
        
        return [self.create_result(
            "Missing or incorrect GenVM magic comment before imports",
            Severity.ERROR,
            line=1,
            filename=filename,
            suggestion='Add before imports: # { "Depends": "py-genlayer:test" }'
        )]


class ImportRule(Rule):
    """Rule to check for the required GenLayer import."""
    
    def __init__(self):
        super().__init__(
            rule_id="genvm-import",
            description="GenVM contracts must import the GenLayer standard library"
        )
    
    def check(self, node: ast.AST, filename: Optional[str] = None) -> List[ValidationResult]:
        """Check for 'from genlayer import *' statement."""
        if not isinstance(node, ast.Module):
            return []
        
        has_genlayer_import = False
        
        for stmt in node.body:
            if (isinstance(stmt, ast.ImportFrom) and 
                stmt.module == "genlayer" and
                any(isinstance(alias, ast.alias) and alias.name == "*" for alias in stmt.names or [])):
                has_genlayer_import = True
                break
        
        if not has_genlayer_import:
            return [self.create_result(
                "Missing required GenLayer import",
                Severity.ERROR,
                line=2,  # Usually on line 2 after magic comment
                filename=filename,
                suggestion='Add: from genlayer import *'
            )]
        
        return []


class ContractClassRule(Rule):
    """Rule to check for exactly one contract class extending gl.Contract."""
    
    def __init__(self):
        super().__init__(
            rule_id="genvm-contract-class",
            description="GenVM contracts must have exactly one class extending gl.Contract"
        )
    
    def check(self, node: ast.AST, filename: Optional[str] = None) -> List[ValidationResult]:
        """Check for contract class structure."""
        if not isinstance(node, ast.Module):
            return []
        
        contract_classes = []
        
        for stmt in node.body:
            if isinstance(stmt, ast.ClassDef):
                # Check if class extends gl.Contract
                for base in stmt.bases:
                    if self._is_gl_contract(base):
                        contract_classes.append((stmt.name, stmt.lineno))
        
        results = []
        
        if len(contract_classes) == 0:
            results.append(self.create_result(
                "No contract class found. Must have a class extending gl.Contract",
                Severity.ERROR,
                line=1,
                filename=filename,
                suggestion='Add: class YourContract(gl.Contract):'
            ))
        elif len(contract_classes) > 1:
            for name, line in contract_classes[1:]:
                results.append(self.create_result(
                    f"Multiple contract classes found. Only one class extending gl.Contract is allowed per file",
                    Severity.ERROR,
                    line=line,
                    filename=filename
                ))
        
        # Check if contract class has proper structure
        if len(contract_classes) == 1:
            class_name, class_line = contract_classes[0]
            class_node = next(stmt for stmt in node.body 
                            if isinstance(stmt, ast.ClassDef) and stmt.name == class_name)
            
            # Check for constructor
            has_init = any(isinstance(method, ast.FunctionDef) and method.name == "__init__" 
                          for method in class_node.body)
            
            if not has_init:
                results.append(self.create_result(
                    f"Contract class '{class_name}' is missing __init__ method",
                    Severity.ERROR,
                    line=class_line,
                    filename=filename,
                    suggestion='Add: def __init__(self, ...): pass'
                ))
        
        return results
    
    def _is_gl_contract(self, base: ast.expr) -> bool:
        """Check if a base class is gl.Contract."""
        if isinstance(base, ast.Attribute):
            return (isinstance(base.value, ast.Name) and 
                   base.value.id == "gl" and 
                   base.attr == "Contract")
        return False