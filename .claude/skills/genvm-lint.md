# GenVM Lint - Contract Validation Skill

Validate GenLayer intelligent contracts and extract ABI schemas.

## Setup

```bash
pip install genvm-linter
```

## Commands

### Quick validation (default workflow)
```bash
genvm-lint check <contract.py>
genvm-lint check <contract.py> --json  # Agent-friendly output
```

### Lint only (fast AST checks, ~50ms)
```bash
genvm-lint lint <contract.py>
genvm-lint lint <contract.py> --json
```

Checks:
- Forbidden imports (random, os, sys, subprocess, etc.)
- Non-deterministic patterns (float usage)
- Contract header structure

### Validate only (SDK semantic validation, ~200ms)
```bash
genvm-lint validate <contract.py>
genvm-lint validate <contract.py> --json
```

Validates:
- Types exist in SDK
- Decorators correctly applied
- Storage fields have valid types
- Method signatures correct

### Extract ABI schema
```bash
genvm-lint schema <contract.py>
genvm-lint schema <contract.py> --json
genvm-lint schema <contract.py> --output abi.json
```

### Type check (Pyright/Pylance)
```bash
genvm-lint typecheck <contract.py>
genvm-lint typecheck <contract.py> --json    # Agent-friendly output
genvm-lint typecheck <contract.py> --strict  # Strict mode
```

Runs Pyright (Pylance's core) with SDK paths auto-configured. Catches:
- Type mismatches
- Missing attributes
- Invalid method signatures
- Undefined variables

JSON output:
```json
{
  "ok": true,
  "diagnostics": [],
  "summary": {"errors": 0, "warnings": 0, "info": 0}
}
```

With errors:
```json
{
  "ok": false,
  "diagnostics": [
    {
      "file": "contract.py",
      "severity": 1,
      "message": "\"foo\" is not defined",
      "rule": "reportUndefinedVariable",
      "range": {"start": {"line": 10, "character": 4}}
    }
  ],
  "summary": {"errors": 1, "warnings": 0, "info": 0}
}
```

### Pre-download GenVM artifacts
```bash
genvm-lint download                    # Latest
genvm-lint download --version v0.2.12  # Specific
genvm-lint download --list             # Show cached
```

## Output Formats

### Human (default)
```
✓ Lint passed (3 checks)
✓ Validation passed
  Contract: CampaignIC
  Methods: 26 (16 view, 10 write)
```

### JSON (--json flag)
```json
{"ok":true,"lint":{"ok":true,"passed":3},"validate":{"ok":true,"contract":"CampaignIC","methods":26,"view_methods":16,"write_methods":10,"ctor_params":29}}
```

## Exit Codes

- `0` - All checks passed
- `1` - Lint or validation errors
- `2` - Contract file not found
- `3` - SDK download failed
