"""AST-based structure checks for GenLayer contracts."""

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StructureWarning:
    """A structure warning from analysis."""

    code: str
    msg: str
    line: int
    col: int = 0


# Storage types that require special handling
GENLAYER_STORAGE_TYPES = {"DynArray", "Array", "TreeMap"}
FORBIDDEN_STORAGE_TYPES = {"list", "dict", "int"}


class ContractStructureChecker(ast.NodeVisitor):
    """Check GenLayer contract structure rules."""

    def __init__(self):
        self.warnings: list[StructureWarning] = []
        self.contract_classes: list[tuple[str, int, int]] = []  # (name, line, col)
        self.current_class: ast.ClassDef | None = None
        self.is_contract_class = False

    def visit_ClassDef(self, node: ast.ClassDef):
        # Check if this is a Contract subclass
        is_contract = self._is_contract_subclass(node)

        if is_contract:
            self.contract_classes.append((node.name, node.lineno, node.col_offset))

        old_class = self.current_class
        old_is_contract = self.is_contract_class
        self.current_class = node
        self.is_contract_class = is_contract

        if is_contract:
            self._check_contract_class(node)

        self.generic_visit(node)

        self.current_class = old_class
        self.is_contract_class = old_is_contract

    def _is_contract_subclass(self, node: ast.ClassDef) -> bool:
        """Check if class inherits from gl.Contract or Contract."""
        for base in node.bases:
            if isinstance(base, ast.Attribute):
                # gl.Contract
                if (isinstance(base.value, ast.Name) and
                    base.value.id == "gl" and
                    base.attr == "Contract"):
                    return True
            elif isinstance(base, ast.Name):
                # Contract (direct import)
                if base.id == "Contract":
                    return True
        return False

    def _check_contract_class(self, node: ast.ClassDef):
        """Check all rules for a contract class."""
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._check_method(item)
            elif isinstance(item, ast.AnnAssign):
                # Storage field annotation
                self._check_storage_field(item)

    def _check_method(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        """Check method-level rules."""
        decorators = self._get_decorator_names(node)
        is_public = "gl.public.write" in decorators or "gl.public.view" in decorators
        is_view = "gl.public.view" in decorators

        # E012: __init__ must be private
        if node.name == "__init__" and is_public:
            self.warnings.append(StructureWarning(
                code="E012",
                msg="__init__ must be private (remove @gl.public decorator)",
                line=node.lineno,
                col=node.col_offset,
            ))

        # E013: Public methods cannot start with __
        if is_public and node.name.startswith("__") and node.name != "__init__":
            self.warnings.append(StructureWarning(
                code="E013",
                msg=f"Public method '{node.name}' cannot start with '__'",
                line=node.lineno,
                col=node.col_offset,
            ))

        # E019: Special methods need correct decorators
        special_methods = {
            "__receive__": "gl.public.write",
            "__on_bridge__": "gl.public.write",
        }
        if node.name in special_methods:
            required = special_methods[node.name]
            if required not in decorators:
                self.warnings.append(StructureWarning(
                    code="E019",
                    msg=f"'{node.name}' requires @{required} decorator",
                    line=node.lineno,
                    col=node.col_offset,
                ))

        # W020: View methods should have return type annotation (for schema generation)
        if is_view and node.returns is None:
            self.warnings.append(StructureWarning(
                code="W020",
                msg=f"View method '{node.name}' should have return type annotation",
                line=node.lineno,
                col=node.col_offset,
            ))

        # E021: No *args/**kwargs in public methods
        if is_public:
            if node.args.vararg:
                self.warnings.append(StructureWarning(
                    code="E021",
                    msg=f"Public method '{node.name}' cannot use *args",
                    line=node.args.vararg.lineno,
                    col=node.args.vararg.col_offset,
                ))
            if node.args.kwarg:
                self.warnings.append(StructureWarning(
                    code="E021",
                    msg=f"Public method '{node.name}' cannot use **kwargs",
                    line=node.args.kwarg.lineno,
                    col=node.args.kwarg.col_offset,
                ))

        # E022: First param must be self
        if len(node.args.args) == 0 or node.args.args[0].arg != "self":
            self.warnings.append(StructureWarning(
                code="E022",
                msg=f"Method '{node.name}' must have 'self' as first parameter",
                line=node.lineno,
                col=node.col_offset,
            ))

    def _check_storage_field(self, node: ast.AnnAssign):
        """Check storage field rules."""
        if not isinstance(node.target, ast.Name):
            return

        field_name = node.target.id
        annotation = node.annotation

        # E015: No raw int in storage
        if isinstance(annotation, ast.Name) and annotation.id == "int":
            self.warnings.append(StructureWarning(
                code="E015",
                msg=f"Storage field '{field_name}' cannot use raw 'int'; use u256/i256",
                line=node.lineno,
                col=node.col_offset,
            ))

        # E016: No list/dict in storage
        if isinstance(annotation, ast.Name):
            if annotation.id == "list":
                self.warnings.append(StructureWarning(
                    code="E016",
                    msg=f"Storage field '{field_name}' cannot use 'list'; use DynArray",
                    line=node.lineno,
                    col=node.col_offset,
                ))
            elif annotation.id == "dict":
                self.warnings.append(StructureWarning(
                    code="E016",
                    msg=f"Storage field '{field_name}' cannot use 'dict'; use TreeMap",
                    line=node.lineno,
                    col=node.col_offset,
                ))

        # Check subscripted types: list[X], dict[K,V]
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name):
                if annotation.value.id == "list":
                    self.warnings.append(StructureWarning(
                        code="E016",
                        msg=f"Storage field '{field_name}' cannot use 'list'; use DynArray",
                        line=node.lineno,
                        col=node.col_offset,
                    ))
                elif annotation.value.id == "dict":
                    self.warnings.append(StructureWarning(
                        code="E016",
                        msg=f"Storage field '{field_name}' cannot use 'dict'; use TreeMap",
                        line=node.lineno,
                        col=node.col_offset,
                    ))

        # E017: Array size must be positive (check Array[T, Literal[N]])
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name) and annotation.value.id == "Array":
                self._check_array_size(node, field_name, annotation)

        # E018: TreeMap keys must be str
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name) and annotation.value.id == "TreeMap":
                self._check_treemap_key(node, field_name, annotation)

    def _check_array_size(self, node: ast.AnnAssign, field_name: str, annotation: ast.Subscript):
        """Check that Array has valid size literal."""
        # Array[T, Literal[N]] - second arg should be Literal with positive int
        if isinstance(annotation.slice, ast.Tuple) and len(annotation.slice.elts) >= 2:
            size_arg = annotation.slice.elts[1]
            # Check for Literal[N]
            if isinstance(size_arg, ast.Subscript):
                if isinstance(size_arg.value, ast.Name) and size_arg.value.id == "Literal":
                    if isinstance(size_arg.slice, ast.Constant):
                        if not isinstance(size_arg.slice.value, int) or size_arg.slice.value <= 0:
                            self.warnings.append(StructureWarning(
                                code="E017",
                                msg=f"Array size for '{field_name}' must be positive integer",
                                line=node.lineno,
                                col=node.col_offset,
                            ))

    def _check_treemap_key(self, node: ast.AnnAssign, field_name: str, annotation: ast.Subscript):
        """Check that TreeMap key type is Comparable (str, Address, u32, u256, etc.)."""
        # TreeMap[K: Comparable, V] - key must be a Comparable type
        # Valid types: str, Address, u32, u256, i32, i256, bytes
        valid_key_types = {"str", "Address", "u32", "u256", "i32", "i256", "bytes"}
        if isinstance(annotation.slice, ast.Tuple) and len(annotation.slice.elts) >= 1:
            key_type = annotation.slice.elts[0]
            if isinstance(key_type, ast.Name) and key_type.id not in valid_key_types:
                self.warnings.append(StructureWarning(
                    code="E018",
                    msg=f"TreeMap key for '{field_name}' must be Comparable (str, Address, u32, etc.), got '{key_type.id}'",
                    line=node.lineno,
                    col=node.col_offset,
                ))

    def _get_decorator_names(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
        """Get all decorator names as strings."""
        names = set()
        for dec in node.decorator_list:
            name = self._decorator_to_string(dec)
            if name:
                names.add(name)
        return names

    def _decorator_to_string(self, dec: ast.expr) -> str | None:
        """Convert decorator AST to string like 'gl.public.view'."""
        if isinstance(dec, ast.Name):
            return dec.id
        elif isinstance(dec, ast.Attribute):
            parts = []
            current = dec
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
                return ".".join(reversed(parts))
        elif isinstance(dec, ast.Call):
            return self._decorator_to_string(dec.func)
        return None


class StorageClassChecker(ast.NodeVisitor):
    """Check classes used in storage for @allow_storage decorator."""

    def __init__(self):
        self.warnings: list[StructureWarning] = []
        self.storage_classes: set[str] = set()  # Classes used in storage
        self.allow_storage_classes: set[str] = set()  # Classes with @allow_storage
        self.class_locations: dict[str, tuple[int, int]] = {}  # class -> (line, col)

    def visit_ClassDef(self, node: ast.ClassDef):
        # Check if has @allow_storage decorator
        for dec in node.decorator_list:
            dec_name = self._decorator_to_string(dec)
            if dec_name in ("allow_storage", "gl.allow_storage"):
                self.allow_storage_classes.add(node.name)
                break

        self.class_locations[node.name] = (node.lineno, node.col_offset)

        # Check if this is a Contract class and collect storage types
        if self._is_contract_subclass(node):
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    self._collect_storage_types(item.annotation)

        self.generic_visit(node)

    def _is_contract_subclass(self, node: ast.ClassDef) -> bool:
        for base in node.bases:
            if isinstance(base, ast.Attribute):
                if (isinstance(base.value, ast.Name) and
                    base.value.id == "gl" and
                    base.attr == "Contract"):
                    return True
            elif isinstance(base, ast.Name):
                if base.id == "Contract":
                    return True
        return False

    def _collect_storage_types(self, annotation: ast.expr | None):
        """Collect custom class types used in storage annotations."""
        if annotation is None:
            return

        if isinstance(annotation, ast.Name):
            # Skip built-in and GenLayer types
            if annotation.id not in ("str", "int", "bool", "bytes", "float",
                                     "u256", "i256", "Address",
                                     "DynArray", "Array", "TreeMap", "Literal"):
                self.storage_classes.add(annotation.id)

        elif isinstance(annotation, ast.Subscript):
            # Recurse into generic types
            self._collect_storage_types(annotation.value)
            if isinstance(annotation.slice, ast.Tuple):
                for elt in annotation.slice.elts:
                    self._collect_storage_types(elt)
            else:
                self._collect_storage_types(annotation.slice)

    def _decorator_to_string(self, dec: ast.expr) -> str | None:
        if isinstance(dec, ast.Name):
            return dec.id
        elif isinstance(dec, ast.Attribute):
            parts = []
            current = dec
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
                return ".".join(reversed(parts))
        elif isinstance(dec, ast.Call):
            return self._decorator_to_string(dec.func)
        return None

    def check_missing_decorators(self) -> list[StructureWarning]:
        """Check for storage classes missing @allow_storage."""
        warnings = []
        for cls_name in self.storage_classes:
            if cls_name not in self.allow_storage_classes:
                if cls_name in self.class_locations:
                    line, col = self.class_locations[cls_name]
                    warnings.append(StructureWarning(
                        code="E014",
                        msg=f"Class '{cls_name}' used in storage needs @allow_storage decorator",
                        line=line,
                        col=col,
                    ))
        return warnings


def check_structure(source: str | Path) -> list[StructureWarning]:
    """
    Check contract structure (magic comment, etc).

    Args:
        source: Contract source code or path to contract file

    Returns:
        List of structure warnings
    """
    if isinstance(source, Path):
        source = source.read_text()

    warnings: list[StructureWarning] = []

    # Check for magic comment header
    # Should have # { "Seq": [...] } at the start
    lines = source.split("\n")

    has_header = False
    header_content = []

    for line in lines:
        if line.startswith("#"):
            header_content.append(line[1:].strip() if line.startswith("# ") else line[1:])
        else:
            break

    if header_content:
        header_text = "".join(header_content)
        # Check if it looks like a valid dependency header
        # Two valid formats:
        # 1. Single dependency: # { "Depends": "py-genlayer:..." }
        # 2. Multiple dependencies: # { "Seq": [{ "Depends": "..." }, ...] }
        if '"Depends"' in header_text:
            has_header = True

    if not has_header:
        warnings.append(
            StructureWarning(
                code="W010",
                msg="Missing contract dependency header (# { \"Seq\": [...] })",
                line=1,
            )
        )

    # Check for py-genlayer dependency specifically
    if has_header:
        if "py-genlayer:" not in "".join(header_content):
            warnings.append(
                StructureWarning(
                    code="W011",
                    msg="Missing py-genlayer dependency in header",
                    line=1,
                )
            )

    # AST-based checks
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Syntax errors are handled elsewhere
        return warnings

    # Contract structure checks
    structure_checker = ContractStructureChecker()
    structure_checker.visit(tree)
    warnings.extend(structure_checker.warnings)

    # E011: Single contract per module
    if len(structure_checker.contract_classes) > 1:
        for name, line, col in structure_checker.contract_classes[1:]:
            warnings.append(
                StructureWarning(
                    code="E011",
                    msg=f"Multiple contracts in module; '{name}' should be in separate file",
                    line=line,
                    col=col,
                )
            )

    # Storage class checks
    storage_checker = StorageClassChecker()
    storage_checker.visit(tree)
    warnings.extend(storage_checker.check_missing_decorators())

    return warnings
