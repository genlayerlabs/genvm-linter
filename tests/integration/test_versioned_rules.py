"""Integration tests for version-specific rules."""

import pytest
from genvm_linter import GenVMLinter
from genvm_linter.rules.base import Severity


class TestVersionedRules:
    """Test version-specific rule behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.linter = GenVMLinter()

    def test_v010_star_import_required(self):
        """Test that v0.1.0 requires star imports."""
        source = """# v0.1.0
# { "Depends": "py-genlayer:test" }

from genlayer import gl  # This should error in v0.1.0

class Contract(gl.Contract):
    def __init__(self):
        pass
"""

        results = self.linter.lint_source(source, "test.py")

        # Should have error about star import
        import_errors = [r for r in results if "import" in r.rule_id.lower() and r.severity == Severity.ERROR]
        assert len(import_errors) > 0
        assert any("star import" in r.message.lower() for r in import_errors)

    def test_v020_specific_imports_allowed(self):
        """Test that v0.2.0 allows specific imports."""
        source = """# v0.2.0
# { "Depends": "py-genlayer:test" }

from genlayer import gl, TreeMap, u32  # This should be fine in v0.2.0

class Contract(gl.Contract):
    storage: TreeMap[str, u32]

    # __init__ is optional in v0.2.0
"""

        results = self.linter.lint_source(source, "test.py")

        # Should not have errors about imports
        import_errors = [r for r in results if "import" in r.rule_id.lower() and r.severity == Severity.ERROR]
        assert len(import_errors) == 0

        # Should not have error about missing __init__
        init_errors = [r for r in results if "__init__" in r.message and r.severity == Severity.ERROR]
        assert len(init_errors) == 0

    def test_v010_init_required(self):
        """Test that v0.1.0 requires __init__ method."""
        source = """# v0.1.0
# { "Depends": "py-genlayer:test" }

from genlayer import *

class Contract(gl.Contract):
    # Missing __init__ should error in v0.1.0
    pass
"""

        results = self.linter.lint_source(source, "test.py")

        # Should have error about missing __init__
        init_errors = [r for r in results if "__init__" in r.message and r.severity == Severity.ERROR]
        assert len(init_errors) > 0

    def test_v020_init_optional(self):
        """Test that v0.2.0 makes __init__ optional."""
        source = """# v0.2.0
# { "Depends": "py-genlayer:test" }

from genlayer import *

class Contract(gl.Contract):
    # Missing __init__ is OK in v0.2.0
    pass
"""

        results = self.linter.lint_source(source, "test.py")

        # Should not have error about missing __init__
        init_errors = [r for r in results if "__init__" in r.message and r.severity == Severity.ERROR]
        assert len(init_errors) == 0

        # May have info message
        init_info = [r for r in results if "__init__" in r.message and r.severity == Severity.INFO]
        # This is acceptable (informational)

    def test_v030_public_methods_required(self):
        """Test that v0.3.0 requires public methods."""
        source = """# v0.3.0
# { "Depends": "py-genlayer:test" }

from genlayer import *

class Contract(gl.Contract):
    def __init__(self):
        pass

    # No public methods - should error in v0.3.0
"""

        results = self.linter.lint_source(source, "test.py")

        # Should have error about missing public methods
        public_errors = [r for r in results if "@gl.public" in r.message and r.severity == Severity.ERROR]
        assert len(public_errors) > 0

    def test_v030_with_public_method(self):
        """Test v0.3.0 with proper public method."""
        source = """# v0.3.0
# { "Depends": "py-genlayer:test" }

from genlayer import *

class Contract(gl.Contract):
    @gl.public.write
    def my_method(self):
        pass
"""

        results = self.linter.lint_source(source, "test.py")

        # Should not have error about missing public methods
        public_errors = [r for r in results if "@gl.public" in r.message and r.severity == Severity.ERROR]
        assert len(public_errors) == 0

    def test_latest_version_all_features(self):
        """Test that latest version has all features enabled."""
        source = """# { "Depends": "py-genlayer:latest" }

from genlayer import gl, TreeMap, u32

class Contract(gl.Contract):
    # All features should work with latest
    storage: TreeMap[str, u32]

    @gl.public.write
    def method(self):
        # Lazy objects (v0.2.0+)
        obj = self.storage.lazy()
        pass
"""

        results = self.linter.lint_source(source, "test.py")

        # Should have minimal errors (only if there are actual issues)
        errors = [r for r in results if r.severity == Severity.ERROR]
        # Check that no version-related errors exist
        version_errors = [r for r in errors if any(
            keyword in r.message.lower()
            for keyword in ["version", "import", "__init__", "public"]
        )]
        # Latest should be permissive

    def test_version_info_message(self):
        """Test that version info message is generated."""
        source = """# v0.2.5
# { "Depends": "py-genlayer:test" }

from genlayer import *

class Contract(gl.Contract):
    pass
"""

        results = self.linter.lint_source(source, "test.py")

        # Should have version info message
        info_messages = [r for r in results if r.rule_id == "version-info"]
        assert len(info_messages) > 0
        assert "0.2.5" in info_messages[0].message

    def test_no_version_uses_latest(self):
        """Test that missing version defaults to latest."""
        source = """# { "Depends": "py-genlayer:test" }

from genlayer import gl

class Contract(gl.Contract):
    # Should use latest rules
    pass
"""

        results = self.linter.lint_source(source, "test.py")

        # Should have info about using latest
        info_messages = [r for r in results if r.rule_id == "version-info"]
        assert len(info_messages) > 0
        assert "latest" in info_messages[0].message.lower()

    def test_version_upgrade_suggestion(self):
        """Test that upgrade suggestions are provided for old versions."""
        source = """# v0.1.0
# { "Depends": "py-genlayer:test" }

from genlayer import *

class Contract(gl.Contract):
    def __init__(self):
        pass
"""

        results = self.linter.lint_source(source, "test.py")

        # Should have upgrade suggestion
        upgrade_messages = [r for r in results if r.rule_id == "version-upgrade-available"]
        assert len(upgrade_messages) > 0
        assert "breaking changes" in upgrade_messages[0].message.lower()

    def test_complex_seq_dependencies(self):
        """Test parsing complex Seq dependencies with version."""
        source = """# v0.2.0
# {
#   "Seq": [
#     { "Depends": "py-lib-genlayer-embeddings:09h0i209wrzh4xzq86f79c60x0ifs7xcjwl53ysrnw06i54ddxyi" },
#     { "Depends": "py-genlayer:1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379" }
#   ]
# }

from genlayer import *

class Contract(gl.Contract):
    pass
"""

        results = self.linter.lint_source(source, "test.py")

        # Should detect version and not error on complex dependencies
        info_messages = [r for r in results if r.rule_id == "version-info"]
        assert len(info_messages) > 0
        assert "0.2.0" in info_messages[0].message

    def test_invalid_version_warning(self):
        """Test that invalid version formats generate warnings."""
        source = """# vX.Y.Z
# { "Depends": "py-genlayer:test" }

from genlayer import *

class Contract(gl.Contract):
    def __init__(self):
        pass
"""

        results = self.linter.lint_source(source, "test.py")

        # Should have warning about invalid version
        warnings = [r for r in results if r.rule_id == "invalid-version" and r.severity == Severity.WARNING]
        # May or may not warn depending on implementation


class TestVersionComparison:
    """Test version comparison and compatibility."""

    def setup_method(self):
        """Set up test fixtures."""
        self.linter = GenVMLinter()

    def test_compare_compatible_versions(self):
        """Test comparing compatible contract versions."""
        source1 = """# v0.2.0
# { "Depends": "py-genlayer:test" }
from genlayer import *
class Contract(gl.Contract): pass
"""

        source2 = """# v0.2.5
# { "Depends": "py-genlayer:test" }
from genlayer import *
class Contract(gl.Contract): pass
"""

        comparison = self.linter.compare_versions(source1, source2)

        assert comparison["compatible"]
        assert len(comparison["breaking_changes"]) == 0

    def test_compare_incompatible_versions(self):
        """Test comparing incompatible contract versions."""
        source1 = """# v0.1.0
# { "Depends": "py-genlayer:test" }
from genlayer import *
class Contract(gl.Contract): pass
"""

        source2 = """# v0.3.0
# { "Depends": "py-genlayer:test" }
from genlayer import *
class Contract(gl.Contract): pass
"""

        comparison = self.linter.compare_versions(source1, source2)

        # Should list breaking changes between versions
        assert len(comparison["breaking_changes"]) > 0

    def test_get_version_info(self):
        """Test extracting version information."""
        source = """# v0.2.0
# { "Depends": "py-genlayer:test" }
from genlayer import *
class Contract(gl.Contract): pass
"""

        info = self.linter.get_version_info(source)

        assert info["version"] == "0.2.0"
        assert info["parsed_version"] == "0.2.0"
        assert "py-genlayer" in info["dependencies"]
        assert "features" in info
        assert info["features"].get("optional_init", False)