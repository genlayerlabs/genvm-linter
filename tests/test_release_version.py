import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "release_version.py"
SPEC = importlib.util.spec_from_file_location("release_version", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
release_version = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release_version
SPEC.loader.exec_module(release_version)


@pytest.mark.parametrize(
    ("raw", "normalized", "branch", "is_prerelease"),
    [
        ("0.11.1", "0.11.1", "v0.11", False),
        ("v0.11.1-rc.1", "0.11.1-rc.1", "v0.11-dev", True),
        ("0.11.1rc2", "0.11.1-rc.2", "v0.11-dev", True),
    ],
)
def test_release_version_normalizes_pep440_rc_spellings(
    raw, normalized, branch, is_prerelease
):
    version = release_version.parse_release_version(raw)

    assert version.normalized == normalized
    assert version.release_branch == branch
    assert version.is_prerelease is is_prerelease


@pytest.mark.parametrize(
    ("branch", "version", "message"),
    [
        ("main", "0.11.1", "not a release branch"),
        ("v0.10-dev", "0.11.1-rc.1", "belongs to v0.11"),
        ("v0.11", "0.11.1-rc.1", "must be cut from v0.11-dev"),
        ("v0.11-dev", "0.11.1", "must be cut from v0.11"),
    ],
)
def test_release_version_rejects_wrong_release_route(branch, version, message):
    with pytest.raises(ValueError, match=message):
        release_version.validate_branch_version(branch, version)


def test_release_version_accepts_rc_only_on_owning_dev_line():
    version = release_version.validate_branch_version("v0.11-dev", "0.11.1rc1")

    assert version.normalized == "0.11.1-rc.1"


@pytest.mark.parametrize("version", ["0.11.1-alpha.1", "0.11.1-rc.0", "00.11.1"])
def test_release_version_rejects_non_rc_or_noncanonical_versions(version):
    with pytest.raises(ValueError, match="not a supported release version"):
        release_version.parse_release_version(version)


def test_release_tag_and_package_version_compare_after_normalization():
    assert release_version.main(
        ["release_version.py", "verify-tag", "v0.11.1-rc.1", "0.11.1rc1"]
    ) == 0
