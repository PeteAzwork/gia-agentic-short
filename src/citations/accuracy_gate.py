"""Citation accuracy verification.

Deterministic, filesystem-first gate that checks whether source-backed claim
statements align with their referenced evidence excerpts.

This is a lightweight early-warning system. It does not attempt full
fact-checking.

Design constraints:
- No LLM calls.
- Avoid persisting evidence excerpts into logs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Sequence, Set, Tuple

from loguru import logger

from src.tracing import safe_set_current_span_attributes
from src.utils.schema_validation import is_valid_claim_record, is_valid_evidence_item
from src.utils.validation import validate_project_folder


class CitationAccuracyGateError(ValueError):
    """Raised when the citation accuracy gate blocks execution."""


OnFailureAction = Literal["block", "downgrade"]


_STOPWORDS: Set[str] = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}


@dataclass(frozen=True)
class CitationAccuracyGateConfig:
    """Configuration for citation accuracy verification."""

    enabled: bool = False
    on_failure: OnFailureAction = "block"

    min_alignment_score: float = 0.18
    min_keyword_overlap: float = 0.06

    enable_entity_overlap: bool = False
    min_entity_overlap: float = 0.20

    enable_numeric_consistency: bool = False

    max_evidence_items_per_claim: int = 5

    @classmethod
    def from_context(cls, context: Dict[str, Any]) -> "CitationAccuracyGateConfig":
        raw = context.get("citation_accuracy_gate")
        if not isinstance(raw, dict):
            return cls()

        enabled = bool(raw.get("enabled", False))
        on_failure = raw.get("on_failure", "block")
        if on_failure not in ("block", "downgrade"):
            on_failure = "block"

        def _as_float(val: Any, default: float) -> float:
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        def _as_int(val: Any, default: int) -> int:
            try:
                return int(val)
            except (TypeError, ValueError):
                return default

        min_alignment_score = _as_float(raw.get("min_alignment_score", cls.min_alignment_score), cls.min_alignment_score)
        min_keyword_overlap = _as_float(raw.get("min_keyword_overlap", cls.min_keyword_overlap), cls.min_keyword_overlap)
        enable_entity_overlap = bool(raw.get("enable_entity_overlap", cls.enable_entity_overlap))
        min_entity_overlap = _as_float(raw.get("min_entity_overlap", cls.min_entity_overlap), cls.min_entity_overlap)
        enable_numeric_consistency = bool(raw.get("enable_numeric_consistency", cls.enable_numeric_consistency))
        max_evidence_items_per_claim = _as_int(raw.get("max_evidence_items_per_claim", cls.max_evidence_items_per_claim), cls.max_evidence_items_per_claim)

        # Clamp ranges.
        min_alignment_score = min(1.0, max(0.0, min_alignment_score))
        min_keyword_overlap = min(1.0, max(0.0, min_keyword_overlap))
        min_entity_overlap = min(1.0, max(0.0, min_entity_overlap))
        if max_evidence_items_per_claim < 1:
            max_evidence_items_per_claim = 1

        return cls(
            enabled=enabled,
            on_failure=on_failure,
            min_alignment_score=min_alignment_score,
            min_keyword_overlap=min_keyword_overlap,
            enable_entity_overlap=enable_entity_overlap,
            min_entity_overlap=min_entity_overlap,
            enable_numeric_consistency=enable_numeric_consistency,
            max_evidence_items_per_claim=max_evidence_items_per_claim,
        )


def _load_json_list(path: Path) -> Tuple[List[Any], Optional[str]]:
    if not path.exists():
        return [], None

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        return [], f"{type(e).__name__}"

    if not isinstance(payload, list):
        return [], "not_a_list"

    return payload, None


def _tokenize(text: str) -> Set[str]:
    tokens: set[str] = set()
    for raw in re.findall(r"[A-Za-z0-9]+", text.lower()):
        if len(raw) < 3:
            continue
        if raw.isdigit():
            # Keep numbers out of keyword overlap; they are handled separately.
            continue
        if raw in _STOPWORDS:
            continue
        tokens.add(raw)
    return tokens


def _extract_named_entities(text: str) -> Set[str]:
    # Heuristic: capture capitalized words and all-caps tokens.
    ents: set[str] = set()
    for m in re.findall(r"\b(?:[A-Z][a-zA-Z]{2,}|[A-Z]{2,})\b", text):
        ents.add(m.lower())
    return ents


def _extract_numbers(text: str) -> Set[str]:
    # Capture integers, decimals, and percents.
    nums: set[str] = set()
    for m in re.findall(r"\b\d+(?:\.\d+)?%?\b", text):
        nums.add(m)
    return nums


def _filter_year_like_numbers(nums: Set[str]) -> Set[str]:
    """Remove year-like integers (1900-2100) so they do not dominate numeric checks."""

    out: set[str] = set()
    for n in nums:
        if n.endswith("%"):
            out.add(n)
            continue

        if n.isdigit() and len(n) == 4:
            try:
                iv = int(n)
            except ValueError:
                out.add(n)
                continue
            if 1900 <= iv <= 2100:
                continue

        out.add(n)
    return out


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


class CitationAccuracyVerifier:
    """Score alignment between claim statement and evidence excerpts."""

    def __init__(self, config: CitationAccuracyGateConfig):
        self._cfg = config

    def verify_claim(self, claim: Mapping[str, Any], evidence_items: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        claim_id = str(claim.get("claim_id") or "").strip()
        statement = str(claim.get("statement") or "").strip()

        evidence_ids = claim.get("evidence_ids")
        evidence_ids_list: List[str] = []
        if isinstance(evidence_ids, list):
            evidence_ids_list = [str(x) for x in evidence_ids if isinstance(x, str) and x.strip()]

        citation_keys = claim.get("citation_keys")
        citation_keys_list: List[str] = []
        if isinstance(citation_keys, list):
            citation_keys_list = [str(x) for x in citation_keys if isinstance(x, str) and x.strip()]

        combined: List[str] = []
        used_ids: List[str] = []
        for item in evidence_items[: self._cfg.max_evidence_items_per_claim]:
            ev_id = item.get("evidence_id")
            if isinstance(ev_id, str) and ev_id.strip():
                used_ids.append(ev_id.strip())
            excerpt = item.get("excerpt")
            if isinstance(excerpt, str) and excerpt.strip():
                combined.append(excerpt)
            context = item.get("context")
            if isinstance(context, str) and context.strip():
                combined.append(context)

        evidence_text = "\n".join(combined)

        reasons: List[str] = []

        claim_tokens = _tokenize(statement)
        evidence_tokens = _tokenize(evidence_text)
        keyword_overlap = _jaccard(claim_tokens, evidence_tokens)

        entity_overlap = 0.0
        if self._cfg.enable_entity_overlap:
            claim_ents = _extract_named_entities(statement)
            evidence_ents = _extract_named_entities(evidence_text)
            entity_overlap = _jaccard(claim_ents, evidence_ents)

        numeric_ok = True
        if self._cfg.enable_numeric_consistency:
            claim_nums = _filter_year_like_numbers(_extract_numbers(statement))
            evidence_nums = _filter_year_like_numbers(_extract_numbers(evidence_text))
            if claim_nums and not claim_nums.issubset(evidence_nums):
                numeric_ok = False

        alignment_score = float(keyword_overlap)
        if self._cfg.enable_entity_overlap:
            alignment_score = min(1.0, alignment_score + 0.20 * float(entity_overlap))

        if self._cfg.enable_numeric_consistency and not numeric_ok:
            alignment_score = max(0.0, alignment_score * 0.50)

        ok = True

        if keyword_overlap < self._cfg.min_keyword_overlap:
            ok = False
            reasons.append("keyword_overlap_below_threshold")

        if self._cfg.enable_entity_overlap and entity_overlap < self._cfg.min_entity_overlap:
            ok = False
            reasons.append("entity_overlap_below_threshold")

        if self._cfg.enable_numeric_consistency and not numeric_ok:
            ok = False
            reasons.append("numeric_mismatch")

        if alignment_score < self._cfg.min_alignment_score:
            ok = False
            reasons.append("alignment_score_below_threshold")

        return {
            "claim_id": claim_id,
            "citation_keys": citation_keys_list,
            "evidence_ids": evidence_ids_list,
            "evidence_ids_used": used_ids,
            "checked": True,
            "ok": ok,
            "reasons": reasons,
            "alignment_score": round(alignment_score, 6),
            "keyword_overlap": round(keyword_overlap, 6),
            "entity_overlap": round(entity_overlap, 6),
            "numeric_ok": numeric_ok,
        }


def _iter_evidence_files(project_folder: Path) -> Iterable[Path]:
    sources_dir = project_folder / "sources"
    if not sources_dir.exists():
        return []
    return sorted(sources_dir.glob("*/evidence.json"))


def _load_evidence_map(project_folder: Path) -> Tuple[Dict[str, Dict[str, Any]], int, int]:
    """Return (by_evidence_id, invalid_items, evidence_files_scanned)."""

    by_id: Dict[str, Dict[str, Any]] = {}
    invalid = 0
    scanned = 0

    for evidence_path in _iter_evidence_files(project_folder):
        if not evidence_path.is_file():
            continue

        scanned += 1
        payload, err = _load_json_list(evidence_path)
        if err:
            logger.debug(f"Citation accuracy gate: evidence read error: {evidence_path}: {err}")
            continue

        for item in payload:
            if not isinstance(item, dict) or not is_valid_evidence_item(item):
                invalid += 1
                continue

            evidence_id = item.get("evidence_id")
            if isinstance(evidence_id, str) and evidence_id.strip():
                by_id[evidence_id.strip()] = item

    return by_id, invalid, scanned


def _load_source_backed_claims(project_folder: Path) -> Tuple[List[Dict[str, Any]], int, bool, Optional[str]]:
    claims_path = project_folder / "claims" / "claims.json"
    payload, err = _load_json_list(claims_path)

    invalid = 0
    claims: List[Dict[str, Any]] = []

    for item in payload:
        if not isinstance(item, dict) or not is_valid_claim_record(item):
            invalid += 1
            continue

        if str(item.get("kind")) != "source_backed":
            continue

        claims.append(item)

    return claims, invalid, claims_path.exists(), err


def check_citation_accuracy_gate(
    *,
    project_folder: str | Path,
    config: Optional[CitationAccuracyGateConfig] = None,
) -> Dict[str, Any]:
    """Check claim statement alignment against evidence excerpts.

    Expected locations:
    - claims/claims.json: list[ClaimRecord]
    - sources/*/evidence.json: list[EvidenceItem]

    Returns a dict with keys:
    - ok (bool)
    - enabled (bool)
    - action (pass|block|downgrade|disabled)
    - reports (list)
    - checked_claims_total (int)
    - failed_claims_total (int)
    - skipped_missing_evidence_total (int)
    - claims_file_present (bool)
    - claims_read_error (str|None)
    - claims_invalid_items (int)
    - evidence_invalid_items (int)
    - evidence_files_scanned (int)
    """

    cfg = config or CitationAccuracyGateConfig()
    pf = validate_project_folder(project_folder)

    if not cfg.enabled:
        result = {
            "ok": True,
            "enabled": False,
            "action": "disabled",
            "reports": [],
            "checked_claims_total": 0,
            "failed_claims_total": 0,
            "skipped_missing_evidence_total": 0,
            "claims_file_present": (pf / "claims" / "claims.json").exists(),
            "claims_read_error": None,
            "claims_invalid_items": 0,
            "evidence_invalid_items": 0,
            "evidence_files_scanned": 0,
        }

        safe_set_current_span_attributes(
            {
                "gate.name": "citation_accuracy",
                "gate.enabled": False,
                "gate.ok": True,
                "gate.action": "disabled",
            }
        )

        return result

    claims, claims_invalid, claims_file_present, claims_read_error = _load_source_backed_claims(pf)
    evidence_map, evidence_invalid, evidence_files_scanned = _load_evidence_map(pf)

    verifier = CitationAccuracyVerifier(cfg)

    reports: List[Dict[str, Any]] = []
    checked = 0
    failed = 0
    skipped_missing = 0

    for claim in claims:
        evidence_ids = claim.get("evidence_ids")
        evidence_ids_list: List[str] = []
        if isinstance(evidence_ids, list):
            evidence_ids_list = [str(x) for x in evidence_ids if isinstance(x, str) and x.strip()]

        if not evidence_ids_list:
            skipped_missing += 1
            reports.append(
                {
                    "claim_id": str(claim.get("claim_id") or "").strip(),
                    "citation_keys": claim.get("citation_keys") if isinstance(claim.get("citation_keys"), list) else [],
                    "evidence_ids": [],
                    "evidence_ids_used": [],
                    "checked": False,
                    "ok": True,
                    "reasons": ["missing_evidence_ids"],
                    "alignment_score": 0.0,
                    "keyword_overlap": 0.0,
                    "entity_overlap": 0.0,
                    "numeric_ok": True,
                }
            )
            continue

        evidence_items: List[Dict[str, Any]] = []
        missing_any = False
        for ev_id in evidence_ids_list:
            item = evidence_map.get(ev_id)
            if item is None:
                missing_any = True
                continue
            evidence_items.append(item)

        if missing_any or not evidence_items:
            skipped_missing += 1
            reports.append(
                {
                    "claim_id": str(claim.get("claim_id") or "").strip(),
                    "citation_keys": claim.get("citation_keys") if isinstance(claim.get("citation_keys"), list) else [],
                    "evidence_ids": evidence_ids_list,
                    "evidence_ids_used": [i.get("evidence_id") for i in evidence_items if isinstance(i.get("evidence_id"), str)],
                    "checked": False,
                    "ok": True,
                    "reasons": ["evidence_ids_unresolved"],
                    "alignment_score": 0.0,
                    "keyword_overlap": 0.0,
                    "entity_overlap": 0.0,
                    "numeric_ok": True,
                }
            )
            continue

        rep = verifier.verify_claim(claim, evidence_items)
        reports.append(rep)
        checked += 1
        if rep.get("ok") is False:
            failed += 1

    has_problem = failed > 0

    action: Literal["pass", "block", "downgrade"] = "pass"
    ok = True

    if has_problem:
        if cfg.on_failure == "block":
            action = "block"
            ok = False
        else:
            action = "downgrade"

    result = {
        "ok": ok,
        "enabled": True,
        "action": action,
        "reports": reports,
        "checked_claims_total": checked,
        "failed_claims_total": failed,
        "skipped_missing_evidence_total": skipped_missing,
        "claims_file_present": claims_file_present,
        "claims_read_error": claims_read_error,
        "claims_invalid_items": claims_invalid,
        "evidence_invalid_items": evidence_invalid,
        "evidence_files_scanned": evidence_files_scanned,
    }

    safe_set_current_span_attributes(
        {
            "gate.name": "citation_accuracy",
            "gate.enabled": True,
            "gate.ok": bool(ok),
            "gate.action": str(action),
            "citation_accuracy.checked_claims_total": int(checked),
            "citation_accuracy.failed_claims_total": int(failed),
            "citation_accuracy.skipped_missing_evidence_total": int(skipped_missing),
            "citation_accuracy.min_alignment_score": float(cfg.min_alignment_score),
            "citation_accuracy.min_keyword_overlap": float(cfg.min_keyword_overlap),
            "citation_accuracy.enable_entity_overlap": bool(cfg.enable_entity_overlap),
            "citation_accuracy.enable_numeric_consistency": bool(cfg.enable_numeric_consistency),
        }
    )

    return result


def enforce_citation_accuracy_gate(
    *,
    project_folder: str | Path,
    config: Optional[CitationAccuracyGateConfig] = None,
) -> Dict[str, Any]:
    """Enforce the citation accuracy gate.

    Raises:
        CitationAccuracyGateError: if the gate is enabled and action=block.
    """

    result = check_citation_accuracy_gate(project_folder=project_folder, config=config)
    if result.get("enabled") and result.get("action") == "block":
        raise CitationAccuracyGateError(f"Citation accuracy gate blocked: {result}")
    return result
