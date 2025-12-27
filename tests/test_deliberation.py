import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.base import AgentResult
from src.agents.deliberation import DeliberationPerspective, build_consensus, detect_conflict
from src.agents.orchestrator import AgentOrchestrator, OrchestratorConfig, ExecutionMode
from src.llm.claude_client import ModelTier, TaskType


@pytest.mark.unit
def test_detect_conflict_flags_different_outputs():
    assert detect_conflict(["a", "b"]) is True


@pytest.mark.unit
def test_build_consensus_marks_degraded_on_conflict():
    perspectives = [
        DeliberationPerspective(agent_id="A01", success=True, content="alpha", error=None, result=None),
        DeliberationPerspective(agent_id="A02", success=True, content="beta", error=None, result=None),
    ]

    out = build_consensus(task_text="t", agent_ids=["A01", "A02"], perspectives=perspectives)
    assert out["conflict_detected"] is True
    assert out["degraded"] is True
    assert "rationale" in out
    assert "consolidated_output" in out
    assert "Perspective (A01)" in out["consolidated_output"]


@pytest.mark.unit
def test_build_consensus_not_degraded_when_equivalent_outputs():
    perspectives = [
        DeliberationPerspective(agent_id="A01", success=True, content="same\n", error=None, result=None),
        DeliberationPerspective(agent_id="A02", success=True, content="same", error=None, result=None),
    ]

    out = build_consensus(task_text="t", agent_ids=["A01", "A02"], perspectives=perspectives)
    assert out["conflict_detected"] is False
    assert out["degraded"] is False
    assert out["consolidated_output"].strip() == "same"


@pytest.mark.unit
@pytest.mark.asyncio
@patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True)
async def test_orchestrator_deliberation_writes_artifact(tmp_path):
    (tmp_path / "project.json").write_text(
        "{\"id\": \"p1\", \"title\": \"t\", \"research_question\": \"q\"}\n",
        encoding="utf-8",
    )

    mock_client = MagicMock()

    with patch("src.agents.orchestrator.ClaudeClient", return_value=mock_client):
        with patch("src.agents.orchestrator.CriticalReviewAgent"):
            config = OrchestratorConfig(
                default_mode=ExecutionMode.SINGLE_PASS,
                agent_timeout=10,
                review_timeout=5,
            )
            orch = AgentOrchestrator(str(tmp_path), config=config)
            orch.client = mock_client

            async def _fake_execute_agent(agent_id: str, context: dict, use_cache: bool = True):
                content = "alpha" if agent_id == "A01" else "beta"
                return AgentResult(
                    agent_name=agent_id,
                    task_type=TaskType.CODING,
                    model_tier=ModelTier.SONNET,
                    success=True,
                    content=content,
                    structured_data={},
                    timestamp="2025-12-27T00:00:00+00:00",
                )

            orch.execute_agent = AsyncMock(side_effect=_fake_execute_agent)

            result = await orch.execute_deliberation_and_consensus(
                task_text="Do the thing",
                context={"project_folder": str(tmp_path)},
                agent_ids=["A01", "A02"],
                artifact_filename="deliberation_test.json",
            )

    assert result["degraded"] is True
    assert result["artifact_path"] == "outputs/deliberation_test.json"
    assert (tmp_path / "outputs" / "deliberation_test.json").exists()
