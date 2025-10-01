"""Version management for GenVM contracts."""

import re
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum


class VersionComponent(Enum):
    """Version component types for semantic versioning."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


@dataclass
class Version:
    """Semantic version representation for GenVM."""

    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None

    def __str__(self) -> str:
        """String representation of version."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        return version

    @classmethod
    def parse(cls, version_string: str) -> "Version":
        """Parse a version string into a Version object.

        Args:
            version_string: Version string (e.g., "0.1.0", "v0.1.0", "0.1.0-beta")

        Returns:
            Version object

        Raises:
            ValueError: If version string is invalid
        """
        # Remove 'v' prefix if present
        version_string = version_string.lstrip('v')

        # Match semantic version pattern
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$'
        match = re.match(pattern, version_string)

        if not match:
            raise ValueError(f"Invalid version string: {version_string}")

        major, minor, patch, prerelease = match.groups()

        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease
        )

    def __eq__(self, other: object) -> bool:
        """Check version equality."""
        if not isinstance(other, Version):
            return False
        return (self.major, self.minor, self.patch, self.prerelease) == \
               (other.major, other.minor, other.patch, other.prerelease)

    def __lt__(self, other: "Version") -> bool:
        """Check if this version is less than another."""
        # Compare major, minor, patch
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

        # Handle prerelease versions
        if self.prerelease and not other.prerelease:
            return True  # Prerelease is less than release
        if not self.prerelease and other.prerelease:
            return False  # Release is greater than prerelease
        if self.prerelease and other.prerelease:
            return self.prerelease < other.prerelease

        return False

    def __le__(self, other: "Version") -> bool:
        """Check if this version is less than or equal to another."""
        return self == other or self < other

    def __gt__(self, other: "Version") -> bool:
        """Check if this version is greater than another."""
        return not self <= other

    def __ge__(self, other: "Version") -> bool:
        """Check if this version is greater than or equal to another."""
        return not self < other

    def is_compatible_with(self, min_version: Optional["Version"], max_version: Optional["Version"]) -> bool:
        """Check if this version is within the specified range.

        Args:
            min_version: Minimum version (inclusive), None means no minimum
            max_version: Maximum version (exclusive), None means no maximum

        Returns:
            True if version is within range
        """
        if min_version and self < min_version:
            return False
        if max_version and self >= max_version:
            return False
        return True


class VersionParser:
    """Parser for extracting version information from GenVM contract source."""

    # Pattern for version comment (e.g., # v0.1.0)
    VERSION_COMMENT_PATTERN = re.compile(r'^\s*#\s*v?(\d+\.\d+\.\d+(?:-\w+)?)\s*$', re.MULTILINE)

    # Pattern for magic comment with dependencies
    MAGIC_COMMENT_PATTERN = re.compile(
        r'#\s*\{\s*"Depends"\s*:\s*"py-genlayer:([^"]+)"\s*\}',
        re.IGNORECASE
    )

    # Pattern for complex dependencies with Seq
    SEQ_PATTERN = re.compile(
        r'#\s*\{\s*"Seq"\s*:\s*\[(.*?)\]\s*\}',
        re.DOTALL | re.IGNORECASE
    )

    @classmethod
    def extract_version(cls, source_code: str) -> Optional[Version]:
        """Extract version from source code.

        Looks for:
        1. Version comment (# v0.1.0)
        2. Version in magic comment dependencies

        Args:
            source_code: Python source code

        Returns:
            Version object or None if no version found
        """
        lines = source_code.splitlines()

        # First, check for explicit version comment before imports
        for line in lines:
            # Stop at first import
            if line.strip().startswith(('import ', 'from ')):
                break

            # Check for version comment
            match = cls.VERSION_COMMENT_PATTERN.match(line)
            if match:
                try:
                    return Version.parse(match.group(1))
                except ValueError:
                    continue

        # If no explicit version, return None (will default to latest)
        return None

    @classmethod
    def extract_dependencies(cls, source_code: str) -> Dict[str, str]:
        """Extract dependency information from magic comments.

        Args:
            source_code: Python source code

        Returns:
            Dictionary of dependency name to version/hash
        """
        dependencies = {}

        # Check for simple Depends format
        match = cls.MAGIC_COMMENT_PATTERN.search(source_code)
        if match:
            dependencies['py-genlayer'] = match.group(1)
            return dependencies

        # Check for complex Seq format
        match = cls.SEQ_PATTERN.search(source_code)
        if match:
            seq_content = match.group(1)
            # Parse individual dependencies from Seq
            dep_pattern = re.compile(r'"Depends"\s*:\s*"([^:]+):([^"]+)"')
            for dep_match in dep_pattern.finditer(seq_content):
                dep_name = dep_match.group(1)
                dep_version = dep_match.group(2)
                dependencies[dep_name] = dep_version

        return dependencies

    @classmethod
    def get_effective_version(cls, source_code: str, default_version: str = "latest") -> str:
        """Get the effective version for a contract.

        Args:
            source_code: Python source code
            default_version: Default version if none specified

        Returns:
            Version string (e.g., "0.1.0" or "latest")
        """
        # Try to extract explicit version
        version = cls.extract_version(source_code)
        if version:
            return str(version)

        # Check dependencies for version hints
        deps = cls.extract_dependencies(source_code)
        if 'py-genlayer' in deps:
            dep_version = deps['py-genlayer']
            # If dependency is "latest" or "test", use default
            if dep_version in ('latest', 'test'):
                return default_version
            # Otherwise, try to parse as version
            try:
                return str(Version.parse(dep_version))
            except ValueError:
                # Might be a hash, use default
                return default_version

        return default_version


class VersionRange:
    """Represents a range of versions."""

    def __init__(self, min_version: Optional[Version] = None, max_version: Optional[Version] = None):
        """Initialize version range.

        Args:
            min_version: Minimum version (inclusive)
            max_version: Maximum version (exclusive)
        """
        self.min_version = min_version
        self.max_version = max_version

    @classmethod
    def parse(cls, range_string: str) -> "VersionRange":
        """Parse a version range string.

        Supports formats:
        - ">=0.1.0" - minimum version
        - "<0.2.0" - maximum version
        - ">=0.1.0 <0.2.0" - range
        - "^0.1.0" - compatible with 0.1.x
        - "~0.1.0" - compatible with 0.1.0 to 0.2.0

        Args:
            range_string: Version range specification

        Returns:
            VersionRange object
        """
        min_version = None
        max_version = None

        # Handle caret notation (^0.1.0 means >=0.1.0 <0.2.0)
        if range_string.startswith('^'):
            base_version = Version.parse(range_string[1:])
            min_version = base_version
            max_version = Version(base_version.major, base_version.minor + 1, 0)
            return cls(min_version, max_version)

        # Handle tilde notation (~0.1.0 means >=0.1.0 <0.2.0)
        if range_string.startswith('~'):
            base_version = Version.parse(range_string[1:])
            min_version = base_version
            max_version = Version(base_version.major, base_version.minor + 1, 0)
            return cls(min_version, max_version)

        # Parse individual constraints
        constraints = range_string.split()
        for constraint in constraints:
            if constraint.startswith('>='):
                min_version = Version.parse(constraint[2:])
            elif constraint.startswith('>'):
                # Convert > to >= next patch
                v = Version.parse(constraint[1:])
                min_version = Version(v.major, v.minor, v.patch + 1)
            elif constraint.startswith('<='):
                # Convert <= to < next patch
                v = Version.parse(constraint[2:])
                max_version = Version(v.major, v.minor, v.patch + 1)
            elif constraint.startswith('<'):
                max_version = Version.parse(constraint[1:])
            elif constraint.startswith('='):
                v = Version.parse(constraint[1:])
                min_version = v
                max_version = Version(v.major, v.minor, v.patch + 1)
            else:
                # Exact version
                v = Version.parse(constraint)
                min_version = v
                max_version = Version(v.major, v.minor, v.patch + 1)

        return cls(min_version, max_version)

    def contains(self, version: Version) -> bool:
        """Check if a version is within this range.

        Args:
            version: Version to check

        Returns:
            True if version is in range
        """
        return version.is_compatible_with(self.min_version, self.max_version)