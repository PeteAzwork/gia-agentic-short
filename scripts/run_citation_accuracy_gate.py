"""Run the citation accuracy gate on a project folder.

Deterministic and offline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the citation accuracy gate")
    parser.add_argument("project_folder", help="Path to a project folder")
    parser.add_argument(
        "--enabled",
        action="store_true",
        help="Enable enforcement (default: false). If false, gate is permissive.",
    )
    parser.add_argument(
        "--on-failure",
        choices=["block", "downgrade"],
        default="block",
        help="Behavior when checks fail (default: block)",
    )
    parser.add_argument("--min-alignment-score", type=float, default=0.18)
    parser.add_argument("--min-keyword-overlap", type=float, default=0.06)
    parser.add_argument("--enable-entity-overlap", action="store_true")
    parser.add_argument("--min-entity-overlap", type=float, default=0.20)
    parser.add_argument("--enable-numeric-consistency", action="store_true")
    parser.add_argument("--max-evidence-items-per-claim", type=int, default=5)

    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.citations.accuracy_gate import (
        CitationAccuracyGateConfig,
        CitationAccuracyGateError,
        enforce_citation_accuracy_gate,
    )

    cfg = CitationAccuracyGateConfig(
        enabled=bool(args.enabled),
        on_failure=args.on_failure,
        min_alignment_score=max(0.0, min(1.0, float(args.min_alignment_score))),
        min_keyword_overlap=max(0.0, min(1.0, float(args.min_keyword_overlap))),
        enable_entity_overlap=bool(args.enable_entity_overlap),
        min_entity_overlap=max(0.0, min(1.0, float(args.min_entity_overlap))),
        enable_numeric_consistency=bool(args.enable_numeric_consistency),
        max_evidence_items_per_claim=max(1, int(args.max_evidence_items_per_claim)),
    )

    try:
        result = enforce_citation_accuracy_gate(project_folder=args.project_folder, config=cfg)
    except CitationAccuracyGateError as e:
        print(str(e))
        return 2

    print(f"project_folder: {args.project_folder}")
    print(f"enabled: {result.get('enabled')}")
    print(f"action: {result.get('action')}")
    print(f"checked_claims_total: {result.get('checked_claims_total')}")
    print(f"failed_claims_total: {result.get('failed_claims_total')}")
    print(f"skipped_missing_evidence_total: {result.get('skipped_missing_evidence_total')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
