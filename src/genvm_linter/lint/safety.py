"""AST-based safety checks for forbidden imports and non-deterministic patterns."""

import ast
from dataclasses import dataclass
from pathlib import Path

# Modules that are forbidden in GenLayer contracts (non-deterministic)
FORBIDDEN_MODULES = frozenset({
    "random",
    "os",
    "sys",
    "subprocess",
    "threading",
    "multiprocessing",
    "asyncio",
    "socket",
    "http",
    "requests",
    "pickle",
    "shelve",
    "sqlite3",
    "tempfile",
    "shutil",
    "glob",
    "pathlib",
    "io",
    "builtins",
})

# Modules that look forbidden but are actually safe
ALLOWED_MODULES = frozenset({
    "urllib.parse",  # Deterministic URL parsing, no network
})

# Specific attributes/functions that are non-deterministic
# Note: datetime.now() is OK in GenLayer - SDK provides deterministic version
FORBIDDEN_CALLS = frozenset({
    "time.time",
    "time.localtime",
    "time.gmtime",
    "uuid.uuid1",
    "uuid.uuid4",
})


@dataclass
class SafetyWarning:
    """A safety warning from AST analysis."""

    code: str
    msg: str
    line: int
    col: int = 0


class SafetyChecker(ast.NodeVisitor):
    """AST visitor that checks for forbidden imports and non-deterministic patterns."""

    def __init__(self):
        self.warnings: list[SafetyWarning] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            # Check if full module path is allowed
            if alias.name in ALLOWED_MODULES:
                continue
            module_name = alias.name.split(".")[0]
            if module_name in FORBIDDEN_MODULES:
                self.warnings.append(
                    SafetyWarning(
                        code="W001",
                        msg=f"Forbidden import '{alias.name}'",
                        line=node.lineno,
                        col=node.col_offset,
                    )
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            # Check if full module path is allowed
            if node.module in ALLOWED_MODULES:
                self.generic_visit(node)
                return
            module_name = node.module.split(".")[0]
            if module_name in FORBIDDEN_MODULES:
                self.warnings.append(
                    SafetyWarning(
                        code="W001",
                        msg=f"Forbidden import from '{node.module}'",
                        line=node.lineno,
                        col=node.col_offset,
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Check for forbidden function calls like datetime.now()
        call_name = self._get_call_name(node)
        if call_name in FORBIDDEN_CALLS:
            self.warnings.append(
                SafetyWarning(
                    code="W002",
                    msg=f"Non-deterministic call '{call_name}()'",
                    line=node.lineno,
                    col=node.col_offset,
                )
            )

        # Check for float() which can cause non-determinism
        if isinstance(node.func, ast.Name) and node.func.id == "float":
            self.warnings.append(
                SafetyWarning(
                    code="W003",
                    msg="Use of 'float' type (non-deterministic); use Decimal instead",
                    line=node.lineno,
                    col=node.col_offset,
                )
            )

        self.generic_visit(node)

    def _get_call_name(self, node: ast.Call) -> str:
        """Extract the full name of a function call."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""


def check_safety(source: str | Path) -> list[SafetyWarning]:
    """
    Check a contract for safety issues.

    Args:
        source: Contract source code or path to contract file

    Returns:
        List of safety warnings
    """
    if isinstance(source, Path):
        source = source.read_text()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Syntax errors are handled by the validate step
        return []

    checker = SafetyChecker()
    checker.visit(tree)
    return checker.warnings
