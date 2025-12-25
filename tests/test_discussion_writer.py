import pytest

from src.agents.discussion_writer import DiscussionWriterAgent


@pytest.mark.unit
@pytest.mark.asyncio
async def test_discussion_writer_downgrades_on_missing_evidence(temp_project_folder):
    agent = DiscussionWriterAgent(client=None)
    ctx = {
        "project_folder": str(temp_project_folder),
        "discussion_writer": {"on_missing_evidence": "downgrade"},
    }

    result = await agent.execute(ctx)
    assert result.success is True

    out_path = temp_project_folder / "outputs/sections/discussion.tex"
    assert out_path.exists()

    tex = out_path.read_text(encoding="utf-8")
    assert "\\section{Discussion}" in tex
    assert "Evidence is not yet available" in tex
    assert result.structured_data["metadata"]["action"] == "downgrade"
