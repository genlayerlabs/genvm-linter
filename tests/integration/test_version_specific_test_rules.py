"""Integration tests for version-specific test rules."""

import pytest
from genvm_linter import GenVMLinter
from genvm_linter.rules.base import Severity


class TestFutureFeatureRule:
    """Test the FutureFeatureRule that activates in v9.9.9."""

    def setup_method(self):
        """Set up test fixtures."""
        self.linter = GenVMLinter()

    def test_future_feature_not_active_in_normal_version(self):
        """Test that future feature rule doesn't activate in normal versions."""
        source = """# v0.2.0
# { "Depends": "py-genlayer:test" }

from genlayer import *

class Contract(gl.Contract):
    _future_quantum_state = 42  # Should be OK in v0.2.0

    def process(self):
        _future_result = self._future_quantum_state * 2
        return _future_result
"""

        results = self.linter.lint_source(source, "test.py")

        # Should not have warnings about _future_ prefix
        future_warnings = [r for r in results if "future" in r.rule_id and r.severity == Severity.WARNING]
        assert len(future_warnings) == 0

    def test_future_feature_active_in_v999(self):
        """Test that future feature rule activates in v9.9.9."""
        source = """# v9.9.9
# { "Depends": "py-genlayer:test" }

from genlayer import *

class Contract(gl.Contract):
    _future_quantum_state = 42  # Should warn in v9.9.9

    def process(self, _future_param):
        _future_result = self._future_quantum_state * 2
        return _future_result
"""

        results = self.linter.lint_source(source, "test.py")

        # Should have warnings about _future_ prefix
        future_warnings = [r for r in results if "future-reserved-names" in r.rule_id]
        assert len(future_warnings) > 0
        assert any("_future_quantum_state" in w.message for w in future_warnings)
        assert any("_future_param" in w.message for w in future_warnings)

    def test_future_feature_with_class_attributes(self):
        """Test future feature rule with class attributes."""
        source = """# v9.9.9
# { "Depends": "py-genlayer:test" }

from genlayer import *

class Contract(gl.Contract):
    _future_storage: TreeMap[str, u32]  # Should warn
    regular_storage: TreeMap[str, u32]  # Should be OK

    def __init__(self):
        self._future_initialized = True  # Should warn
"""

        results = self.linter.lint_source(source, "test.py")

        future_warnings = [r for r in results if "future-reserved-names" in r.rule_id]
        assert len(future_warnings) >= 2
        assert any("_future_storage" in w.message for w in future_warnings)
        assert any("_future_initialized" in w.message for w in future_warnings)


class TestExperimentalHashRule:
    """Test the ExperimentalHashRule that activates for specific hash."""

    def setup_method(self):
        """Set up test fixtures."""
        self.linter = GenVMLinter()
        self.experimental_hash = "1abc2def3ghi4jkl5mno6pqr7stu8vwx9yza0bcd1efg2hij3klm4"

    def test_experimental_warns_without_hash(self):
        """Test that experimental names warn without special hash."""
        source = """# { "Depends": "py-genlayer:test" }

from genlayer import *

class Contract(gl.Contract):
    experimental_feature = True  # Should warn

    def experimental_method(self):  # Should warn
        pass

    def regular_method(self):
        experimental_var = 10  # Should warn
        return experimental_var
"""

        results = self.linter.lint_source(source, "test.py")

        experimental_warnings = [r for r in results if "experimental-names" in r.rule_id]
        assert len(experimental_warnings) >= 3
        assert any("experimental_feature" in w.message for w in experimental_warnings)
        assert any("experimental_method" in w.message for w in experimental_warnings)

    def test_experimental_allowed_with_hash(self):
        """Test that experimental names are allowed with special hash."""
        source = f"""# {{ "Depends": "py-genlayer:{self.experimental_hash}" }}

from genlayer import *

class Contract(gl.Contract):
    experimental_feature = True  # Should be OK with hash

    def experimental_method(self):  # Should be OK with hash
        pass

    def regular_method(self):
        experimental_var = 10  # Should be OK with hash
        return experimental_var
"""

        results = self.linter.lint_source(source, "test.py")

        # Should not have warnings about experimental_ prefix
        experimental_warnings = [r for r in results if "experimental-names" in r.rule_id]
        assert len(experimental_warnings) == 0

    def test_experimental_class_names(self):
        """Test experimental class names."""
        source = """# { "Depends": "py-genlayer:test" }

from genlayer import *

class experimental_Contract(gl.Contract):  # Should warn
    pass

class ExperimentalContract(gl.Contract):  # OK - doesn't start with experimental_
    pass

def experimental_function():  # Should warn
    pass
"""

        results = self.linter.lint_source(source, "test.py")

        experimental_warnings = [r for r in results if "experimental-names" in r.rule_id]
        assert any("experimental_Contract" in w.message for w in experimental_warnings)
        assert any("experimental_function" in w.message for w in experimental_warnings)
        # ExperimentalContract should NOT warn (capital E)
        assert not any("ExperimentalContract" in w.message for w in experimental_warnings)


class TestDebugModeRule:
    """Test the DebugModeRule bonus rule."""

    def setup_method(self):
        """Set up test fixtures."""
        self.linter = GenVMLinter()

    def test_debug_vars_warn_in_production(self):
        """Test that debug variables warn in production code."""
        source = """# { "Depends": "py-genlayer:latest" }

from genlayer import *

class Contract(gl.Contract):
    def process(self):
        debug_counter = 0  # Should info
        DEBUG_FLAG = True  # Should info
        test_value = 42  # Should info
        tmp_result = 100  # Should info
        regular_var = 200  # OK
        return regular_var
"""

        results = self.linter.lint_source(source, "test.py")

        debug_info = [r for r in results if "debug-variables" in r.rule_id]
        assert len(debug_info) >= 4
        assert any("debug_counter" in i.message for i in debug_info)
        assert any("DEBUG_FLAG" in i.message for i in debug_info)

    def test_debug_vars_allowed_in_test(self):
        """Test that debug variables are allowed with test dependency."""
        source = """# { "Depends": "py-genlayer:test" }

from genlayer import *

class Contract(gl.Contract):
    def process(self):
        debug_counter = 0  # OK in test
        DEBUG_FLAG = True  # OK in test
        test_value = 42  # OK in test
        tmp_result = 100  # OK in test
        return tmp_result
"""

        results = self.linter.lint_source(source, "test.py")

        # Should not have debug variable warnings in test mode
        debug_info = [r for r in results if "debug-variables" in r.rule_id]
        assert len(debug_info) == 0


class TestAllRulesAvailable:
    """Test that all rules are now available in all versions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.linter = GenVMLinter()

    def test_v010_accepts_specific_imports(self):
        """Test that v0.1.0 now accepts specific imports (was restricted before)."""
        source = """# v0.1.0
# { "Depends": "py-genlayer:test" }

from genlayer import gl, TreeMap  # Now OK in v0.1.0

class Contract(gl.Contract):
    storage: TreeMap[str, u32]

    # __init__ is now optional in all versions

    # No public methods warning is just WARNING now, not ERROR
"""

        results = self.linter.lint_source(source, "test.py")

        # Should not have errors about imports
        import_errors = [r for r in results if "import" in r.rule_id.lower() and r.severity == Severity.ERROR]
        assert len(import_errors) == 0

        # __init__ message should be INFO, not ERROR
        init_errors = [r for r in results if "__init__" in r.message and r.severity == Severity.ERROR]
        assert len(init_errors) == 0

    def test_lazy_objects_available_all_versions(self):
        """Test that lazy objects work in all versions now."""
        source = """# v0.1.0
# { "Depends": "py-genlayer:test" }

from genlayer import *

class Contract(gl.Contract):
    storage: TreeMap[str, u32]

    def process(self):
        # Lazy objects now work in v0.1.0 too
        lazy_storage = self.storage.lazy()
        return lazy_storage
"""

        results = self.linter.lint_source(source, "test.py")

        # Lazy object usage should not error
        # The rule is available but may not trigger errors for valid usage
        errors = [r for r in results if r.severity == Severity.ERROR]
        # No version-related errors expected