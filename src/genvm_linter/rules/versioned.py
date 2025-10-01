"""Version-aware rule base classes for GenVM linter."""

import ast
from abc import abstractmethod
from typing import List, Optional, Union, Dict, Any
from dataclasses import dataclass, field

from .base import Rule, ValidationResult, Severity
from ..version import Version, VersionRange, VersionParser


@dataclass
class VersionContext:
    """Context containing version information for the current file."""
    version: Optional[Version] = None
    version_string: str = "latest"
    dependencies: Dict[str, str] = field(default_factory=dict)
    source_code: Optional[str] = None


class VersionedRule(Rule):
    """Base class for rules that are version-aware."""

    def __init__(
        self,
        rule_id: str,
        description: str,
        min_version: Optional[str] = None,
        max_version: Optional[str] = None,
        deprecated_version: Optional[str] = None
    ):
        """Initialize a versioned rule.

        Args:
            rule_id: Unique rule identifier
            description: Rule description
            min_version: Minimum version where this rule applies (inclusive)
            max_version: Maximum version where this rule applies (exclusive)
            deprecated_version: Version where this rule is deprecated
        """
        super().__init__(rule_id, description)
        self.min_version = Version.parse(min_version) if min_version else None
        self.max_version = Version.parse(max_version) if max_version else None
        self.deprecated_version = Version.parse(deprecated_version) if deprecated_version else None
        self.version_context: Optional[VersionContext] = None

    def set_version_context(self, context: VersionContext) -> None:
        """Set the version context for this rule.

        Args:
            context: Version context containing file version info
        """
        self.version_context = context

    def is_applicable(self, version: Optional[Version] = None) -> bool:
        """Check if this rule is applicable for the given version.

        Args:
            version: Version to check, uses context version if not provided

        Returns:
            True if rule should be applied
        """
        if version is None:
            if self.version_context and self.version_context.version:
                version = self.version_context.version
            else:
                # If no version specified, treat as latest
                return self.max_version is None

        # Check if version is in range
        if not version.is_compatible_with(self.min_version, self.max_version):
            return False

        # Check if deprecated
        if self.deprecated_version and version >= self.deprecated_version:
            return False

        return True

    def check(self, node: Union[ast.AST, str], filename: Optional[str] = None) -> List[ValidationResult]:
        """Check the node/source for violations, considering version.

        Args:
            node: AST node or source code to check
            filename: Optional filename for error reporting

        Returns:
            List of validation results
        """
        # Extract version if we have source code
        if isinstance(node, str) and not self.version_context:
            self.version_context = VersionContext(
                version_string=VersionParser.get_effective_version(node),
                dependencies=VersionParser.extract_dependencies(node),
                source_code=node
            )
            # Try to parse version
            if self.version_context.version_string != "latest":
                try:
                    self.version_context.version = Version.parse(self.version_context.version_string)
                except ValueError:
                    pass

        # Check if rule is applicable
        if not self.is_applicable():
            return []

        # Perform version-specific check
        return self.check_versioned(node, filename)

    @abstractmethod
    def check_versioned(self, node: Union[ast.AST, str], filename: Optional[str] = None) -> List[ValidationResult]:
        """Perform the actual version-specific check.

        This method should be implemented by subclasses to perform
        the actual validation logic.

        Args:
            node: AST node or source code to check
            filename: Optional filename for error reporting

        Returns:
            List of validation results
        """
        pass


class EvolvingRule(VersionedRule):
    """Rule that evolves across versions with different implementations."""

    def __init__(
        self,
        rule_id: str,
        description: str,
        implementations: Dict[str, 'VersionedRuleImplementation']
    ):
        """Initialize an evolving rule with multiple version implementations.

        Args:
            rule_id: Unique rule identifier
            description: Rule description
            implementations: Dictionary of version range to implementation
        """
        super().__init__(rule_id, description)
        self.implementations = implementations

    def check_versioned(self, node: Union[ast.AST, str], filename: Optional[str] = None) -> List[ValidationResult]:
        """Check using the appropriate version implementation.

        Args:
            node: AST node or source code to check
            filename: Optional filename for error reporting

        Returns:
            List of validation results
        """
        # Get current version
        current_version = self.version_context.version if self.version_context else None

        # Find applicable implementation
        for version_range_str, implementation in self.implementations.items():
            version_range = VersionRange.parse(version_range_str)

            # Use latest if no version specified
            if current_version is None and version_range.max_version is None:
                return implementation.check(node, filename, self)

            # Check if current version matches range
            if current_version and version_range.contains(current_version):
                return implementation.check(node, filename, self)

        return []


@dataclass
class VersionedRuleImplementation:
    """Implementation for a specific version range of a rule."""

    def check(
        self,
        node: Union[ast.AST, str],
        filename: Optional[str],
        parent_rule: VersionedRule
    ) -> List[ValidationResult]:
        """Check implementation for this version.

        Args:
            node: AST node or source code to check
            filename: Optional filename
            parent_rule: Parent rule for creating results

        Returns:
            List of validation results
        """
        raise NotImplementedError


class ConditionalRule(VersionedRule):
    """Rule that is conditionally enabled based on version features."""

    def __init__(
        self,
        rule_id: str,
        description: str,
        feature_flag: str,
        min_version: Optional[str] = None,
        max_version: Optional[str] = None
    ):
        """Initialize a conditional rule.

        Args:
            rule_id: Unique rule identifier
            description: Rule description
            feature_flag: Feature flag that must be enabled
            min_version: Minimum version
            max_version: Maximum version
        """
        super().__init__(rule_id, description, min_version, max_version)
        self.feature_flag = feature_flag

    def is_feature_enabled(self, version: Optional[Version] = None) -> bool:
        """Check if the feature is enabled for this version.

        Args:
            version: Version to check

        Returns:
            True if feature is enabled
        """
        # This would check against a feature configuration
        # For now, we'll implement basic version-based features
        if version is None:
            return True  # Latest has all features

        # Example feature flags (to be configured externally)
        feature_versions = {
            "lazy_objects": Version(0, 2, 0),
            "non_deterministic_storage": Version(0, 3, 0),
            "advanced_types": Version(0, 4, 0),
        }

        if self.feature_flag in feature_versions:
            return version >= feature_versions[self.feature_flag]

        return True  # Unknown features default to enabled

    def is_applicable(self, version: Optional[Version] = None) -> bool:
        """Check if rule is applicable, including feature check.

        Args:
            version: Version to check

        Returns:
            True if rule should be applied
        """
        if not super().is_applicable(version):
            return False

        return self.is_feature_enabled(version)