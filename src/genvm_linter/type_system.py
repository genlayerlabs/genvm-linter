"""
Centralized type system definitions for GenVM.
This module provides a single source of truth for all type-related definitions
and compatibility checks used throughout the linter.
"""

from typing import Set, Dict, Optional


class GenVMTypeSystem:
    """Central repository for GenVM type definitions and equivalences."""

    # Unsigned integer types
    UNSIGNED_INT_TYPES: Set[str] = {
        "u8", "u16", "u24", "u32", "u40", "u48", "u56", "u64",
        "u72", "u80", "u88", "u96", "u104", "u112", "u120", "u128",
        "u136", "u144", "u152", "u160", "u168", "u176", "u184", "u192",
        "u200", "u208", "u216", "u224", "u232", "u240", "u248", "u256"
    }

    # Signed integer types
    SIGNED_INT_TYPES: Set[str] = {
        "i8", "i16", "i24", "i32", "i40", "i48", "i56", "i64",
        "i72", "i80", "i88", "i96", "i104", "i112", "i120", "i128",
        "i136", "i144", "i152", "i160", "i168", "i176", "i184", "i192",
        "i200", "i208", "i216", "i224", "i232", "i240", "i248", "i256"
    }

    # All sized integer types (excluding bigint)
    SIZED_INT_TYPES: Set[str] = UNSIGNED_INT_TYPES | SIGNED_INT_TYPES

    # All integer types including bigint
    ALL_INT_TYPES: Set[str] = SIZED_INT_TYPES | {"bigint"}

    # GenVM collection types
    GENVM_COLLECTIONS: Set[str] = {"DynArray", "TreeMap"}

    # Python collection types
    PYTHON_COLLECTIONS: Set[str] = {"list", "dict", "set"}

    # Type mappings from Python to GenVM
    PYTHON_TO_GENVM_MAPPING: Dict[str, str] = {
        "list": "DynArray",
        "dict": "TreeMap",
        "set": "DynArray",  # No direct set equivalent in GenVM
        "List": "DynArray",  # typing.List
        "Dict": "TreeMap",   # typing.Dict
        "Set": "DynArray"    # typing.Set
    }

    # Commonly used sized types for suggestions
    COMMON_SIZED_TYPES: Set[str] = {"u8", "u16", "u32", "u64", "u128", "u256", "i64", "i128", "i256", "bigint"}

    @classmethod
    def is_sized_int_type(cls, type_name: str) -> bool:
        """Check if a type is a sized integer type."""
        return type_name in cls.SIZED_INT_TYPES

    @classmethod
    def is_genvm_int_type(cls, type_name: str) -> bool:
        """Check if a type is any GenVM integer type (sized or bigint)."""
        return type_name in cls.ALL_INT_TYPES

    @classmethod
    def is_genvm_collection(cls, type_name: str) -> bool:
        """Check if a type is a GenVM collection type."""
        return type_name in cls.GENVM_COLLECTIONS

    @classmethod
    def is_python_collection(cls, type_name: str) -> bool:
        """Check if a type is a Python collection type."""
        return type_name in cls.PYTHON_COLLECTIONS

    @classmethod
    def get_genvm_equivalent(cls, python_type: str) -> Optional[str]:
        """Get the GenVM equivalent of a Python type."""
        return cls.PYTHON_TO_GENVM_MAPPING.get(python_type)

    @classmethod
    def is_type_compatible(cls, value_type: str, expected_type: str) -> bool:
        """
        Check if value_type is compatible with expected_type in GenVM.

        This handles type equivalences like:
        - int -> sized integer types (u256, i64, etc.)
        - list -> DynArray
        - dict -> TreeMap
        """
        # Exact match
        if value_type == expected_type:
            return True

        # int can be assigned to any sized integer type
        if value_type == "int" and expected_type in cls.SIZED_INT_TYPES:
            return True

        # list/List can be assigned to DynArray
        if value_type in ["list", "List"] and expected_type == "DynArray":
            return True

        # dict/Dict can be assigned to TreeMap
        if value_type in ["dict", "Dict"] and expected_type == "TreeMap":
            return True

        # Check if Python type has GenVM equivalent
        genvm_equiv = cls.get_genvm_equivalent(value_type)
        if genvm_equiv and genvm_equiv == expected_type:
            return True

        return False

    @classmethod
    def get_suggested_type_for_storage(cls, current_type: str) -> Optional[str]:
        """Get the suggested GenVM type for storage fields."""
        if current_type == "int":
            return "u256"  # Default suggestion for int in storage
        return cls.get_genvm_equivalent(current_type)

    @classmethod
    def should_use_int_in_signature(cls, type_name: str) -> bool:
        """Check if a type in method signature should be 'int' instead of sized."""
        return type_name in cls.SIZED_INT_TYPES  # Sized types should use 'int' in signatures


# Convenience exports for backward compatibility and easier imports
UNSIGNED_INT_TYPES = GenVMTypeSystem.UNSIGNED_INT_TYPES
SIGNED_INT_TYPES = GenVMTypeSystem.SIGNED_INT_TYPES
SIZED_INT_TYPES = GenVMTypeSystem.SIZED_INT_TYPES
ALL_INT_TYPES = GenVMTypeSystem.ALL_INT_TYPES
GENVM_COLLECTIONS = GenVMTypeSystem.GENVM_COLLECTIONS
PYTHON_COLLECTIONS = GenVMTypeSystem.PYTHON_COLLECTIONS
PYTHON_TO_GENVM_MAPPING = GenVMTypeSystem.PYTHON_TO_GENVM_MAPPING