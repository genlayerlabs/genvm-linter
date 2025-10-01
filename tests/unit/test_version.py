"""Unit tests for version parsing and management."""

import pytest
from genvm_linter.version import Version, VersionParser, VersionRange


class TestVersion:
    """Test cases for Version class."""

    def test_parse_simple_version(self):
        """Test parsing simple version strings."""
        v = Version.parse("0.1.0")
        assert v.major == 0
        assert v.minor == 1
        assert v.patch == 0
        assert v.prerelease is None

    def test_parse_version_with_v_prefix(self):
        """Test parsing version with 'v' prefix."""
        v = Version.parse("v0.2.3")
        assert v.major == 0
        assert v.minor == 2
        assert v.patch == 3

    def test_parse_prerelease_version(self):
        """Test parsing version with prerelease."""
        v = Version.parse("1.0.0-beta")
        assert v.major == 1
        assert v.minor == 0
        assert v.patch == 0
        assert v.prerelease == "beta"

    def test_invalid_version_raises_error(self):
        """Test that invalid version strings raise ValueError."""
        with pytest.raises(ValueError, match="Invalid version string"):
            Version.parse("not-a-version")

        with pytest.raises(ValueError):
            Version.parse("1.2")  # Missing patch

        with pytest.raises(ValueError):
            Version.parse("a.b.c")

    def test_version_comparison(self):
        """Test version comparison operators."""
        v1 = Version(0, 1, 0)
        v2 = Version(0, 2, 0)
        v3 = Version(1, 0, 0)
        v4 = Version(0, 1, 0)

        assert v1 < v2
        assert v2 < v3
        assert v1 <= v4
        assert v1 == v4
        assert v3 > v2
        assert v3 >= v2

    def test_prerelease_comparison(self):
        """Test that prerelease versions are less than release versions."""
        release = Version(1, 0, 0)
        prerelease = Version(1, 0, 0, "beta")

        assert prerelease < release
        assert release > prerelease

    def test_version_string_representation(self):
        """Test string representation of versions."""
        v1 = Version(0, 1, 0)
        assert str(v1) == "0.1.0"

        v2 = Version(1, 2, 3, "alpha")
        assert str(v2) == "1.2.3-alpha"

    def test_is_compatible_with(self):
        """Test version range compatibility checking."""
        v = Version(0, 2, 0)

        # Within range
        assert v.is_compatible_with(Version(0, 1, 0), Version(0, 3, 0))

        # Below minimum
        assert not v.is_compatible_with(Version(0, 3, 0), None)

        # At or above maximum
        assert not v.is_compatible_with(None, Version(0, 2, 0))

        # No constraints
        assert v.is_compatible_with(None, None)


class TestVersionParser:
    """Test cases for VersionParser class."""

    def test_extract_version_comment(self):
        """Test extracting version from comment."""
        source = """# v0.1.0
# { "Depends": "py-genlayer:test" }

from genlayer import *"""

        version = VersionParser.extract_version(source)
        assert version is not None
        assert str(version) == "0.1.0"

    def test_extract_version_without_v_prefix(self):
        """Test extracting version without 'v' prefix."""
        source = """# 0.2.5
# { "Depends": "py-genlayer:test" }"""

        version = VersionParser.extract_version(source)
        assert version is not None
        assert str(version) == "0.2.5"

    def test_no_version_returns_none(self):
        """Test that missing version returns None."""
        source = """# { "Depends": "py-genlayer:test" }

from genlayer import *"""

        version = VersionParser.extract_version(source)
        assert version is None

    def test_version_after_import_ignored(self):
        """Test that version after import is ignored."""
        source = """# { "Depends": "py-genlayer:test" }
from genlayer import *
# v0.1.0  # This should be ignored"""

        version = VersionParser.extract_version(source)
        assert version is None

    def test_extract_simple_dependencies(self):
        """Test extracting simple dependency format."""
        source = '# { "Depends": "py-genlayer:latest" }'

        deps = VersionParser.extract_dependencies(source)
        assert deps == {"py-genlayer": "latest"}

    def test_extract_seq_dependencies(self):
        """Test extracting Seq dependency format."""
        source = '''# {
#   "Seq": [
#     { "Depends": "py-lib-genlayer-embeddings:09h0i209wrzh4xzq86f79c60x0ifs7xcjwl53ysrnw06i54ddxyi" },
#     { "Depends": "py-genlayer:1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379" }
#   ]
# }'''

        deps = VersionParser.extract_dependencies(source)
        assert "py-lib-genlayer-embeddings" in deps
        assert "py-genlayer" in deps
        assert deps["py-genlayer"] == "1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379"

    def test_get_effective_version_explicit(self):
        """Test getting effective version with explicit version comment."""
        source = """# v0.3.0
# { "Depends": "py-genlayer:test" }"""

        version = VersionParser.get_effective_version(source)
        assert version == "0.3.0"

    def test_get_effective_version_from_deps(self):
        """Test getting effective version from dependencies."""
        source = '# { "Depends": "py-genlayer:0.2.0" }'

        version = VersionParser.get_effective_version(source)
        assert version == "0.2.0"

    def test_get_effective_version_default(self):
        """Test default version when none specified."""
        source = '# { "Depends": "py-genlayer:latest" }'

        version = VersionParser.get_effective_version(source, "latest")
        assert version == "latest"

        version = VersionParser.get_effective_version(source, "0.4.0")
        assert version == "0.4.0"


class TestVersionRange:
    """Test cases for VersionRange class."""

    def test_parse_minimum_version(self):
        """Test parsing minimum version constraint."""
        r = VersionRange.parse(">=0.1.0")
        assert r.min_version == Version(0, 1, 0)
        assert r.max_version is None

    def test_parse_maximum_version(self):
        """Test parsing maximum version constraint."""
        r = VersionRange.parse("<0.2.0")
        assert r.min_version is None
        assert r.max_version == Version(0, 2, 0)

    def test_parse_range(self):
        """Test parsing version range."""
        r = VersionRange.parse(">=0.1.0 <0.3.0")
        assert r.min_version == Version(0, 1, 0)
        assert r.max_version == Version(0, 3, 0)

    def test_parse_caret_notation(self):
        """Test parsing caret notation (^0.1.0 = >=0.1.0 <0.2.0)."""
        r = VersionRange.parse("^0.1.0")
        assert r.min_version == Version(0, 1, 0)
        assert r.max_version == Version(0, 2, 0)

    def test_parse_tilde_notation(self):
        """Test parsing tilde notation (~0.1.0 = >=0.1.0 <0.2.0)."""
        r = VersionRange.parse("~0.1.0")
        assert r.min_version == Version(0, 1, 0)
        assert r.max_version == Version(0, 2, 0)

    def test_parse_exact_version(self):
        """Test parsing exact version."""
        r = VersionRange.parse("0.1.5")
        assert r.min_version == Version(0, 1, 5)
        assert r.max_version == Version(0, 1, 6)

    def test_contains(self):
        """Test checking if version is in range."""
        r = VersionRange.parse(">=0.1.0 <0.3.0")

        assert r.contains(Version(0, 1, 0))  # At minimum
        assert r.contains(Version(0, 2, 0))  # In range
        assert r.contains(Version(0, 2, 9))  # In range
        assert not r.contains(Version(0, 0, 9))  # Below minimum
        assert not r.contains(Version(0, 3, 0))  # At maximum (exclusive)
        assert not r.contains(Version(1, 0, 0))  # Above maximum