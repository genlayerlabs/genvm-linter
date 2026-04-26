# genvm-linter

Fast validation and schema extraction for GenLayer intelligent contracts.

## Installation

```bash
pip install genvm-linter
```

## Usage

```bash
# Run both lint and validate (default)
genvm-lint check contract.py

# Fast AST safety checks only (~50ms)
genvm-lint lint contract.py

# Full SDK semantic validation (~200ms cached)
genvm-lint validate contract.py

# Extract ABI schema
genvm-lint schema contract.py
genvm-lint schema contract.py --output abi.json

# Pyright type checking with SDK auto-configured
genvm-lint typecheck contract.py
genvm-lint typecheck contract.py --strict      # Strict mode
genvm-lint typecheck contract.py --all         # Show all errors (disable SDK suppressions)

# IDE setup — download SDK and output extraPaths for Pylance
genvm-lint setup                               # Latest version
genvm-lint setup --contract contract.py        # Auto-detect version from header
genvm-lint setup --version v0.2.12             # Specific version
genvm-lint setup --json                        # JSON output for IDE integration

# Pre-download GenVM artifacts
genvm-lint download                    # Latest
genvm-lint download --version v0.2.12  # Specific version
genvm-lint download --list             # Show cached

# JSON output (all commands)
genvm-lint check contract.py --json
```

## How It Works

### Layer 1: AST Lint Checks (Fast)
- Forbidden imports (`random`, `os`, `time`, etc.)
- Non-deterministic patterns (`float()`, `time.time()`)
- Structure validation (dependency header)
- Semantic prompt and consensus rules (GL-S01, GL-S02, GL-S03)

### Semantic Rules (GL-S)

These rules run as part of Layer 1 and catch common mistakes in GenLayer prompt and consensus patterns.

#### GL-S01 — Vague prompt language (WARNING)

Flags `exec_prompt` calls whose prompt string contains ambiguous terms (`fair`, `reasonable`,
`appropriate`, `good`, `bad`, `assess`, `evaluate`, `determine if`, `decide if`, `judge whether`,
etc.) without explicit acceptance criteria.

Also flags when the result of `exec_prompt` is used directly in an `if` condition but
`response_format` is absent or `"text"`.

```python
# Bad — ambiguous, no criteria
result = gl.exec_prompt("Is this a fair assessment of the candidate?")

# Good — explicit YES/NO condition
result = gl.exec_prompt(
    "Return YES if the score > 80, NO if the score <= 80",
    response_format=bool,
)
```

#### GL-S02 — Weak `eq_principle` criteria (WARNING / ERROR)

Scores the `principle` kwarg of `eq_principle_prompt_comparative` and the `criteria` kwarg of
`eq_principle_prompt_non_comparative` for vagueness:

| Condition | Severity |
|---|---|
| Fewer than 10 words | HIGH RISK (error) |
| Only vague comparative adjectives (`same`, `equivalent`, `match`, …) | HIGH RISK (error) |
| No numeric bounds, no category list, no conditional logic | MEDIUM RISK (warning) |

```python
# Bad — single word, no bounds (HIGH)
gl.eq_principle.prompt_comparative(fn, principle="same")

# Bad — no criteria (MEDIUM)
gl.eq_principle.prompt_comparative(
    fn,
    principle="The output should be reasonable and appropriate",
)

# Good — explicit bound
gl.eq_principle.prompt_comparative(
    fn,
    principle="Return YES if prices differ by less than 5%, NO otherwise",
)
```

#### GL-S03 — `eq_principle_strict_eq` type mismatch (ERROR)

Flags `eq_principle_strict_eq` wrapping a lambda or function that calls `exec_prompt` or
`get_webpage`. LLM outputs and raw web content are non-deterministic across validators, so strict
equality consensus will always fail.

```python
# Bad — LLM output is non-deterministic
gl.eq_principle.strict_eq(lambda: gl.exec_prompt("What is 2+2?"))

# Bad — raw web content varies
gl.eq_principle.strict_eq(lambda: gl.get_webpage("https://example.com"))

# Good — switch to a comparative principle
gl.eq_principle.prompt_comparative(
    lambda: gl.exec_prompt("What is 2+2?", response_format=int),
    principle="Return YES if both answers are numerically equal",
)
```

### Layer 2: SDK Validation (Accurate)
- Downloads GenVM release artifacts (cached at `~/.cache/genvm-linter/`)
- Loads exact SDK version specified in contract header
- Validates types, decorators, storage fields
- Extracts ABI schema

## Exit Codes

- `0` - All checks passed
- `1` - Lint or validation errors
- `2` - Contract file not found
- `3` - SDK download failed

## IDE Integration

### VS Code Extension

This linter is used by the [GenLayer VS Code Extension](https://github.com/genlayerlabs/vscode-extension) for real-time contract validation.

### Manual Pylance Setup

Use `genvm-lint setup` to configure Pylance with the correct SDK paths. This gives you hover docs, go-to-definition, and type checking without the extension.

```bash
genvm-lint setup --contract contract.py
```

Add the output paths to your VS Code `settings.json`:

```json
{
  "python.analysis.extraPaths": ["<output paths>"],
  "python.analysis.reportMissingModuleSource": "none"
}
```

### Type Checking

`genvm-lint typecheck` runs Pyright with the SDK auto-configured. By default it suppresses SDK-internal noise (dynamic attributes, NewType compat). Use `--all` to see everything, `--strict` for strict mode.

## Development

```bash
git clone https://github.com/genlayerlabs/genvm-linter.git
cd genvm-linter
pip install -e ".[dev]"
pytest
```

## License

MIT
