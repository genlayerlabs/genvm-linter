"""Unit tests for SDK layout compatibility."""

import io
import json
import sys
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

from genvm_linter.validate import artifacts, sdk_loader


def _package(name: str) -> ModuleType:
    package = ModuleType(name)
    package.__path__ = []
    return package


def _clear_genlayer_modules(monkeypatch):
    for name in list(sys.modules):
        if name == "genlayer" or name.startswith("genlayer."):
            monkeypatch.delitem(sys.modules, name)


def _make_usable_prebuilt_root(tmp_path: Path) -> Path:
    root = tmp_path / "genvm"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "genvm-modules").write_bytes(b"")
    (root / "runners").mkdir()
    return root


def _write_runner_tar(
    root: Path,
    runner_type: str,
    runner_hash: str,
    files: dict[str, bytes],
    *,
    legacy_version: str | None = None,
) -> Path:
    if legacy_version is None:
        tar_path = (
            root
            / "runners"
            / runner_type
            / runner_hash[:2]
            / f"{runner_hash[2:]}.tar"
        )
    else:
        tar_path = (
            root
            / "executor"
            / legacy_version
            / "legacy-runners"
            / runner_type
            / runner_hash[:2]
            / f"{runner_hash[2:]}.tar"
        )
    tar_path.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tar_path, mode="w") as runner_tar:
        for name, payload in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            runner_tar.addfile(member, io.BytesIO(payload))
    return tar_path


def _write_sdk_runners(
    root: Path,
    *,
    legacy_version: str | None = None,
) -> tuple[str, str]:
    genlayer_hash = "abgenlayerhash"
    std_hash = "cdstdlibhash"
    runner_manifest = {
        "Seq": [{"Depends": f"py-lib-genlayer-std:{std_hash}"}],
    }
    _write_runner_tar(
        root,
        "py-genlayer",
        genlayer_hash,
        {"runner.json": json.dumps(runner_manifest).encode()},
        legacy_version=legacy_version,
    )
    _write_runner_tar(
        root,
        "py-lib-genlayer-std",
        std_hash,
        {"src/genlayer/__init__.py": b""},
        legacy_version=legacy_version,
    )
    return genlayer_hash, std_hash


def _clear_source_environment(monkeypatch) -> None:
    for env_var in (
        artifacts.GENVM_SOURCE_MODE_ENV,
        artifacts.GENVM_PREBUILT_DIR_ENV,
        artifacts.GENVMROOT_ENV,
    ):
        monkeypatch.delenv(env_var, raising=False)


def test_prebuilt_tree_is_preferred_and_resolves_sdk(monkeypatch, tmp_path):
    _clear_source_environment(monkeypatch)
    root = _make_usable_prebuilt_root(tmp_path)
    genlayer_hash, std_hash = _write_sdk_runners(root)
    monkeypatch.setenv(artifacts.GENVM_PREBUILT_DIR_ENV, str(root))
    monkeypatch.setattr(artifacts, "CACHE_DIR", tmp_path / "cache")

    def _fail_download(*args, **kwargs):
        raise AssertionError("a usable prebuilt tree must prevent release download")

    monkeypatch.setattr(artifacts, "download_artifacts", _fail_download)

    artifact_path = artifacts.resolve_artifact_source()
    sdk_paths, notes = sdk_loader.extract_sdk_paths(
        artifact_path,
        {"py-genlayer": genlayer_hash},
    )

    assert artifact_path == root
    assert notes == []
    assert sdk_paths == [
        tmp_path
        / "cache"
        / "extracted"
        / "prebuilt"
        / "py-lib-genlayer-std"
        / std_hash
    ]
    assert (sdk_paths[0] / "src" / "genlayer" / "__init__.py").is_file()


def test_explicit_broken_prebuilt_tree_hard_fails(monkeypatch, tmp_path):
    _clear_source_environment(monkeypatch)
    broken_root = tmp_path / "incomplete-genvm"
    broken_root.mkdir()
    monkeypatch.setenv(artifacts.GENVM_SOURCE_MODE_ENV, "prebuilt")
    monkeypatch.setenv(artifacts.GENVM_PREBUILT_DIR_ENV, str(broken_root))

    def _fail_download(*args, **kwargs):
        raise AssertionError("explicit prebuilt mode must never fall back to release")

    monkeypatch.setattr(artifacts, "download_artifacts", _fail_download)

    with pytest.raises(RuntimeError, match="GENVM_SOURCE_MODE=prebuilt.*unusable"):
        artifacts.resolve_artifact_source()


def test_auto_mode_without_tree_downloads_release(monkeypatch, tmp_path):
    _clear_source_environment(monkeypatch)
    bundle = tmp_path / "bundle.tar.xz"
    calls = []

    def _download(version=None, progress_callback=None):
        calls.append((version, progress_callback))
        return bundle

    monkeypatch.setattr(artifacts, "download_artifacts", _download)

    assert artifacts.resolve_artifact_source() == bundle
    assert calls == [(None, None)]


def test_prebuilt_legacy_layout_resolves_sdk(monkeypatch, tmp_path):
    _clear_source_environment(monkeypatch)
    root = _make_usable_prebuilt_root(tmp_path)
    genlayer_hash, std_hash = _write_sdk_runners(
        root,
        legacy_version="v0.2.17",
    )
    monkeypatch.setenv(artifacts.GENVM_SOURCE_MODE_ENV, "prebuilt")
    monkeypatch.setenv(artifacts.GENVM_PREBUILT_DIR_ENV, str(root))
    monkeypatch.setattr(artifacts, "CACHE_DIR", tmp_path / "cache")

    artifact_path = artifacts.resolve_artifact_source()
    sdk_paths, _notes = sdk_loader.extract_sdk_paths(
        artifact_path,
        {"py-genlayer": genlayer_hash},
    )

    assert artifact_path == root
    assert sdk_paths[0].name == std_hash
    assert (sdk_paths[0] / "src" / "genlayer" / "__init__.py").is_file()


def test_genvmroot_is_a_backwards_compatible_prebuilt_alias(monkeypatch, tmp_path):
    _clear_source_environment(monkeypatch)
    root = _make_usable_prebuilt_root(tmp_path)
    monkeypatch.setenv(artifacts.GENVMROOT_ENV, str(root))

    assert artifacts.resolve_artifact_source() == root


def test_genvm_prebuilt_dir_takes_precedence_over_genvmroot(monkeypatch, tmp_path):
    _clear_source_environment(monkeypatch)
    preferred_root = _make_usable_prebuilt_root(tmp_path / "preferred")
    alias_root = _make_usable_prebuilt_root(tmp_path / "alias")
    monkeypatch.setenv(artifacts.GENVM_PREBUILT_DIR_ENV, str(preferred_root))
    monkeypatch.setenv(artifacts.GENVMROOT_ENV, str(alias_root))

    assert artifacts.resolve_artifact_source() == preferred_root


def test_release_mode_ignores_configured_prebuilt_tree(monkeypatch, tmp_path):
    _clear_source_environment(monkeypatch)
    root = _make_usable_prebuilt_root(tmp_path)
    bundle = tmp_path / "bundle.tar.xz"
    monkeypatch.setenv(artifacts.GENVM_SOURCE_MODE_ENV, "release")
    monkeypatch.setenv(artifacts.GENVM_PREBUILT_DIR_ENV, str(root))
    monkeypatch.setattr(
        artifacts,
        "download_artifacts",
        lambda version=None, progress_callback=None: bundle,
    )

    assert artifacts.resolve_artifact_source() == bundle


def test_import_get_schema_prefers_current_sdk_layout(monkeypatch):
    _clear_genlayer_modules(monkeypatch)

    def expected(contract):
        return {"contract": contract}

    module = ModuleType("genlayer._internal.get_schema")
    module.get_schema = expected
    monkeypatch.setitem(sys.modules, "genlayer", _package("genlayer"))
    monkeypatch.setitem(sys.modules, "genlayer._internal", _package("genlayer._internal"))
    monkeypatch.setitem(sys.modules, "genlayer._internal.get_schema", module)

    assert sdk_loader._import_get_schema() is expected


def test_import_get_schema_falls_back_to_legacy_sdk_layout(monkeypatch):
    _clear_genlayer_modules(monkeypatch)

    def expected(contract):
        return {"contract": contract}

    module = ModuleType("genlayer.py.get_schema")
    module.get_schema = expected
    monkeypatch.setitem(sys.modules, "genlayer", _package("genlayer"))
    monkeypatch.setitem(sys.modules, "genlayer.py", _package("genlayer.py"))
    monkeypatch.setitem(sys.modules, "genlayer.py.get_schema", module)

    assert sdk_loader._import_get_schema() is expected


def test_broken_new_sdk_is_not_masked_by_legacy_fallback(monkeypatch):
    """A new-layout SDK whose own imports are broken must surface that error.

    Falling back to the legacy path here would hide a genuinely broken SDK
    behind a confusing 'no module named genlayer.py' error.
    """
    _clear_genlayer_modules(monkeypatch)

    genlayer = _package("genlayer")
    internal = _package("genlayer._internal")

    def _explode():
        raise ModuleNotFoundError(
            "No module named 'genlayer._internal.calldata'",
            name="genlayer._internal.calldata",
        )

    get_schema_mod = ModuleType("genlayer._internal.get_schema")
    get_schema_mod.__getattr__ = lambda _name: _explode()

    monkeypatch.setitem(sys.modules, "genlayer", genlayer)
    monkeypatch.setitem(sys.modules, "genlayer._internal", internal)
    # Importing the module raises a ModuleNotFoundError for a DIFFERENT module.
    monkeypatch.setitem(sys.modules, "genlayer._internal.get_schema", None)

    def _fake_import(name, *args, **kwargs):
        if name == "genlayer._internal.get_schema":
            _explode()
        raise AssertionError(f"legacy fallback must not be reached (tried {name})")

    monkeypatch.setattr("builtins.__import__", _fake_import)

    try:
        sdk_loader._import_get_schema()
    except ModuleNotFoundError as exc:
        assert exc.name == "genlayer._internal.calldata"
    else:
        raise AssertionError("expected the underlying ModuleNotFoundError to propagate")
