"""Type system validation rules."""

import ast
from typing import List, Optional, Set

from .base import Rule, ValidationResult, Severity
from ..type_system import GenVMTypeSystem


class TypeSystemRule(Rule):
    """Rule to validate GenVM type system usage."""
    
    def __init__(self):
        super().__init__(
            rule_id="genvm-types",
            description="GenVM type system validation for storage and method signatures"
        )
    
    def check(self, node: ast.AST, filename: Optional[str] = None) -> List[ValidationResult]:
        """Check for proper GenVM type usage."""
        if not isinstance(node, ast.Module):
            return []
        
        results = []
        
        # Find the contract class
        contract_class = self._find_contract_class(node)
        if not contract_class:
            return results
        
        # Check storage field types
        results.extend(self._check_storage_fields(contract_class, filename))
        
        # Check method signatures
        for method in contract_class.body:
            if isinstance(method, ast.FunctionDef):
                results.extend(self._check_method_types(method, filename))
        
        # Check dataclass usage
        results.extend(self._check_dataclasses(node, filename))
        
        return results
    
    def _find_contract_class(self, module: ast.Module) -> Optional[ast.ClassDef]:
        """Find the contract class in the module."""
        for stmt in module.body:
            if isinstance(stmt, ast.ClassDef):
                for base in stmt.bases:
                    if self._is_gl_contract(base):
                        return stmt
        return None
    
    def _is_gl_contract(self, base: ast.expr) -> bool:
        """Check if a base class is gl.Contract."""
        if isinstance(base, ast.Attribute):
            return (isinstance(base.value, ast.Name) and 
                   base.value.id == "gl" and 
                   base.attr == "Contract")
        return False
    
    def _check_storage_fields(self, contract_class: ast.ClassDef, filename: Optional[str]) -> List[ValidationResult]:
        """Check storage field type annotations."""
        results = []
        
        for stmt in contract_class.body:
            if isinstance(stmt, ast.AnnAssign) and stmt.target:
                # This is a type-annotated assignment (storage field)
                if isinstance(stmt.target, ast.Name):
                    field_name = stmt.target.id
                    results.extend(self._check_storage_field_type(
                        field_name, stmt.annotation, stmt.lineno, filename
                    ))
        
        return results
    
    def _check_storage_field_type(self, field_name: str, annotation: ast.expr, 
                                line: int, filename: Optional[str]) -> List[ValidationResult]:
        """Check a single storage field type."""
        results = []
        
        # Check for plain 'int' usage (should use sized integers)
        if isinstance(annotation, ast.Name) and annotation.id == "int":
            results.append(self.create_result(
                f"Storage field '{field_name}' uses 'int' type. Use sized integers like u64, u256, or bigint",
                Severity.ERROR,
                line=line,
                filename=filename,
                suggestion=f"Replace 'int' with a sized integer type like '{GenVMTypeSystem.get_suggested_type_for_storage('int')}'"
            ))
        
        # Check for Python collections (should use GenVM collections)
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name):
                if annotation.value.id == "list":
                    results.append(self.create_result(
                        f"Storage field '{field_name}' uses 'list' type. Use '{GenVMTypeSystem.get_genvm_equivalent('list')}' instead",
                        Severity.ERROR,
                        line=line,
                        filename=filename,
                        suggestion=f"Replace 'list' with '{GenVMTypeSystem.get_genvm_equivalent('list')}'"
                    ))
                elif annotation.value.id == "dict":
                    results.append(self.create_result(
                        f"Storage field '{field_name}' uses 'dict' type. Use '{GenVMTypeSystem.get_genvm_equivalent('dict')}' instead",
                        Severity.ERROR,
                        line=line,
                        filename=filename,
                        suggestion=f"Replace 'dict' with '{GenVMTypeSystem.get_genvm_equivalent('dict')}'"
                    ))
        
        return results
    
    def _check_method_types(self, method: ast.FunctionDef, filename: Optional[str]) -> List[ValidationResult]:
        """Check method parameter and return types."""
        results = []
        
        # Check return type annotation
        if method.returns:
            results.extend(self._check_return_type(method, filename))
        
        # Check parameter types - sized integers should not be used in method signatures
        for arg in method.args.args:
            if arg.annotation and arg.arg != 'self':  # Skip 'self' parameter
                results.extend(self._check_parameter_type(method, arg, filename))
        
        return results
    
    def _check_parameter_type(self, method: ast.FunctionDef, arg: ast.arg, filename: Optional[str]) -> List[ValidationResult]:
        """Check method parameter type annotation."""
        results = []
        
        if not arg.annotation:
            return results
        
        # Check for sized integer types in parameter annotations (should use int)
        if isinstance(arg.annotation, ast.Name):
            if GenVMTypeSystem.should_use_int_in_signature(arg.annotation.id):
                results.append(self.create_result(
                    f"Method '{method.name}' parameter '{arg.arg}' uses '{arg.annotation.id}' type. Use 'int' for parameter types",
                    Severity.ERROR,
                    line=arg.lineno if hasattr(arg, 'lineno') else method.lineno,
                    filename=filename,
                    suggestion=f"Change parameter type from '{arg.annotation.id}' to 'int'"
                ))
        
        return results
    
    def _check_return_type(self, method: ast.FunctionDef, filename: Optional[str]) -> List[ValidationResult]:
        """Check method return type annotation."""
        results = []
        
        if not method.returns:
            return results
        
        # Check for sized integer types in return annotations (should use int)
        if isinstance(method.returns, ast.Name):
            if GenVMTypeSystem.should_use_int_in_signature(method.returns.id):
                results.append(self.create_result(
                    f"Method '{method.name}' returns '{method.returns.id}' type. Use 'int' for return types",
                    Severity.ERROR,
                    line=method.lineno,
                    filename=filename,
                    suggestion=f"Change return type from '{method.returns.id}' to 'int'"
                ))
        
        return results
    
    def _check_dataclasses(self, module: ast.Module, filename: Optional[str]) -> List[ValidationResult]:
        """Check dataclass usage and decorators."""
        results = []
        
        for stmt in module.body:
            if isinstance(stmt, ast.ClassDef):
                # Skip the contract class
                if any(self._is_gl_contract(base) for base in stmt.bases):
                    continue
                
                # Check if this is a dataclass
                has_dataclass_decorator = any(
                    (isinstance(decorator, ast.Name) and decorator.id == "dataclass") or
                    (isinstance(decorator, ast.Attribute) and decorator.attr == "dataclass")
                    for decorator in stmt.decorator_list
                )
                
                if has_dataclass_decorator:
                    results.extend(self._check_dataclass_storage_decorator(stmt, filename))
                    results.extend(self._check_dataclass_field_types(stmt, filename))
        
        return results
    
    def _check_dataclass_storage_decorator(self, class_def: ast.ClassDef, 
                                         filename: Optional[str]) -> List[ValidationResult]:
        """Check if dataclass has @allow_storage decorator when needed."""
        results = []
        
        has_allow_storage = any(
            isinstance(decorator, ast.Name) and decorator.id == "allow_storage"
            for decorator in class_def.decorator_list
        )
        
        # Heuristic: if dataclass has sized integer fields, it probably needs @allow_storage
        has_sized_integers = False
        for stmt in class_def.body:
            if isinstance(stmt, ast.AnnAssign) and stmt.annotation:
                if isinstance(stmt.annotation, ast.Name):
                    if GenVMTypeSystem.is_sized_int_type(stmt.annotation.id):
                        has_sized_integers = True
                        break
        
        if has_sized_integers and not has_allow_storage:
            results.append(self.create_result(
                f"Dataclass '{class_def.name}' with sized integer fields should have @allow_storage decorator",
                Severity.WARNING,
                line=class_def.lineno,
                filename=filename,
                suggestion=f"Add @allow_storage decorator to {class_def.name}"
            ))
        
        return results
    
    def _check_dataclass_field_types(self, class_def: ast.ClassDef, 
                                   filename: Optional[str]) -> List[ValidationResult]:
        """Check dataclass field types."""
        results = []
        
        for stmt in class_def.body:
            if isinstance(stmt, ast.AnnAssign) and stmt.target:
                if isinstance(stmt.target, ast.Name):
                    field_name = stmt.target.id
                    
                    # Similar checks as storage fields
                    if isinstance(stmt.annotation, ast.Name) and stmt.annotation.id == "int":
                        results.append(self.create_result(
                            f"Dataclass field '{field_name}' uses 'int' type. Consider using sized integers",
                            Severity.WARNING,
                            line=stmt.lineno,
                            filename=filename,
                            suggestion=f"Consider using u64, u256, or another sized integer type"
                        ))
        
        return results