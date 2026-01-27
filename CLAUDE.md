# CLAUDE.md

## Project Overview

genvm-linter is a fast validation tool for GenLayer intelligent contracts. It provides two-layer validation and ABI schema extraction.

## Architecture

### Two-Layer Validation

**Layer 1: AST Lint (~50ms)**
Fast static analysis using Python's AST module. No dependencies required.

Checks:
- Forbidden imports (random, os, sys, subprocess, etc.)
- Non-deterministic calls (time.time, uuid.uuid4)
- Float usage (must use Decimal)
- Contract structure

**Layer 2: SDK Validation (~200ms first run, cached after)**
Semantic validation using the actual GenLayer SDK. Downloads and caches GenVM release artifacts.

Validates:
- Contract class inherits from `Contract`
- Decorators (`@gl.public.view`, `@gl.public.write`) applied correctly
- Storage fields use valid SDK types
- Method signatures are correct
- Types exist in SDK

### GenVM Artifact Resolution

GenLayer intelligent contracts embed their SDK version in a header:

```python
# {
#   "Seq": [
#     { "Depends": "py-genlayer:0asq35p8mz..." }
#   ]
# }
```

The linter:
1. Parses the contract header for dependency hashes
2. Downloads `genvm-universal.tar.xz` from GitHub releases
3. Extracts the nested tarball structure:
   ```
   genvm-universal.tar.xz
   └── runners/py-genlayer/{hash}.tar
       └── runner.json  (specifies py-lib-genlayer-std version)
   └── runners/py-lib-genlayer-std/{hash}.tar
       └── src/genlayer/...
   ```
4. Adds SDK to Python path and imports `get_schema()`
5. Executes contract to extract ABI

**Critical Detail**: numpy must be imported BEFORE the SDK. The SDK's type registration only happens if numpy is already in `sys.modules`.

### Caching

Artifacts cached at `~/.cache/genvm-linter/`:
- `genvm-universal-{version}.tar.xz` - Downloaded release
- `extracted/{version}/{runner}/{hash}/` - Extracted runners

First validation downloads ~50MB, subsequent validations use cache.

## Commands

```bash
npm run build     # N/A - pure Python
pip install -e .  # Install in dev mode
pytest            # Run tests

# CLI
genvm-lint check <contract.py>       # Full validation (lint + validate)
genvm-lint lint <contract.py>        # Fast AST checks only
genvm-lint validate <contract.py>    # SDK validation only
genvm-lint schema <contract.py>      # Extract ABI schema
genvm-lint download --version v0.9.0 # Pre-download artifacts
```

## Key Files

```
src/genvm_linter/
├── cli.py              # Click CLI, legacy VS Code mode
├── output.py           # Formatters (human, JSON, VS Code)
├── lint/
│   ├── linter.py       # Orchestrates lint checks
│   ├── safety.py       # Forbidden imports, non-determinism
│   └── structure.py    # Contract structure checks
└── validate/
    ├── validator.py    # Orchestrates SDK validation
    ├── sdk_loader.py   # Load SDK, parse headers, mock WASI
    └── artifacts.py    # Download/extract GenVM releases
```

## VS Code Extension Integration

The VS Code extension calls the linter and expects JSON output:

```bash
genvm-lint check contract.py --json
```

Legacy mode (direct path argument) also supported for backwards compatibility.

## Adding New Lint Rules

1. Add check to `lint/safety.py` (forbidden patterns) or `lint/structure.py` (contract structure)
2. Return `SafetyWarning` or `StructureWarning` with code, message, line number
3. Warning codes: `W0xx` for safety, `S0xx` for structure, `E0xx` for errors

## Testing

```bash
pytest tests/ -v
pytest tests/test_safety.py -v  # Specific file
```
