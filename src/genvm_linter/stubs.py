"""Generate type stubs for GenLayer SDK."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .validate.artifacts import download_artifacts, get_latest_version
from .validate.sdk_loader import get_sdk_paths_from_genvmroot, extract_sdk_paths, parse_contract_header

CACHE_DIR = Path.home() / ".cache" / "genvm-linter" / "stubs"

# Manual type definitions to fill in gaps from stubgen
MANUAL_TYPES = '''
# Unsigned integers
u8 = int
u16 = int
u24 = int
u32 = int
u40 = int
u48 = int
u56 = int
u64 = int
u72 = int
u80 = int
u88 = int
u96 = int
u104 = int
u112 = int
u120 = int
u128 = int
u136 = int
u144 = int
u152 = int
u160 = int
u168 = int
u176 = int
u184 = int
u192 = int
u200 = int
u208 = int
u216 = int
u224 = int
u232 = int
u240 = int
u248 = int
u256 = int

# Signed integers
i8 = int
i16 = int
i24 = int
i32 = int
i40 = int
i48 = int
i56 = int
i64 = int
i72 = int
i80 = int
i88 = int
i96 = int
i104 = int
i112 = int
i120 = int
i128 = int
i136 = int
i144 = int
i152 = int
i160 = int
i168 = int
i176 = int
i184 = int
i192 = int
i200 = int
i208 = int
i216 = int
i224 = int
i232 = int
i240 = int
i248 = int
i256 = int

bigint = int
'''

MANUAL_ADDRESS = '''
class Address:
    """GenLayer address type."""
    def __init__(self, value: str | bytes) -> None: ...
    @property
    def as_hex(self) -> str: ...
    @property
    def as_bytes(self) -> bytes: ...
    @property
    def as_b64(self) -> str: ...
    @property
    def as_int(self) -> int: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...
    def __str__(self) -> str: ...
'''

MANUAL_STORAGE = '''
from typing import TypeVar, Generic, Iterator

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

class Array(Generic[T]):
    """Fixed-size array storage type."""
    def __getitem__(self, index: int) -> T: ...
    def __setitem__(self, index: int, value: T) -> None: ...
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[T]: ...

class DynArray(Generic[T]):
    """Dynamic array storage type."""
    def __getitem__(self, index: int) -> T: ...
    def __setitem__(self, index: int, value: T) -> None: ...
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[T]: ...
    def append(self, value: T) -> None: ...
    def pop(self) -> T: ...

class TreeMap(Generic[K, V]):
    """Sorted map storage type."""
    def __getitem__(self, key: K) -> V: ...
    def __setitem__(self, key: K, value: V) -> None: ...
    def __delitem__(self, key: K) -> None: ...
    def __contains__(self, key: K) -> bool: ...
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[K]: ...
    def get(self, key: K, default: V = ...) -> V: ...
    def keys(self) -> Iterator[K]: ...
    def values(self) -> Iterator[V]: ...
    def items(self) -> Iterator[tuple[K, V]]: ...

def allow_storage(cls: type[T]) -> type[T]:
    """Decorator to allow a class to be used in storage."""
    ...
'''

MANUAL_GL = '''
from typing import Callable, TypeVar, Any, overload
from .py.types import Address, u256

T = TypeVar('T')
R = TypeVar('R')

class Contract:
    """Base class for GenLayer contracts."""
    def __init__(self) -> None: ...

class Event:
    """Base class for contract events."""
    ...

class Lazy(Generic[T]):
    """Lazy-loaded value."""
    def __call__(self) -> T: ...

class MessageType:
    """Transaction message context."""
    @property
    def sender(self) -> Address: ...
    @property
    def sender_address(self) -> Address: ...
    @property
    def contract_address(self) -> Address: ...
    @property
    def origin_address(self) -> Address: ...
    @property
    def value(self) -> u256: ...
    @property
    def chain_id(self) -> u256: ...

message: MessageType

class _Public:
    """Public method decorators."""
    @property
    def view(self) -> Callable[[Callable[..., R]], Callable[..., R]]: ...
    @property
    def write(self) -> _PublicWrite: ...

class _PublicWrite:
    """Public write method decorators."""
    def __call__(self, fn: Callable[..., R]) -> Callable[..., R]: ...
    @property
    def payable(self) -> Callable[[Callable[..., R]], Callable[..., R]]: ...
    def min_gas(self, leader: int, validator: int) -> Callable[[Callable[..., R]], Callable[..., R]]: ...

public: _Public

class _Nondet:
    """Non-deterministic operations."""
    def exec_prompt(self, prompt: str) -> str: ...
    @property
    def web(self) -> _NondetWeb: ...

class _NondetWeb:
    """Web operations (non-deterministic)."""
    def render(self, url: str) -> str: ...
    def get(self, url: str) -> Any: ...
    def post(self, url: str, body: Any = None) -> Any: ...
    def request(self, url: str, method: str = "GET", body: Any = None) -> Any: ...
    def delete(self, url: str) -> Any: ...
    def head(self, url: str) -> Any: ...
    def patch(self, url: str, body: Any = None) -> Any: ...

nondet: _Nondet

class _EqPrinciple:
    """Equivalence principle validators."""
    def strict_eq(self, fn: Callable[..., R]) -> Callable[..., R]: ...
    def prompt_comparative(self, fn: Callable[..., R], principle: str) -> Callable[..., R]: ...
    def prompt_non_comparative(self, fn: Callable[..., R], task: str, criteria: str) -> Callable[..., R]: ...

eq_principle: _EqPrinciple

class _Advanced:
    """Advanced operations."""
    def user_error_immediate(self, message: str) -> None: ...

advanced: _Advanced

class _Storage:
    """Storage operations."""
    def inmem_allocate(self, typ: type[T]) -> T: ...
    def copy_to_memory(self, data: T) -> T: ...
    class Root: ...

storage: _Storage

def ContractAt(address: Address) -> Any:
    """Get contract proxy at address."""
    ...

def deploy_contract(contract_cls: type[T], *args: Any, **kwargs: Any) -> T:
    """Deploy a new contract."""
    ...

def get_contract_at(contract_cls: type[T], address: Address) -> T:
    """Get typed contract proxy at address."""
    ...

def trace(*args: Any) -> None:
    """Debug trace output."""
    ...

def contract_interface(cls: type[T]) -> type[T]:
    """Decorator for contract interface."""
    ...
'''


def get_stubs_path(version: str) -> Path:
    """Get path to cached stubs for a version."""
    return CACHE_DIR / version


def generate_stubs(
    version: str | None = None,
    output_path: Path | None = None,
    progress_callback=None,
) -> Path:
    """
    Generate type stubs for GenLayer SDK.

    Args:
        version: SDK version (e.g., "v0.2.12"). If None, uses latest.
        output_path: Where to write stubs. If None, uses cache.
        progress_callback: Optional callback for download progress.

    Returns:
        Path to generated stubs directory.
    """
    # Resolve version
    if version is None:
        version = get_latest_version()

    # Check cache
    stubs_path = output_path or get_stubs_path(version)
    if stubs_path.exists() and not output_path:
        return stubs_path

    # Download SDK artifacts
    tarball_path = download_artifacts(version, progress_callback=progress_callback)

    # Extract SDK
    from .validate.sdk_loader import extract_sdk_paths
    sdk_paths = extract_sdk_paths(tarball_path, {})

    if not sdk_paths:
        raise RuntimeError("Could not extract SDK paths")

    sdk_path = sdk_paths[0]
    src_path = sdk_path / "src" if (sdk_path / "src").exists() else sdk_path

    # Create output directory
    stubs_path.mkdir(parents=True, exist_ok=True)

    # Try to run stubgen
    stubgen_success = False
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(src_path)

        result = subprocess.run(
            [sys.executable, "-m", "mypy.stubgen", "-p", "genlayer", "-o", str(stubs_path)],
            env=env,
            capture_output=True,
            text=True,
        )
        stubgen_success = result.returncode == 0
    except Exception:
        pass

    # Post-process or create from scratch
    genlayer_stubs = stubs_path / "genlayer"
    genlayer_stubs.mkdir(parents=True, exist_ok=True)

    # Write/fix type definitions
    _write_types_stub(genlayer_stubs / "py" / "types.pyi")
    _write_gl_stub(genlayer_stubs / "gl" / "__init__.pyi")
    _write_init_stub(genlayer_stubs / "__init__.pyi")

    # Write version marker
    (stubs_path / "VERSION").write_text(version)

    return stubs_path


def _write_types_stub(path: Path):
    """Write types.pyi with proper type definitions."""
    path.parent.mkdir(parents=True, exist_ok=True)

    content = '''"""GenLayer type definitions."""

from typing import TypeVar, Generic, Iterator

'''
    content += MANUAL_TYPES
    content += "\n"
    content += MANUAL_ADDRESS
    content += "\n"
    content += MANUAL_STORAGE

    path.write_text(content)


def _write_gl_stub(path: Path):
    """Write gl/__init__.pyi with gl module definitions."""
    path.parent.mkdir(parents=True, exist_ok=True)

    content = '''"""GenLayer gl module."""

'''
    content += MANUAL_GL

    path.write_text(content)


def _write_init_stub(path: Path):
    """Write main __init__.pyi."""
    content = '''"""GenLayer SDK type stubs."""

from .py.types import (
    Address,
    Array,
    DynArray,
    TreeMap,
    allow_storage,
    u8, u16, u24, u32, u40, u48, u56, u64, u72, u80, u88, u96,
    u104, u112, u120, u128, u136, u144, u152, u160, u168, u176, u184, u192,
    u200, u208, u216, u224, u232, u240, u248, u256,
    i8, i16, i24, i32, i40, i48, i56, i64, i72, i80, i88, i96,
    i104, i112, i120, i128, i136, i144, i152, i160, i168, i176, i184, i192,
    i200, i208, i216, i224, i232, i240, i248, i256,
    bigint,
)
from .gl import (
    Contract,
    Event,
    Lazy,
    MessageType,
    message,
    public,
    nondet,
    eq_principle,
    advanced,
    storage,
    ContractAt,
    deploy_contract,
    get_contract_at,
    trace,
    contract_interface,
)
import genlayer.gl as gl

__all__ = [
    "gl",
    "Address",
    "Array",
    "DynArray",
    "TreeMap",
    "allow_storage",
    "Contract",
    "Event",
    "Lazy",
    "message",
    "public",
    "nondet",
    "eq_principle",
    "advanced",
    "storage",
    "ContractAt",
    "deploy_contract",
    "get_contract_at",
    "trace",
    "contract_interface",
    "u8", "u16", "u24", "u32", "u40", "u48", "u56", "u64", "u72", "u80", "u88", "u96",
    "u104", "u112", "u120", "u128", "u136", "u144", "u152", "u160", "u168", "u176", "u184", "u192",
    "u200", "u208", "u216", "u224", "u232", "u240", "u248", "u256",
    "i8", "i16", "i24", "i32", "i40", "i48", "i56", "i64", "i72", "i80", "i88", "i96",
    "i104", "i112", "i120", "i128", "i136", "i144", "i152", "i160", "i168", "i176", "i184", "i192",
    "i200", "i208", "i216", "i224", "i232", "i240", "i248", "i256",
    "bigint",
]
'''
    path.write_text(content)


def list_cached_stubs() -> list[str]:
    """List all cached stub versions."""
    if not CACHE_DIR.exists():
        return []

    versions = []
    for d in CACHE_DIR.iterdir():
        if d.is_dir() and (d / "VERSION").exists():
            versions.append((d / "VERSION").read_text().strip())
    return sorted(versions)
