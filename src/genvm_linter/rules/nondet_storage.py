"""
Non-deterministic storage access validation rule.
Detects illegal storage access within non-deterministic execution blocks.
"""

import ast
from typing import Dict, List, Optional, Set
from .base import Rule, ValidationResult, Severity
from ..type_system import GenVMTypeSystem


class NondetStorageAccessRule(Rule, ast.NodeVisitor):
    """Rule to detect illegal storage access in non-deterministic blocks."""

    def __init__(self):
        super().__init__(
            rule_id="genvm-nondet-storage",
            description="Detect storage access in non-deterministic execution blocks"
        )
        # Track variable storage status
        self.storage_tainted: Set[str] = set()
        self.safe_copies: Set[str] = set()
        # Track if we're analyzing a nondet function
        self.in_nondet_context = False
        self.current_nondet_func: Optional[ast.FunctionDef] = None
        # Track class attributes and their types
        self.class_attributes: Dict[str, str] = {}
        # Track function definitions by name
        self.function_defs: Dict[str, ast.FunctionDef] = {}
        # Results
        self.results: List[ValidationResult] = []
        self.filename: Optional[str] = None

    def check(self, node: ast.AST, filename: Optional[str] = None) -> List[ValidationResult]:
        """Check for storage access in non-deterministic blocks."""
        if not isinstance(node, ast.Module):
            return []

        self.results = []
        self.filename = filename
        self.storage_tainted = set()
        self.safe_copies = set()
        self.class_attributes = {}

        # First pass: collect class attribute types
        self._collect_class_attributes(node)

        # Second pass: analyze the module
        self.visit(node)

        return self.results

    def _collect_class_attributes(self, module: ast.Module):
        """Collect information about class attributes and their types."""
        for node in module.body:
            if isinstance(node, ast.ClassDef):
                # Check if this extends gl.Contract
                if any(self._is_gl_contract(base) for base in node.bases):
                    # Collect attribute type annotations
                    for item in node.body:
                        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                            attr_name = item.target.id
                            attr_type = self._extract_type(item.annotation)
                            self.class_attributes[attr_name] = attr_type

    def _is_gl_contract(self, base: ast.expr) -> bool:
        """Check if a base class is gl.Contract."""
        if isinstance(base, ast.Attribute):
            return (isinstance(base.value, ast.Name) and
                   base.value.id == "gl" and
                   base.attr == "Contract")
        return False

    def _extract_type(self, annotation: ast.AST) -> str:
        """Extract type name from annotation."""
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Subscript):
            # Handle generic types like DynArray[str]
            if isinstance(annotation.value, ast.Name):
                return annotation.value.id
        return "unknown"

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Track function definitions that might be used in nondet contexts."""
        # Store the function for later analysis if used in nondet
        self.function_defs[node.name] = node

        # Check if this function is being defined inside a method
        # and analyze assignments within it
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                self.visit_Assign(stmt)

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Detect nondet method calls and analyze their function arguments."""
        # Check for gl.eq_principle methods
        if self._is_gl_eq_principle_call(node):
            self._analyze_nondet_function(node)
        # Check for gl.vm.run_nondet
        elif self._is_gl_vm_run_nondet(node):
            self._analyze_run_nondet_functions(node)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        """Track variable assignments for storage tainting."""
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id

            # Check if it's self.attribute assignment
            if self._is_self_attribute(node.value):
                attr_name = node.value.attr
                attr_type = self.class_attributes.get(attr_name, "unknown")

                # Check if it's a primitive type
                if self._is_primitive_or_simple_type(attr_type):
                    self.safe_copies.add(var_name)
                else:
                    # Storage object or unknown - mark as tainted
                    self.storage_tainted.add(var_name)

            # Check if it's gl.storage.copy_to_memory call
            elif self._is_copy_to_memory_call(node.value):
                self.safe_copies.add(var_name)

            # Check if it's assignment from another variable
            elif isinstance(node.value, ast.Name):
                source_var = node.value.id
                # Propagate taint status
                if source_var in self.storage_tainted:
                    self.storage_tainted.add(var_name)
                elif source_var in self.safe_copies:
                    self.safe_copies.add(var_name)

        self.generic_visit(node)

    def _is_gl_eq_principle_call(self, node: ast.Call) -> bool:
        """Check if this is a gl.eq_principle method call."""
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ['strict_eq', 'prompt_comparative', 'ALL_PRINCIPLES']:
                if isinstance(node.func.value, ast.Attribute):
                    if (node.func.value.attr == 'eq_principle' and
                        isinstance(node.func.value.value, ast.Name) and
                        node.func.value.value.id == 'gl'):
                        return True
        return False

    def _is_gl_vm_run_nondet(self, node: ast.Call) -> bool:
        """Check if this is gl.vm.run_nondet call."""
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == 'run_nondet':
                if isinstance(node.func.value, ast.Attribute):
                    if (node.func.value.attr == 'vm' and
                        isinstance(node.func.value.value, ast.Name) and
                        node.func.value.value.id == 'gl'):
                        return True
        return False

    def _analyze_nondet_function(self, call_node: ast.Call):
        """Analyze function passed to eq_principle methods."""
        if len(call_node.args) > 0:
            func_arg = call_node.args[0]

            # Handle lambda or function definition
            if isinstance(func_arg, ast.Lambda):
                self._check_storage_access_in_function(func_arg.body, is_lambda=True)
            elif isinstance(func_arg, ast.Name):
                # Look for the function definition by name
                if func_arg.id in self.function_defs:
                    self._check_storage_access_in_function(self.function_defs[func_arg.id])
            # Handle inline function definition
            elif isinstance(func_arg, ast.FunctionDef):
                self._check_storage_access_in_function(func_arg)

    def _analyze_run_nondet_functions(self, call_node: ast.Call):
        """Analyze leader and validator functions in run_nondet."""
        # First argument is leader_fn, second is validator_fn
        for i, func_arg in enumerate(call_node.args[:2]):
            if isinstance(func_arg, ast.Lambda):
                self._check_storage_access_in_function(func_arg.body, is_lambda=True)
            elif isinstance(func_arg, ast.Name):
                # Look for the function definition by name
                if func_arg.id in self.function_defs:
                    self._check_storage_access_in_function(self.function_defs[func_arg.id])
            elif isinstance(func_arg, ast.FunctionDef):
                self._check_storage_access_in_function(func_arg)

    def _check_storage_access_in_function(self, func_node, is_lambda=False):
        """Check for storage access within a function."""
        # Create a visitor to check storage access
        checker = StorageAccessChecker(
            self.storage_tainted,
            self.safe_copies,
            self.results,
            self.filename
        )
        if is_lambda:
            checker.visit(func_node)
        else:
            checker.visit(func_node)

    def _is_self_attribute(self, node: ast.AST) -> bool:
        """Check if node is self.attribute access."""
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == 'self':
                return True
        return False

    def _is_copy_to_memory_call(self, node: ast.AST) -> bool:
        """Check if node is gl.storage.copy_to_memory call."""
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == 'copy_to_memory':
                    if isinstance(node.func.value, ast.Attribute):
                        if (node.func.value.attr == 'storage' and
                            isinstance(node.func.value.value, ast.Name) and
                            node.func.value.value.id == 'gl'):
                            return True
        return False

    def _is_primitive_or_simple_type(self, type_name: str) -> bool:
        """Check if type is a primitive or simple type that gets copied by value."""
        primitives = {'bool', 'int', 'float', 'str', 'bytes', 'NoneType'}

        # Check if it's a primitive
        if type_name in primitives:
            return True

        # Check if it's a GenVM sized integer (treated as primitive)
        if GenVMTypeSystem.is_sized_int_type(type_name):
            return True

        return False


class StorageAccessChecker(ast.NodeVisitor):
    """Helper visitor to check storage access within a function."""

    def __init__(self, storage_tainted: Set[str], safe_copies: Set[str],
                 results: List[ValidationResult], filename: Optional[str]):
        self.storage_tainted = storage_tainted
        self.safe_copies = safe_copies
        self.results = results
        self.filename = filename

    def visit_Attribute(self, node: ast.Attribute):
        """Check for self.attribute access."""
        if isinstance(node.value, ast.Name) and node.value.id == 'self':
            self.results.append(ValidationResult(
                rule_id="genvm-nondet-storage",
                message=f"Direct storage access 'self.{node.attr}' is not allowed in non-deterministic blocks",
                severity=Severity.ERROR,
                line=node.lineno,
                column=node.col_offset,
                filename=self.filename,
                suggestion=f"Copy the value before the nondet block: `{node.attr} = self.{node.attr}` or use `gl.storage.copy_to_memory(self.{node.attr})` for complex objects"
            ))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        """Check for storage-tainted variable access."""
        if node.id in self.storage_tainted:
            # Check if we're in a load context (reading the variable)
            if isinstance(node.ctx, ast.Load):
                self.results.append(ValidationResult(
                    rule_id="genvm-nondet-storage",
                    message=f"Variable '{node.id}' holds a storage reference and cannot be accessed in non-deterministic blocks",
                    severity=Severity.ERROR,
                    line=node.lineno,
                    column=node.col_offset,
                    filename=self.filename,
                    suggestion=f"Use `gl.storage.copy_to_memory()` to create a safe copy before the nondet block"
                ))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Handle nested function definitions."""
        # Recursively check nested functions
        for stmt in node.body:
            self.visit(stmt)

    def visit_Lambda(self, node: ast.Lambda):
        """Handle nested lambda functions."""
        self.visit(node.body)