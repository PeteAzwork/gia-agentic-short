"""Evidence extractor agent.

Reads per-source parsed artifacts and produces schema-valid EvidenceItem objects.

This agent is intended as a Sprint 1 bridge:
- It is deterministic and offline by default
- It writes extracted items to sources/<source_id>/evidence.json

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

from src.agents.base import BaseAgent, AgentResult
from src.llm.claude_client import TaskType
from src.evidence.extraction import extract_evidence_items
from src.evidence.store import EvidenceStore


class EvidenceExtractorAgent(BaseAgent):
    """Extract EvidenceItems from a parsed source artifact."""

    def __init__(
        self,
        client=None,
        time_budget_seconds: Optional[int] = None,
    ):
        system_prompt = (
            "You extract evidence items from parsed sources. "
            "Prefer deterministic extraction. "
            "If you need current information, you must flag that web search is required."
        )

        super().__init__(
            name="EvidenceExtractor",
            task_type=TaskType.DATA_EXTRACTION,
            system_prompt=system_prompt,
            client=client,
            time_budget_seconds=time_budget_seconds,
        )

    async def execute(self, context: dict) -> AgentResult:
        """Execute evidence extraction.

        Required context:
        - project_folder: path to the project folder
        - source_id: the source identifier

        Optional context:
        - max_items: int
        - locator: dict compatible with EvidenceItem.locator
        - append_to_ledger: bool (default False)
        """

        self.start_execution_timer()

        project_folder = context.get("project_folder")
        source_id = context.get("source_id")

        if not isinstance(project_folder, str) or not project_folder:
            return AgentResult(
                agent_name=self.name,
                task_type=self.task_type,
                model_tier=self.model_tier,
                success=False,
                content="",
                error="Missing required context: project_folder",
                tokens_used=0,
                execution_time=self.get_elapsed_time(),
            )
        if not isinstance(source_id, str) or not source_id:
            return AgentResult(
                agent_name=self.name,
                task_type=self.task_type,
                model_tier=self.model_tier,
                success=False,
                content="",
                error="Missing required context: source_id",
                tokens_used=0,
                execution_time=self.get_elapsed_time(),
            )

        max_items = context.get("max_items", 25)
        locator = context.get("locator")
        append_to_ledger = bool(context.get("append_to_ledger", False))

        try:
            store = EvidenceStore(project_folder)
            parsed = store.read_parsed(source_id)

            items = extract_evidence_items(
                parsed=parsed,
                source_id=source_id,
                locator=locator if isinstance(locator, dict) else None,
                max_items=int(max_items),
            )

            store.write_evidence_items(source_id, items)

            if append_to_ledger and items:
                store.append_many(items)

            sp = store.source_paths(source_id)
            structured: Dict[str, Any] = {
                "source_id": source_id,
                "evidence_count": len(items),
                "evidence_path": str(sp.evidence_path),
            }

            elapsed = self.get_elapsed_time()
            self._check_time_budget(elapsed)
            return AgentResult(
                agent_name=self.name,
                task_type=self.task_type,
                model_tier=self.model_tier,
                success=True,
                content=f"Extracted {len(items)} evidence items",
                structured_data=structured,
                tokens_used=0,
                execution_time=elapsed,
            )

        except FileNotFoundError as e:
            logger.error(f"Parsed artifact missing for {source_id}: {e}")
            return AgentResult(
                agent_name=self.name,
                task_type=self.task_type,
                model_tier=self.model_tier,
                success=False,
                content="",
                error=f"Parsed artifact missing for source_id={source_id}: {e}",
                tokens_used=0,
                execution_time=self.get_elapsed_time(),
            )
        except Exception as e:
            logger.error(f"Evidence extraction failed: {e}")
            return AgentResult(
                agent_name=self.name,
                task_type=self.task_type,
                model_tier=self.model_tier,
                success=False,
                content="",
                error=str(e),
                tokens_used=0,
                execution_time=self.get_elapsed_time(),
            )
