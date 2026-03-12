"""Load GenLayer SDK for contract validation."""

import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock

from .artifacts import (
    download_artifacts,
    extract_runner,
    find_latest_runner,
    parse_runner_manifest,
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
                f"See https://github.com/genlayerlabs/genvm/releases for changes."
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
                    f"See https://github.com/genlayerlabs/genvm/releases for changes."
                )
        emb_path = extract_runner(tarball_path, "py-lib-genlayer-embeddings", emb_hash)
        paths.append(emb_path)

    return paths, notes


def get_sdk_paths_from_genvmroot() -> list[Path] | None:
    """
    Get SDK paths from GENVMROOT environment variable if available.

    This reuses GenVM artifacts already downloaded by studio/other tools.
    Returns None if GENVMROOT is not set or SDK not found.
    """
    genvmroot = os.environ.get("GENVMROOT")
    if not genvmroot:
        return None

    genvm_path = Path(genvmroot)
    if not genvm_path.exists():
        return None

    # Studio layout: /genvm/runners/genlayer-py-std/src
    sdk_path = genvm_path / "runners" / "genlayer-py-std" / "src"
    if sdk_path.exists():
        return [sdk_path]

    # Alternative: /genvm/runners/py-lib-genlayer-std/src
    alt_path = genvm_path / "runners" / "py-lib-genlayer-std" / "src"
    if alt_path.exists():
        return [alt_path]

    return None


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
        If GENVMROOT env var is set, reuses SDK from that location
        instead of downloading. This is useful in studio/CI environments.
    """
    # 1. CRITICAL: Import numpy BEFORE SDK
    # SDK's _internal/numpy.py only registers numpy types if numpy is already imported
    import numpy as np  # noqa: F401

    # 2. Mock WASI
    setup_wasi_mocks()

    # 3. Try to use GENVMROOT if available (reuse studio's GenVM)
    sdk_paths = get_sdk_paths_from_genvmroot()
    upgrade_notes: list[str] = []

    if sdk_paths is None:
        # 4. Parse contract header for version info
        dependencies = parse_contract_header(contract_path)

        # 5. Download artifacts if needed
        tarball_path = download_artifacts(progress_callback=progress_callback)

        # 6. Extract SDK paths
        sdk_paths, upgrade_notes = extract_sdk_paths(tarball_path, dependencies)

    # 7. Add SDK to path
    for path in reversed(sdk_paths):
        src_path = path / "src" if (path / "src").exists() else path
        sys.path.insert(0, str(src_path))

    # 8. Import get_schema
    from genlayer.py.get_schema import get_schema

    return get_schema, upgrade_notes


def load_contract_module(contract_path: Path):
    """Load contract as a Python module."""
    spec = importlib.util.spec_from_file_location("contract", contract_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load contract: {contract_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["contract"] = module
    spec.loader.exec_module(module)
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
