#!/usr/bin/env python3
"""
Example usage of the GenVM Linter.
This demonstrates how to use the linter programmatically.
"""

import sys
from pathlib import Path

# Add the src directory to Python path for direct usage
sys.path.insert(0, str(Path(__file__).parent / "src"))

from genvm_linter import GenVMLinter
from genvm_linter.rules import Severity

def main():
    # Create linter instance
    linter = GenVMLinter()
    
    # Example contract source code with various issues
    invalid_contract = '''
# Missing magic comment!
from genlayer import *

class BadContract(gl.Contract):
    balance: int  # Should use u256
    users: dict[str, int]  # Should use TreeMap
    
    def __init__(self):
        self.balance = 0
    
    def get_balance(self) -> u256:  # Missing decorator, wrong return type
        return self.balance
    
    @gl.public.view
    def set_balance(self, amount: int):  # Wrong decorator for state modification
        self.balance = amount
'''
    
    # Lint the source code
    print("🔍 Linting invalid contract...")
    results = linter.lint_source(invalid_contract, "example.py")
    
    # Display results
    error_count = 0
    warning_count = 0
    
    for result in results:
        if result.severity == Severity.ERROR:
            color = "🔴"
            error_count += 1
        elif result.severity == Severity.WARNING:
            color = "🟡"
            warning_count += 1
        else:
            color = "🔵"
        
        print(f"{color} Line {result.line}: {result.message}")
        if result.suggestion:
            print(f"   💡 Suggestion: {result.suggestion}")
        print()
    
    print(f"Summary: {error_count} errors, {warning_count} warnings")
    
    # Example of a valid contract
    valid_contract = '''# { "Depends": "py-genlayer:test" }

from genlayer import *

class GoodContract(gl.Contract):
    balance: u256
    users: TreeMap[Address, u256]
    
    def __init__(self, initial_balance: int):
        self.balance = initial_balance
    
    @gl.public.view
    def get_balance(self) -> int:
        return self.balance
    
    @gl.public.write
    def set_balance(self, amount: int):
        self.balance = amount
'''
    
    print("\n✅ Linting valid contract...")
    results = linter.lint_source(valid_contract, "valid_example.py")
    
    if not results:
        print("🎉 No issues found! Contract is valid.")
    else:
        print(f"Found {len(results)} issues:")
        for result in results:
            print(f"  {result.severity.value}: {result.message}")

if __name__ == "__main__":
    main()