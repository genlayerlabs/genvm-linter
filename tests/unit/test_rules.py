"""Tests for individual linting rules."""

import ast
import pytest

from genvm_linter.rules import (
    MagicCommentRule, ImportRule, ContractClassRule, 
    DecoratorRule, TypeSystemRule, Severity
)


class TestMagicCommentRule:
    """Test cases for magic comment rule."""
    
    def test_valid_magic_comment(self):
        """Test valid magic comment detection."""
        rule = MagicCommentRule()
        source = '# { "Depends": "py-genlayer:test" }\nfrom genlayer import *'
        
        results = rule.check(source)
        assert len(results) == 0, "Valid magic comment should not produce errors"
    
    def test_missing_magic_comment(self):
        """Test missing magic comment detection."""
        rule = MagicCommentRule()
        source = 'from genlayer import *\nclass Test: pass'
        
        results = rule.check(source)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "missing" in results[0].message.lower()
    
    def test_incorrect_magic_comment(self):
        """Test incorrect magic comment detection."""
        rule = MagicCommentRule()
        source = '# Wrong comment\nfrom genlayer import *'
        
        results = rule.check(source)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
    
    def test_empty_file(self):
        """Test empty file handling."""
        rule = MagicCommentRule()
        source = ''
        
        results = rule.check(source)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "empty" in results[0].message.lower()


class TestImportRule:
    """Test cases for import rule."""
    
    def test_valid_import(self):
        """Test valid GenLayer import detection."""
        rule = ImportRule()
        source = 'from genlayer import *'
        tree = ast.parse(source)
        
        results = rule.check(tree)
        assert len(results) == 0, "Valid import should not produce errors"
    
    def test_missing_import(self):
        """Test missing import detection."""
        rule = ImportRule()
        source = 'import os\nclass Test: pass'
        tree = ast.parse(source)
        
        results = rule.check(tree)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "missing" in results[0].message.lower()
    
    def test_wrong_import(self):
        """Test wrong import detection."""
        rule = ImportRule()
        source = 'from genlayer import Contract'  # Should be import *
        tree = ast.parse(source)
        
        results = rule.check(tree)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR


class TestContractClassRule:
    """Test cases for contract class rule."""
    
    def test_valid_contract_class(self):
        """Test valid contract class detection."""
        rule = ContractClassRule()
        source = '''
class TestContract(gl.Contract):
    def __init__(self):
        pass
'''
        tree = ast.parse(source)
        
        results = rule.check(tree)
        assert len(results) == 0, "Valid contract class should not produce errors"
    
    def test_missing_contract_class(self):
        """Test missing contract class detection."""
        rule = ContractClassRule()
        source = 'class RegularClass: pass'
        tree = ast.parse(source)
        
        results = rule.check(tree)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "no contract class" in results[0].message.lower()
    
    def test_multiple_contract_classes(self):
        """Test multiple contract classes detection."""
        rule = ContractClassRule()
        source = '''
class Contract1(gl.Contract):
    pass

class Contract2(gl.Contract):
    pass
'''
        tree = ast.parse(source)
        
        results = rule.check(tree)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "multiple contract classes" in results[0].message.lower()
    
    def test_missing_constructor(self):
        """Test missing constructor detection."""
        rule = ContractClassRule()
        source = '''
class TestContract(gl.Contract):
    @gl.public.view
    def get_value(self):
        return 42
'''
        tree = ast.parse(source)
        
        results = rule.check(tree)
        assert len(results) == 1
        assert results[0].severity == Severity.WARNING
        assert "__init__" in results[0].message


class TestTypeSystemRule:
    """Test cases for type system rule."""
    
    def test_valid_storage_types(self):
        """Test valid storage type usage."""
        rule = TypeSystemRule()
        source = '''
class TestContract(gl.Contract):
    balance: u256
    users: TreeMap[str, u64]
    items: DynArray[str]
'''
        tree = ast.parse(source)
        
        results = rule.check(tree)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0, "Valid storage types should not produce errors"
    
    def test_invalid_storage_int(self):
        """Test invalid int usage in storage."""
        rule = TypeSystemRule()
        source = '''
class TestContract(gl.Contract):
    balance: int
'''
        tree = ast.parse(source)
        
        results = rule.check(tree)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "uses 'int' type" in errors[0].message
    
    def test_invalid_collection_types(self):
        """Test invalid collection type usage."""
        rule = TypeSystemRule()
        source = '''
class TestContract(gl.Contract):
    users: dict[str, int]
    items: list[str]
'''
        tree = ast.parse(source)
        
        results = rule.check(tree)
        errors = [r for r in results if r.severity == Severity.ERROR]
        
        # Should detect both dict and list usage
        assert len(errors) == 2
        messages = [e.message for e in errors]
        assert any("uses 'dict' type" in msg for msg in messages)
        assert any("uses 'list' type" in msg for msg in messages)
    
    def test_return_type_validation(self):
        """Test return type validation."""
        rule = TypeSystemRule()
        source = '''
class TestContract(gl.Contract):
    @gl.public.view
    def get_balance(self) -> u256:  # Should be int
        return 0
    
    @gl.public.view  
    def get_count(self) -> int:  # This is correct
        return 1
'''
        tree = ast.parse(source)
        
        results = rule.check(tree)
        errors = [r for r in results if r.severity == Severity.ERROR]
        
        # Should detect u256 return type
        assert len(errors) == 1
        assert "returns 'u256' type" in errors[0].message


class TestDecoratorRule:
    """Test cases for decorator rule."""
    
    def test_valid_decorators(self):
        """Test valid decorator usage."""
        rule = DecoratorRule()
        source = '''
class TestContract(gl.Contract):
    def __init__(self):  # No decorator - correct
        pass
    
    @gl.public.view
    def get_value(self):
        return 42
    
    @gl.public.write
    def set_value(self, value):
        self.value = value
    
    def _private_method(self):  # No decorator - correct
        pass
'''
        tree = ast.parse(source)
        
        results = rule.check(tree)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0, "Valid decorators should not produce errors"
    
    def test_missing_decorator(self):
        """Test missing decorator detection."""
        rule = DecoratorRule()
        source = '''
class TestContract(gl.Contract):
    def get_value(self):  # Missing decorator
        return 42
'''
        tree = ast.parse(source)
        
        results = rule.check(tree)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "missing @gl.public decorator" in errors[0].message
    
    def test_constructor_with_decorator(self):
        """Test constructor with decorator detection."""
        rule = DecoratorRule()
        source = '''
class TestContract(gl.Contract):
    @gl.public.view
    def __init__(self):  # Constructor should not have decorator
        pass
'''
        tree = ast.parse(source)
        
        results = rule.check(tree)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "constructor" in errors[0].message.lower()
    
    def test_multiple_decorators(self):
        """Test multiple decorators detection."""
        rule = DecoratorRule()
        source = '''
class TestContract(gl.Contract):
    @gl.public.view
    @gl.public.write
    def method(self):  # Multiple decorators
        pass
'''
        tree = ast.parse(source)
        
        results = rule.check(tree)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "multiple @gl.public decorators" in errors[0].message