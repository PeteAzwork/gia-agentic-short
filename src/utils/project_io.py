""" 
Project IO Utilities
====================
Helpers for reading project metadata safely.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_project_json(project_folder: str) -> Dict[str, Any]:
    """Load a project's project.json safely.

    Returns an empty dict when project.json is missing or unreadable.
    """
    project_json_path = Path(project_folder) / "project.json"
    if not project_json_path.exists():
        return {}

    try:
        with open(project_json_path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, IOError, OSError):
        return {}


def get_project_id(project_folder: str) -> str:
    """Return project id from project.json, or 'unknown' when unavailable."""
    data = load_project_json(project_folder)
    project_id = data.get("id")
    return str(project_id) if project_id else "unknown"
