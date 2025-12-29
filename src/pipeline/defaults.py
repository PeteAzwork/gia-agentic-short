"""Shared default configuration for pipeline components.

This module centralizes default gate configurations to avoid duplication
across runner.py and standalone scripts.

Gate Modes:
- "warn" (default): Log warning and continue with degraded output
- "block": Fail the pipeline if gate conditions are not met

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict


class GateMode(str, Enum):
    """Gate operation mode."""
    WARN = "warn"      # Log warning, continue with degraded output
    BLOCK = "block"    # Fail the pipeline if gate fails
    SKIP = "skip"      # Skip the gate entirely


def default_gate_config(mode: str = "warn") -> Dict[str, Dict[str, Any]]:
    """Return default gate configurations.

    Args:
        mode: Default mode for all gates. One of "warn", "block", or "skip".
              Default is "warn" which enables gates in degradation mode.
              
    Returns:
        Dict of gate configurations.
        
    By default, gates are enabled in 'warn' mode (downgrade on failure).
    This ensures issues are surfaced without blocking the pipeline.
    
    To enable strict blocking mode:
        config = default_gate_config(mode="block")
    """
    on_failure = "block" if mode == "block" else "downgrade"
    enabled = mode != "skip"
    
    return {
        "evidence_gate": {
            "enabled": enabled,
            "require_evidence": enabled,
            "min_items_per_source": 1,
            "on_failure": on_failure,
        },
        "citation_gate": {
            "enabled": enabled,
            "on_missing": on_failure,
            "on_unverified": on_failure,
        },
        "computation_gate": {
            "enabled": enabled,
            "on_missing_metrics": on_failure,
        },
        "claim_evidence_gate": {
            "enabled": enabled,
            "on_failure": on_failure,
        },
        "literature_gate": {
            "enabled": enabled,
            "on_failure": on_failure,
        },
        "analysis_gate": {
            "enabled": enabled,
            "on_failure": on_failure,
        },
        "citation_accuracy_gate": {
            "enabled": enabled,
            "on_failure": on_failure,
        },
    }
