"""Filesystem helpers.

This module contains small utilities for mapping identifiers to filesystem-safe
paths used by the Sprint 1 evidence ledger.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

from __future__ import annotations


def validate_source_id(source_id: str) -> None:
    if not source_id or not isinstance(source_id, str):
        raise ValueError("source_id must be a non-empty string")
    if "/" in source_id or "\\" in source_id:
        raise ValueError("source_id must not contain path separators")
    if ".." in source_id:
        raise ValueError("source_id must not contain '..'")


def source_id_to_dirname(source_id: str) -> str:
    """Map a source_id to a filesystem-safe directory name.

    Notes:
    - Keeps alphanumerics plus '-', '_', '.'
    - Replaces other characters with '_'
    - Ensures a non-empty result
    """
    safe: list[str] = []
    for ch in source_id:
        if ch.isalnum() or ch in {"-", "_", "."}:
            safe.append(ch)
        else:
            safe.append("_")

    dirname = "".join(safe).strip("_")
    return dirname or "source"
