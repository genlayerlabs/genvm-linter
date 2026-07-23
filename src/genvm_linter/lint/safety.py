"""AST-based safety checks for forbidden imports and non-deterministic patterns."""

import ast
from dataclasses import dataclass
from pathlib import Path

from .ast_utils import is_contract_subclass

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
        """Check if the class inherits from a supported Contract base."""
        return is_contract_subclass(node)

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

    def visit_Lambda(self, node: ast.Lambda):
        lambda_scope = f"<lambda:{node.lineno}:{node.col_offset}>"
        self.function_stack.append(lambda_scope)
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

    # Decorator names that mark a function as a safe entry point.
    # Must stay in sync with _STRICT_EQ_CALLS in GL-S03.
    _STRICT_EQ_DECORATORS = frozenset({
        "eq_principle_strict_eq",
        "gl.eq_principle_strict_eq",
        "gl.eq_principle.strict_eq",
        "eq_principle.strict_eq",
    })

    # Patterns that mark safe entry points.
    # strict_eq entries must stay in sync with _STRICT_EQ_CALLS in GL-S03.
    SAFE_PATTERNS = {
        "gl.vm.run_nondet": [0, 1],  # Both leader_fn and validator_fn args
        "gl.vm.run_nondet_unsafe": [0, 1],
        "gl.eq_principle.strict_eq": [0],        # v0.1.3+ — first arg
        "gl.eq_principle_strict_eq": [0],        # v0.1.0 gl attribute form
        "eq_principle_strict_eq": [0],           # direct import alias
        "eq_principle.strict_eq": [0],           # from genlayer.gl import eq_principle
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
        if any(_decorator_name(dec) in self._STRICT_EQ_DECORATORS for dec in node.decorator_list):
            self.safe_functions.add(func_name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        func_name = self._get_qualified_name(node.name)
        self.function_stack.append(func_name)
        if any(_decorator_name(dec) in self._STRICT_EQ_DECORATORS for dec in node.decorator_list):
            self.safe_functions.add(func_name)
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
            # Register the lambda's own synthetic scope so NondetCallFinder
            # can match it regardless of whether there's a containing function.
            self.safe_functions.add(f"<lambda:{arg.lineno}:{arg.col_offset}>")
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


# Calls that spawn non-deterministic blocks
NONDET_SPAWN_CALLS = frozenset({
    "gl.vm.run_nondet",
    "gl.vm.run_nondet_unsafe",
    "gl.eq_principle.strict_eq",
    "gl.eq_principle.prompt_comparative",
    "gl.eq_principle.prompt_non_comparative",
})

# Calls that access other contracts
CONTRACT_ACCESS_CALLS = frozenset({
    "gl.get_contract_at",
    "genlayer.get_contract_at",
})

# Error messages per code
_NONDET_MESSAGES = {
    "E023": "message emission is forbidden in non-deterministic contexts",
    "E024": "inter-contract calls are forbidden in non-deterministic contexts",
    "E025": "nested non-deterministic blocks are forbidden",
    "E026": "storage writes are forbidden in non-deterministic contexts",
}


def _find_evm_interface_classes(tree: ast.Module) -> set[str]:
    """Find class names decorated with @gl.evm.contract_interface."""
    classes = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for dec in node.decorator_list:
            parts = []
            current = dec
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
                name = ".".join(reversed(parts))
                if name in ("gl.evm.contract_interface", "genlayer.evm.contract_interface"):
                    classes.add(node.name)
    return classes


class ForbiddenInNondetFinder(ast.NodeVisitor):
    """Find operations that are forbidden inside non-deterministic blocks."""

    def __init__(self, evm_interface_classes: set[str]):
        # (code, description, func_name, line, col)
        self.findings: list[tuple[str, str, str | None, int, int]] = []
        self.current_class: str | None = None
        self.function_stack: list[str] = []
        self.evm_interface_classes = evm_interface_classes

    def _get_qualified_name(self, name: str) -> str:
        if self.function_stack:
            return f"{self.function_stack[-1]}.<locals>.{name}"
        if self.current_class:
            return f"{self.current_class}.{name}"
        return name

    def _get_current_scope(self) -> str | None:
        return self.function_stack[-1] if self.function_stack else None

    def _add(self, code: str, desc: str, node: ast.expr | ast.stmt):
        self.findings.append((
            code, desc, self._get_current_scope(),
            node.lineno, node.col_offset,
        ))

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
        # E023: .emit()
        if isinstance(node.func, ast.Attribute) and node.func.attr == "emit":
            self._add("E023", ".emit()", node)

        call_name = self._get_full_call_name(node)

        # E024: gl.get_contract_at()
        if call_name in CONTRACT_ACCESS_CALLS:
            self._add("E024", call_name + "()", node)

        # E024: EVM interface instantiation
        if isinstance(node.func, ast.Name) and node.func.id in self.evm_interface_classes:
            self._add("E024", f"{node.func.id}(...)", node)

        # E025: nested run_nondet / eq_principle
        if call_name in NONDET_SPAWN_CALLS:
            self._add("E025", call_name + "()", node)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            field = self._self_storage_field(target)
            if field:
                self._add("E026", f"self.{field}", node)
                break
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        field = self._self_storage_field(node.target)
        if field:
            self._add("E026", f"self.{field}", node)
        self.generic_visit(node)

    def _self_storage_field(self, node: ast.expr) -> str | None:
        """If node is self.xxx or self.xxx[...], return the field name."""
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                return node.attr
        if isinstance(node, ast.Subscript):
            return self._self_storage_field(node.value)
        return None

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


def check_forbidden_in_nondet(source: str) -> list[SafetyWarning]:
    """
    Check for operations forbidden inside non-deterministic blocks.

    Detects .emit(), inter-contract calls, nested run_nondet, and storage
    writes that are reachable from leader/validator functions.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    # Find EVM interface classes first
    evm_classes = _find_evm_interface_classes(tree)

    # Find all forbidden operations
    finder = ForbiddenInNondetFinder(evm_classes)
    finder.visit(tree)

    if not finder.findings:
        return []

    # Find nondet entry points
    entry_finder = SafeEntryPointFinder()
    entry_finder.visit(tree)
    all_safe = entry_finder.safe_functions | entry_finder.lambda_scopes

    if not all_safe:
        return []

    # Build call graph for reachability
    cg_builder = CallGraphBuilder()
    cg_builder.visit(tree)
    call_graph = cg_builder.calls

    warnings = []
    for code, desc, func_name, line, col in finder.findings:
        if func_name is None:
            continue  # Module-level — not in a nondet block
        if is_reachable(call_graph, all_safe, func_name):
            warnings.append(SafetyWarning(
                code=code,
                msg=f"{desc} in '{func_name}' reachable from non-deterministic block; {_NONDET_MESSAGES[code]}",
                line=line,
                col=col,
            ))

    return warnings


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

    # Add checks for operations forbidden inside nondet blocks
    forbidden_warnings = check_forbidden_in_nondet(source)

    # Semantic eq_principle quality check (GL-S03)
    semantic_warnings = check_eq_strict_mismatch(source)

    return checker.warnings + nondet_warnings + forbidden_warnings + semantic_warnings


# ---------------------------------------------------------------------------
# Shared helper for semantic rules
# ---------------------------------------------------------------------------


def _full_call_name(node: ast.Call) -> str:
    """Return the full dotted name of a call, e.g. 'gl.eq_principle.strict_eq'."""
    parts: list[str] = []
    current: ast.expr = node.func
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return ""


# ---------------------------------------------------------------------------
# GL-S03: eq_principle_strict_eq nondeterminism mismatch
# ---------------------------------------------------------------------------

# GL-S03 detects the following SDK call names by convention.
# Import-aware alias tracking is out of scope for this rule.
# Local or third-party functions named exec_prompt or get_webpage
# that are NOT accessed through the gl/genlayer namespace will
# not be flagged (they don't match the supported name list).
# Supported strict_eq names: gl.eq_principle_strict_eq (v0.1.0),
# gl.eq_principle.strict_eq (v0.1.3+), eq_principle_strict_eq
# (direct import alias).

# SDK nondeterministic calls — explicit names only (v0.1.0 and v0.1.3+ APIs).
# No prefix or wildcard matching; only the exact names listed here are in scope.
_S03_NONDET_CALLS = frozenset({
    # v0.1.0 — get_webpage is the direct predecessor of nondet.web.render;
    # both capture rendered page output, not stable API responses
    "get_webpage",
    "gl.get_webpage",
    "genlayer.get_webpage",
    # exec_prompt — LLM call, always nondeterministic
    "exec_prompt",
    "gl.exec_prompt",
    "genlayer.exec_prompt",
    # v0.1.3+ equivalents
    "gl.nondet.exec_prompt",
    "gl.nondet.web.render",
    "genlayer.gl.nondet.exec_prompt",
    "genlayer.gl.nondet.web.render",
})

# strict_eq patterns — v0.1.0, v0.1.3+, and aliased import forms
_STRICT_EQ_CALLS = frozenset({
    "eq_principle_strict_eq",           # direct import alias
    "gl.eq_principle_strict_eq",        # v0.1.0 — gl module attribute form
    "gl.eq_principle.strict_eq",        # v0.1.3+
    "eq_principle.strict_eq",           # from genlayer.gl import eq_principle
})

_GL_S03_MSG = (
    "GL-S03: eq_principle_strict_eq on line {line} wraps a function "
    "that returns raw nondeterministic output ({call_name} on line "
    "{nondet_line}). Strict equality will fail across validators. "
    "Use eq_principle_prompt_comparative or eq_principle_prompt_non_comparative instead."
)


def _s03_nondet_call(node: ast.expr) -> tuple[str, int] | None:
    """Return (call_name, line) if node is an SDK nondeterministic Call (unwraps await). Else None."""
    inner: ast.expr = node.value if isinstance(node, ast.Await) else node
    if isinstance(inner, ast.Call):
        name = _full_call_name(inner)
        if name in _S03_NONDET_CALLS:
            return name, inner.lineno
    return None


def _decorator_name(dec: ast.expr) -> str:
    """Return the full dotted name of a decorator (Name or Attribute only), else ''."""
    if isinstance(dec, ast.Name):
        return dec.id
    if isinstance(dec, ast.Attribute):
        parts: list[str] = []
        current: ast.expr = dec
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return ".".join(reversed(parts))
    return ""


def _get_compound_bodies(stmt: ast.stmt) -> list[list[ast.stmt]]:
    """Return nested statement lists from a compound statement, excluding function/class bodies."""
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return []
    bodies: list[list[ast.stmt]] = []
    if isinstance(stmt, (ast.If, ast.For, ast.While, ast.AsyncFor)):
        bodies.append(stmt.body)
        if stmt.orelse:
            bodies.append(stmt.orelse)
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        bodies.append(stmt.body)
    elif isinstance(stmt, ast.Try):
        bodies.append(stmt.body)
        for handler in stmt.handlers:
            bodies.append(handler.body)
        if stmt.orelse:
            bodies.append(stmt.orelse)
        if stmt.finalbody:
            bodies.append(stmt.finalbody)
    return bodies


def _iter_func_returns(stmts: list[ast.stmt]):
    """Yield Return nodes from a statement list, not descending into nested functions/classes."""
    for stmt in stmts:
        if isinstance(stmt, ast.Return):
            yield stmt
        else:
            for body in _get_compound_bodies(stmt):
                yield from _iter_func_returns(body)


def _collect_var_assigns(
    stmts: list[ast.stmt],
) -> dict[str, list[tuple[str | None, int]]]:
    """
    Collect all assignments to each variable in a function body.

    Returns dict[var_name -> list[(nondet_call_name_or_None, line)]].
    A None entry means the variable was reassigned to a non-nondet value.
    Does not descend into nested functions/classes.
    """
    result: dict[str, list[tuple[str | None, int]]] = {}

    def record(var: str, info: tuple[str | None, int]) -> None:
        result.setdefault(var, []).append(info)

    def scan(stmts_list: list[ast.stmt]) -> None:
        for stmt in stmts_list:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(stmt, ast.Assign):
                if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                    hit = _s03_nondet_call(stmt.value)
                    record(stmt.targets[0].id, hit if hit else (None, stmt.lineno))
            elif isinstance(stmt, ast.AnnAssign):
                if stmt.value and isinstance(stmt.target, ast.Name):
                    hit = _s03_nondet_call(stmt.value)
                    record(stmt.target.id, hit if hit else (None, stmt.lineno))
            elif isinstance(stmt, ast.AugAssign):
                if isinstance(stmt.target, ast.Name):
                    record(stmt.target.id, (None, stmt.lineno))
            for body in _get_compound_bodies(stmt):
                scan(body)

    scan(stmts)
    return result


def _raw_nondet_in_lambda(node: ast.Lambda) -> tuple[str, int] | None:
    """
    Return (call_name, line) if the lambda body IS a raw nondet SDK call, else None.

    Conservative: only flags when the entire body is the nondet call itself,
    not when it is wrapped in any comparison, boolean operation, or other expression.
    Lambdas cannot contain await, so no await-unwrapping is needed here.
    """
    if isinstance(node.body, ast.Call):
        name = _full_call_name(node.body)
        if name in _S03_NONDET_CALLS:
            return name, node.body.lineno
    return None


def _raw_nondet_in_func(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    func_defs: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    _depth: int = 0,
) -> tuple[str, int] | None:
    """
    Return (call_name, nondet_line) if the function returns raw nondeterministic output.

    Conservative — only flags:
    - return nondet_call(...)
    - var = nondet_call(...); return var   (only if var is exclusively nondet-assigned)
    - return module_fn()                  (one level deep only — module-level functions)

    When in doubt, returns None.
    """
    var_assigns = _collect_var_assigns(func_node.body)

    for ret in _iter_func_returns(func_node.body):
        if ret.value is None:
            continue

        # Direct return of a nondet call (including await)
        hit = _s03_nondet_call(ret.value)
        if hit:
            return hit

        val: ast.expr = ret.value.value if isinstance(ret.value, ast.Await) else ret.value

        # Return of a variable that was exclusively assigned from nondet calls
        if isinstance(val, ast.Name):
            assigns = var_assigns.get(val.id, [])
            if assigns and all(name is not None for name, _ in assigns):
                first_name, nondet_line = assigns[0]
                if first_name is not None:
                    return first_name, nondet_line

        # One-level transitive: return module_fn()
        if (
            _depth == 0
            and isinstance(val, ast.Call)
            and isinstance(val.func, ast.Name)
            and val.func.id in func_defs
        ):
            return _raw_nondet_in_func(func_defs[val.func.id], func_defs, _depth=1)

    return None


def check_eq_strict_mismatch(source: str) -> list[SafetyWarning]:
    """
    GL-S03: Flag eq_principle_strict_eq wrapping a lambda or function that returns
    raw nondeterministic output.

    Conservative — only flags direct returns of nondet calls or simple passthroughs.
    When in doubt (processed output, unknown functions, multi-file), does not flag.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    # Index module-level function definitions only — class methods must not collide
    func_defs: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_defs[node.name] = node

    # Index top-level class methods for self.method resolution
    class_methods: dict[str, dict[str, ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods[item.name] = item
            class_methods[node.name] = methods

    warnings: list[SafetyWarning] = []

    def _emit(line: int, col: int, result: tuple[str, int]) -> None:
        call_name, nondet_line = result
        warnings.append(SafetyWarning(
            code="GL-S03",
            msg=_GL_S03_MSG.format(
                line=line,
                call_name=call_name,
                nondet_line=nondet_line,
            ),
            line=line,
            col=col,
        ))

    def _resolve_arg(
        fn_arg: ast.expr,
        current_class: str | None,
    ) -> tuple[str, int] | None:
        if isinstance(fn_arg, ast.Lambda):
            return _raw_nondet_in_lambda(fn_arg)
        if isinstance(fn_arg, ast.Name) and fn_arg.id in func_defs:
            return _raw_nondet_in_func(func_defs[fn_arg.id], func_defs)
        if (
            isinstance(fn_arg, ast.Attribute)
            and isinstance(fn_arg.value, ast.Name)
            and fn_arg.value.id == "self"
            and current_class is not None
        ):
            method_node = class_methods.get(current_class, {}).get(fn_arg.attr)
            if method_node is not None:
                return _raw_nondet_in_func(method_node, func_defs)
        return None

    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.current_class: str | None = None

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            old = self.current_class
            self.current_class = node.name
            self.generic_visit(node)
            self.current_class = old

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._check_decorators(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._check_decorators(node)
            self.generic_visit(node)

        def _check_decorators(
            self, node: ast.FunctionDef | ast.AsyncFunctionDef
        ) -> None:
            for dec in node.decorator_list:
                if _decorator_name(dec) in _STRICT_EQ_CALLS:
                    result = _raw_nondet_in_func(node, func_defs)
                    if result is not None:
                        _emit(dec.lineno, dec.col_offset, result)

        def visit_Call(self, node: ast.Call) -> None:
            if _full_call_name(node) in _STRICT_EQ_CALLS and node.args:
                result = _resolve_arg(node.args[0], self.current_class)
                if result is not None:
                    _emit(node.lineno, node.col_offset, result)
            self.generic_visit(node)

    _Visitor().visit(tree)
    return warnings
