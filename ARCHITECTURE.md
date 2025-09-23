# GenVM Linter Architecture

## Overview

The GenVM Linter is a comprehensive validation system for GenLayer intelligent contracts, consisting of three main components:
1. **Python Linter Core** - Rule-based validation engine
2. **MyPy Integration** - Python type checking
3. **VS Code Extension** - IDE integration

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     VS Code Editor                          │
│  ┌────────────────────────────────────────────────────┐    │
│  │              VS Code Extension (TypeScript)         │    │
│  │  • extension.ts (entry point)                      │    │
│  │  • diagnostics-provider.ts                         │    │
│  │  • hover-provider.ts, autocomplete-provider.ts     │    │
│  └──────────────┬────────────────┬────────────────────┘    │
│                 │                │                          │
│                 ▼                ▼                          │
│         Spawns Process      JSON Communication              │
└─────────────────┼────────────────┼─────────────────────────┘
                  │                │
                  ▼                ▼
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
│  │  • python_types.py - MyPy integration              │    │
│  │  • genvm_patterns.py - API usage patterns          │    │
│  └─────────────┬───────────────────────────────────────┘    │
│                │                                            │
│                ▼                                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │              MyPy Integration                       │    │
│  │  • Runs MyPy programmatically                      │    │
│  │  • Custom GenVM type stubs                         │    │
│  │  • Python type validation                          │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Entry Points

### 1. CLI Entry Point (`src/genvm_linter/cli.py`)

The main command-line interface that users and the VS Code extension interact with:

```python
# Key function: main()
@click.command()
@click.argument('paths', nargs=-1, type=click.Path(exists=True))
@click.option('--format', type=click.Choice(['text', 'json']), default='text')
@click.option('--severity', type=click.Choice(['error', 'warning', 'info']))
def main(paths, format, severity):
    """Main CLI entry point"""
    linter = GenVMLinter()
    results = []

    for path in paths:
        results.extend(linter.lint_file(path))

    if format == 'json':
        output_json(results)
    else:
        output_text(results)
```

### 2. Python API Entry Point (`src/genvm_linter/linter.py`)

The core linter class that manages all validation:

```python
class GenVMLinter:
    def __init__(self):
        # Initialize all validation rules
        self.rules = [
            MagicCommentRule(),
            ImportRule(),
            ContractClassRule(),
            DecoratorRule(),
            TypeSystemRule(),
            GenVMApiUsageRule(),
            PythonTypeCheckRule(),  # MyPy integration
            # ... more rules
        ]

    def lint_source(self, source_code: str) -> List[ValidationResult]:
        # Parse AST and run all rules
        tree = ast.parse(source_code)
        results = []

        for rule in self.rules:
            results.extend(rule.validate(tree, source_code))

        return results
```

### 3. VS Code Extension Entry Point (`vscode-extension/src/extension.ts`)

The TypeScript extension that integrates with VS Code:

```typescript
export function activate(context: vscode.ExtensionContext) {
    // Register all providers
    const diagnosticsProvider = new GenVMDiagnosticsProvider();
    const hoverProvider = new GenVMHoverProvider();
    const completionProvider = new GenVMCompletionProvider();

    // Register file watcher for real-time validation
    const watcher = vscode.workspace.createFileSystemWatcher('**/*.py');
    watcher.onDidChange(uri => diagnosticsProvider.validateFile(uri));

    // Register commands
    vscode.commands.registerCommand('genvm.lintCurrentFile', lintCurrentFile);
}
```

## Component Integration

### Python Linter ↔ MyPy Integration

The `PythonTypeCheckRule` in `src/genvm_linter/rules/python_types.py` integrates MyPy:

```python
class PythonTypeCheckRule(Rule):
    def validate(self, tree: ast.AST, source_code: str) -> List[ValidationResult]:
        # Create temporary file with source code
        with tempfile.NamedTemporaryFile(suffix='.py') as tmp:
            tmp.write(source_code.encode())
            tmp.flush()

            # Run MyPy with custom GenVM stubs
            result = mypy_api.run([
                tmp.name,
                '--config-file', self.get_mypy_config(),
                '--custom-typeshed', self.get_genvm_stubs()
            ])

            # Parse MyPy output and convert to ValidationResults
            return self.parse_mypy_output(result[0])
```

**Key Features:**
- Validates standard Python type hints
- Uses custom type stubs for GenVM types (u256, TreeMap, etc.)
- Runs alongside GenVM-specific validation rules
- Provides type inference and checking

### Python Linter ↔ VS Code Extension

The VS Code extension communicates with the Python linter via subprocess:

```typescript
// In vscode-extension/src/genvm-linter.ts
export class GenVMLinter {
    async lintFile(filePath: string): Promise<Diagnostic[]> {
        // Spawn Python subprocess
        const pythonPath = this.getPythonPath();
        const child = spawn(pythonPath, [
            '-m', 'genvm_linter.cli',
            '--format', 'json',
            filePath
        ]);

        // Collect JSON output
        let output = '';
        child.stdout.on('data', (data) => {
            output += data.toString();
        });

        // Parse JSON and convert to VS Code diagnostics
        return new Promise((resolve) => {
            child.on('close', () => {
                const results = JSON.parse(output);
                const diagnostics = this.convertToDiagnostics(results);
                resolve(diagnostics);
            });
        });
    }
}
```

**Communication Flow:**
1. VS Code detects file change/save
2. Extension spawns Python process: `python3 -m genvm_linter.cli --format json file.py`
3. Python linter validates and returns JSON results
4. Extension parses JSON and creates VS Code diagnostics
5. Editor displays errors/warnings with squiggles

## Data Flow

1. **Source Code Input**
   - User writes/edits a `.py` file in VS Code
   - File contains GenVM magic comment: `# { "Depends": "py-genlayer:test" }`

2. **VS Code Detection**
   - Extension activates on Python files
   - File watcher triggers on save/change
   - Checks for GenVM contract patterns

3. **Validation Process**
   ```
   File Change → Extension → Python CLI → Linter Core → Rules → Results
   ```

4. **Rule Execution Pipeline**
   - Each rule class inherits from `Rule` base class
   - Rules implement `validate(tree: ast.AST, source: str)` method
   - Rules return `List[ValidationResult]` with:
     - Severity (ERROR, WARNING, INFO)
     - Line/column location
     - Error message
     - Fix suggestions

5. **Result Processing**
   - Results aggregated from all rules
   - Formatted as JSON for VS Code
   - Extension converts to diagnostics
   - Editor displays inline errors

## Rule System

### Base Rule Class (`src/genvm_linter/rules/base.py`)

```python
class Rule(ABC):
    @abstractmethod
    def validate(self, tree: ast.AST, source_code: str) -> List[ValidationResult]:
        """Validate the AST and return results"""
        pass

class ValidationResult:
    rule_id: str
    message: str
    severity: Severity
    line: int
    column: int
    suggestion: Optional[str]
```

### Rule Categories

1. **Structure Rules** (`contract.py`)
   - Magic comment validation
   - Import statement checking
   - Contract class structure

2. **Type System Rules** (`types.py`)
   - Sized integer validation (u256, u64, etc.)
   - Collection type checking (TreeMap, DynArray)
   - Return type validation

3. **Decorator Rules** (`decorators.py`)
   - `@gl.public.view` and `@gl.public.write` validation
   - Constructor decorator checking
   - State modification detection

4. **Python Type Rules** (`python_types.py`)
   - MyPy integration
   - Type hint validation
   - GenVM stub generation

5. **Pattern Rules** (`genvm_patterns.py`)
   - GenVM API usage patterns
   - Lazy object validation
   - Storage pattern checking

## VS Code Extension Features

### Providers

1. **Diagnostics Provider**
   - Real-time error/warning display
   - Squiggles and problem panel integration

2. **Hover Provider**
   - Documentation on hover
   - Type information display
   - Links to GenLayer docs

3. **Completion Provider**
   - Auto-complete for GenVM types
   - Snippet suggestions
   - Import completions

4. **Code Actions Provider**
   - Quick fixes for common issues
   - Auto-import missing types
   - Decorator corrections

5. **Inlay Hints Provider**
   - Type hints for variables
   - Parameter hints for methods

## Configuration

### Python Linter Configuration

Via `pyproject.toml`:
```toml
[tool.genvm]
exclude_rules = ["genvm-magic-comment"]
severity = "warning"
```

### VS Code Extension Configuration

Via VS Code settings:
```json
{
  "genvm.linting.enabled": true,
  "genvm.linting.severity": "warning",
  "genvm.python.interpreterPath": "python3"
}
```

## Performance Optimizations

1. **AST Caching** - Parse once, validate with all rules
2. **Parallel Rule Execution** - Rules run independently
3. **Incremental Validation** - Only re-validate changed files
4. **JSON Communication** - Efficient IPC between processes
5. **Lazy Loading** - Load rules only when needed

## Testing Architecture

- **Unit Tests** - Individual rule validation
- **Integration Tests** - Full contract validation
- **VS Code Tests** - Extension functionality
- **MyPy Tests** - Type checking validation

## Future Enhancements

1. **Language Server Protocol (LSP)** - Replace subprocess with LSP
2. **Incremental Parsing** - Parse only changed regions
3. **Custom Rule Plugins** - User-defined validation rules
4. **Multi-file Analysis** - Cross-contract validation
5. **Performance Profiling** - Optimization opportunities