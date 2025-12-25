import json

import pytest

from src.citations.accuracy_gate import (
    CitationAccuracyGateConfig,
    CitationAccuracyGateError,
    check_citation_accuracy_gate,
    enforce_citation_accuracy_gate,
)
from src.evidence.store import EvidenceStore


def _write_claims(project_folder, claims):
    (project_folder / "claims").mkdir(exist_ok=True)
    (project_folder / "claims" / "claims.json").write_text(
        json.dumps(claims, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _minimal_evidence_item(*, evidence_id: str, source_id: str, excerpt: str, context: str | None = None):
    item = {
        "schema_version": "1.0",
        "evidence_id": evidence_id,
        "source_id": source_id,
        "kind": "quote",
        "locator": {"type": "file", "value": "dummy.txt", "span": {"start_line": 1, "end_line": 1}},
        "excerpt": excerpt,
        "created_at": "2025-01-01T00:00:00Z",
        "parser": {"name": "mvp"},
    }
    if context is not None:
        item["context"] = context
    return item


@pytest.mark.unit
def test_citation_accuracy_gate_aligned_claim_passes(temp_project_folder):
    store = EvidenceStore(str(temp_project_folder))
    store.write_evidence_items(
        "source1",
        [
            _minimal_evidence_item(
                evidence_id="ev1",
                source_id="source1",
                excerpt="In 2020, the inflation rate increased to 5 percent.",
            )
        ],
    )

    _write_claims(
        temp_project_folder,
        [
            {
                "schema_version": "1.0",
                "claim_id": "c1",
                "kind": "source_backed",
                "statement": "The inflation rate increased in 2020 to 5 percent.",
                "citation_keys": ["smith2020"],
                "evidence_ids": ["ev1"],
                "created_at": "2025-01-01T00:00:00Z",
            }
        ],
    )

    cfg = CitationAccuracyGateConfig(
        enabled=True,
        on_failure="block",
        min_alignment_score=0.10,
        min_keyword_overlap=0.05,
        enable_numeric_consistency=True,
    )

    result = check_citation_accuracy_gate(project_folder=str(temp_project_folder), config=cfg)
    assert result["ok"] is True
    assert result["action"] == "pass"
    assert result["checked_claims_total"] == 1
    assert result["failed_claims_total"] == 0
    assert result["reports"][0]["ok"] is True
    assert result["reports"][0]["alignment_score"] > 0


@pytest.mark.unit
def test_citation_accuracy_gate_misaligned_claim_downgrades(temp_project_folder):
    store = EvidenceStore(str(temp_project_folder))
    store.write_evidence_items(
        "source1",
        [
            _minimal_evidence_item(
                evidence_id="ev1",
                source_id="source1",
                excerpt="GDP increased to 5 percent in 2020.",
            )
        ],
    )

    _write_claims(
        temp_project_folder,
        [
            {
                "schema_version": "1.0",
                "claim_id": "c1",
                "kind": "source_backed",
                "statement": "Inflation decreased to 1 percent in 2020.",
                "citation_keys": ["smith2020"],
                "evidence_ids": ["ev1"],
                "created_at": "2025-01-01T00:00:00Z",
            }
        ],
    )

    cfg = CitationAccuracyGateConfig(
        enabled=True,
        on_failure="downgrade",
        min_alignment_score=0.25,
        min_keyword_overlap=0.15,
        enable_numeric_consistency=True,
    )

    result = check_citation_accuracy_gate(project_folder=str(temp_project_folder), config=cfg)
    assert result["ok"] is True
    assert result["action"] == "downgrade"
    assert result["checked_claims_total"] == 1
    assert result["failed_claims_total"] == 1

    rep = result["reports"][0]
    assert rep["checked"] is True
    assert rep["ok"] is False
    assert rep["reasons"]


@pytest.mark.unit
def test_citation_accuracy_gate_blocks_when_configured(temp_project_folder):
    store = EvidenceStore(str(temp_project_folder))
    store.write_evidence_items(
        "source1",
        [
            _minimal_evidence_item(
                evidence_id="ev1",
                source_id="source1",
                excerpt="GDP increased to 5 percent in 2020.",
            )
        ],
    )

    _write_claims(
        temp_project_folder,
        [
            {
                "schema_version": "1.0",
                "claim_id": "c1",
                "kind": "source_backed",
                "statement": "Inflation decreased to 1 percent in 2020.",
                "citation_keys": ["smith2020"],
                "evidence_ids": ["ev1"],
                "created_at": "2025-01-01T00:00:00Z",
            }
        ],
    )

    cfg = CitationAccuracyGateConfig(
        enabled=True,
        on_failure="block",
        min_alignment_score=0.25,
        min_keyword_overlap=0.15,
        enable_numeric_consistency=True,
    )

    with pytest.raises(CitationAccuracyGateError):
        enforce_citation_accuracy_gate(project_folder=str(temp_project_folder), config=cfg)


@pytest.mark.unit
def test_citation_accuracy_gate_missing_evidence_ids_is_graceful(temp_project_folder):
    _write_claims(
        temp_project_folder,
        [
            {
                "schema_version": "1.0",
                "claim_id": "c1",
                "kind": "source_backed",
                "statement": "Some statement.",
                "citation_keys": ["smith2020"],
                "evidence_ids": ["missing"],
                "created_at": "2025-01-01T00:00:00Z",
            }
        ],
    )

    cfg = CitationAccuracyGateConfig(enabled=True, on_failure="block")
    result = enforce_citation_accuracy_gate(project_folder=str(temp_project_folder), config=cfg)
    assert result["action"] == "pass"
    assert result["checked_claims_total"] == 0
    assert result["skipped_missing_evidence_total"] == 1


@pytest.mark.unit
def test_citation_accuracy_gate_config_from_context_parses_and_sanitizes_values():
    cfg = CitationAccuracyGateConfig.from_context(
        {
            "citation_accuracy_gate": {
                "enabled": True,
                "on_failure": "downgrade",
                "min_alignment_score": "0.4",
                "min_keyword_overlap": "0.2",
                "enable_entity_overlap": True,
                "min_entity_overlap": 2,  # will clamp to 1.0
                "enable_numeric_consistency": True,
                "max_evidence_items_per_claim": "2",
            }
        }
    )

    assert cfg.enabled is True
    assert cfg.on_failure == "downgrade"
    assert 0.0 <= cfg.min_alignment_score <= 1.0
    assert 0.0 <= cfg.min_keyword_overlap <= 1.0
    assert cfg.enable_entity_overlap is True
    assert cfg.min_entity_overlap == 1.0
    assert cfg.enable_numeric_consistency is True
    assert cfg.max_evidence_items_per_claim == 2

    bad = CitationAccuracyGateConfig.from_context({"citation_accuracy_gate": {"enabled": True, "on_failure": "nope"}})
    assert bad.enabled is True
    assert bad.on_failure == "block"
