#!/usr/bin/env python3
"""Run the Phase 1.5 gap resolution workflow for a project folder."""

import asyncio
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.llm.claude_client import load_env_file_lenient  # noqa: E402
load_env_file_lenient()

from src.agents.gap_resolution_workflow import GapResolutionWorkflow  # noqa: E402


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_gap_resolution.py <project_folder>")
        sys.exit(1)

    project_folder = sys.argv[1]
    print(f"Starting gap resolution workflow for: {project_folder}", flush=True)

    workflow = GapResolutionWorkflow()
    result = await workflow.run(project_folder)

    print(f"\n{'=' * 60}")
    print("GAP RESOLUTION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Success: {result.success}")
    print(f"Total tokens: {result.total_tokens}")
    print(f"Total time: {result.total_time:.2f}s")
    print(f"Gaps resolved: {result.gaps_resolved}/{result.gaps_total}")
    if result.updated_overview_path:
        print(f"\nUpdated overview: {result.updated_overview_path}")
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  - {error}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
