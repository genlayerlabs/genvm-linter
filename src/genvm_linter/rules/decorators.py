"""Decorator validation rules."""

import ast
from typing import List, Optional

from .base import Rule, ValidationResult, Severity


class DecoratorRule(Rule):
    """Rule to validate proper usage of GenLayer decorators."""
    
    def __init__(self):
        super().__init__(
            rule_id="genvm-decorators",
            description="GenVM contract methods must use proper decorators"
        )
    
    def check(self, node: ast.AST, filename: Optional[str] = None) -> List[ValidationResult]:
        """Check for proper decorator usage on contract methods."""
        if not isinstance(node, ast.Module):
            return []
        
        results = []
        
        # Find the contract class
        contract_class = self._find_contract_class(node)
        if not contract_class:
            return results
        
        for method in contract_class.body:
            if isinstance(method, ast.FunctionDef):
                results.extend(self._check_method_decorators(method, filename))
        
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
    
    def _check_method_decorators(self, method: ast.FunctionDef, filename: Optional[str]) -> List[ValidationResult]:
        """Check decorators on a single method."""
        results = []
        
        # Constructor should not have public decorators
        if method.name == "__init__":
            for decorator in method.decorator_list:
                if self._is_public_decorator(decorator):
                    results.append(self.create_result(
                        "Constructor (__init__) method should not have public decorators",
                        Severity.ERROR,
                        line=method.lineno,
                        filename=filename,
                        suggestion="Remove @gl.public decorators from __init__"
                    ))
            return results
        
        # Private methods (starting with _) should not have public decorators
        if method.name.startswith("_"):
            for decorator in method.decorator_list:
                if self._is_public_decorator(decorator):
                    results.append(self.create_result(
                        f"Private method '{method.name}' should not have public decorators",
                        Severity.ERROR,
                        line=method.lineno,
                        filename=filename,
                        suggestion=f"Remove @gl.public decorators from {method.name} or make it public"
                    ))
            return results
        
        # Check if write methods return values (they shouldn't)
        if self._has_write_decorator(method):
            if self._method_returns_value(method):
                results.append(self.create_result(
                    f"Write method '{method.name}' should not return a value",
                    Severity.WARNING,
                    line=method.lineno,
                    filename=filename,
                    suggestion=f"@gl.public.write methods modify state and should not return values. Consider using @gl.public.view if you need to return data"
                ))
        
        # Public methods should have exactly one public decorator
        public_decorators = [d for d in method.decorator_list if self._is_public_decorator(d)]
        
        if len(public_decorators) == 0:
            results.append(self.create_result(
                f"Method '{method.name}' is missing @gl.public decorator",
                Severity.WARNING,
                line=method.lineno,
                filename=filename,
                suggestion=f"Add @gl.public.view or @gl.public.write to make '{method.name}' publicly accessible, or prefix with underscore (e.g., '_{method.name}') to indicate it's a private/internal method"
            ))
        elif len(public_decorators) > 1:
            results.append(self.create_result(
                f"Method '{method.name}' has multiple @gl.public decorators",
                Severity.ERROR,
                line=method.lineno,
                filename=filename,
                suggestion=f"Use only one @gl.public decorator on {method.name}"
            ))
        
        # Check for proper decorator types
        for decorator in public_decorators:
            if self._is_write_decorator(decorator):
                # Check if method modifies state (heuristic)
                if self._appears_read_only(method):
                    results.append(self.create_result(
                        f"Method '{method.name}' uses @gl.public.write but appears to be read-only",
                        Severity.WARNING,
                        line=method.lineno,
                        filename=filename,
                        suggestion=f"Consider using @gl.public.view for {method.name}"
                    ))
            elif self._is_view_decorator(decorator):
                # Check if method might modify state
                if self._appears_to_modify_state(method):
                    results.append(self.create_result(
                        f"Method '{method.name}' uses @gl.public.view but appears to modify state",
                        Severity.ERROR,
                        line=method.lineno,
                        filename=filename,
                        suggestion=f"Use @gl.public.write for {method.name}"
                    ))
        
        return results
    
    def _is_public_decorator(self, decorator: ast.expr) -> bool:
        """Check if decorator is a @gl.public.* decorator."""
        if isinstance(decorator, ast.Attribute):
            if isinstance(decorator.value, ast.Attribute):
                return (isinstance(decorator.value.value, ast.Name) and
                       decorator.value.value.id == "gl" and
                       decorator.value.attr == "public")
        return False
    
    def _is_write_decorator(self, decorator: ast.expr) -> bool:
        """Check if decorator is @gl.public.write or @gl.public.write.payable."""
        if isinstance(decorator, ast.Attribute):
            if isinstance(decorator.value, ast.Attribute):
                return (isinstance(decorator.value.value, ast.Name) and
                       decorator.value.value.id == "gl" and
                       decorator.value.attr == "public" and
                       decorator.attr == "write")
            elif isinstance(decorator.value, ast.Attribute) and decorator.attr == "payable":
                # Check for @gl.public.write.payable
                if isinstance(decorator.value.value, ast.Attribute):
                    return (isinstance(decorator.value.value.value, ast.Name) and
                           decorator.value.value.value.id == "gl" and
                           decorator.value.value.attr == "public" and
                           decorator.value.attr == "write")
        return False
    
    def _is_view_decorator(self, decorator: ast.expr) -> bool:
        """Check if decorator is @gl.public.view."""
        if isinstance(decorator, ast.Attribute):
            if isinstance(decorator.value, ast.Attribute):
                return (isinstance(decorator.value.value, ast.Name) and
                       decorator.value.value.id == "gl" and
                       decorator.value.attr == "public" and
                       decorator.attr == "view")
        return False
    
    def _appears_read_only(self, method: ast.FunctionDef) -> bool:
        """Heuristic to determine if a method appears to be read-only."""
        class StateModificationVisitor(ast.NodeVisitor):
            def __init__(self):
                self.modifies_state = False
            
            def visit_Assign(self, node):
                # Check for self.attribute assignments
                for target in node.targets:
                    if (isinstance(target, ast.Attribute) and
                        isinstance(target.value, ast.Name) and
                        target.value.id == "self"):
                        self.modifies_state = True
                    # Check for self.collection[key] = value assignments
                    elif (isinstance(target, ast.Subscript) and
                          isinstance(target.value, ast.Attribute) and
                          isinstance(target.value.value, ast.Name) and
                          target.value.value.id == "self"):
                        self.modifies_state = True
                self.generic_visit(node)
            
            def visit_AugAssign(self, node):
                # Check for self.attribute += assignments
                if (isinstance(node.target, ast.Attribute) and
                    isinstance(node.target.value, ast.Name) and
                    node.target.value.id == "self"):
                    self.modifies_state = True
                # Check for self.collection[key] += assignments  
                elif (isinstance(node.target, ast.Subscript) and
                      isinstance(node.target.value, ast.Attribute) and
                      isinstance(node.target.value.value, ast.Name) and
                      node.target.value.value.id == "self"):
                    self.modifies_state = True
                self.generic_visit(node)
        
        visitor = StateModificationVisitor()
        visitor.visit(method)
        return not visitor.modifies_state
    
    def _method_returns_value(self, method: ast.FunctionDef) -> bool:
        """Check if method has a return statement with a value."""
        for node in ast.walk(method):
            if isinstance(node, ast.Return):
                # Return with a value (not just 'return' or 'return None')
                if node.value is not None:
                    # Check if it's returning None explicitly
                    if isinstance(node.value, ast.Constant) and node.value.value is None:
                        continue
                    if isinstance(node.value, ast.NameConstant) and node.value.value is None:
                        continue
                    # This is returning an actual value
                    return True
        return False
    
    def _has_write_decorator(self, method: ast.FunctionDef) -> bool:
        """Check if method has @gl.public.write decorator."""
        for decorator in method.decorator_list:
            if self._is_write_decorator(decorator):
                return True
        return False
    
    def _appears_to_modify_state(self, method: ast.FunctionDef) -> bool:
        """Heuristic to determine if a method appears to modify state."""
        return not self._appears_read_only(method)