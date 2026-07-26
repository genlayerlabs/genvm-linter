"""Load GenLayer SDK for contract validation."""

import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock

from .artifacts import (
    GITHUB_RELEASES_URL,
    extract_runner,
    find_latest_runner,
    parse_runner_manifest,
    resolve_artifact_source,
)


def parse_contract_header(contract_path: Path) -> dict[str, str]:
    """
    Parse the contract header to extract SDK version hashes.

    Contract header format:
    # {
    #   "Seq": [
    #     { "Depends": "py-lib-genlayer-embeddings:HASH" },
    #     { "Depends": "py-genlayer:HASH" }
    #   ]
    # }
    """
    content = contract_path.read_text()

    header_lines = []
    for line in content.split("\n"):
        if line.startswith("#"):
            header_lines.append(line[1:].strip() if line.startswith("# ") else line[1:])
        else:
            break

    header_text = "\n".join(header_lines)

    depends_pattern = r'"Depends":\s*"([^:]+):([^"]+)"'
    matches = re.findall(depends_pattern, header_text)

    return {name: hash_val for name, hash_val in matches}


def setup_wasi_mocks():
    """Mock the _genlayer_wasi module."""
    wasi_mock = MagicMock()
    wasi_mock.storage_read = MagicMock(return_value=None)
    wasi_mock.storage_write = MagicMock(return_value=None)
    wasi_mock.get_balance = MagicMock(return_value=0)
    wasi_mock.get_self_balance = MagicMock(return_value=0)
    wasi_mock.gl_call = MagicMock(return_value=0)
    sys.modules["_genlayer_wasi"] = wasi_mock
    os.environ["GENERATING_DOCS"] = "true"


def extract_sdk_paths(
    tarball_path: Path,
    dependencies: dict[str, str],
) -> tuple[list[Path], list[str]]:
    """
    Extract SDK components needed for the contract.

    Opens the tarball once and performs all extractions / lookups
    through a single decompression pass.

    Returns:
        Tuple of (sdk_paths, upgrade_notes).
    """
    paths = []
    notes = []
    _SPECIAL_HASHES = {"test", "latest"}

    # 1. Resolve py-genlayer runner
    if "py-genlayer" in dependencies and dependencies["py-genlayer"] not in _SPECIAL_HASHES:
        genlayer_hash = dependencies["py-genlayer"]
        latest_hash = find_latest_runner(tarball_path, "py-genlayer")
        if latest_hash and latest_hash != genlayer_hash:
            notes.append(
                f"py-genlayer: a newer runner is available ({latest_hash}). "
                f"See {GITHUB_RELEASES_URL} for changes."
            )
    else:
        genlayer_hash = find_latest_runner(tarball_path, "py-genlayer")
        if not genlayer_hash:
            raise RuntimeError("Could not find py-genlayer in release")

    runner_path = extract_runner(tarball_path, "py-genlayer", genlayer_hash)

    # 2. Parse runner manifest for exact lib versions
    runner_deps = parse_runner_manifest(runner_path)

    # 3. Extract py-lib-genlayer-std
    if "py-lib-genlayer-std" not in runner_deps:
        raise RuntimeError("py-genlayer runner doesn't specify py-lib-genlayer-std")

    std_hash = runner_deps["py-lib-genlayer-std"]
    std_path = extract_runner(tarball_path, "py-lib-genlayer-std", std_hash)
    paths.append(std_path)

    # 4. Extract py-lib-protobuf (needed by embeddings)
    proto_hash = find_latest_runner(tarball_path, "py-lib-protobuf")
    if proto_hash:
        proto_path = extract_runner(tarball_path, "py-lib-protobuf", proto_hash)
        paths.append(proto_path)

    # 5. Extract embeddings if contract uses it
    if "py-lib-genlayer-embeddings" in dependencies:
        emb_hash = dependencies["py-lib-genlayer-embeddings"]
        if emb_hash in _SPECIAL_HASHES:
            emb_hash = find_latest_runner(tarball_path, "py-lib-genlayer-embeddings")
            if not emb_hash:
                raise RuntimeError("Could not find py-lib-genlayer-embeddings in release")
        else:
            latest_emb = find_latest_runner(tarball_path, "py-lib-genlayer-embeddings")
            if latest_emb and latest_emb != emb_hash:
                notes.append(
                    f"py-lib-genlayer-embeddings: a newer runner is available ({latest_emb}). "
                    f"See {GITHUB_RELEASES_URL} for changes."
                )
        emb_path = extract_runner(tarball_path, "py-lib-genlayer-embeddings", emb_hash)
        paths.append(emb_path)

    return paths, notes


def _import_get_schema() -> Callable[[type], dict[str, Any]]:
    """Import get_schema from the current SDK or its legacy location."""
    try:
        from genlayer._internal.get_schema import get_schema
    except ModuleNotFoundError as exc:
        if exc.name not in {"genlayer._internal", "genlayer._internal.get_schema"}:
            raise
        from genlayer.py.get_schema import get_schema
    return get_schema


def load_sdk(
    contract_path: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[Callable[[type], dict[str, Any]], list[str]]:
    """
    Load GenLayer SDK for contract validation.

    Args:
        contract_path: Path to the contract file
        progress_callback: Optional callback for download progress

    Returns:
        Tuple of (get_schema function, upgrade_notes list)

    Note:
        GENVM_SOURCE_MODE controls whether artifacts come from a prebuilt
        GenVM tree or a downloaded release bundle.
    """
    # 1. CRITICAL: Import numpy BEFORE SDK
    # SDK's _internal/numpy.py only registers numpy types if numpy is already imported
    import numpy as np  # noqa: F401

    # 2. Mock WASI
    setup_wasi_mocks()

    # 3. Parse contract header for runner hashes
    dependencies = parse_contract_header(contract_path)

    # 4. Resolve a prebuilt tree or download a release bundle
    artifact_path = resolve_artifact_source(progress_callback=progress_callback)

    # 5. Extract SDK paths from the selected source
    sdk_paths, upgrade_notes = extract_sdk_paths(artifact_path, dependencies)

    # 6. Add SDK to path.  SDK paths are inserted at the FRONT of sys.path so the
    #    contract resolves to the right SDK version.  Without cleanup this leaks:
    #    repeated validations (long-running VS Code extension, programmatic loops)
    #    accumulate stale paths, and a prior SDK version can shadow the current one.
    #    We remove any stale genlayer.* modules so the new paths are actually
    #    consulted, then drop the paths we inserted once the import completes.
    #    The returned get_schema callable keeps the imported modules alive via its
    #    globals, so clearing sys.modules here is safe.  The contract loaded later
    #    by load_contract_module reuses the cached genlayer modules, so sys.path no
    #    longer needs the SDK entries.
    _inserted: list[str] = []
    _clear_genlayer_modules()
    try:
        for path in reversed(sdk_paths):
            src_path = path / "src" if (path / "src").exists() else path
            sys.path.insert(0, str(src_path))
            _inserted.append(str(src_path))

        # 7. Import get_schema from the current SDK, falling back to the legacy layout.
        get_schema = _import_get_schema()
    finally:
        # Remove only the paths we added (they sit at the front); leave any
        # pre-existing entries intact.
        for p in _inserted:
            if sys.path and sys.path[0] == p:
                sys.path.pop(0)

    return get_schema, upgrade_notes


def _clear_genlayer_modules() -> None:
    """Remove cached ``genlayer`` and ``genlayer.*`` modules from ``sys.modules``.

    Python's import system returns a cached module from ``sys.modules`` without
    consulting ``sys.path``.  After the first ``load_sdk`` call the genlayer SDK
    modules live in the cache; a second call with a different SDK version (or a
    re-downloaded tarball) would silently reuse the stale modules unless they are
    evicted here first.  numpy and other third-party modules are left untouched.
    """
    for name in list(sys.modules):
        if name == "genlayer" or name.startswith("genlayer."):
            del sys.modules[name]


def load_contract_module(contract_path: Path):
    """Load contract as a Python module.

    The module is registered under the name ``"contract"`` in ``sys.modules``
    while it executes so that ``import contract`` references inside the contract
    file resolve to itself.  It is removed again afterwards: a stale entry would
    leak the previous contract's code (and its class/imports) into the next
    ``validate_contract`` call in the same process, silently returning the wrong
    schema for every contract validated after the first.
    """
    spec = importlib.util.spec_from_file_location("contract", contract_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load contract: {contract_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["contract"] = module
    try:
        spec.loader.exec_module(module)
    finally:
        # Drop the cache entry so a later call (different contract) is not
        # shadowed by this one.  `module` is returned to the caller, which keeps
        # it alive independently of sys.modules.
        sys.modules.pop("contract", None)
    return module


def find_contract_class(module) -> type | None:
    """Find the contract class in a module."""
    for name, obj in vars(module).items():
        if not isinstance(obj, type) or name == "Contract":
            continue

        # Check for @gl.public decorated methods
        for method_name in dir(obj):
            method = getattr(obj, method_name, None)
            if callable(method) and hasattr(method, "__gl_public__"):
                return obj

        # Check for Contract base class
        bases = [b.__name__ for b in obj.__mro__ if b.__name__ != "object"]
        if "Contract" in bases:
            return obj

    return None
