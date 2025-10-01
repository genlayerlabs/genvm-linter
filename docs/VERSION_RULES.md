# Version-Based Rules System

The GenVM linter includes a version-aware rule system that can adapt validation based on the GenVM version or dependency hash specified in contracts. This infrastructure enables version-specific and hash-specific rule behavior.

## Current State

**All base validation rules are currently enabled for all versions.** The version-aware infrastructure is in place for future version-specific rules.

## Version Declaration

Contracts can specify their GenVM version in three ways:

### 1. Explicit Version Comment
```python
# v0.1.0
# { "Depends": "py-genlayer:test" }
```

### 2. Version in Dependencies
```python
# { "Depends": "py-genlayer:0.2.0" }
```

### 3. Hash in Dependencies
```python
# { "Depends": "py-genlayer:1abc2def3ghi4jkl5mno6pqr7stu8vwx9yza0bcd1efg2hij3klm4" }
```

If no version is specified, the linter uses "latest".

## Test Rules

The linter includes test rules that demonstrate the version-aware capabilities:

### FutureFeatureRule
- **Type**: Version-specific
- **Activation**: Only in version 9.9.9
- **Behavior**: Warns about variables starting with `_future_`
- **Implementation**: Uses `min_version` and `max_version` constraints

### ExperimentalHashRule
- **Type**: Hash-specific
- **Activation**: Always active except with specific hash
- **Disabled with**: Hash `1abc2def3ghi4jkl5mno6pqr7stu8vwx9yza0bcd1efg2hij3klm4`
- **Behavior**: Warns about `experimental_` prefix
- **Implementation**: Checks hash internally

### DebugModeRule
- **Type**: Dependency-based
- **Activation**: Always active in production
- **Disabled with**: `py-genlayer:test` dependency
- **Behavior**: Warns about debug variables (`debug_`, `test_`, `tmp_`)
- **Implementation**: Checks dependency value

## Using the Version-Aware Linter

### Basic Usage

```python
from genvm_linter import GenVMLinter

# Create linter instance (version-aware by default)
linter = GenVMLinter()

# Lint a file (version detected automatically)
results = linter.lint_file("contract.py")

# Lint source code
source = """# v0.2.0
# { "Depends": "py-genlayer:test" }
from genlayer import gl
class Contract(gl.Contract): pass
"""
results = linter.lint_source(source)
```

### Version Information API

```python
# Get version info from source
info = linter.get_version_info(source_code)
print(info["version"])  # Detected version
print(info["dependencies"])  # Dependencies dict
print(info["features"])  # Available features
```

## Creating Version-Aware Rules

### Using VersionedRule Base Class

```python
from genvm_linter.rules.versioned import VersionedRule
from genvm_linter.version import Version

class MyVersionedRule(VersionedRule):
    def __init__(self):
        super().__init__(
            rule_id="my-rule",
            description="My version-aware rule"
        )

    def check_versioned(self, node, filename=None):
        # Access version context
        if self.version_context:
            version = self.version_context.version
            dependencies = self.version_context.dependencies

            # Version-specific logic
            if version and version >= Version(2, 0, 0):
                # Apply v2.0.0+ specific checks
                pass

            # Hash-specific logic
            if dependencies.get("py-genlayer") == "specific-hash":
                # Apply hash-specific behavior
                pass

        return []
```

### Registering Rules with Constraints

```python
from genvm_linter.rule_registry import RuleDefinition
from genvm_linter.version import Version

# Version-constrained rule
registry.register_rule("future-rule", RuleDefinition(
    rule_class=MyFutureRule,
    min_version=Version(5, 0, 0),  # Only v5.0.0+
    max_version=Version(6, 0, 0),  # Not in v6.0.0+
    enabled_by_default=True
))

# Hash-specific rule
registry.register_rule("hash-rule", RuleDefinition(
    rule_class=MyHashRule,
    allowed_hashes=["hash1", "hash2"],  # Only these hashes
    excluded_hashes=["hash3"],  # Not this hash
    enabled_by_default=True
))
```

## Rule Definition Options

The `RuleDefinition` class supports:

- **min_version**: Minimum version where rule applies (inclusive)
- **max_version**: Maximum version where rule applies (exclusive)
- **allowed_hashes**: List of hashes where rule is enabled
- **excluded_hashes**: List of hashes where rule is disabled
- **enabled_by_default**: Whether rule is active by default

## Configuration

The system is configured via `config/versions.yaml`:

```yaml
# All base rules are always enabled
rules:
  base_rules:
    - "magic-comment"
    - "import"
    - "contract-class"
    - "decorator"
    - "type-system"
    - "genvm-api"
    - "lazy-object"
    - "storage-pattern"
    - "dataclass"
    - "nondet-storage"
    - "python-types"
    - "type-stub"

  # Test rules demonstrate version/hash behavior
  test_rules:
    future-feature:
      activation: "Only in version 9.9.9"
    experimental-hash:
      disabled_with: "Hash: 1abc2def..."
    debug-mode:
      disabled_with: "Dependency: test"
```

## Version Context

When a rule extends `VersionedRule`, it has access to:

```python
self.version_context.version       # Version object or None
self.version_context.version_string  # String like "0.2.0" or "latest"
self.version_context.dependencies   # Dict of dependencies
self.version_context.source_code    # Full source code
```

## Best Practices

1. **Use version detection** for informational purposes
2. **Test rules demonstrate** the version-aware capabilities
3. **Infrastructure is ready** for future version-specific rules
4. **Hash-based rules** can enable experimental features
5. **Dependency-based rules** can adjust behavior for test/production

## Future Extensions

The infrastructure supports:
- Version-specific validation rules
- Feature flags via hashes
- Gradual migration paths
- Backward compatibility
- A/B testing of new rules