"""Subprocess text decoding helpers.

These helpers make subprocess output handling deterministic and robust when
stdout/stderr contain arbitrary bytes.
"""

from __future__ import annotations


def to_text(value: object, *, encoding: str = "utf-8") -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode(encoding, errors="replace")
    return ""
