"""Regression tests for the ``setup`` command's JSON version field."""

import json

import pytest
from click.testing import CliRunner

from genvm_linter import cli
from genvm_linter.validate import artifacts


class _FakeBundle:
    """Stands in for the downloaded bundle path without touching the disk."""

    def __init__(self, name):
        self.name = name

    def exists(self):
        return True

    def is_dir(self):
        return False


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def contract(tmp_path):
    path = tmp_path / "contract.py"
    path.write_text("class Storage:\n    pass\n")
    return path


class TestSetupJsonVersion:
    """`setup --json` must report the bare version, not the namespaced filename.

    Cache files are namespaced by repository
    (``genvm-universal-genlayerlabs-genvm-manager-<version>.tar.xz``), so the
    version cannot be recovered by stripping a fixed prefix off the name.
    """

    def _stub_download(self, monkeypatch, tarball_name):
        monkeypatch.setattr(
            cli,
            "download_artifacts",
            lambda version=None, progress_callback=None: _FakeBundle(tarball_name),
        )
        monkeypatch.setattr(cli, "extract_sdk_paths", lambda *a, **k: ([], []))

    def test_contract_header_autodetect_reports_bare_version(
        self, runner, monkeypatch, contract
    ):
        # No --version: the contract-header path leaves version unset, which is
        # the branch that has to recover it from the cached filename.
        self._stub_download(
            monkeypatch, f"{artifacts._cache_prefix()}v0.6.0-rc7.tar.xz"
        )
        result = runner.invoke(
            cli.main, ["setup", "--json", "--contract", str(contract)]
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["version"] == "v0.6.0-rc7"

    def test_explicit_version_argument_is_passed_through(
        self, runner, monkeypatch, contract
    ):
        self._stub_download(
            monkeypatch, f"{artifacts._cache_prefix()}v0.6.0-rc7.tar.xz"
        )
        result = runner.invoke(
            cli.main,
            ["setup", "--json", "--contract", str(contract), "--version", "v0.5.0"],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["version"] == "v0.5.0"
