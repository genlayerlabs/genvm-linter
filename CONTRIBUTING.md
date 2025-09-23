# Contributing to GenVM Linter

We welcome contributions to the GenVM Linter! This document provides guidelines for contributing to the project.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Node.js 16+ (for VS Code extension development)
- Git

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/genvm-linter.git
   cd genvm-linter
   ```

2. **Install Python Development Dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

3. **Install VS Code Extension Dependencies**
   ```bash
   cd vscode-extension
   npm install
   ```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 2. Make Your Changes

- Write clean, readable code
- Follow existing code style and patterns
- Add docstrings to new functions/classes
- Update tests for new functionality

### 3. Run Tests

**Python Linter Tests:**
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_rules.py

# Run with coverage
pytest --cov=genvm_linter tests/
```

**VS Code Extension Tests:**
```bash
cd vscode-extension
npm test
```

### 4. Code Quality Checks

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/
```

### 5. Test Your Changes

**Test Python Linter:**
```bash
# Test on a contract file
python -m genvm_linter.cli tests/fixtures/valid_contract.py

# Test with different options
python -m genvm_linter.cli --format json --severity error tests/
```

**Test VS Code Extension:**
1. Open VS Code in the `vscode-extension` directory
2. Press `F5` to launch Extension Development Host
3. Test the extension in the new VS Code window

## Adding New Validation Rules

### 1. Create a New Rule Class

Create a new file in `src/genvm_linter/rules/` or add to an existing file:

```python
# src/genvm_linter/rules/my_new_rule.py
from typing import List
import ast
from .base import Rule, ValidationResult, Severity

class MyNewRule(Rule):
    """Description of what this rule validates."""

    def validate(self, tree: ast.AST, source_code: str) -> List[ValidationResult]:
        """Validate the AST and return any issues found."""
        results = []

        # Your validation logic here
        # Walk the AST and check for issues

        for node in ast.walk(tree):
            if self.is_invalid(node):
                results.append(ValidationResult(
                    rule_id="genvm-my-rule",
                    message="Description of the issue",
                    severity=Severity.ERROR,
                    line=node.lineno,
                    column=node.col_offset,
                    suggestion="How to fix this issue"
                ))

        return results

    def is_invalid(self, node: ast.AST) -> bool:
        """Check if node violates the rule."""
        # Your validation logic
        return False
```

### 2. Register the Rule

Add your rule to the linter in `src/genvm_linter/linter.py`:

```python
from .rules.my_new_rule import MyNewRule

class GenVMLinter:
    def __init__(self):
        self.rules = [
            # ... existing rules
            MyNewRule(),  # Add your rule here
        ]
```

### 3. Add Tests

Create tests for your rule in `tests/unit/test_my_rule.py`:

```python
import pytest
from genvm_linter.rules.my_new_rule import MyNewRule

def test_my_rule_valid():
    rule = MyNewRule()
    source = """
    # Valid code that passes the rule
    """
    tree = ast.parse(source)
    results = rule.validate(tree, source)
    assert len(results) == 0

def test_my_rule_invalid():
    rule = MyNewRule()
    source = """
    # Invalid code that violates the rule
    """
    tree = ast.parse(source)
    results = rule.validate(tree, source)
    assert len(results) == 1
    assert results[0].rule_id == "genvm-my-rule"
```

## Adding VS Code Extension Features

### 1. Create a New Provider

Add to `vscode-extension/src/`:

```typescript
// my-provider.ts
import * as vscode from 'vscode';

export class MyProvider implements vscode.SomeProvider {
    // Implementation
}
```

### 2. Register in Extension

Update `vscode-extension/src/extension.ts`:

```typescript
import { MyProvider } from './my-provider';

export function activate(context: vscode.ExtensionContext) {
    const myProvider = new MyProvider();
    context.subscriptions.push(
        vscode.languages.registerSomeProvider('python', myProvider)
    );
}
```

## Code Style Guidelines

### Python Code Style

- Follow PEP 8
- Use type hints for all function parameters and returns
- Maximum line length: 88 characters (Black default)
- Use descriptive variable names
- Add docstrings to all public functions/classes

### TypeScript Code Style

- Use TypeScript strict mode
- Use `const` and `let`, never `var`
- Use async/await instead of callbacks
- Add JSDoc comments for public APIs
- Use meaningful variable and function names

### Commit Message Guidelines

Follow conventional commits format:

```
type(scope): brief description

Longer explanation if needed

Closes #123
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(rules): add validation for storage patterns
fix(types): correct u256 type checking in methods
docs: update installation instructions
```

## Pull Request Process

1. **Update Documentation**
   - Update README.md if adding new features
   - Update ARCHITECTURE.md for structural changes
   - Add/update docstrings and comments

2. **Ensure Tests Pass**
   - All existing tests must pass
   - Add tests for new functionality
   - Aim for high test coverage

3. **Update CHANGELOG**
   - Add your changes to CHANGELOG.md under "Unreleased"
   - Follow the existing format

4. **Create Pull Request**
   - Use a clear, descriptive title
   - Reference any related issues
   - Describe what changes you made and why
   - Include screenshots for UI changes

5. **Code Review**
   - Respond to review comments
   - Make requested changes
   - Be open to feedback

## Reporting Issues

### Bug Reports

Include:
- Python/Node.js version
- OS and version
- Steps to reproduce
- Expected behavior
- Actual behavior
- Error messages/stack traces
- Sample code that triggers the issue

### Feature Requests

Include:
- Use case description
- Proposed solution
- Alternative solutions considered
- Examples of the feature in action

## Testing Guidelines

### Unit Tests
- Test individual rules in isolation
- Mock external dependencies
- Test edge cases and error conditions

### Integration Tests
- Test complete contract validation
- Test CLI with various options
- Test VS Code extension features

### Test File Naming
- Unit tests: `test_<module_name>.py`
- Integration tests: `test_integration_<feature>.py`
- Fixtures: Place in `tests/fixtures/`

## Release Process

1. Update version in:
   - `pyproject.toml`
   - `vscode-extension/package.json`

2. Update CHANGELOG.md:
   - Move "Unreleased" items to new version section
   - Add release date

3. Create a release tag:
   ```bash
   git tag -a v0.2.0 -m "Release version 0.2.0"
   git push origin v0.2.0
   ```

4. Publish:
   - Python package: `python -m build && twine upload dist/*`
   - VS Code extension: `vsce publish`

## Community

- **Issues**: [GitHub Issues](https://github.com/genlayerlabs/genvm-linter/issues)
- **Discussions**: [GitHub Discussions](https://github.com/genlayerlabs/genvm-linter/discussions)
- **GenLayer Docs**: [docs.genlayer.com](https://docs.genlayer.com)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

If you have questions about contributing, please:
1. Check existing issues and discussions
2. Read the ARCHITECTURE.md for technical details
3. Open a new discussion for general questions
4. Contact the maintainers for specific concerns

Thank you for contributing to GenVM Linter!