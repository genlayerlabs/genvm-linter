# Changelog

All notable changes to the GenVM Linter project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of GenVM Linter
- Python package for linting GenVM intelligent contracts
- VS Code extension for IDE integration
- Comprehensive validation rules:
  - Magic comment validation
  - GenLayer import checking
  - Contract class structure validation
  - Method decorator validation (`@gl.public.view`, `@gl.public.write`)
  - Type system enforcement (sized integers, collections, dataclasses)
- MyPy integration for Python type checking
- Support for GenVM-specific types:
  - Sized integers (`u8`, `u16`, `u32`, `u64`, `u128`, `u256`, `i8`-`i256`)
  - Collections (`TreeMap`, `DynArray`)
  - Special types (`Address`, `bigint`)
- VS Code features:
  - Real-time diagnostics
  - Hover documentation
  - Auto-completion for GenVM types
  - Code actions and quick fixes
  - Inlay hints for type information
  - Signature help
- Command-line interface with multiple output formats
- Configurable severity levels and rule exclusions
- Code snippets for common patterns
- Custom syntax highlighting for GenVM constructs
- VS Code command "Create New Contract" for quickly generating contract templates
- Support for creating contracts via Explorer context menu
- Auto-installation prompt for missing Python dependencies
- Improved type inference for GenVM-specific types
- Comprehensive ARCHITECTURE.md documentation
- CONTRIBUTING.md guidelines for contributors
- Improved folder structure with organized test directories

### Changed
- **BREAKING**: `__init__` method is now required for all GenVM contracts (changed from WARNING to ERROR)
- Improved error messages with more helpful suggestions
- Reorganized project structure with proper test directories
- Updated documentation to remove personal paths and debug artifacts
- Replaced "smart contract" with "intelligent contract" throughout documentation
- Separated VS Code extension documentation from Python linter documentation
- Improved documentation structure and content

### Fixed
- Documentation links now point to correct GenLayer documentation pages
- Hover provider shows accurate links for all GenVM types
- Fixed type checking for sized integers in return types

### Removed
- Removed debug-specific markdown files
- Removed internal test documentation