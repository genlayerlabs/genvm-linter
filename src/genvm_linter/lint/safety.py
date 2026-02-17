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

# Built-in Python exception types that should not be raised in contracts.
# These crash the GenVM WASM runtime (generic exit_code 1), lose the error
# message, break consensus, and break downstream error parsing.
# Use gl.vm.UserError("message") instead.
BUILTIN_EXCEPTIONS = frozenset({
    "BaseException", "Exception", "ArithmeticError", "AssertionError",
    "AttributeError", "BlockingIOError", "BrokenPipeError", "BufferError",
    "ChildProcessError", "ConnectionAbortedError", "ConnectionError",
    "ConnectionRefusedError", "ConnectionResetError", "EOFError",
    "FileExistsError", "FileNotFoundError", "FloatingPointError",
    "GeneratorExit", "IOError", "ImportError", "IndexError",
    "InterruptedError", "IsADirectoryError", "KeyError",
    "KeyboardInterrupt", "LookupError", "MemoryError",
    "ModuleNotFoundError", "NameError", "NotADirectoryError",
    "NotImplementedError", "OSError", "OverflowError", "PermissionError",
    "ProcessLookupError", "RecursionError", "ReferenceError",
    "RuntimeError", "StopAsyncIteration", "StopIteration", "SyntaxError",
    "SystemError", "SystemExit", "TimeoutError", "TypeError",
    "UnboundLocalError", "UnicodeDecodeError", "UnicodeEncodeError",
    "UnicodeError", "UnicodeTranslateError", "ValueError",
    "ZeroDivisionError",
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
        self._contract_depth: int = 0

    def visit_ClassDef(self, node: ast.ClassDef):
        is_contract = self._is_contract_class(node)
        if is_contract:
            self._contract_depth += 1
        self.generic_visit(node)
        if is_contract:
            self._contract_depth -= 1

    def visit_Raise(self, node: ast.Raise):
        if self._contract_depth > 0 and node.exc is not None:
            exc_name = self._get_exception_name(node.exc)
            if exc_name in BUILTIN_EXCEPTIONS:
                self.warnings.append(
                    SafetyWarning(
                        code="W004",
                        msg=f"Bare Python exception '{exc_name}' in contract; use gl.vm.UserError(\"message\") instead",
                        line=node.lineno,
                        col=node.col_offset,
                    )
                )
        self.generic_visit(node)

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

    def _is_contract_class(self, node: ast.ClassDef) -> bool:
        """Check if a class inherits from gl.Contract / genlayer.Contract / Contract."""
        for base in node.bases:
            if isinstance(base, ast.Attribute) and base.attr == "Contract":
                if isinstance(base.value, ast.Name) and base.value.id in ("gl", "genlayer"):
                    return True
            if isinstance(base, ast.Name) and base.id == "Contract":
                return True
        return False

    def _get_exception_name(self, node: ast.expr) -> str:
        """Extract the exception class name from a raise target."""
        if isinstance(node, ast.Call):
            return self._get_exception_name(node.func)
        if isinstance(node, ast.Name):
            return node.id
        return ""


class CallGraphBuilder(ast.NodeVisitor):
    """Build a call graph mapping functions to the functions they call."""

    def __init__(self):
        self.calls: dict[str, set[str]] = {}  # func_name -> set of called func names
        self.current_class: str | None = None
        self.function_stack: list[str] = []  # For nested functions

    def _get_qualified_name(self, name: str) -> str:
        """Get fully qualified name for a function/method."""
        # For nested functions, include parent scope
        if self.function_stack:
            return f"{self.function_stack[-1]}.<locals>.{name}"
        if self.current_class:
            return f"{self.current_class}.{name}"
        return name

    def _get_current_scope(self) -> str | None:
        """Get the current function scope."""
        return self.function_stack[-1] if self.function_stack else None

    def visit_ClassDef(self, node: ast.ClassDef):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        func_name = self._get_qualified_name(node.name)
        if func_name not in self.calls:
            self.calls[func_name] = set()

        # If nested, parent calls this function
        if self.function_stack:
            self.calls[self.function_stack[-1]].add(func_name)

        self.function_stack.append(func_name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        func_name = self._get_qualified_name(node.name)
        if func_name not in self.calls:
            self.calls[func_name] = set()

        if self.function_stack:
            self.calls[self.function_stack[-1]].add(func_name)

        self.function_stack.append(func_name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Lambda(self, node: ast.Lambda):
        # Lambdas are part of their containing function's scope
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        current_scope = self._get_current_scope()
        if current_scope:
            called_name = self._get_call_target(node)
            if called_name:
                self.calls[current_scope].add(called_name)
        self.generic_visit(node)

    def _get_call_target(self, node: ast.Call) -> str | None:
        """Extract the target function name from a call."""
        if isinstance(node.func, ast.Name):
            # Could be a local nested function or a global
            name = node.func.id
            # Check if it's a nested function in current scope
            if self.function_stack:
                nested_name = f"{self.function_stack[-1]}.<locals>.{name}"
                if nested_name in self.calls:
                    return nested_name
            return name
        elif isinstance(node.func, ast.Attribute):
            # Handle self.method() -> ClassName.method
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                if self.current_class:
                    return f"{self.current_class}.{node.func.attr}"
            # Handle other attribute access
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return None


class NondetCallFinder(ast.NodeVisitor):
    """Find all gl.nondet.* calls and their containing function."""

    def __init__(self):
        self.nondet_calls: list[tuple[str | None, int, int]] = []  # (func_name, line, col)
        self.current_class: str | None = None
        self.function_stack: list[str] = []

    def _get_qualified_name(self, name: str) -> str:
        # For nested functions, include parent scope
        if self.function_stack:
            return f"{self.function_stack[-1]}.<locals>.{name}"
        if self.current_class:
            return f"{self.current_class}.{name}"
        return name

    def _get_current_scope(self) -> str | None:
        return self.function_stack[-1] if self.function_stack else None

    def visit_ClassDef(self, node: ast.ClassDef):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        func_name = self._get_qualified_name(node.name)
        self.function_stack.append(func_name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        func_name = self._get_qualified_name(node.name)
        self.function_stack.append(func_name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Call(self, node: ast.Call):
        # Check if this is a gl.nondet.* call
        call_name = self._get_full_call_name(node)
        if call_name and call_name.startswith("gl.nondet."):
            self.nondet_calls.append((
                self._get_current_scope(),
                node.lineno,
                node.col_offset,
            ))
        self.generic_visit(node)

    def _get_full_call_name(self, node: ast.Call) -> str | None:
        """Get full dotted name of call like gl.nondet.web.get."""
        parts = []
        current = node.func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return ".".join(reversed(parts))
        return None


class SafeEntryPointFinder(ast.NodeVisitor):
    """Find functions passed to eq_principle/run_nondet (safe contexts for nondet)."""

    # Patterns that mark safe entry points
    SAFE_PATTERNS = {
        "gl.vm.run_nondet": [0, 1],  # Both leader_fn and validator_fn args
        "gl.vm.run_nondet_unsafe": [0, 1],
        "gl.eq_principle.strict_eq": [0],  # First arg
        "gl.eq_principle.prompt_comparative": [0],
        "gl.eq_principle.prompt_non_comparative": [0],
    }

    def __init__(self):
        self.safe_functions: set[str] = set()
        self.current_class: str | None = None
        self.function_stack: list[str] = []
        # Track lambdas that contain nondet - their containing scope is safe
        self.lambda_scopes: set[str] = set()

    def _get_qualified_name(self, name: str) -> str:
        # For nested functions, include parent scope
        if self.function_stack:
            return f"{self.function_stack[-1]}.<locals>.{name}"
        if self.current_class:
            return f"{self.current_class}.{name}"
        return name

    def _get_current_scope(self) -> str | None:
        return self.function_stack[-1] if self.function_stack else None

    def visit_ClassDef(self, node: ast.ClassDef):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        func_name = self._get_qualified_name(node.name)
        self.function_stack.append(func_name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        func_name = self._get_qualified_name(node.name)
        self.function_stack.append(func_name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Call(self, node: ast.Call):
        call_name = self._get_full_call_name(node)

        if call_name in self.SAFE_PATTERNS:
            arg_indices = self.SAFE_PATTERNS[call_name]
            for idx in arg_indices:
                if idx < len(node.args):
                    arg = node.args[idx]
                    self._extract_function_from_arg(arg)

        self.generic_visit(node)

    def _get_full_call_name(self, node: ast.Call) -> str | None:
        parts = []
        current = node.func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return ".".join(reversed(parts))
        return None

    def _extract_function_from_arg(self, arg: ast.expr):
        """Extract function name from an argument passed to safe pattern."""
        if isinstance(arg, ast.Name):
            # Direct function reference: run_nondet(leader_fn, ...)
            # This could be a nested function - qualify it with current scope
            name = arg.id
            if self.function_stack:
                # It's likely a local nested function
                qualified = f"{self.function_stack[-1]}.<locals>.{name}"
                self.safe_functions.add(qualified)
            self.safe_functions.add(name)  # Also add bare name for fallback
        elif isinstance(arg, ast.Attribute):
            # Method reference: run_nondet(self.leader, ...)
            if isinstance(arg.value, ast.Name) and arg.value.id == "self":
                if self.current_class:
                    self.safe_functions.add(f"{self.current_class}.{arg.attr}")
            else:
                # Other attribute access
                parts = []
                current = arg
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                    self.safe_functions.add(".".join(reversed(parts)))
        elif isinstance(arg, ast.Lambda):
            # Lambda passed directly: eq_principle.strict_eq(lambda: ...)
            # The containing function scope is safe for this lambda's calls
            scope = self._get_current_scope()
            if scope:
                self.lambda_scopes.add(scope)


def is_reachable(call_graph: dict[str, set[str]], sources: set[str], target: str) -> bool:
    """Check if target function is reachable from any source via call graph."""
    if target in sources:
        return True

    visited: set[str] = set()
    queue = list(sources)

    while queue:
        current = queue.pop(0)
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        queue.extend(call_graph.get(current, set()))

    return False


def check_nondet_outside_eq_principle(source: str) -> list[SafetyWarning]:
    """
    Check for gl.nondet.* calls that are not in equivalence principle blocks.

    These calls will cause consensus failures at runtime because validators
    cannot agree on non-deterministic results without an equivalence principle.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    # Build call graph
    cg_builder = CallGraphBuilder()
    cg_builder.visit(tree)
    call_graph = cg_builder.calls

    # Find all nondet calls
    nondet_finder = NondetCallFinder()
    nondet_finder.visit(tree)
    nondet_calls = nondet_finder.nondet_calls

    # Find safe entry points
    entry_finder = SafeEntryPointFinder()
    entry_finder.visit(tree)
    safe_functions = entry_finder.safe_functions
    lambda_scopes = entry_finder.lambda_scopes

    # Combine safe functions with lambda scopes
    all_safe = safe_functions | lambda_scopes

    warnings = []
    for func_name, line, col in nondet_calls:
        if func_name is None:
            # Module-level nondet call - always error
            warnings.append(SafetyWarning(
                code="E010",
                msg="gl.nondet.* call at module level (must be in equivalence principle block)",
                line=line,
                col=col,
            ))
        elif not is_reachable(call_graph, all_safe, func_name):
            warnings.append(SafetyWarning(
                code="E010",
                msg=f"gl.nondet.* call in '{func_name}' not reachable from equivalence principle block",
                line=line,
                col=col,
            ))

    return warnings


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

    # Add nondet-outside-eq-principle check
    nondet_warnings = check_nondet_outside_eq_principle(source)

    return checker.warnings + nondet_warnings
