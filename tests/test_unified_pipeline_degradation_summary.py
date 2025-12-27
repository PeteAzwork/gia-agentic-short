from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.utils.schema_validation import validate_degradation_summary


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unified_pipeline_writes_degradation_summary_on_early_failure(tmp_path):
    project_folder = tmp_path / "proj"
    project_folder.mkdir()

    failing = {"success": False, "errors": ["nope"]}

    with patch("src.pipeline.runner.ResearchWorkflow") as RW:
        RW.return_value.run = AsyncMock(return_value=failing)

        from src.pipeline.runner import run_full_pipeline

        ctx = await run_full_pipeline(str(project_folder), enable_gap_resolution=False, enable_writing_review=False)

    assert ctx.success is False

    summary_path = project_folder / "outputs" / "degradation_summary.json"
    assert summary_path.exists()

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    validate_degradation_summary(payload)
    assert payload["counts"]["total"] == 0
