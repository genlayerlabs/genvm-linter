# GenVM Linter Architecture

## Overview

The GenVM Linter is a Python-based validation system for GenLayer intelligent contracts, providing comprehensive rule-based checking and integration with Python's type system.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Python Linter (genvm-linter)                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │                  CLI Entry Point                    │    │
│  │              src/genvm_linter/cli.py               │    │
│  │  • Parses command-line arguments                   │    │
│  │  • Formats output (text/JSON)                      │    │
│  └──────────────────┬──────────────────────────────────┘    │
│                     │                                       │
│                     ▼                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │                Core Linter Engine                   │    │
│  │            src/genvm_linter/linter.py              │    │
│  │  • GenVMLinter class                               │    │
│  │  • Orchestrates all validation rules               │    │
│  │  • lint_file() and lint_source() methods           │    │
│  └──────────────────┬──────────────────────────────────┘    │
│                     │                                       │
│                     ▼                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │               Validation Rules                      │    │
│  │            src/genvm_linter/rules/                 │    │
│  │  • contract.py - Structure validation              │    │
│  │  • types.py - GenVM type system                    │    │
│  │  • decorators.py - Method decorators               │    │
│  │  • genvm_patterns.py - GenVM patterns              │    │
│  │  • python_types.py - MyPy integration              │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. CLI Interface (`src/genvm_linter/cli.py`)

The main command-line interface that users and external tools interact with:

```python
def main(paths, output_format, severity, rules, exclude_rules, stats):
    # Initialize linter with configuration
    linter = GenVMLinter()

    # Filter rules based on CLI arguments
    if rules:
        linter.rules = [r for r in linter.rules if r.rule_id in rules]

    # Lint specified paths
    for path in paths:
        results = linter.lint_file(path)

    # Format and output results (text or JSON)
    if output_format == 'json':
        output_json(results)
    else:
        output_text(results)
```

### 2. Core Linter (`src/genvm_linter/linter.py`)

The orchestration layer that manages all validation rules:

```python
class GenVMLinter:
    def __init__(self):
        self.rules = [
            MagicCommentRule(),
            ImportsRule(),
            ContractStructureRule(),
            ConstructorRule(),
            DecoratorRule(),
            StorageTypesRule(),
            ReturnTypesRule(),
            MyPyIntegrationRule()
        ]

    def lint_source(self, source_code: str) -> List[ValidationResult]:
        tree = ast.parse(source_code)
        results = []

        for rule in self.rules:
            if hasattr(rule, 'check_source'):
                results.extend(rule.check_source(source_code, tree))
            if hasattr(rule, 'check_node'):
                for node in ast.walk(tree):
                    results.extend(rule.check_node(node))

        return results
```

## Validation Rules

### Rule Categories

1. **Structure Rules** (`rules/contract.py`)
   - Magic comment validation
   - Import statement checking
   - Contract class structure
   - Constructor requirements

2. **Type System Rules** (`rules/types.py`)
   - Sized integer enforcement (u256, u64, etc.)
   - Collection type validation (TreeMap, DynArray)
   - Return type checking

3. **Decorator Rules** (`rules/decorators.py`)
   - Method decorator validation
   - State modification detection
   - Constructor decoration prevention

4. **Pattern Rules** (`rules/genvm_patterns.py`)
   - GenVM-specific API usage
   - Best practices enforcement

5. **MyPy Integration** (`rules/python_types.py`)
   - Python type checking
   - Type inference support

### Rule Implementation Pattern

Each rule follows a consistent pattern:

```python
class BaseRule:
    def __init__(self, rule_id: str):
        self.rule_id = rule_id

    def check_source(self, source: str, tree: ast.AST) -> List[ValidationResult]:
        """Check entire source file"""
        pass

    def check_node(self, node: ast.AST) -> List[ValidationResult]:
        """Check individual AST node"""
        pass
```

## Data Flow

1. **Input**: Python source file or code string
2. **Parsing**: Convert to AST using Python's `ast` module
3. **Validation**: Apply each rule to the AST
4. **Results**: Collect `ValidationResult` objects
5. **Output**: Format as text or JSON

## Configuration

The linter can be configured through:

1. **Command-line arguments**:
   - `--severity`: Minimum severity level
   - `--rule`: Specific rules to run
   - `--exclude-rule`: Rules to skip

2. **Python API**:
   ```python
   linter = GenVMLinter()
   linter.rules = [rule for rule in linter.rules if should_run(rule)]
   ```

## Integration Points

### External Tools

The linter provides a JSON output format for integration with IDEs and CI/CD pipelines:

```json
{
    "results": [
        {
            "rule_id": "genvm-types",
            "message": "Storage field must use sized integer",
            "severity": "error",
            "line": 10,
            "column": 4,
            "filename": "contract.py",
            "suggestion": "Change 'int' to 'u256'"
        }
    ],
    "summary": {
        "total": 1,
        "by_severity": {
            "error": 1,
            "warning": 0,
            "info": 0
        }
    }
}
```

### Python Package

The linter can be used as a Python library:

```python
from genvm_linter import GenVMLinter

linter = GenVMLinter()
results = linter.lint_file("contract.py")

for result in results:
    print(f"{result.severity}: {result.message}")
```

## Testing Strategy

### Unit Tests
- Individual rule validation
- Edge case handling
- Error message formatting

### Integration Tests
- Complete contract validation
- Multiple rule interaction
- CLI functionality

### Test Organization
```
tests/
├── unit/
│   ├── test_rules.py
│   └── test_linter.py
├── integration/
│   ├── test_complete_contracts.py
│   └── test_cli.py
└── fixtures/
    ├── valid_contracts/
    └── invalid_contracts/
```

## Performance Considerations

- **AST Parsing**: Single parse per file
- **Rule Execution**: Parallel rule checking where possible
- **Caching**: Results can be cached based on file modification time
- **Memory**: Minimal memory footprint, processes one file at a time

## Future Enhancements

1. **Incremental Linting**: Only re-check modified portions
2. **Auto-fix Capability**: Automatically fix certain issues
3. **Custom Rule Support**: Allow user-defined rules
4. **Performance Profiling**: Built-in performance metrics