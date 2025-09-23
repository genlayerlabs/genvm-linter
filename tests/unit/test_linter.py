"""Tests for GenVM linter."""

import pytest
from pathlib import Path

from genvm_linter import GenVMLinter
from genvm_linter.rules import Severity


class TestGenVMLinter:
    """Test cases for the main linter class."""
    
    def test_valid_contract(self):
        """Test that a valid contract produces no errors."""
        linter = GenVMLinter()
        fixture_path = Path(__file__).parent / "fixtures" / "valid_contract.py"
        
        results = linter.lint_file(fixture_path)
        
        # Should have no errors
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0, f"Valid contract should have no errors, got: {errors}"
    
    def test_invalid_contract_magic_comment(self):
        """Test detection of missing magic comment."""
        linter = GenVMLinter()
        fixture_path = Path(__file__).parent / "fixtures" / "invalid_contract.py"
        
        results = linter.lint_file(fixture_path)
        
        # Should detect missing magic comment
        magic_comment_errors = [r for r in results if r.rule_id == "genvm-magic-comment"]
        assert len(magic_comment_errors) > 0, "Should detect missing magic comment"
    
    def test_missing_import(self):
        """Test detection of missing GenLayer import."""
        linter = GenVMLinter()
        fixture_path = Path(__file__).parent / "fixtures" / "missing_import.py"
        
        results = linter.lint_file(fixture_path)
        
        # Should detect missing import
        import_errors = [r for r in results if r.rule_id == "genvm-import"]
        assert len(import_errors) > 0, "Should detect missing GenLayer import"
    
    def test_no_contract_class(self):
        """Test detection of missing contract class."""
        linter = GenVMLinter()
        fixture_path = Path(__file__).parent / "fixtures" / "no_contract.py"
        
        results = linter.lint_file(fixture_path)
        
        # Should detect missing contract class
        contract_errors = [r for r in results if r.rule_id == "genvm-contract-class"]
        assert len(contract_errors) > 0, "Should detect missing contract class"
    
    def test_type_system_violations(self):
        """Test detection of type system violations."""
        linter = GenVMLinter()
        fixture_path = Path(__file__).parent / "fixtures" / "invalid_contract.py"
        
        results = linter.lint_file(fixture_path)
        
        # Should detect type violations
        type_errors = [r for r in results if r.rule_id == "genvm-types"]
        assert len(type_errors) > 0, "Should detect type system violations"
        
        # Check specific violations
        error_messages = [r.message for r in type_errors]
        
        # Should detect int usage instead of sized integers
        assert any("uses 'int' type" in msg for msg in error_messages), \
            "Should detect plain 'int' usage in storage"
        
        # Should detect dict instead of TreeMap
        assert any("uses 'dict' type" in msg for msg in error_messages), \
            "Should detect 'dict' usage instead of TreeMap"
        
        # Should detect list instead of DynArray  
        assert any("uses 'list' type" in msg for msg in error_messages), \
            "Should detect 'list' usage instead of DynArray"
        
        # Should detect sized integer in return type
        assert any("returns 'u256' type" in msg for msg in error_messages), \
            "Should detect sized integer in return type"
    
    def test_decorator_violations(self):
        """Test detection of decorator violations."""
        linter = GenVMLinter()
        fixture_path = Path(__file__).parent / "fixtures" / "invalid_contract.py"
        
        results = linter.lint_file(fixture_path)
        
        # Should detect decorator violations
        decorator_errors = [r for r in results if r.rule_id == "genvm-decorators"]
        assert len(decorator_errors) > 0, "Should detect decorator violations"
        
        error_messages = [r.message for r in results]
        
        # Should detect missing decorator
        assert any("is missing @gl.public decorator" in msg for msg in error_messages), \
            "Should detect missing decorator"
        
        # Should detect multiple decorators
        assert any("has multiple @gl.public decorators" in msg for msg in error_messages), \
            "Should detect multiple decorators"
        
        # Should detect wrong decorator on constructor
        assert any("Constructor (__init__) method should not have public decorators" in msg 
                  for msg in error_messages), \
            "Should detect decorator on constructor"
    
    def test_source_code_linting(self):
        """Test linting source code directly."""
        linter = GenVMLinter()
        
        valid_source = '''# { "Depends": "py-genlayer:test" }

from genlayer import *

class TestContract(gl.Contract):
    value: u256

    def __init__(self):
        self.value = 0

    @gl.public.view
    def get_value(self) -> int:
        return self.value
'''
        
        results = linter.lint_source(valid_source)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0, f"Valid source should have no errors, got: {errors}"
    
    def test_syntax_error_handling(self):
        """Test handling of Python syntax errors."""
        linter = GenVMLinter()
        
        invalid_source = '''# { "Depends": "py-genlayer:test" }

from genlayer import *

class TestContract(gl.Contract
    # Missing colon and indentation issues
'''
        
        results = linter.lint_source(invalid_source, "test.py")
        
        # Should detect syntax error
        syntax_errors = [r for r in results if r.rule_id == "syntax-error"]
        assert len(syntax_errors) > 0, "Should detect syntax error"
    
    def test_file_not_found(self):
        """Test handling of non-existent files."""
        linter = GenVMLinter()
        
        results = linter.lint_file("non_existent_file.py")
        
        # Should return file not found error
        assert len(results) == 1
        assert results[0].rule_id == "file-not-found"
        assert results[0].severity == Severity.ERROR
    
    def test_directory_linting(self):
        """Test linting a directory."""
        linter = GenVMLinter()
        fixtures_dir = Path(__file__).parent / "fixtures"
        
        results = linter.lint_directory(fixtures_dir)
        
        # Should have results from all fixture files
        assert len(results) > 0, "Should find issues in fixture files"
        
        # Should have results from multiple files
        filenames = {r.filename for r in results if r.filename}
        assert len(filenames) > 1, "Should lint multiple files"