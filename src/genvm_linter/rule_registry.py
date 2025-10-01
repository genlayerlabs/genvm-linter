"""Rule registry for managing version-specific rules."""

from typing import Dict, List, Optional, Set, Type, Union, TYPE_CHECKING
from dataclasses import dataclass, field
import json
import yaml
from pathlib import Path

from .rules.base import Rule
from .version import Version, VersionRange

if TYPE_CHECKING:
    from .rules.versioned import VersionContext


@dataclass
class RuleDefinition:
    """Definition of a rule with version constraints."""
    rule_class: Type[Rule]
    min_version: Optional[Version] = None
    max_version: Optional[Version] = None
    enabled_by_default: bool = True
    allowed_hashes: List[str] = field(default_factory=list)  # List of hashes where rule is enabled
    excluded_hashes: List[str] = field(default_factory=list)  # List of hashes where rule is disabled
    feature_flags: Set[str] = field(default_factory=set)  # Deprecated but kept for compatibility
    breaking_changes: Dict[str, str] = field(default_factory=dict)  # version -> description


class RuleRegistry:
    """Registry for managing version-aware rules."""

    def __init__(self, config_file: Optional[Path] = None):
        """Initialize the rule registry.

        Args:
            config_file: Optional path to version configuration file
        """
        self.rules: Dict[str, List[RuleDefinition]] = {}
        self.version_features: Dict[str, Dict[str, bool]] = {}  # version -> features
        self.breaking_changes: Dict[str, List[str]] = {}  # version -> list of changes
        self.current_version_context: Optional[VersionContext] = None

        # Always setup default rules
        self.setup_default_rules()

        # Then load config to override if provided
        if config_file and config_file.exists():
            self.load_config(config_file)

    def setup_default_rules(self):
        """Setup default rule configurations for different versions."""
        from .rules.contract import (
            MagicCommentRule,
            ImportRule,
            ContractClassRule
        )
        from .rules.decorators import DecoratorRule
        from .rules.types import TypeSystemRule
        from .rules.genvm_patterns import GenVMApiUsageRule, LazyObjectRule, StoragePatternRule
        from .rules.python_types import PythonTypeCheckRule, GenVMTypeStubRule
        from .rules.genvm_dataclasses import DataclassValidation
        from .rules.nondet_storage import NondetStorageAccessRule
        from .rules.test_rules import FutureFeatureRule, ExperimentalHashRule, DebugModeRule

        # Contract rules (now work with all versions)
        self.register_rule("magic-comment", RuleDefinition(
            rule_class=MagicCommentRule,
            enabled_by_default=True
        ))

        self.register_rule("import", RuleDefinition(
            rule_class=ImportRule,
            enabled_by_default=True
        ))

        self.register_rule("contract-class", RuleDefinition(
            rule_class=ContractClassRule,
            enabled_by_default=True
        ))

        # Core rules (all versions)
        self.register_rule("decorator", RuleDefinition(
            rule_class=DecoratorRule,
            enabled_by_default=True
        ))

        self.register_rule("type-system", RuleDefinition(
            rule_class=TypeSystemRule,
            enabled_by_default=True
        ))

        # Pattern rules with version constraints
        self.register_rule("genvm-api", RuleDefinition(
            rule_class=GenVMApiUsageRule,
            enabled_by_default=True
        ))

        self.register_rule("lazy-object", RuleDefinition(
            rule_class=LazyObjectRule,
            enabled_by_default=True  # Available in all versions now
        ))

        self.register_rule("storage-pattern", RuleDefinition(
            rule_class=StoragePatternRule,
            enabled_by_default=True
        ))

        # Type checking rules
        self.register_rule("python-types", RuleDefinition(
            rule_class=PythonTypeCheckRule,
            enabled_by_default=True
        ))

        self.register_rule("type-stub", RuleDefinition(
            rule_class=GenVMTypeStubRule,
            enabled_by_default=True  # Available in all versions now
        ))

        # Advanced features
        self.register_rule("dataclass", RuleDefinition(
            rule_class=DataclassValidation,
            enabled_by_default=True  # Available in all versions now
        ))

        self.register_rule("nondet-storage", RuleDefinition(
            rule_class=NondetStorageAccessRule,
            enabled_by_default=True  # Available in all versions now
        ))

        # Test rules for demonstrating version/hash-specific behavior
        self.register_rule("future-feature", RuleDefinition(
            rule_class=FutureFeatureRule,
            min_version=Version(9, 9, 9),  # Only in v9.9.9
            max_version=Version(10, 0, 0),
            enabled_by_default=True
        ))

        self.register_rule("experimental-hash", RuleDefinition(
            rule_class=ExperimentalHashRule,
            enabled_by_default=True  # Checks hash internally
        ))

        self.register_rule("debug-mode", RuleDefinition(
            rule_class=DebugModeRule,
            enabled_by_default=True  # Active unless using test dependency
        ))

        # Define version features (kept for historical documentation only)
        # All features are now available in all versions
        self.version_features = {
            "0.1.0": {},
            "0.2.0": {},
            "0.3.0": {},
            "latest": {"all_features": True}
        }

        # Define breaking changes
        self.breaking_changes = {
            "0.2.0": [
                "Star imports no longer required, specific imports allowed",
                "__init__ method now optional for contract classes",
                "Lazy object support introduced"
            ],
            "0.3.0": [
                "Dataclass support added",
                "Non-deterministic storage patterns introduced",
                "At least one public method required in contracts"
            ]
        }

    def register_rule(self, rule_id: str, definition: RuleDefinition):
        """Register a rule definition.

        Args:
            rule_id: Unique identifier for the rule
            definition: Rule definition with version constraints
        """
        if rule_id not in self.rules:
            self.rules[rule_id] = []
        self.rules[rule_id].append(definition)

    def get_rules_for_version(self, version: Optional[Version] = None) -> List[Rule]:
        """Get all rules applicable for a specific version.

        Args:
            version: Target version, None for latest

        Returns:
            List of rule instances
        """
        applicable_rules = []

        for rule_id, definitions in self.rules.items():
            for definition in definitions:
                if self._is_rule_applicable(definition, version):
                    # Create rule instance
                    rule_instance = definition.rule_class()

                    # Set version context if versioned
                    from .rules.versioned import VersionedRule
                    if isinstance(rule_instance, VersionedRule):
                        if self.current_version_context:
                            rule_instance.set_version_context(self.current_version_context)

                    applicable_rules.append(rule_instance)
                    break  # Use first applicable definition

        return applicable_rules

    def _is_rule_applicable(self, definition: RuleDefinition, version: Optional[Version]) -> bool:
        """Check if a rule definition is applicable for a version or hash.

        Args:
            definition: Rule definition
            version: Target version

        Returns:
            True if rule should be applied
        """
        if not definition.enabled_by_default:
            return False

        # Get current hash from version context if available
        current_hash = None
        if self.current_version_context and self.current_version_context.dependencies:
            # Get the first hash from dependencies (usually py-genlayer)
            for dep_name, dep_value in self.current_version_context.dependencies.items():
                # Check if it's a hash (52 chars, alphanumeric)
                if len(dep_value) == 52 and dep_value.isalnum():
                    current_hash = dep_value
                    break

        # Check hash exclusions first (takes precedence)
        if current_hash and definition.excluded_hashes:
            if current_hash in definition.excluded_hashes:
                return False

        # Check hash allowlist (if specified, hash must be in list)
        if current_hash and definition.allowed_hashes:
            if current_hash not in definition.allowed_hashes:
                return False

        # Check version constraints
        if version:
            if definition.min_version and version < definition.min_version:
                return False
            if definition.max_version and version >= definition.max_version:
                return False

            # Check feature flags (deprecated but kept for compatibility)
            version_str = str(version)
            if version_str in self.version_features:
                features = self.version_features[version_str]
                for flag in definition.feature_flags:
                    if not features.get(flag, False):
                        return False

        return True

    def get_breaking_changes(self, from_version: Version, to_version: Version) -> List[str]:
        """Get breaking changes between two versions.

        Args:
            from_version: Starting version
            to_version: Target version

        Returns:
            List of breaking change descriptions
        """
        changes = []

        for version_str, version_changes in self.breaking_changes.items():
            version = Version.parse(version_str)
            if from_version < version <= to_version:
                changes.extend(version_changes)

        return changes

    def load_config(self, config_file: Path):
        """Load version configuration from file.

        Args:
            config_file: Path to YAML configuration file
        """
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        # Load version features
        if 'versions' in config:
            for version_str, features in config['versions'].items():
                self.version_features[version_str] = features

        # Load breaking changes
        if 'breaking_changes' in config:
            self.breaking_changes = config['breaking_changes']

        # Load rule configurations
        if 'rules' in config:
            for rule_config in config['rules']:
                # Dynamic rule loading would go here
                pass

    def save_config(self, config_file: Path):
        """Save current configuration to file.

        Args:
            config_file: Path to save configuration
        """
        config = {
            'versions': self.version_features,
            'breaking_changes': self.breaking_changes,
            'rules': []  # Would serialize rule definitions
        }

        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

    def set_version_context(self, context: "VersionContext"):
        """Set the current version context for all rules.

        Args:
            context: Version context to use
        """
        self.current_version_context = context

    def get_features_for_version(self, version: Optional[Version]) -> Dict[str, bool]:
        """Get feature flags for a specific version.

        Args:
            version: Target version

        Returns:
            Dictionary of feature flags
        """
        if version:
            version_str = str(version)
            if version_str in self.version_features:
                return self.version_features[version_str]

            # Find closest version
            for v_str in sorted(self.version_features.keys(), reverse=True):
                if v_str == "latest":
                    continue
                try:
                    v = Version.parse(v_str)
                    if v <= version:
                        return self.version_features[v_str]
                except ValueError:
                    continue

        return self.version_features.get("latest", {})