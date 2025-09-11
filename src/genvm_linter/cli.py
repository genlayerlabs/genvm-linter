"""Command-line interface for GenVM linter."""

import json
import sys
from pathlib import Path
from typing import List, Optional

import click
from colorama import init, Fore, Style

from .linter import GenVMLinter
from .rules import ValidationResult, Severity

# Initialize colorama for cross-platform colored output
init(autoreset=True)


def format_result_text(result: ValidationResult, show_suggestion: bool = True) -> str:
    """Format a validation result as colored text."""
    # Color mapping for severity levels
    severity_colors = {
        Severity.ERROR: Fore.RED,
        Severity.WARNING: Fore.YELLOW,
        Severity.INFO: Fore.CYAN,
    }
    
    color = severity_colors.get(result.severity, Fore.WHITE)
    
    # Format the main message
    location = f"{result.filename}:" if result.filename else ""
    location += f"{result.line}:{result.column}"
    
    formatted = f"{color}{location} {result.severity.value}: {result.message} [{result.rule_id}]{Style.RESET_ALL}"
    
    # Add suggestion if available and requested
    if show_suggestion and result.suggestion:
        formatted += f"\n  {Fore.GREEN}💡 Suggestion: {result.suggestion}{Style.RESET_ALL}"
    
    return formatted


def format_result_json(result: ValidationResult) -> dict:
    """Format a validation result as JSON."""
    return {
        "rule_id": result.rule_id,
        "message": result.message,
        "severity": result.severity.value,
        "line": result.line,
        "column": result.column,
        "filename": result.filename,
        "suggestion": result.suggestion
    }


def count_by_severity(results: List[ValidationResult]) -> dict:
    """Count results by severity level."""
    counts = {severity.value: 0 for severity in Severity}
    for result in results:
        counts[result.severity.value] += 1
    return counts


@click.command()
@click.argument('paths', nargs=-1, type=click.Path(exists=True))
@click.option('--format', 'output_format', type=click.Choice(['text', 'json']), 
              default='text', help='Output format')
@click.option('--severity', type=click.Choice(['error', 'warning', 'info']),
              help='Minimum severity level to show')
@click.option('--no-suggestions', is_flag=True, help='Hide suggestions in text output')
@click.option('--rule', 'rules', multiple=True, 
              help='Only run specific rules (can be used multiple times)')
@click.option('--exclude-rule', 'exclude_rules', multiple=True,
              help='Exclude specific rules (can be used multiple times)')
@click.option('--stats', is_flag=True, help='Show summary statistics')
@click.version_option(version="0.1.0", prog_name="genvm-lint")
def main(paths: tuple, output_format: str, severity: Optional[str], 
         no_suggestions: bool, rules: tuple, exclude_rules: tuple, stats: bool) -> None:
    """
    GenVM Linter - Lint GenLayer intelligent contracts.
    
    PATHS can be files or directories. If no paths are provided, 
    the current directory is linted.
    """
    if not paths:
        paths = ('.',)
    
    # Convert severity string to enum
    min_severity = None
    if severity:
        min_severity = Severity(severity)
    
    # Initialize linter
    linter = GenVMLinter()
    
    # Filter rules if requested
    if rules:
        linter.rules = [rule for rule in linter.rules if rule.rule_id in rules]
    
    if exclude_rules:
        linter.rules = [rule for rule in linter.rules if rule.rule_id not in exclude_rules]
    
    # Collect all results
    all_results = []
    
    for path_str in paths:
        path = Path(path_str)
        
        try:
            if path.is_file():
                if path.suffix == '.py':
                    results = linter.lint_file(path)
                    all_results.extend(results)
                else:
                    click.echo(f"Skipping non-Python file: {path}", err=True)
            elif path.is_dir():
                results = linter.lint_directory(path)
                all_results.extend(results)
            else:
                click.echo(f"Path not found: {path}", err=True)
                sys.exit(1)
        except Exception as e:
            click.echo(f"Error processing {path}: {e}", err=True)
            sys.exit(1)
    
    # Filter by severity if requested
    if min_severity:
        severity_order = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}
        min_level = severity_order[min_severity]
        all_results = [r for r in all_results if severity_order[r.severity] >= min_level]
    
    # Sort results by filename, then by line number
    all_results.sort(key=lambda r: (r.filename or "", r.line, r.column))
    
    # Output results
    if output_format == 'json':
        output = {
            "results": [format_result_json(r) for r in all_results],
            "summary": {
                "total": len(all_results),
                "by_severity": count_by_severity(all_results)
            }
        }
        click.echo(json.dumps(output, indent=2))
    else:
        # Text format
        if not all_results:
            click.echo(f"{Fore.GREEN}✓ No issues found!{Style.RESET_ALL}")
        else:
            for result in all_results:
                click.echo(format_result_text(result, not no_suggestions))
        
        # Show statistics if requested
        if stats or all_results:
            counts = count_by_severity(all_results)
            click.echo()
            click.echo("Summary:")
            click.echo(f"  {Fore.RED}Errors: {counts['error']}{Style.RESET_ALL}")
            click.echo(f"  {Fore.YELLOW}Warnings: {counts['warning']}{Style.RESET_ALL}")
            click.echo(f"  {Fore.CYAN}Info: {counts['info']}{Style.RESET_ALL}")
            click.echo(f"  Total: {len(all_results)}")
    
    # Exit with error code if there are errors
    error_count = sum(1 for r in all_results if r.severity == Severity.ERROR)
    if error_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()