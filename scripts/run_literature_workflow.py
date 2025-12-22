#!/usr/bin/env python3
"""Run the Phase 2 literature workflow for a project folder."""

import asyncio
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.llm.claude_client import load_env_file_lenient  # noqa: E402
load_env_file_lenient()

from src.agents.literature_workflow import LiteratureWorkflow  # noqa: E402


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_literature_workflow.py <project_folder>")
        sys.exit(1)

    project_folder = sys.argv[1]
    print(f"Starting literature workflow for: {project_folder}", flush=True)

    workflow = LiteratureWorkflow()
    result = await workflow.run(project_folder)

    print(f"\n{'=' * 60}")
    print("LITERATURE WORKFLOW COMPLETE")
    print(f"{'=' * 60}")
    print(f"Success: {result.success}")
    print(f"Total tokens: {result.total_tokens}")
    print(f"Total time: {result.total_time:.2f}s")
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  - {error}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
