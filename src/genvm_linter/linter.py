"""Main linter implementation for GenVM contracts with optional version awareness."""

import ast
from pathlib import Path
from typing import List, Optional, Union, Dict

from .rules import Rule, ValidationResult
from .rules.contract import MagicCommentRule, ImportRule, ContractClassRule
from .rules.decorators import DecoratorRule
from .rules.types import TypeSystemRule
from .rules.genvm_patterns import GenVMApiUsageRule, LazyObjectRule, StoragePatternRule
from .rules.python_types import PythonTypeCheckRule, GenVMTypeStubRule
from .rules.genvm_dataclasses import DataclassValidation
from .rules.nondet_storage import NondetStorageAccessRule
from .rules.test_rules import FutureFeatureRule, ExperimentalHashRule, DebugModeRule
from .rules.versioned import VersionedRule, VersionContext
from .rule_registry import RuleRegistry
from .version import Version, VersionParser


class GenVMLinter:
    """Main linter class for GenVM intelligent contracts with optional version awareness."""

    def __init__(self, use_version_aware: bool = True, config_file: Optional[Path] = None):
        """Initialize the linter with default rules.

        Args:
            use_version_aware: Whether to use version-aware rule loading
            config_file: Optional path to version configuration file
        """
        self.use_version_aware = use_version_aware
        self.default_version = "latest"

        if self.use_version_aware:
            # Use rule registry for version-aware rule management
            if config_file is None:
                default_config = Path(__file__).parent.parent.parent / "config" / "versions.yaml"
                if default_config.exists():
                    config_file = default_config

            self.registry = RuleRegistry(config_file)
            self.rules: List[Rule] = []  # Will be populated based on version
        else:
            # Use traditional fixed rule set
            self.rules: List[Rule] = [
                MagicCommentRule(),
                ImportRule(),
                ContractClassRule(),
                DecoratorRule(),
                TypeSystemRule(),
                GenVMApiUsageRule(),
                LazyObjectRule(),
                StoragePatternRule(),
                PythonTypeCheckRule(),
                GenVMTypeStubRule(),
                DataclassValidation(),
                NondetStorageAccessRule(),
                FutureFeatureRule(),
                ExperimentalHashRule(),
                DebugModeRule(),
            ]

    def add_rule(self, rule: Rule) -> None:
        """Add a custom rule to the linter."""
        self.rules.append(rule)

    def lint_file(self, filepath: Union[str, Path]) -> List[ValidationResult]:
        """Lint a single Python file.

        Args:
            filepath: Path to the Python file to lint

        Returns:
            List of validation results
        """
        filepath = Path(filepath)

        if not filepath.exists():
            from .rules.base import ValidationResult, Severity
            return [ValidationResult(
                rule_id="file-not-found",
                message=f"File not found: {filepath}",
                severity=Severity.ERROR,
                line=1,
                column=0,
                filename=str(filepath)
            )]

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except Exception as e:
            from .rules.base import ValidationResult, Severity
            return [ValidationResult(
                rule_id="file-read-error",
                message=f"Error reading file: {e}",
                severity=Severity.ERROR,
                line=1,
                column=0,
                filename=str(filepath)
            )]

        return self.lint_source(source_code, str(filepath))

    def lint_source(self, source_code: str, filename: Optional[str] = None) -> List[ValidationResult]:
        """Lint Python source code with optional version detection.

        Args:
            source_code: The Python source code to lint
            filename: Optional filename for error reporting

        Returns:
            List of validation results
        """
        results: List[ValidationResult] = []

        # Extract version information if version-aware mode is enabled
        if self.use_version_aware:
            version_str = VersionParser.get_effective_version(source_code, self.default_version)
            dependencies = VersionParser.extract_dependencies(source_code)

            # Parse version
            version = None
            if version_str != "latest":
                try:
                    version = Version.parse(version_str)
                except ValueError:
                    from .rules.base import ValidationResult, Severity
                    results.append(ValidationResult(
                        rule_id="invalid-version",
                        message=f"Invalid version format: {version_str}",
                        severity=Severity.WARNING,
                        line=1,
                        column=0,
                        filename=filename
                    ))

            # Create version context
            context = VersionContext(
                version=version,
                version_string=version_str,
                dependencies=dependencies,
                source_code=source_code
            )

            # Set context in registry and get rules for this version
            self.registry.set_version_context(context)
            self.rules = self.registry.get_rules_for_version(version)

            # Add version info message
            from .rules.base import ValidationResult, Severity
            if version:
                results.append(ValidationResult(
                    rule_id="version-info",
                    message=f"Linting with GenVM version {version}",
                    severity=Severity.INFO,
                    line=1,
                    column=0,
                    filename=filename
                ))

                # Check for breaking changes if upgrading
                if version < Version.parse("0.4.0"):  # Current latest
                    changes = self.registry.get_breaking_changes(version, Version.parse("0.4.0"))
                    if changes:
                        results.append(ValidationResult(
                            rule_id="version-upgrade-available",
                            message=f"Consider upgrading to latest version. Breaking changes: {', '.join(changes[:2])}...",
                            severity=Severity.INFO,
                            line=1,
                            column=0,
                            filename=filename
                        ))
            else:
                results.append(ValidationResult(
                    rule_id="version-info",
                    message="Linting with latest GenVM version (no version specified)",
                    severity=Severity.INFO,
                    line=1,
                    column=0,
                    filename=filename
                ))

        # First, run string-based rules that need to check the raw source
        for rule in self.rules:
            if hasattr(rule, 'needs_source_code') and rule.needs_source_code:
                # Set version context for versioned rules if available
                if self.use_version_aware and isinstance(rule, VersionedRule):
                    rule.set_version_context(context)
                results.extend(rule.check(source_code, filename))

        # Try to parse the AST
        try:
            tree = ast.parse(source_code, filename=filename)
        except SyntaxError as e:
            from .rules.base import ValidationResult, Severity
            results.append(ValidationResult(
                rule_id="syntax-error",
                message=f"Syntax error: {e.msg}",
                severity=Severity.ERROR,
                line=e.lineno or 1,
                column=e.offset or 0,
                filename=filename
            ))
            return results

        # Run AST-based rules
        for rule in self.rules:
            if not (hasattr(rule, 'needs_source_code') and rule.needs_source_code):
                # Set version context for versioned rules if available
                if self.use_version_aware and isinstance(rule, VersionedRule):
                    rule.set_version_context(context)
                results.extend(rule.check(tree, filename))

        return results

    def lint_directory(self, directory: Union[str, Path], pattern: str = "*.py") -> List[ValidationResult]:
        """Lint all Python files in a directory.

        Args:
            directory: Path to the directory to lint
            pattern: File pattern to match (default: "*.py")

        Returns:
            List of validation results
        """
        directory = Path(directory)
        results: List[ValidationResult] = []

        if not directory.exists():
            from .rules.base import ValidationResult, Severity
            return [ValidationResult(
                rule_id="directory-not-found",
                message=f"Directory not found: {directory}",
                severity=Severity.ERROR,
                line=1,
                column=0
            )]

        for filepath in directory.rglob(pattern):
            if filepath.is_file():
                results.extend(self.lint_file(filepath))

        return results

    def get_version_info(self, source_code: str) -> Dict:
        """Get version information from source code.

        Args:
            source_code: Python source code

        Returns:
            Dictionary with version information
        """
        if not self.use_version_aware:
            return {"version": "N/A", "features": {}}

        version_str = VersionParser.get_effective_version(source_code, self.default_version)
        dependencies = VersionParser.extract_dependencies(source_code)

        version = None
        if version_str != "latest":
            try:
                version = Version.parse(version_str)
            except ValueError:
                pass

        features = self.registry.get_features_for_version(version) if hasattr(self, 'registry') else {}

        return {
            "version": version_str,
            "parsed_version": str(version) if version else None,
            "dependencies": dependencies,
            "features": features
        }

    def compare_versions(self, source1: str, source2: str) -> Dict:
        """Compare version requirements between two source files.

        Args:
            source1: First source code
            source2: Second source code

        Returns:
            Comparison results
        """
        if not self.use_version_aware:
            return {"compatible": True, "breaking_changes": []}

        info1 = self.get_version_info(source1)
        info2 = self.get_version_info(source2)

        v1 = Version.parse(info1["version"]) if info1["version"] != "latest" else None
        v2 = Version.parse(info2["version"]) if info2["version"] != "latest" else None

        breaking_changes = []
        if hasattr(self, 'registry'):
            if v1 and v2 and v1 < v2:
                breaking_changes = self.registry.get_breaking_changes(v1, v2)
            elif v1 and v2 and v2 < v1:
                breaking_changes = self.registry.get_breaking_changes(v2, v1)

        return {
            "file1": info1,
            "file2": info2,
            "compatible": self._check_compatibility(v1, v2),
            "breaking_changes": breaking_changes
        }

    def _check_compatibility(self, v1: Optional[Version], v2: Optional[Version]) -> bool:
        """Check if two versions are compatible.

        Args:
            v1: First version
            v2: Second version

        Returns:
            True if compatible
        """
        if v1 is None or v2 is None:
            return True  # Latest is compatible with everything

        # Check major version compatibility
        if v1.major != v2.major:
            return False

        # Minor versions are backward compatible
        return True


# Backward compatibility - export the enhanced linter as VersionAwareGenVMLinter too
VersionAwareGenVMLinter = GenVMLinter