import json
from unittest.mock import patch

import pytest

from src.agents.evidence_extractor import EvidenceExtractorAgent
from src.evidence.store import EvidenceStore


@pytest.mark.unit
@pytest.mark.asyncio
@patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True)
async def test_evidence_extractor_agent_writes_evidence_file(temp_project_folder):
    source_id = "local:paper-1"

    store = EvidenceStore(str(temp_project_folder))
    store.write_parsed(
        source_id,
        {
            "blocks": [
                {
                    "kind": "paragraph",
                    "span": {"start_line": 1, "end_line": 1},
                    "text": '"A quoted fact" appears here.',
                }
            ]
        },
    )

    agent = EvidenceExtractorAgent()
    result = await agent.execute(
        {
            "project_folder": str(temp_project_folder),
            "source_id": source_id,
            "max_items": 5,
        }
    )

    assert result.success is True
    sp = store.source_paths(source_id)
    assert sp.evidence_path.exists()

    payload = json.loads(sp.evidence_path.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["source_id"] == source_id
