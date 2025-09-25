"""
Dataclass validation rules for GenVM contracts.
Tracks dataclass definitions and validates instantiations.
"""

import ast
from typing import Dict, List, Optional, Set
from .base import Rule, ValidationResult, Severity
from ..type_system import GenVMTypeSystem


class DataclassValidation(Rule, ast.NodeVisitor):
    """Validates dataclass field names and types at instantiation."""

    def __init__(self):
        super().__init__(
            rule_id="genvm-dataclasses",
            description="Validate dataclass field names and types"
        )
        self.dataclass_info: Dict[str, DataclassInfo] = {}
        self.results: List[ValidationResult] = []
        self.filename: Optional[str] = None

    def check(self, node: ast.AST, filename: Optional[str] = None) -> List[ValidationResult]:
        """Check for dataclass validation issues."""
        if not isinstance(node, ast.Module):
            return []

        self.results = []
        self.filename = filename
        self.dataclass_info = {}

        # First pass: collect dataclass definitions
        for stmt in node.body:
            if isinstance(stmt, ast.ClassDef):
                self._check_dataclass_def(stmt)

        # Second pass: validate dataclass instantiations
        self.visit(node)

        return self.results

    def _check_dataclass_def(self, node: ast.ClassDef):
        """Track dataclass definitions."""
        # Check if this is a dataclass
        is_dataclass = any(
            isinstance(dec, ast.Name) and dec.id == 'dataclass'
            or isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == 'dataclass'
            for dec in node.decorator_list
        )

        if is_dataclass:
            # Extract field information from the class
            fields = {}
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    field_name = stmt.target.id
                    field_type = self._extract_type(stmt.annotation)
                    fields[field_name] = field_type

            self.dataclass_info[node.name] = DataclassInfo(
                name=node.name,
                fields=fields,
                node=node
            )

    def visit_Call(self, node: ast.Call):
        """Validate dataclass instantiations."""
        if isinstance(node.func, ast.Name) and node.func.id in self.dataclass_info:
            dataclass = self.dataclass_info[node.func.id]

            # Collect provided field names from keyword arguments
            provided_fields = set()
            field_values = {}

            # Handle positional arguments (matched to field order)
            field_names = list(dataclass.fields.keys())
            for i, arg in enumerate(node.args):
                if i < len(field_names):
                    field_name = field_names[i]
                    provided_fields.add(field_name)
                    field_values[field_name] = arg

            # Handle keyword arguments
            for keyword in node.keywords:
                if keyword.arg is not None:
                    provided_fields.add(keyword.arg)
                    field_values[keyword.arg] = keyword.value

                    # Check if field exists in dataclass
                    if keyword.arg not in dataclass.fields:
                        self.results.append(self.create_result(
                            message=f"Dataclass '{dataclass.name}' has no field '{keyword.arg}'",
                            severity=Severity.ERROR,
                            line=node.lineno,
                            column=node.col_offset,
                            filename=self.filename,
                            suggestion=f"Available fields: {', '.join(dataclass.fields.keys())}"
                        ))

            # Check type compatibility for provided fields
            for field_name, value in field_values.items():
                if field_name in dataclass.fields:
                    expected_type = dataclass.fields[field_name]
                    if expected_type and not self._is_type_compatible(value, expected_type):
                        actual_type = self._get_value_type(value)
                        self.results.append(self.create_result(
                            message=f"Type mismatch for field '{field_name}': expected {expected_type}, got {actual_type}",
                            severity=Severity.ERROR,
                            line=value.lineno if hasattr(value, 'lineno') else node.lineno,
                            column=value.col_offset if hasattr(value, 'col_offset') else node.col_offset,
                            filename=self.filename,
                            suggestion=f"Ensure the value matches the expected type '{expected_type}'"
                        ))

        self.generic_visit(node)

    def _extract_type(self, annotation: ast.AST) -> Optional[str]:
        """Extract type name from annotation."""
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Constant):
            return str(annotation.value)
        elif isinstance(annotation, ast.Attribute):
            return f"{self._extract_type(annotation.value)}.{annotation.attr}"
        elif isinstance(annotation, ast.Subscript):
            # Handle generic types like List[str], Dict[str, int]
            base = self._extract_type(annotation.value)
            return base
        return None

    def _is_type_compatible(self, value: ast.AST, expected_type: str) -> bool:
        """Check if a value is compatible with the expected type."""
        if isinstance(value, ast.Constant):
            if expected_type == 'str' and isinstance(value.value, str):
                return True
            elif expected_type == 'int' and isinstance(value.value, int) and not isinstance(value.value, bool):
                return True
            elif expected_type == 'float' and isinstance(value.value, (int, float)) and not isinstance(value.value, bool):
                return True
            elif expected_type == 'bool' and isinstance(value.value, bool):
                return True
            # GenVM type equivalences: int literals can be used for sized integer types
            elif GenVMTypeSystem.is_sized_int_type(expected_type) and isinstance(value.value, int) and not isinstance(value.value, bool):
                return True
        elif isinstance(value, ast.Name):
            # Can't determine variable type without more analysis
            return True  # Assume compatible for now
        elif isinstance(value, ast.Call):
            # Constructor calls - check if types match
            if isinstance(value.func, ast.Name):
                return value.func.id == expected_type
        elif isinstance(value, ast.List):
            # Use centralized type compatibility check
            if GenVMTypeSystem.is_type_compatible('list', expected_type):
                return True
        elif isinstance(value, ast.Dict):
            # Use centralized type compatibility check
            if GenVMTypeSystem.is_type_compatible('dict', expected_type):
                return True

        return False

    def _get_value_type(self, value: ast.AST) -> str:
        """Get the type of a value node."""
        if isinstance(value, ast.Constant):
            return type(value.value).__name__
        elif isinstance(value, ast.Name):
            return 'variable'
        elif isinstance(value, ast.Call):
            if isinstance(value.func, ast.Name):
                return value.func.id
            return 'call'
        elif isinstance(value, ast.List):
            return 'list'
        elif isinstance(value, ast.Dict):
            return 'dict'
        return 'unknown'


class DataclassInfo:
    """Information about a dataclass."""

    def __init__(self, name: str, fields: Dict[str, Optional[str]], node: ast.ClassDef):
        self.name = name
        self.fields = fields  # field_name -> type_name
        self.node = node