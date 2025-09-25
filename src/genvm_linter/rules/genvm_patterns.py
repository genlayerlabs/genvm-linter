"""Advanced GenVM pattern validation rules."""

import ast
import re
from typing import List, Optional, Set

from .base import Rule, ValidationResult, Severity
from ..type_system import GenVMTypeSystem


class GenVMApiUsageRule(Rule):
    """Rule to validate proper usage of GenVM API methods."""
    
    def __init__(self):
        super().__init__(
            rule_id="genvm-api-usage",
            description="Validate proper usage of GenVM API methods and patterns"
        )
    
    def check(self, node: ast.AST, filename: Optional[str] = None) -> List[ValidationResult]:
        results = []
        
        if isinstance(node, ast.Module):
            for stmt in ast.walk(node):
                results.extend(self._check_node(stmt, filename))
        
        return results
    
    def _check_node(self, node: ast.AST, filename: Optional[str] = None) -> List[ValidationResult]:
        results = []
        
        # Check for improper gl.eq_principle usage
        if isinstance(node, ast.Call):
            if self._is_gl_method_call(node, 'eq_principle', 'strict_eq'):
                results.extend(self._validate_strict_eq(node, filename))
            elif self._is_gl_method_call(node, 'eq_principle', 'prompt_comparative'):
                results.extend(self._validate_prompt_comparative(node, filename))
            elif self._is_gl_method_call(node, 'nondet', 'exec_prompt'):
                results.extend(self._validate_exec_prompt(node, filename))
            elif self._is_gl_method_call(node, 'storage', 'inmem_allocate'):
                results.extend(self._validate_inmem_allocate(node, filename))
        
        # Check for direct access to lazy objects without .get()
        if isinstance(node, ast.Attribute) and node.attr != 'get':
            if self._might_be_lazy_object(node.value):
                results.append(self.create_result(
                    "Lazy objects must be resolved with .get() before accessing other attributes",
                    Severity.WARNING,
                    line=node.lineno,
                    filename=filename,
                    suggestion="Use .get() to resolve the lazy object first"
                ))
        
        return results
    
    def _is_gl_method_call(self, node: ast.Call, module: str, method: str) -> bool:
        """Check if node is a call to gl.module.method."""
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == method:
                if isinstance(node.func.value, ast.Attribute):
                    if (node.func.value.attr == module and 
                        isinstance(node.func.value.value, ast.Name) and
                        node.func.value.value.id == 'gl'):
                        return True
        return False
    
    def _validate_strict_eq(self, node: ast.Call, filename: Optional[str]) -> List[ValidationResult]:
        """Validate gl.eq_principle.strict_eq usage."""
        results = []
        
        if len(node.args) != 1:
            results.append(self.create_result(
                "strict_eq() requires exactly one argument (a callable)",
                Severity.ERROR,
                line=node.lineno,
                filename=filename,
                suggestion="Usage: gl.eq_principle.strict_eq(lambda: your_function())"
            ))
        
        return results
    
    def _validate_prompt_comparative(self, node: ast.Call, filename: Optional[str]) -> List[ValidationResult]:
        """Validate gl.eq_principle.prompt_comparative usage."""
        results = []
        
        if len(node.args) != 2:
            results.append(self.create_result(
                "prompt_comparative() requires exactly two arguments (function, principle)",
                Severity.ERROR,
                line=node.lineno,
                filename=filename,
                suggestion="Usage: gl.eq_principle.prompt_comparative(fn, 'comparison principle')"
            ))
        elif len(node.args) >= 2:
            # Check that second argument is a string
            principle_arg = node.args[1]
            if not isinstance(principle_arg, ast.Constant) or not isinstance(principle_arg.value, str):
                results.append(self.create_result(
                    "prompt_comparative() principle argument must be a string literal",
                    Severity.ERROR,
                    line=node.lineno,
                    filename=filename,
                    suggestion="Use a string literal for the principle parameter"
                ))
        
        return results
    
    def _validate_exec_prompt(self, node: ast.Call, filename: Optional[str]) -> List[ValidationResult]:
        """Validate gl.nondet.exec_prompt usage."""
        results = []
        
        if len(node.args) == 0:
            results.append(self.create_result(
                "exec_prompt() requires at least one argument (prompt text)",
                Severity.ERROR,
                line=node.lineno,
                filename=filename,
                suggestion="Usage: gl.nondet.exec_prompt('Your prompt here')"
            ))
        
        # Check for response_format in keywords
        for keyword in node.keywords:
            if keyword.arg == 'response_format':
                if isinstance(keyword.value, ast.Constant):
                    if keyword.value.value not in ['text', 'json']:
                        results.append(self.create_result(
                            "exec_prompt() response_format must be 'text' or 'json'",
                            Severity.ERROR,
                            line=node.lineno,
                            filename=filename,
                            suggestion="Use response_format='text' or response_format='json'"
                        ))
        
        return results
    
    def _validate_inmem_allocate(self, node: ast.Call, filename: Optional[str]) -> List[ValidationResult]:
        """Validate gl.storage.inmem_allocate usage."""
        results = []
        
        if len(node.args) == 0:
            results.append(self.create_result(
                "inmem_allocate() requires at least one argument (type)",
                Severity.ERROR,
                line=node.lineno,
                filename=filename,
                suggestion="Usage: gl.storage.inmem_allocate(MyStorageType, ...)"
            ))
        
        return results
    
    def _might_be_lazy_object(self, node: ast.AST) -> bool:
        """Check if node might be a lazy object."""
        # Only check for explicit .lazy() calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'lazy':
                return True
        return False


class LazyObjectRule(Rule):
    """Rule to ensure Lazy objects are properly resolved with .get()."""
    
    def __init__(self):
        super().__init__(
            rule_id="genvm-lazy-objects",
            description="Ensure Lazy objects are resolved with .get() before use"
        )
    
    def check(self, node: ast.AST, filename: Optional[str] = None) -> List[ValidationResult]:
        results = []
        
        if isinstance(node, ast.Module):
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Assign):
                    results.extend(self._check_assignment(stmt, filename))
        
        return results
    
    def _check_assignment(self, node: ast.Assign, filename: Optional[str]) -> List[ValidationResult]:
        """Check if assignment uses lazy object without .get()."""
        results = []
        
        # Look for patterns like: result = gl.eq_principle.strict_eq(...)
        # These should be: result = gl.eq_principle.strict_eq(...).get()
        if isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Attribute):
                # Check for gl.eq_principle or gl.nondet methods that return Lazy
                if self._returns_lazy_object(func):
                    results.append(self.create_result(
                        "GenVM method returns Lazy object - call .get() to resolve value",
                        Severity.WARNING,
                        line=node.lineno,
                        filename=filename,
                        suggestion="Add .get() at the end: result = gl.method(...).get()"
                    ))
        
        return results
    
    def _returns_lazy_object(self, func: ast.Attribute) -> bool:
        """Check if function returns a Lazy object."""
        # Only check for explicit .lazy() method calls
        if func.attr == 'lazy':
            return True
        return False


class StoragePatternRule(Rule):
    """Rule to validate GenVM storage patterns and usage."""
    
    def __init__(self):
        super().__init__(
            rule_id="genvm-storage-patterns",
            description="Validate GenVM storage type usage and patterns"
        )
    
    def check(self, node: ast.AST, filename: Optional[str] = None) -> List[ValidationResult]:
        results = []
        
        if isinstance(node, ast.Module):
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.AnnAssign):
                    results.extend(self._check_storage_annotation(stmt, filename))
        
        return results
    
    def _check_storage_annotation(self, node: ast.AnnAssign, filename: Optional[str]) -> List[ValidationResult]:
        """Check storage type annotations in class fields."""
        results = []
        
        # Check if we're inside a contract class
        parent = getattr(node, 'parent', None)
        if not (isinstance(parent, ast.ClassDef) and self._extends_gl_contract(parent)):
            return results
        
        # Check for proper storage type usage
        if isinstance(node.annotation, ast.Name):
            type_name = node.annotation.id
            if GenVMTypeSystem.is_python_collection(type_name):
                genvm_alternative = GenVMTypeSystem.get_genvm_equivalent(type_name)
                if genvm_alternative:
                    results.append(self.create_result(
                        f"Use GenVM storage type '{genvm_alternative}' instead of '{type_name}' for contract storage",
                        Severity.WARNING,
                        line=node.lineno,
                        filename=filename,
                        suggestion=f"Replace '{type_name}' with 'gl.storage.{genvm_alternative}'"
                    ))
        
        return results
    
    def _extends_gl_contract(self, class_node: ast.ClassDef) -> bool:
        """Check if class extends gl.Contract."""
        for base in class_node.bases:
            if isinstance(base, ast.Attribute):
                if (isinstance(base.value, ast.Name) and 
                    base.value.id == 'gl' and 
                    base.attr == 'Contract'):
                    return True
        return False