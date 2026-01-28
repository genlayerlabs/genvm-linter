"""CLI entry point for genvm-linter."""

import json
import sys
from pathlib import Path

import click

from . import __version__
from .lint import lint_contract
from .output import (
    format_human_lint,
    format_human_schema,
    format_human_validate,
    format_json,
    format_vscode_json,
)
from .validate import validate_contract
from .validate.artifacts import (
    clean_cache,
    download_artifacts,
    get_latest_version,
    list_cached_versions,
)
from .validate.sdk_loader import extract_sdk_paths, parse_contract_header

# Subcommand names for detecting legacy mode
SUBCOMMANDS = {"check", "lint", "validate", "schema", "download", "stubs", "setup", "cache", "typecheck"}


def print_progress(downloaded: int, total: int):
    """Print download progress."""
    if total > 0:
        percent = min(100, downloaded * 100 // total)
        mb_down = downloaded / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        click.echo(f"\rDownloading: {mb_down:.1f}/{mb_total:.1f} MB ({percent}%)", nl=False)


def _is_legacy_invocation() -> bool:
    """Detect if this is a legacy VS Code invocation.

    Legacy: python -m genvm_linter.cli <file> --format json
    Modern: genvm-lint check <file> --json
    """
    if len(sys.argv) < 2:
        return False

    first_arg = sys.argv[1]

    # If first arg is a subcommand or starts with -, it's modern mode
    if first_arg in SUBCOMMANDS or first_arg.startswith("-"):
        return False

    # If first arg looks like a file path, it's legacy mode
    return True


def _run_legacy_lint():
    """Run lint in legacy mode for VS Code extension compatibility.

    Expected invocation: python -m genvm_linter.cli <file> --format json
    """
    import argparse

    parser = argparse.ArgumentParser(description="GenLayer contract linter (legacy mode)")
    parser.add_argument("contract", help="Path to contract file")
    parser.add_argument("--format", dest="output_format", choices=["json", "text"], default="text")
    parser.add_argument("--severity", choices=["error", "warning", "info"])
    parser.add_argument("--exclude-rule", dest="exclude_rules", action="append", default=[])

    args = parser.parse_args()

    contract_path = Path(args.contract)
    if not contract_path.exists():
        if args.output_format == "json":
            print(format_vscode_json(
                type("LintResult", (), {"warnings": [{"code": "E001", "msg": f"File not found: {args.contract}", "line": 1}], "ok": False, "checks_passed": 0})()
            ))
        else:
            print(f"Error: File not found: {args.contract}")
        sys.exit(1)

    result = lint_contract(contract_path)

    # Filter by severity if specified
    if args.severity == "error":
        result.warnings = [w for w in result.warnings if w.get("code", "").startswith("E")]

    # Filter excluded rules
    if args.exclude_rules:
        result.warnings = [w for w in result.warnings if w.get("code") not in args.exclude_rules]

    if args.output_format == "json":
        print(format_vscode_json(result))
    else:
        print(format_human_lint(result))

    sys.exit(0 if result.ok else 1)


@click.group()
@click.version_option(__version__, prog_name="genvm-lint")
def main():
    """GenLayer contract linter and validator."""
    pass


@main.command(name="check")
@click.argument("contract", type=click.Path(exists=True))
@click.option("--json", "json_output", is_flag=True, help="Output JSON (agent-friendly)")
def check_cmd(contract, json_output):
    """Run both lint and validate (default workflow)."""
    contract_path = Path(contract)

    # Lint
    lint_result = lint_contract(contract_path)

    # Validate
    progress_cb = None if json_output else print_progress
    validate_result = validate_contract(contract_path, progress_callback=progress_cb)
    if progress_cb:
        click.echo()  # newline after progress

    if json_output:
        output = {
            "ok": lint_result.ok and validate_result.ok,
            "lint": lint_result.to_dict(),
            "validate": validate_result.to_dict(),
        }
        click.echo(format_json(output))
    else:
        click.echo(format_human_lint(lint_result))
        click.echo(format_human_validate(validate_result))

    sys.exit(0 if (lint_result.ok and validate_result.ok) else 1)


@main.command()
@click.argument("contract", type=click.Path(exists=True))
@click.option("--json", "json_output", is_flag=True, help="Output JSON")
def lint(contract, json_output):
    """Run fast AST-based safety checks only."""
    result = lint_contract(Path(contract))

    if json_output:
        click.echo(format_json(result.to_dict()))
    else:
        click.echo(format_human_lint(result))

    sys.exit(0 if result.ok else 1)


@main.command()
@click.argument("contract", type=click.Path(exists=True))
@click.option("--json", "json_output", is_flag=True, help="Output JSON")
def validate(contract, json_output):
    """Run SDK-based semantic validation."""
    progress_cb = None if json_output else print_progress
    result = validate_contract(Path(contract), progress_callback=progress_cb)
    if progress_cb:
        click.echo()  # newline after progress

    if json_output:
        click.echo(format_json(result.to_dict()))
    else:
        click.echo(format_human_validate(result))

    sys.exit(0 if result.ok else 1)


@main.command()
@click.argument("contract", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Write schema to file")
@click.option("--json", "json_output", is_flag=True, help="Output JSON")
def schema(contract, output, json_output):
    """Extract ABI schema from contract."""
    progress_cb = None if json_output else print_progress
    result = validate_contract(Path(contract), progress_callback=progress_cb)
    if progress_cb:
        click.echo()  # newline after progress

    if not result.ok:
        if json_output:
            click.echo(format_json({"ok": False, "errors": result.errors}))
        else:
            click.echo(format_human_validate(result))
        sys.exit(1)

    if output:
        Path(output).write_text(json.dumps(result.schema, indent=2))
        click.echo(f"Schema written to {output}")
    elif json_output:
        click.echo(format_json({"ok": True, "schema": result.schema}))
    else:
        click.echo(format_human_schema(result))

    sys.exit(0)


@main.command()
@click.option("--version", "-v", "version", help="GenVM version (e.g., v0.2.12)")
@click.option("--list", "list_versions", is_flag=True, help="List cached versions")
def download(version, list_versions):
    """Pre-download GenVM artifacts for offline use."""
    if list_versions:
        versions = list_cached_versions()
        if versions:
            click.echo("Cached versions:")
            for v in versions:
                click.echo(f"  {v}")
        else:
            click.echo("No cached versions")
        return

    if version is None:
        click.echo("Fetching latest version...")
        version = get_latest_version()
        click.echo(f"Latest: {version}")

    click.echo(f"Downloading GenVM {version}...")

    def progress(downloaded: int, total: int):
        if total > 0:
            percent = min(100, downloaded * 100 // total)
            mb_down = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            click.echo(f"\r  {mb_down:.1f}/{mb_total:.1f} MB ({percent}%)", nl=False)

    try:
        path = download_artifacts(version, progress_callback=progress)
        click.echo()  # newline after progress
        click.echo(f"✓ Downloaded to {path}")
    except Exception as e:
        click.echo()
        click.echo(f"✗ Download failed: {e}", err=True)
        sys.exit(3)


@main.command()
@click.option("--version", "-v", "version", help="GenVM version (e.g., v0.2.12)")
@click.option("--output", "-o", type=click.Path(), help="Output directory for stubs")
@click.option("--list", "list_versions", is_flag=True, help="List cached stub versions")
def stubs(version, output, list_versions):
    """Generate type stubs for IDE intellisense (deprecated: use 'setup' instead)."""
    from .stubs import generate_stubs, list_cached_stubs, get_stubs_path

    if list_versions:
        versions = list_cached_stubs()
        if versions:
            click.echo("Cached stub versions:")
            for v in versions:
                click.echo(f"  {v} -> {get_stubs_path(v)}")
        else:
            click.echo("No cached stubs")
        return

    if version is None:
        click.echo("Fetching latest version...")
        version = get_latest_version()
        click.echo(f"Latest: {version}")

    click.echo(f"Generating stubs for GenVM {version}...")

    def progress(downloaded: int, total: int):
        if total > 0:
            percent = min(100, downloaded * 100 // total)
            mb_down = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            click.echo(f"\r  Downloading SDK: {mb_down:.1f}/{mb_total:.1f} MB ({percent}%)", nl=False)

    try:
        output_path = Path(output) if output else None
        stubs_path = generate_stubs(version, output_path, progress_callback=progress)
        click.echo()  # newline after progress
        click.echo(f"✓ Stubs generated at {stubs_path}")
        click.echo()
        click.echo("To use in VS Code, add to settings.json:")
        click.echo(f'  "python.analysis.stubPath": "{stubs_path}"')
    except Exception as e:
        click.echo()
        click.echo(f"✗ Stub generation failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--version", "-v", "version", help="GenVM version (e.g., v0.2.12)")
@click.option("--contract", "-c", type=click.Path(exists=True), help="Contract file (auto-detect version)")
@click.option("--json", "json_output", is_flag=True, help="Output JSON (for IDE integration)")
def setup(version, contract, json_output):
    """Download SDK and output paths for IDE intellisense.

    Outputs extraPaths for Pylance configuration. Better than stubs because
    you get hover docs, go-to-definition, and no "missing source" warnings.
    """
    # Auto-detect version from contract header if provided
    if contract and not version:
        deps = parse_contract_header(Path(contract))
        if not json_output and "py-genlayer" in deps:
            click.echo("Detected SDK from contract header")
        # Will use version from tarball based on deps

    if version is None and not contract:
        if not json_output:
            click.echo("Fetching latest version...")
        version = get_latest_version()
        if not json_output:
            click.echo(f"Latest: {version}")

    if not json_output:
        click.echo(f"Setting up GenVM SDK...")

    def progress(downloaded: int, total: int):
        if not json_output and total > 0:
            percent = min(100, downloaded * 100 // total)
            mb_down = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            click.echo(f"\r  Downloading: {mb_down:.1f}/{mb_total:.1f} MB ({percent}%)", nl=False)

    try:
        # Download tarball
        tarball_path = download_artifacts(version, progress_callback=progress)
        if not json_output:
            click.echo()  # newline after progress

        # Parse contract for dependencies if provided
        deps = parse_contract_header(Path(contract)) if contract else {}

        # Extract SDK paths
        sdk_paths = extract_sdk_paths(tarball_path, deps)

        # Convert to src paths for Pylance
        extra_paths = []
        for path in sdk_paths:
            src_path = path / "src" if (path / "src").exists() else path
            extra_paths.append(str(src_path))

        if json_output:
            resolved_version = version or tarball_path.name.replace("genvm-universal-", "").replace(".tar.xz", "")
            click.echo(json.dumps({
                "ok": True,
                "extraPaths": extra_paths,
                "version": resolved_version,
            }))
        else:
            click.echo("✓ SDK ready")
            click.echo()
            click.echo("Add to VS Code settings.json:")
            click.echo('  "python.analysis.extraPaths": [')
            for p in extra_paths:
                click.echo(f'    "{p}",')
            click.echo('  ],')
            click.echo('  "python.analysis.reportMissingModuleSource": "none"')

    except Exception as e:
        if json_output:
            click.echo(json.dumps({"ok": False, "error": str(e)}))
        else:
            click.echo()
            click.echo(f"✗ Setup failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("contract", type=click.Path(exists=True))
@click.option("--json", "json_output", is_flag=True, help="Output JSON (agent-friendly)")
@click.option("--strict", is_flag=True, help="Enable strict type checking mode")
def typecheck(contract, json_output, strict):
    """Run Pyright type checking with GenLayer SDK configured.

    Uses pyright (Pylance's open-source core) to type-check contracts
    with the correct SDK paths automatically configured.

    Example:
        genvm-lint typecheck contract.py --json
    """
    import subprocess
    import tempfile

    contract_path = Path(contract)

    if not json_output:
        click.echo(f"Type checking {contract_path.name}...")

    # Parse contract header for SDK version
    deps = parse_contract_header(contract_path)

    # Download SDK if needed
    def progress(downloaded: int, total: int):
        if not json_output and total > 0:
            percent = min(100, downloaded * 100 // total)
            click.echo(f"\r  Downloading SDK: {percent}%", nl=False)

    try:
        tarball_path = download_artifacts(None, progress_callback=progress)
        if not json_output and deps:
            click.echo()  # newline after progress
    except Exception as e:
        if json_output:
            click.echo(json.dumps({"ok": False, "error": f"Failed to download SDK: {e}"}))
        else:
            click.echo(f"Failed to download SDK: {e}", err=True)
        sys.exit(1)

    # Extract SDK paths
    sdk_paths = extract_sdk_paths(tarball_path, deps)
    extra_paths = []
    for path in sdk_paths:
        src_path = path / "src" if (path / "src").exists() else path
        extra_paths.append(str(src_path))

    # Create temporary pyrightconfig.json
    # Note: "include" with absolute paths is ignored by pyright, so we pass file as argument
    pyright_config = {
        "extraPaths": extra_paths,
        "typeCheckingMode": "strict" if strict else "basic",
        "reportMissingModuleSource": False,
        "reportAttributeAccessIssue": "none",  # SDK uses dynamic attrs
        "reportArgumentType": "none",  # DynArray/list compat
        "reportReturnType": "none",  # int/u256 NewType compat (runtime equivalent)
        "pythonVersion": "3.12",
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(pyright_config, f)
        config_path = f.name

    try:
        # Run pyright with file as argument (not in config, since absolute paths are ignored)
        result = subprocess.run(
            ["pyright", "--project", config_path, str(contract_path.absolute()), "--outputjson"],
            capture_output=True,
            text=True,
        )

        pyright_output = json.loads(result.stdout) if result.stdout else {}
        diagnostics = pyright_output.get("generalDiagnostics", [])

        # Filter to only show errors from the contract file (not SDK)
        contract_diagnostics = [
            d for d in diagnostics
            if contract_path.name in d.get("file", "")
        ]

        if json_output:
            output = {
                "ok": len(contract_diagnostics) == 0,
                "diagnostics": contract_diagnostics,
                "summary": {
                    "errors": sum(1 for d in contract_diagnostics if d.get("severity") == 1),
                    "warnings": sum(1 for d in contract_diagnostics if d.get("severity") == 2),
                    "info": sum(1 for d in contract_diagnostics if d.get("severity") == 3),
                },
            }
            click.echo(json.dumps(output, indent=2))
        else:
            if not contract_diagnostics:
                click.echo("✓ No type errors found")
            else:
                for d in contract_diagnostics:
                    severity = {1: "error", 2: "warning", 3: "info"}.get(d.get("severity"), "?")
                    line = d.get("range", {}).get("start", {}).get("line", 0) + 1
                    msg = d.get("message", "")
                    rule = d.get("rule", "")
                    click.echo(f"{contract_path.name}:{line}: {severity}: {msg} [{rule}]")

                errors = sum(1 for d in contract_diagnostics if d.get("severity") == 1)
                warnings = sum(1 for d in contract_diagnostics if d.get("severity") == 2)
                click.echo(f"\n{errors} error(s), {warnings} warning(s)")

        sys.exit(0 if len(contract_diagnostics) == 0 else 1)

    except FileNotFoundError:
        msg = "pyright not found. Install with: pip install pyright"
        if json_output:
            click.echo(json.dumps({"ok": False, "error": msg}))
        else:
            click.echo(msg, err=True)
        sys.exit(1)
    except json.JSONDecodeError as e:
        msg = f"Failed to parse pyright output: {e}"
        if json_output:
            click.echo(json.dumps({"ok": False, "error": msg}))
        else:
            click.echo(msg, err=True)
        sys.exit(1)
    finally:
        Path(config_path).unlink(missing_ok=True)


@main.group()
def cache():
    """Manage cached GenVM artifacts."""
    pass


@cache.command(name="list")
def cache_list():
    """List cached versions."""
    versions = list_cached_versions()
    if versions:
        click.echo("Cached versions:")
        for v in versions:
            click.echo(f"  {v}")
    else:
        click.echo("No cached versions")


@cache.command(name="clean")
@click.option("--keep", "-k", multiple=True, help="Versions to keep (can specify multiple)")
@click.option("--all", "clean_all", is_flag=True, help="Remove all cached versions")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted")
def cache_clean(keep, clean_all, dry_run):
    """Remove old cached versions.

    By default keeps the latest version. Use --all to remove everything.
    """
    keep_versions = list(keep) if keep else None
    keep_latest = not clean_all

    if dry_run:
        versions = list_cached_versions()
        if keep_latest:
            try:
                latest = get_latest_version()
                click.echo(f"Would keep latest: {latest}")
            except Exception:
                pass
        for v in versions:
            if keep_versions and v in keep_versions:
                click.echo(f"Would keep: {v}")
            elif keep_latest:
                try:
                    latest = get_latest_version()
                    if v == latest:
                        continue
                except Exception:
                    pass
                click.echo(f"Would delete: {v}")
            else:
                click.echo(f"Would delete: {v}")
        return

    files_deleted, bytes_freed = clean_cache(keep_versions, keep_latest)

    if files_deleted > 0:
        mb_freed = bytes_freed / (1024 * 1024)
        click.echo(f"✓ Cleaned {files_deleted} files ({mb_freed:.1f} MB freed)")
    else:
        click.echo("Nothing to clean")


def cli():
    """Entry point that handles both legacy and modern invocation."""
    if _is_legacy_invocation():
        _run_legacy_lint()
    else:
        main()


if __name__ == "__main__":
    cli()
