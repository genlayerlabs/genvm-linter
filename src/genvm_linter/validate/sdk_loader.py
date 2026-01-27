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
) -> list[Path]:
    """
    Extract SDK components needed for the contract.

    Resolution:
    1. Get py-genlayer runner manifest
    2. Extract py-lib-genlayer-std with exact version from manifest
    3. Extract embeddings if needed
    """
    paths = []

    # 1. Resolve py-genlayer runner
    if "py-genlayer" in dependencies:
        genlayer_hash = dependencies["py-genlayer"]
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
        emb_path = extract_runner(tarball_path, "py-lib-genlayer-embeddings", emb_hash)
        paths.append(emb_path)

    return paths


def load_sdk(
    contract_path: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Callable[[type], dict[str, Any]]:
    """
    Load GenLayer SDK for contract validation.

    Args:
        contract_path: Path to the contract file
        progress_callback: Optional callback for download progress

    Returns:
        The get_schema function from the SDK
    """
    # 1. Parse contract header
    dependencies = parse_contract_header(contract_path)

    # 2. Download artifacts if needed
    tarball_path = download_artifacts(progress_callback=progress_callback)

    # 3. Extract SDK paths
    sdk_paths = extract_sdk_paths(tarball_path, dependencies)

    # 4. CRITICAL: Import numpy BEFORE SDK
    # SDK's _internal/numpy.py only registers numpy types if numpy is already imported
    import numpy as np  # noqa: F401

    # 5. Mock WASI
    setup_wasi_mocks()

    # 6. Add SDK to path
    for path in reversed(sdk_paths):
        src_path = path / "src" if (path / "src").exists() else path
        sys.path.insert(0, str(src_path))

    # 7. Import get_schema
    from genlayer.py.get_schema import get_schema

    return get_schema


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
