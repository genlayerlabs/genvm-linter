"""AST-based structure checks for GenLayer contracts."""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StructureWarning:
    """A structure warning from analysis."""

    code: str
    msg: str
    line: int
    col: int = 0


def check_structure(source: str | Path) -> list[StructureWarning]:
    """
    Check contract structure (magic comment, etc).

    Args:
        source: Contract source code or path to contract file

    Returns:
        List of structure warnings
    """
    if isinstance(source, Path):
        source = source.read_text()

    warnings: list[StructureWarning] = []

    # Check for magic comment header
    # Should have # { "Seq": [...] } at the start
    lines = source.split("\n")

    has_header = False
    header_content = []

    for i, line in enumerate(lines):
        if line.startswith("#"):
            header_content.append(line[1:].strip() if line.startswith("# ") else line[1:])
        else:
            break

    if header_content:
        header_text = "".join(header_content)
        # Check if it looks like a valid dependency header
        if '"Seq"' in header_text and '"Depends"' in header_text:
            has_header = True

    if not has_header:
        warnings.append(
            StructureWarning(
                code="W010",
                msg="Missing contract dependency header (# { \"Seq\": [...] })",
                line=1,
            )
        )

    # Check for py-genlayer dependency specifically
    if has_header:
        if "py-genlayer:" not in "".join(header_content):
            warnings.append(
                StructureWarning(
                    code="W011",
                    msg="Missing py-genlayer dependency in header",
                    line=1,
                )
            )

    return warnings
