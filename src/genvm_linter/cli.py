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
    download_artifacts,
    get_latest_version,
    list_cached_versions,
)

# Subcommand names for detecting legacy mode
SUBCOMMANDS = {"check", "lint", "validate", "schema", "download"}


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


def cli():
    """Entry point that handles both legacy and modern invocation."""
    if _is_legacy_invocation():
        _run_legacy_lint()
    else:
        main()


if __name__ == "__main__":
    cli()
