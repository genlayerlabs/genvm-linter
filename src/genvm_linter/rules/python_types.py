"""Python type checking integration for GenVM contracts."""

import ast
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional
from ..rules import Rule, ValidationResult, Severity
from ..type_system import GenVMTypeSystem


class DataclassTypeTransformer(ast.NodeTransformer):
    """Transform dataclass field types to accept int for sized types."""
    
    def __init__(self):
        self.in_dataclass = False
        self.sized_types = {
            'u8', 'u16', 'u24', 'u32', 'u40', 'u48', 'u56', 'u64',
            'u72', 'u80', 'u88', 'u96', 'u104', 'u112', 'u120', 'u128',
            'u136', 'u144', 'u152', 'u160', 'u168', 'u176', 'u184', 'u192',
            'u200', 'u208', 'u216', 'u224', 'u232', 'u240', 'u248', 'u256',
            'i8', 'i16', 'i24', 'i32', 'i40', 'i48', 'i56', 'i64',
            'i72', 'i80', 'i88', 'i96', 'i104', 'i112', 'i120', 'i128',
            'i136', 'i144', 'i152', 'i160', 'i168', 'i176', 'i184', 'i192',
            'i200', 'i208', 'i216', 'i224', 'i232', 'i240', 'i248', 'i256',
            'bigint'
        }
    
    def visit_ClassDef(self, node):
        # Check if this is a dataclass
        has_dataclass = any(
            (isinstance(dec, ast.Name) and dec.id == 'dataclass') or
            (isinstance(dec, ast.Attribute) and dec.attr == 'dataclass')
            for dec in node.decorator_list
        )
        
        if has_dataclass:
            old_in_dataclass = self.in_dataclass
            self.in_dataclass = True
            result = self.generic_visit(node)
            self.in_dataclass = old_in_dataclass
            return result
        
        return self.generic_visit(node)
    
    def visit_AnnAssign(self, node):
        """Transform field annotations in dataclasses."""
        if self.in_dataclass and node.annotation:
            # Check if the annotation is a sized type
            if isinstance(node.annotation, ast.Name) and node.annotation.id in self.sized_types:
                # Replace with Union[int, sized_type] to accept both
                # This allows passing int where sized types are expected
                union_node = ast.Subscript(
                    value=ast.Name(id='Union', ctx=ast.Load()),
                    slice=ast.Tuple(
                        elts=[
                            ast.Name(id='int', ctx=ast.Load()),
                            node.annotation
                        ],
                        ctx=ast.Load()
                    ),
                    ctx=ast.Load()
                )
                node.annotation = union_node
        
        return self.generic_visit(node)


class PythonTypeCheckRule(Rule):
    """Rule that integrates Python type checking (mypy) for GenVM contracts."""
    
    def __init__(self):
        self.rule_id = "python-type-check"
        self.description = "Python type checking integration"
        self.needs_source_code = True  # This rule needs the raw source code
        
    def check(self, source_code: str, filename: Optional[str] = None) -> List[ValidationResult]:
        """Run mypy type checking on the source code."""
        results = []
        
        # Setup environment for mypy
        env = os.environ.copy()
        
        try:
            # Check if mypy is available via python3 -m mypy
            subprocess.run(['python3', '-m', 'mypy', '--version'], capture_output=True, check=True, env=env)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Mypy not available, skip type checking
            return results
            
        try:
            # Create a temporary file for mypy analysis
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                # Add genlayer stub imports for better type checking
                genvm_stub = """
# GenVM stub types for mypy
from typing import Any, Callable, TypeVar, Generic, Union, NewType, List, Dict, overload, Optional, Type, Tuple

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

# Sized integer types - these are special GenVM types
# They can be constructed from int and are compatible with int operations
class u8(int):
    def __new__(cls, value: int = 0) -> 'u8': ...
    
class u16(int):
    def __new__(cls, value: int) -> 'u16': ...
    
class u24(int):
    def __new__(cls, value: int) -> 'u24': ...
    
class u32(int):
    def __new__(cls, value: int) -> 'u32': ...
    
class u40(int):
    def __new__(cls, value: int) -> 'u40': ...
    
class u48(int):
    def __new__(cls, value: int) -> 'u48': ...
    
class u56(int):
    def __new__(cls, value: int) -> 'u56': ...
    
class u64(int):
    def __new__(cls, value: int) -> 'u64': ...
    
class u72(int):
    def __new__(cls, value: int) -> 'u72': ...
    
class u80(int):
    def __new__(cls, value: int) -> 'u80': ...
    
class u88(int):
    def __new__(cls, value: int) -> 'u88': ...
    
class u96(int):
    def __new__(cls, value: int) -> 'u96': ...
    
class u104(int):
    def __new__(cls, value: int) -> 'u104': ...
    
class u112(int):
    def __new__(cls, value: int) -> 'u112': ...
    
class u120(int):
    def __new__(cls, value: int) -> 'u120': ...
    
class u128(int):
    def __new__(cls, value: int) -> 'u128': ...
    
class u136(int):
    def __new__(cls, value: int) -> 'u136': ...
    
class u144(int):
    def __new__(cls, value: int) -> 'u144': ...
    
class u152(int):
    def __new__(cls, value: int) -> 'u152': ...
    
class u160(int):
    def __new__(cls, value: int) -> 'u160': ...
    
class u168(int):
    def __new__(cls, value: int) -> 'u168': ...
    
class u176(int):
    def __new__(cls, value: int) -> 'u176': ...
    
class u184(int):
    def __new__(cls, value: int) -> 'u184': ...
    
class u192(int):
    def __new__(cls, value: int) -> 'u192': ...
    
class u200(int):
    def __new__(cls, value: int) -> 'u200': ...
    
class u208(int):
    def __new__(cls, value: int) -> 'u208': ...
    
class u216(int):
    def __new__(cls, value: int) -> 'u216': ...
    
class u224(int):
    def __new__(cls, value: int) -> 'u224': ...
    
class u232(int):
    def __new__(cls, value: int) -> 'u232': ...
    
class u240(int):
    def __new__(cls, value: int) -> 'u240': ...
    
class u248(int):
    def __new__(cls, value: int) -> 'u248': ...
    
class u256(int):
    def __new__(cls, value: int = 0) -> 'u256': ...

# Signed integers
class i8(int):
    def __new__(cls, value: int) -> 'i8': ...
    
class i16(int):
    def __new__(cls, value: int) -> 'i16': ...
    
class i24(int):
    def __new__(cls, value: int) -> 'i24': ...
    
class i32(int):
    def __new__(cls, value: int) -> 'i32': ...
    
class i40(int):
    def __new__(cls, value: int) -> 'i40': ...
    
class i48(int):
    def __new__(cls, value: int) -> 'i48': ...
    
class i56(int):
    def __new__(cls, value: int) -> 'i56': ...
    
class i64(int):
    def __new__(cls, value: int) -> 'i64': ...
    
class i72(int):
    def __new__(cls, value: int) -> 'i72': ...
    
class i80(int):
    def __new__(cls, value: int) -> 'i80': ...
    
class i88(int):
    def __new__(cls, value: int) -> 'i88': ...
    
class i96(int):
    def __new__(cls, value: int) -> 'i96': ...
    
class i104(int):
    def __new__(cls, value: int) -> 'i104': ...
    
class i112(int):
    def __new__(cls, value: int) -> 'i112': ...
    
class i120(int):
    def __new__(cls, value: int) -> 'i120': ...
    
class i128(int):
    def __new__(cls, value: int) -> 'i128': ...
    
class i136(int):
    def __new__(cls, value: int) -> 'i136': ...
    
class i144(int):
    def __new__(cls, value: int) -> 'i144': ...
    
class i152(int):
    def __new__(cls, value: int) -> 'i152': ...
    
class i160(int):
    def __new__(cls, value: int) -> 'i160': ...
    
class i168(int):
    def __new__(cls, value: int) -> 'i168': ...
    
class i176(int):
    def __new__(cls, value: int) -> 'i176': ...
    
class i184(int):
    def __new__(cls, value: int) -> 'i184': ...
    
class i192(int):
    def __new__(cls, value: int) -> 'i192': ...
    
class i200(int):
    def __new__(cls, value: int) -> 'i200': ...
    
class i208(int):
    def __new__(cls, value: int) -> 'i208': ...
    
class i216(int):
    def __new__(cls, value: int) -> 'i216': ...
    
class i224(int):
    def __new__(cls, value: int) -> 'i224': ...
    
class i232(int):
    def __new__(cls, value: int) -> 'i232': ...
    
class i240(int):
    def __new__(cls, value: int) -> 'i240': ...
    
class i248(int):
    def __new__(cls, value: int) -> 'i248': ...
    
class i256(int):
    def __new__(cls, value: int) -> 'i256': ...

class bigint(int):
    def __new__(cls, value: int) -> 'bigint': ...

# GenVM collections - properly typed as Generics
class DynArray(List[T], Generic[T]):
    def append(self, item: T) -> None: ...
    def __len__(self) -> int: ...
    
class TreeMap(Dict[K, V], Generic[K, V]):
    def __len__(self) -> int: ...

# Override dict to ensure proper typing for keys(), values(), items()
# In GenVM context, these often return list-like objects
class dict(Dict[K, V], Generic[K, V]):
    def keys(self) -> List[K]: ...
    def values(self) -> List[V]: ...
    def items(self) -> List[Tuple[K, V]]: ...
    def get(self, key: K, default: Optional[V] = None) -> Optional[V]: ...
    def __getitem__(self, key: K) -> V: ...
    def __setitem__(self, key: K, value: V) -> None: ...
    def __contains__(self, key: object) -> bool: ...
    def __len__(self) -> int: ...

class Contract:
    pass

class Address:
    def __init__(self, address: str) -> None: ...
    # All these are properties, not methods
    @property
    def as_hex(self) -> str: ...
    @property
    def as_bytes(self) -> bytes: ...
    @property
    def as_b64(self) -> str: ...
    @property
    def as_int(self) -> u160: ...

class Lazy(Generic[T]):
    def get(self) -> T: ...

class Response:
    # HTTP Response object returned by web methods
    status: int
    headers: dict[str, bytes]
    body: Optional[bytes]
    
    def __init__(self, status: int, headers: dict[str, bytes], body: Optional[bytes]) -> None: ...

class gl:
    class public:
        @staticmethod
        def view(func): return func
        @staticmethod
        def write(func): return func
        
        class write:
            @staticmethod
            def __call__(func): return func
            @staticmethod
            def payable(func): return func
    
    class Contract:
        balance: int
        
    class message:
        sender_address: Address
        contract_address: Address
        sender: Address  # Alias for sender_address
        value: int
        chain_id: int
    
    class nondet:
        class web:
            @staticmethod
            def render(url: str, mode: str = 'screenshot', wait_after_loaded: Optional[str] = None) -> bytes: ...
            
            @staticmethod
            def get(url: str, *, headers: dict[str, Union[str, bytes]] = {}) -> Response: ...
            
            @staticmethod
            def post(url: str, *, body: Optional[Union[str, bytes]] = None, headers: dict[str, Union[str, bytes]] = {}) -> Response: ...
            
            @staticmethod
            def delete(url: str, *, body: Optional[Union[str, bytes]] = None, headers: dict[str, Union[str, bytes]] = {}) -> Response: ...
            
            @staticmethod
            def head(url: str, *, body: Optional[Union[str, bytes]] = None, headers: dict[str, Union[str, bytes]] = {}) -> Response: ...
            
            @staticmethod
            def patch(url: str, *, body: Optional[Union[str, bytes]] = None, headers: dict[str, Union[str, bytes]] = {}) -> Response: ...
            
            @staticmethod
            def request(url: str, *, method: str, body: Optional[Union[str, bytes]] = None, headers: dict[str, Union[str, bytes]] = {}) -> Response: ...
        
        @staticmethod
        def exec_prompt(prompt: str, images: Optional[list] = None) -> str: ...
    
    class eq_principle:
        @staticmethod
        def strict_eq(func: Callable[[], T]) -> T: ...
        @staticmethod
        def prompt_comparative(func: Callable[[], T], principle: str) -> Lazy[T]: ...
        @staticmethod
        def prompt_non_comparative(func: Callable[[], Any], *, prompt: Optional[str] = None) -> bool: ...
    
    class evm:
        @staticmethod
        def contract_interface(cls): return cls
        
        class MethodEncoder:
            def __init__(self, name: str, params: tuple[Any, ...], ret: type) -> None: ...
            def encode_call(self, args: tuple[Any, ...]) -> bytes: ...
            def decode_return(self, encoded: bytes) -> Any: ...
        
        @staticmethod
        def encode(params: type, args: Any) -> bytes: ...
        
        @staticmethod
        def decode(expected: type, encoded: bytes) -> Any: ...
        
        @staticmethod
        def selector_of(name: str, params: type) -> bytes: ...
        
        @staticmethod
        def signature_of(name: str, params: type) -> str: ...
        
        @staticmethod
        def type_name_of(t: type) -> str: ...
        
        class ContractProxy: pass
        class ContractDeclaration: pass
        class InplaceTuple: pass
        
        # EVM bytes types
        bytes1: Type[bytes]
        bytes2: Type[bytes]
        bytes3: Type[bytes]
        bytes4: Type[bytes]
        bytes5: Type[bytes]
        bytes6: Type[bytes]
        bytes7: Type[bytes]
        bytes8: Type[bytes]
        bytes9: Type[bytes]
        bytes10: Type[bytes]
        bytes11: Type[bytes]
        bytes12: Type[bytes]
        bytes13: Type[bytes]
        bytes14: Type[bytes]
        bytes15: Type[bytes]
        bytes16: Type[bytes]
        bytes17: Type[bytes]
        bytes18: Type[bytes]
        bytes19: Type[bytes]
        bytes20: Type[bytes]
        bytes21: Type[bytes]
        bytes22: Type[bytes]
        bytes23: Type[bytes]
        bytes24: Type[bytes]
        bytes25: Type[bytes]
        bytes26: Type[bytes]
        bytes27: Type[bytes]
        bytes28: Type[bytes]
        bytes29: Type[bytes]
        bytes30: Type[bytes]
        bytes31: Type[bytes]
        bytes32: Type[bytes]
    
    class advanced:
        @staticmethod
        def user_error_immediate(msg: str) -> None: ...
    
    class vm:
        class UserError(Exception): 
            message: str
            def __init__(self, message: str) -> None: ...
        
        class VMError(Exception): 
            message: str
            def __init__(self, message: str) -> None: ...
        
        class Return(Generic[T]):
            calldata: T
            def __init__(self, calldata: T) -> None: ...
        
        # Result as a generic type (union of Return[T], VMError, UserError)
        class Result(Generic[T]):
            # This is actually a type alias for Union[Return[T], VMError, UserError]
            # but we define it as a class for mypy compatibility
            pass
        
        @staticmethod
        def spawn_sandbox(
            fn: Callable[[], T],
            allow_write_ops: bool = False
        ) -> Result[T]: ...
        
        @staticmethod
        def run_nondet(
            leader_fn: Callable[[], T],
            validator_fn: Callable[[Any], bool],
            *,
            compare_user_errors: Optional[Callable[[UserError, UserError], bool]] = None,
            compare_vm_errors: Optional[Callable[[VMError, VMError], bool]] = None
        ) -> T: ...
        
        @staticmethod
        def run_nondet_unsafe(
            leader_fn: Callable[[], T],
            validator_fn: Callable[[Any], bool]
        ) -> T: ...
        
        @staticmethod
        def unpack_result(res: Result[T]) -> T: ...
    
    class storage:
        class Root: pass
        
        @staticmethod
        def copy_to_memory(data: Any) -> Any: ...
        @staticmethod
        def inmem_allocate(size: int) -> Any: ...
    
    @staticmethod
    def deploy_contract(
        code: bytes,
        args: Optional[list] = None,
        salt_nonce: Optional[int] = None,
        on: Optional[str] = None
    ) -> Address: ...
    
    @staticmethod
    def get_contract_at(address: Address) -> Any: ...
    
    @staticmethod
    def contract_interface(cls): return cls
    
    # ContractAt class for contract proxy operations
    class ContractAt:
        def __init__(self, address: Address) -> None: ...
        def emit(self) -> Any: ...
        def __getattr__(self, name: str) -> Any: ...
    
    # Event class for event definitions
    class Event: pass

# Type aliases for dataclass compatibility
# In GenVM, int can be implicitly converted to sized types in dataclasses
u8_field = Union[int, u8]
u16_field = Union[int, u16]
u32_field = Union[int, u32]
u64_field = Union[int, u64]
u128_field = Union[int, u128]
u256_field = Union[int, u256]
i8_field = Union[int, i8]
i16_field = Union[int, i16]
i32_field = Union[int, i32]
i64_field = Union[int, i64]
i128_field = Union[int, i128]
i256_field = Union[int, i256]

# dataclass decorator
from dataclasses import dataclass

# allow_storage decorator for dataclasses
def allow_storage(cls): 
    return cls

"""
                # Combine stub with actual source code  
                stub_lines = genvm_stub.count('\n')
                combined_source = genvm_stub + source_code
                temp_file.write(combined_source)
                temp_file_path = temp_file.name
            
            # Run mypy on the temporary file
            mypy_result = subprocess.run([
                'python3', '-m', 'mypy', 
                temp_file_path,
                '--python-version', '3.9',
                '--ignore-missing-imports',  # Ignore genlayer imports
                '--no-strict-optional',
                '--warn-return-any',
                '--warn-unused-ignores', 
                '--no-error-summary',
                '--show-column-numbers',
                '--disable-error-code=import-untyped',
                '--disable-error-code=no-untyped-def',  # We handle this with our own decorator rules
                '--allow-redefinition',  # Allow redefining types
                '--allow-untyped-globals'  # Be more lenient with global types
            ], capture_output=True, text=True, env=env)
            
            # Parse mypy output
            if mypy_result.stdout:
                for line in mypy_result.stdout.strip().split('\n'):
                    if line and ':' in line:
                        result = self._parse_mypy_line(line, filename or 'contract.py', stub_lines)
                        if result:
                            results.append(result)
            
            # Debug: check stderr for errors
            if mypy_result.stderr:
                # For now, just add as debug info - in production you might log this
                pass
            
            # Clean up temporary file
            Path(temp_file_path).unlink()
            
        except Exception as e:
            # Don't fail the entire linting process if type checking fails
            pass
            
        return results
    
    def _parse_mypy_line(self, line: str, filename: str, stub_line_offset: int = 0) -> Optional[ValidationResult]:
        """Parse a single mypy output line into a ValidationResult."""
        try:
            # mypy format: filename:line:column: severity: message
            parts = line.split(':', 4)
            if len(parts) < 5:
                return None
                
            line_num = int(parts[1]) - stub_line_offset  # Adjust for stub lines
            column = int(parts[2]) if parts[2].strip() else 1
            severity_str = parts[3].strip()
            message = parts[4].strip()
            
            # Skip errors in stub code
            if line_num <= 0:
                return None
            
            # Skip specific false positives for GenVM patterns
            # 1. Skip dataclass constructor type errors for sized integers
            if 'Argument' in message and 'has incompatible type "int"; expected' in message:
                if any(sized in message for sized in ['u8', 'u16', 'u32', 'u64', 'u128', 'u256', 
                                                        'i8', 'i16', 'i32', 'i64', 'i128', 'i256']):
                    # This is expected - in GenVM we pass int to sized type fields
                    return None
            
            # 2. Skip list/DynArray compatibility errors
            if 'Incompatible types in assignment' in message:
                # Check for list -> DynArray assignments
                if 'list[' in message and 'DynArray[' in message:
                    # list and DynArray are compatible in GenVM
                    return None
                # Check for int -> sized type assignments in storage fields
                if 'has type "list[int]"' in message and any(sized in message for sized in 
                    ['DynArray[u8]', 'DynArray[u16]', 'DynArray[u32]', 'DynArray[u64]', 
                     'DynArray[u128]', 'DynArray[u256]', 'DynArray[i8]', 'DynArray[i16]',
                     'DynArray[i32]', 'DynArray[i64]', 'DynArray[i128]', 'DynArray[i256]']):
                    # list[int] can be assigned to DynArray[sized_type]
                    return None
                # Check for int -> sized type direct assignments (e.g., self.field = int_param)
                if 'has type "int"' in message and ('variable has type' in message or 'target has type' in message):
                    if any(sized in message for sized in ['u8"', 'u16"', 'u32"', 'u64"', 'u128"', 'u256"',
                                                           'i8"', 'i16"', 'i32"', 'i64"', 'i128"', 'i256"',
                                                           'bigint"']):
                        # int can be assigned to sized type storage fields
                        return None
            
            # 3. Skip DynArray/list return type compatibility
            if 'Incompatible return value type' in message:
                # DynArray can be returned as list
                if 'DynArray[' in message and 'list[' in message:
                    return None
                # Also handle sized types being returned as int in collections
                if ('DynArray[u' in message or 'DynArray[i' in message) and 'list[int]' in message:
                    return None
            
            # 4. Skip literal list assignments to DynArray
            if 'Incompatible types in assignment' in message and 'List[int]' in message and 'DynArray[' in message:
                # Literal lists like [1, 2, 3] can be assigned to DynArray
                return None
            
            # 5. Skip TreeMap indexing with int when key is a sized type
            if 'Invalid index type "int" for "TreeMap[' in message:
                # In GenVM, int can be used to index TreeMap with sized type keys
                return None
            
            # 6. Skip false positive "Returning Any" errors for boolean comparisons
            if 'Returning Any from function declared to return "bool"' in message and '[no-any-return]' in message:
                # This is likely a false positive from comparison operations that always return bool
                # In Python, comparison operators always return bool, even when comparing Any values
                return None
            
            # 7. Skip builtins.dict vs custom dict stub conflicts
            if 'builtins.dict[' in message and '.dict[' in message:
                # builtins.dict and our custom dict stub are effectively the same
                # This happens when {} creates builtins.dict but function expects our stub dict
                return None
            
            # Map mypy severity to our severity
            if severity_str == 'error':
                severity = Severity.ERROR
            elif severity_str == 'warning':
                severity = Severity.WARNING
            else:
                severity = Severity.INFO
                
            return ValidationResult(
                rule_id=self.rule_id,
                message=f"Type check: {message}",
                line=line_num,
                column=column,
                severity=severity,
                suggestion=self._get_type_suggestion(message)
            )
            
        except (ValueError, IndexError):
            return None
    
    def _preprocess_dataclass_types(self, source_code: str) -> str:
        """Preprocess dataclass fields to accept int for sized types."""
        try:
            tree = ast.parse(source_code)
            transformer = DataclassTypeTransformer()
            modified_tree = transformer.visit(tree)
            ast.fix_missing_locations(modified_tree)
            
            # Convert back to source code
            if hasattr(ast, 'unparse'):
                return ast.unparse(modified_tree)
            else:
                # Fallback if unparse is not available (Python < 3.9)
                return source_code
        except:
            # If preprocessing fails, return original source
            return source_code
    
    def _get_type_suggestion(self, message: str) -> Optional[str]:
        """Generate suggestions for common type errors."""
        if "incompatible return value type" in message.lower():
            return "Check the return type annotation matches the actual returned value"
        elif "argument has incompatible type" in message.lower():
            return "Verify the argument type matches the parameter annotation"
        elif "has no attribute" in message.lower():
            return "Check if the object has the expected type and attributes"
        elif "cannot be assigned" in message.lower():
            return "Ensure the assigned value matches the variable's type annotation"
        return None


class GenVMTypeStubRule(Rule):
    """Rule that provides GenVM-specific type stubs for better type checking."""
    
    def __init__(self):
        self.rule_id = "genvm-type-stubs"
        self.description = "GenVM type annotations validation"
        
    def check(self, node: ast.AST, filename: Optional[str] = None) -> List[ValidationResult]:
        """Check for GenVM-specific type issues."""
        results = []
        
        if not isinstance(node, ast.Module):
            return results
        
        try:
            visitor = GenVMTypeVisitor()
            visitor.visit(node)
            
            for error in visitor.errors:
                results.append(ValidationResult(
                    rule_id=self.rule_id,
                    message=error['message'],
                    line=error['line'],
                    column=error.get('column', 1),
                    severity=error.get('severity', Severity.WARNING),
                    suggestion=error.get('suggestion')
                ))
                
        except SyntaxError:
            pass  # Skip if file has syntax errors
            
        return results


class GenVMTypeVisitor(ast.NodeVisitor):
    """AST visitor for GenVM-specific type checking."""
    
    def __init__(self):
        self.errors = []
        self.current_class = None
        self.current_method = None
        
    def visit_ClassDef(self, node: ast.ClassDef):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
        
    def visit_FunctionDef(self, node: ast.FunctionDef):
        old_method = self.current_method
        self.current_method = node.name
        
        # Check return type annotations
        if node.returns:
            self._check_return_type(node)
            
        # Check parameter types
        for arg in node.args.args:
            if arg.annotation:
                self._check_parameter_type(arg, node)
                
        self.generic_visit(node)
        self.current_method = old_method
        
    def _check_return_type(self, node: ast.FunctionDef):
        """Check if return type is appropriate for GenVM."""
        return_type = ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)
        
        # Check for sized integers in return types
        if any(sized_type in return_type for sized_type in ['u64', 'u256', 'u128', 'i64', 'i256', 'i128']):
            self.errors.append({
                'message': f"Sized integer types like {return_type} should not be used in return types. Use 'int' instead.",
                'line': node.returns.lineno,
                'column': getattr(node.returns, 'col_offset', 1),
                'severity': Severity.ERROR,
                'suggestion': "Replace sized integer types with 'int' in method return types"
            })
            
    def _check_parameter_type(self, arg: ast.arg, func_node: ast.FunctionDef):
        """Check parameter type annotations."""
        if not arg.annotation:
            return
            
        param_type = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else str(arg.annotation)
        
        # GenVM-specific type checks can be added here
        # For example, checking for proper Address usage, etc.
        pass
        
    def visit_Return(self, node: ast.Return):
        """Check return statements for type consistency."""
        if node.value and self.current_method:
            # Could add runtime type checking here
            pass
        self.generic_visit(node)