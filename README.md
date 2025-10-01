# GenVM Linter

A Python linter specifically designed for GenLayer GenVM intelligent contracts. This linter validates GenLayer intelligent contracts according to GenVM's type system and coding conventions.

## Features

✨ **Comprehensive Validation**
- Magic comment validation (`# { "Depends": "py-genlayer:test" }`)
- GenLayer import checking (`from genlayer import *`)
- Contract class structure validation
- Method decorator validation (`@gl.public.view`, `@gl.public.write`)
- Type system enforcement (sized integers, collections, dataclasses)

🔧 **Type System Rules**
- Enforces use of sized integers (`u64`, `u256`, etc.) in storage fields
- Prevents use of `int` return types (should use `int` instead of `u256`)
- Validates proper collection types (`DynArray` vs `list`, `TreeMap` vs `dict`)
- Checks `@allow_storage` decorator usage on dataclasses

🎯 **Smart Error Detection**
- Detects missing or incorrect decorators
- Identifies state modification in view methods
- Validates constructor decoration rules
- Comprehensive error messages with suggestions

🚀 **Version Awareness**
- Automatic version detection from contract comments
- Version-aware rule infrastructure
- Support for version and hash-based rule activation
- Test rules demonstrating version/hash-specific behavior

## Installation

### From Source

```bash
git clone https://github.com/genlayerlabs/genvm-linter.git
cd genvm-linter
pip install -e .
```

### Using pip (when published)

```bash
pip install genvm-linter
```

## Usage

### Command Line

```bash
# Lint a single file
genvm-lint contract.py

# Lint all Python files in a directory
genvm-lint contracts/

# Show only errors
genvm-lint --severity error contract.py

# Output as JSON
genvm-lint --format json contract.py

# Show statistics
genvm-lint --stats contracts/

# Run specific rules only
genvm-lint --rule genvm-types --rule genvm-decorators contract.py

# Exclude specific rules
genvm-lint --exclude-rule genvm-magic-comment contract.py
```

### Python API

```python
from genvm_linter import GenVMLinter

# Create linter instance (version-aware by default)
linter = GenVMLinter()

# Or disable version awareness for traditional behavior
linter = GenVMLinter(use_version_aware=False)

# Lint a file
results = linter.lint_file("path/to/contract.py")

# Lint source code directly
source_code = '''
# { "Depends": "py-genlayer:test" }
from genlayer import *

class MyContract(gl.Contract):
    balance: u256
    
    def __init__(self, initial_balance: int):
        self.balance = initial_balance
    
    @gl.public.view
    def get_balance(self) -> int:
        return self.balance
'''

results = linter.lint_source(source_code)

# Process results
for result in results:
    print(f"{result.severity.value}: {result.message}")
    if result.suggestion:
        print(f"💡 {result.suggestion}")
```

## Version Detection

The linter automatically detects version information from your contracts:

### Version Specification

Contracts can specify their GenVM version using:

```python
# Method 1: Explicit version comment
# v0.1.0
# { "Depends": "py-genlayer:test" }

# Method 2: Version in dependency
# { "Depends": "py-genlayer:0.2.0" }

# Method 3: Using dependency hash
# { "Depends": "py-genlayer:1abc2def3ghi4jkl5mno6pqr7stu8vwx9yza0bcd1efg2hij3klm4" }
```

If no version is specified, the linter uses "latest".

### Test Rules

The linter includes test rules demonstrating the version-aware capabilities:

#### FutureFeatureRule
- **Activation:** Only in version 9.9.9
- **Behavior:** Warns about variables starting with `_future_`
- **Purpose:** Demonstrates version-specific rule activation

#### ExperimentalHashRule
- **Activation:** Always active except with specific hash
- **Disabled when:** Using hash `1abc2def3ghi4jkl5mno6pqr7stu8vwx9yza0bcd1efg2hij3klm4`
- **Behavior:** Warns about `experimental_` prefix
- **Purpose:** Demonstrates hash-specific rule control
- **Note:** Infrastructure supports multiple hashes via `allowed_hashes` and `excluded_hashes` lists for future rules

#### DebugModeRule
- **Activation:** Always active in production
- **Disabled when:** Using `py-genlayer:test` dependency
- **Behavior:** Warns about debug variables (`debug_`, `test_`, `tmp_`)
- **Purpose:** Keeps production code clean

### Version Information API

```python
# Get version information from source
info = linter.get_version_info(source_code)
print(info["version"])  # Detected version
print(info["dependencies"])  # Dependencies dict
print(info["features"])  # Available features for this version
```

## Validation Rules

All validation rules are currently enabled for all versions. The version-aware infrastructure allows for future version-specific rules.

### Required Structure Rules

| Rule ID | Description |
|---------|-------------|
| `genvm-magic-comment` | First line must contain `# { "Depends": "py-genlayer:test" }` |
| `genvm-import` | Must include `from genlayer import *` |
| `genvm-contract-class` | Exactly one class extending `gl.Contract` |

### Decorator Rules  

| Rule ID | Description |
|---------|-------------|
| `genvm-decorators` | Proper usage of `@gl.public.view` and `@gl.public.write` |

**Decorator Requirements:**
- `__init__` methods must NOT have public decorators
- Public methods must have exactly one `@gl.public.*` decorator
- Private methods (starting with `_`) should not have public decorators
- Use `@gl.public.view` for read-only methods
- Use `@gl.public.write` for state-modifying methods

### Type System Rules

| Rule ID | Description |
|---------|-------------|
| `genvm-types` | Validates GenVM type system usage |

**Type System Requirements:**

#### Storage Fields
- ✅ Use sized integers: `u8`, `u16`, `u32`, `u64`, `u128`, `u256`, `i8`, `i16`, etc.
- ❌ Don't use plain `int` in storage annotations
- ✅ Use `DynArray[T]` instead of `list[T]`
- ✅ Use `TreeMap[K, V]` instead of `dict[K, V]`

#### Method Return Types
- ✅ Use `int` for return type annotations
- ❌ Don't use sized integers (`u256`, etc.) in return types

#### Dataclasses
- Use `@allow_storage` decorator for dataclasses used in storage
- Consider sized integers for dataclass fields

## Example: Valid Contract

```python
# { "Depends": "py-genlayer:test" }

from genlayer import *
from dataclasses import dataclass

@allow_storage
@dataclass
class UserData:
    name: str
    balance: u256
    is_active: bool

class TokenContract(gl.Contract):
    owner: Address
    users: TreeMap[Address, UserData]
    total_supply: u256

    def __init__(self, initial_supply: int):
        self.owner = gl.message.sender_address
        self.total_supply = initial_supply

    @gl.public.view
    def get_balance(self, user: str) -> int:
        address = Address(user)
        user_data = self.users.get(address)
        return user_data.balance if user_data else 0

    @gl.public.write
    def transfer(self, to: str, amount: int):
        # Transfer logic here
        to_address = Address(to)
        # ... implementation
```

## Example: Common Issues

```python
# ❌ Missing magic comment
from genlayer import *  # Should have magic comment above

class BadContract(gl.Contract):
    balance: int  # ❌ Should be u256
    users: dict[str, int]  # ❌ Should be TreeMap[Address, u256]
    items: list[str]  # ❌ Should be DynArray[str]

    def __init__(self, initial_balance: int):
        self.balance = initial_balance

    # ❌ Missing decorator
    def get_balance(self) -> u256:  # ❌ Should return int
        return self.balance

    @gl.public.view  # ❌ Wrong decorator for state modification
    def set_balance(self, amount: int):
        self.balance = amount
```

## Development

### Setup Development Environment

```bash
git clone https://github.com/genlayerlabs/genvm-linter.git
cd genvm-linter

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run linter on itself
genvm-lint src/

# Format code
black src/ tests/
isort src/ tests/

# Type checking
mypy src/
```

### Project Structure

```
genvm-linter/
├── src/genvm_linter/
│   ├── __init__.py          # Main package
│   ├── linter.py            # Core linter with version awareness
│   ├── cli.py               # Command-line interface
│   ├── version.py           # Version management
│   ├── rule_registry.py     # Rule registry system
│   └── rules/               # Validation rules
│       ├── __init__.py
│       ├── base.py          # Base rule classes
│       ├── versioned.py     # Version-aware rule base
│       ├── contract.py      # Contract structure rules
│       ├── decorators.py    # Decorator validation
│       ├── types.py         # Type system rules
│       ├── genvm_patterns.py # GenVM API patterns
│       ├── python_types.py  # MyPy integration
│       └── test_rules.py    # Test/demo rules
├── tests/
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   ├── fixtures/            # Test contract files
│   └── examples/            # Example contracts
├── config/
│   └── versions.yaml        # Version configuration
├── docs/
│   └── VERSION_RULES.md     # Detailed version docs
├── examples/
│   └── versioned_contracts.py # Version examples
├── ARCHITECTURE.md          # System architecture
├── CONTRIBUTING.md          # Contribution guidelines
├── CHANGELOG.md             # Version history
├── pyproject.toml           # Package configuration
└── README.md                # This file
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Python linter architecture and rule system
- [CONTRIBUTING.md](CONTRIBUTING.md) - Guidelines for contributing to the project
- [CHANGELOG.md](CHANGELOG.md) - Version history and release notes
- [docs/VERSION_RULES.md](docs/VERSION_RULES.md) - Detailed version-aware rules documentation
- [examples/versioned_contracts.py](examples/versioned_contracts.py) - Example contracts with different versions

## VS Code Extension

The VS Code extension for this linter is maintained in a separate repository:
[GenLayer VS Code Extension](https://github.com/genlayerlabs/vscode-extension)

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on how to contribute to this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Related Projects

- [GenLayer](https://www.genlayer.com/) - The GenLayer protocol
- [GenLayer CLI](https://github.com/genlayerlabs/genlayer-cli) - Command-line tools for GenLayer
- [GenLayer Studio](https://studio.genlayer.com/) - Web IDE for GenLayer development
- [GenLayer Documentation](https://docs.genlayer.com/) - Complete GenLayer documentation