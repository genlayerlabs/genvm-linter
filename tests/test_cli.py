"""Unit tests for CLI entry-point helpers."""

import io
import sys

from genvm_linter.cli import _ensure_utf8_stdio


class TestEnsureUtf8Stdio:
    """Regression tests for issue #17: printing the ✓/✗ symbols crashed
    genvm-lint on Windows consoles whose active codepage isn't UTF-8
    (e.g. cp1254 for Turkish locales)."""

    def test_reproduces_crash_without_fix(self, monkeypatch):
        """Sanity check that the scenario really does crash before the fix,
        so this test suite would catch a regression if the guard were removed."""
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1254", errors="strict")

        raised = False
        try:
            stream.write("\u2713 Lint passed")
            stream.flush()
        except UnicodeEncodeError:
            raised = True

        assert raised

    def test_fix_prevents_crash_on_non_utf8_console(self, monkeypatch):
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1254", errors="strict")
        monkeypatch.setattr(sys, "stdout", stream)
        monkeypatch.setattr(sys, "stderr", stream)

        _ensure_utf8_stdio()

        # Must not raise even though cp1254 can't natively encode '✓'.
        sys.stdout.write("\u2713 Lint passed")
        sys.stdout.flush()

        raw.seek(0)
        assert raw.read().decode("utf-8") == "\u2713 Lint passed"

    def test_noop_when_stream_has_no_reconfigure(self, monkeypatch):
        """Streams without a reconfigure() method (e.g. some test runners'
        captured stdout) must be left alone rather than raising."""

        class _NoReconfigure:
            pass

        monkeypatch.setattr(sys, "stdout", _NoReconfigure())
        monkeypatch.setattr(sys, "stderr", _NoReconfigure())

        _ensure_utf8_stdio()  # should not raise
