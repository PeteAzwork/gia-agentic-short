import json
from unittest.mock import patch

import pytest

from src.evidence.pipeline import EvidencePipelineConfig, run_local_evidence_pipeline
from src.evidence.store import EvidenceStore


@pytest.mark.unit
@patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True)
def test_local_evidence_pipeline_writes_parsed_and_evidence(temp_project_folder):
    literature_dir = temp_project_folder / "literature"
    literature_dir.mkdir(exist_ok=True)
    (literature_dir / "notes.md").write_text(
        "This is a sufficiently long paragraph to extract evidence from. It includes 42%.",
        encoding="utf-8",
    )

    cfg = EvidencePipelineConfig(enabled=True, max_sources=10, ingest_sources=True, append_to_ledger=True)
    summary = run_local_evidence_pipeline(project_folder=str(temp_project_folder), config=cfg)

    assert summary["processed_count"] >= 1
    assert len(summary["source_ids"]) >= 1

    store = EvidenceStore(str(temp_project_folder))
    source_id = summary["source_ids"][0]

    parsed = store.read_parsed(source_id)
    assert isinstance(parsed, dict)
    assert "blocks" in parsed

    evidence = store.read_evidence_items(source_id)
    assert isinstance(evidence, list)
    assert len(evidence) >= 1

    # If append_to_ledger is enabled, the ledger should contain entries.
    assert store.count() >= 1

    # evidence.json should be valid JSON array on disk
    sp = store.source_paths(source_id)
    on_disk = json.loads(sp.evidence_path.read_text(encoding="utf-8"))
    assert isinstance(on_disk, list)
