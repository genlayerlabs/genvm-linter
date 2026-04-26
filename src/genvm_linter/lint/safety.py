"""AST-based safety checks for forbidden imports and non-deterministic patterns."""

import ast
import re
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

    # Semantic prompt and eq_principle quality checks
    semantic_warnings = (
        check_vague_prompts(source)
        + check_weak_eq_criteria(source)
        + check_eq_strict_mismatch(source)
    )

    return checker.warnings + nondet_warnings + forbidden_warnings + semantic_warnings


# ---------------------------------------------------------------------------
# Shared helpers for semantic rules (GL-S01, GL-S02, GL-S03)
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


def _extract_str(node: ast.expr) -> str | None:
    """Extract text from a string Constant or an f-string JoinedStr."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for part in node.values:
            if isinstance(part, ast.Constant):
                parts.append(str(part.value))
            else:
                parts.append("{expr}")
        return "".join(parts)
    return None


def _is_exec_prompt(node: ast.Call) -> bool:
    name = _full_call_name(node)
    return name == "exec_prompt" or name.endswith(".exec_prompt")


# ---------------------------------------------------------------------------
# GL-S01: Vague prompt language
# ---------------------------------------------------------------------------

AMBIGUITY_MARKERS = [
    "fair", "unfair", "reasonable", "appropriate", "good", "bad",
    "acceptable", "deserves", "worthy", "suitable", "assess",
    "evaluate", "determine if", "decide if", "judge whether",
]

_CRITERIA_SIGNALS = frozenset({
    "if ", "when ", "≤", "≥", ">", "<",
    "return yes/no", "yes/no", "return yes", "return no",
})


def _has_criteria_language(text: str) -> bool:
    lower = text.lower()
    return any(s in lower for s in _CRITERIA_SIGNALS)


def _response_format_value(node: ast.Call) -> str | None:
    """Return response_format kwarg value, '__other__' if not a str literal, or None if absent."""
    for kw in node.keywords:
        if kw.arg == "response_format":
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                return kw.value.value
            return "__other__"
    return None


def _check_response_format_in_func(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[SafetyWarning]:
    """Best-effort: flag exec_prompt with absent/text response_format used in conditions."""
    # Collect assignments: var = exec_prompt(...)
    prompt_assignments: dict[str, tuple[ast.Call, int, int]] = {}
    for node in ast.walk(func_node):
        if isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
                and _is_exec_prompt(node.value)
            ):
                var = node.targets[0].id
                prompt_assignments[var] = (node.value, node.value.lineno, node.value.col_offset)
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.value
                and isinstance(node.value, ast.Call)
                and _is_exec_prompt(node.value)
            ):
                var = node.target.id
                prompt_assignments[var] = (node.value, node.value.lineno, node.value.col_offset)

    if not prompt_assignments:
        return []

    # Collect variables referenced inside conditional tests
    conditional_vars: set[str] = set()
    for node in ast.walk(func_node):
        test: ast.expr | None = None
        if isinstance(node, (ast.If, ast.While)):
            test = node.test
        elif isinstance(node, ast.IfExp):
            test = node.test
        if test is not None:
            for n in ast.walk(test):
                if isinstance(n, ast.Name):
                    conditional_vars.add(n.id)

    warnings: list[SafetyWarning] = []
    for var in conditional_vars:
        if var not in prompt_assignments:
            continue
        call_node, line, col = prompt_assignments[var]
        rf = _response_format_value(call_node)
        if rf is None or rf == "text":
            warnings.append(
                SafetyWarning(
                    code="GL-S01",
                    msg=(
                        f"exec_prompt on line {line} feeds into conditional logic "
                        f"but has no structured response_format. "
                        f"Add response_format=bool or a Pydantic model."
                    ),
                    line=line,
                    col=col,
                )
            )
    return warnings


def check_vague_prompts(source: str) -> list[SafetyWarning]:
    """Check for vague language in exec_prompt calls (GL-S01)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    warnings: list[SafetyWarning] = []

    # Check all exec_prompt calls for ambiguity markers
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_exec_prompt(node):
            continue
        if not node.args:
            continue
        prompt_str = _extract_str(node.args[0])
        if prompt_str is None:
            continue
        lower = prompt_str.lower()
        if any(m in lower for m in AMBIGUITY_MARKERS) and not _has_criteria_language(prompt_str):
            warnings.append(
                SafetyWarning(
                    code="GL-S01",
                    msg=(
                        f"Vague prompt on line {node.lineno}: prompt contains ambiguous terms "
                        f"without explicit criteria. Add specific conditions "
                        f"(e.g., 'return YES/NO if X', numeric thresholds, rubric)."
                    ),
                    line=node.lineno,
                    col=node.col_offset,
                )
            )

    # Per-function: flag missing structured response_format when result is in conditions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            warnings.extend(_check_response_format_in_func(node))

    return warnings


# ---------------------------------------------------------------------------
# GL-S02: Weak eq_principle criteria
# ---------------------------------------------------------------------------

_WEAK_ADJECTIVES = frozenset({
    "similar", "equivalent", "same", "match", "matching", "equal", "like",
})
_NUMERIC_RE = re.compile(r"\d+|[≤≥%]|\bpercent\b|\bgreater\b|\bless\b|\bat least\b|\bat most\b")
_CONDITIONAL_WORDS = frozenset({
    "if", "when", "unless", "until", "condition", "yes", "no",
})
_CATEGORY_RE = re.compile(r"\b(one of|any of|among|either)\b|,", re.IGNORECASE)

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "be", "to", "of", "in", "it",
    "that", "for", "and", "or", "with", "by", "on", "at",
})


def _score_criteria_weakness(text: str) -> tuple[str, str] | None:
    """Return (level, reason) where level is 'HIGH' or 'MEDIUM', or None if acceptable."""
    words = [w.strip(".,!?:;\"'") for w in text.split() if w.strip(".,!?:;\"'")]
    word_count = len(words)

    if word_count < 10:
        plural = "s" if word_count != 1 else ""
        return ("HIGH", f"criteria is too short ({word_count} word{plural})")

    lower_words = {w.lower() for w in words}
    meaningful = lower_words - _STOP_WORDS
    if meaningful and meaningful.issubset(_WEAK_ADJECTIVES):
        return ("HIGH", "criteria contains only vague comparative terms without bounds")

    has_numeric = bool(_NUMERIC_RE.search(text))
    has_conditional = bool(lower_words & _CONDITIONAL_WORDS)
    has_categories = bool(_CATEGORY_RE.search(text))

    if not has_numeric and not has_conditional and not has_categories:
        return ("MEDIUM", "no numeric bounds, category lists, or conditional logic")

    return None


def _kwarg_str(node: ast.Call, name: str) -> str | None:
    for kw in node.keywords:
        if kw.arg == name:
            return _extract_str(kw.value)
    return None


def check_weak_eq_criteria(source: str) -> list[SafetyWarning]:
    """Check for weak criteria/principle strings in eq_principle calls (GL-S02)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    warnings: list[SafetyWarning] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _full_call_name(node)

        if name in ("eq_principle_prompt_comparative", "gl.eq_principle.prompt_comparative"):
            criteria_str = _kwarg_str(node, "principle")
        elif name in (
            "eq_principle_prompt_non_comparative",
            "gl.eq_principle.prompt_non_comparative",
        ):
            criteria_str = _kwarg_str(node, "criteria")
        else:
            continue

        if criteria_str is None:
            continue

        result = _score_criteria_weakness(criteria_str)
        if result is None:
            continue

        level, reason = result
        snippet = criteria_str[:60] + "..." if len(criteria_str) > 60 else criteria_str
        severity_tag = "[HIGH RISK] " if level == "HIGH" else "[MEDIUM RISK] "
        warnings.append(
            SafetyWarning(
                code="GL-S02",
                msg=(
                    f"{severity_tag}Weak eq_principle on line {node.lineno}: "
                    f"criteria '{snippet}' does not define acceptance bounds "
                    f"({reason}). Specify numeric ranges, categories, or explicit "
                    f"YES/NO conditions."
                ),
                line=node.lineno,
                col=node.col_offset,
            )
        )

    return warnings


# ---------------------------------------------------------------------------
# GL-S03: eq_principle_strict_eq type mismatch
# ---------------------------------------------------------------------------

_GL_S03_MSG = (
    "eq_principle_strict_eq on line {line} wraps a function with non-deterministic output "
    "(LLM call or raw web fetch). Strict equality will fail across validators. "
    "Use eq_principle_prompt_comparative or eq_principle_prompt_non_comparative."
)


def _contains_exec_prompt(node: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Call) and _is_exec_prompt(n)
        for n in ast.walk(node)
    )


def _contains_get_webpage(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            call_name = _full_call_name(n)
            if call_name in ("get_webpage", "gl.get_webpage") or call_name.endswith(".get_webpage"):
                return True
    return False


def check_eq_strict_mismatch(source: str) -> list[SafetyWarning]:
    """Check for non-deterministic functions wrapped in eq_principle_strict_eq (GL-S03)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    # Index all named function definitions for lookup by bare name
    func_defs: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_defs[node.name] = node

    warnings: list[SafetyWarning] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _full_call_name(node)
        if name not in ("eq_principle_strict_eq", "gl.eq_principle.strict_eq"):
            continue
        if not node.args:
            continue

        fn_arg = node.args[0]
        target: ast.AST | None = None

        if isinstance(fn_arg, ast.Lambda):
            target = fn_arg.body
        elif isinstance(fn_arg, ast.Name) and fn_arg.id in func_defs:
            target = func_defs[fn_arg.id]

        if target is None:
            continue

        if _contains_exec_prompt(target) or _contains_get_webpage(target):
            warnings.append(
                SafetyWarning(
                    code="GL-S03",
                    msg=_GL_S03_MSG.format(line=node.lineno),
                    line=node.lineno,
                    col=node.col_offset,
                )
            )

    return warnings
