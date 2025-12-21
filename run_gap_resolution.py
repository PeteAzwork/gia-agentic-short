#!/usr/bin/env python3
"""
Run the gap resolution workflow for a project folder.

This script runs after the initial workflow to:
1. Analyze the RESEARCH_OVERVIEW.md
2. Execute Python code to resolve data-related gaps
3. Generate an UPDATED_RESEARCH_OVERVIEW.md

Usage:
    python run_gap_resolution.py <project_folder>
    python run_gap_resolution.py user-input/3f479ad2_* -v
"""
import asyncio
import sys
from src.agents.gap_resolution_workflow import GapResolutionWorkflow

async def main():
    if len(sys.argv) < 2:
        print("Usage: python run_gap_resolution.py <project_folder>")
        print("Example: python run_gap_resolution.py user-input/3f479ad2_disentangling-voting-premium...")
        sys.exit(1)
    
    project_folder = sys.argv[1]
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    
    print(f'Starting gap resolution workflow for: {project_folder}', flush=True)
    
    workflow = GapResolutionWorkflow()
    result = await workflow.run(project_folder)
    
    print(f'\n{"="*60}')
    print(f'GAP RESOLUTION COMPLETE')
    print(f'{"="*60}')
    print(f'Success: {result.success}')
    print(f'Total tokens: {result.total_tokens}')
    print(f'Total time: {result.total_time:.2f}s')
    print(f'Gaps resolved: {result.gaps_resolved}/{result.gaps_total}')
    
    if result.code_executions:
        print(f'\nCode Executions:')
        for exec_info in result.code_executions:
            status = "RESOLVED" if exec_info.get("resolved") else "EXECUTED" if exec_info.get("success") else "FAILED"
            print(f'  - {exec_info.get("gap_id")}: {status}')
    
    if result.updated_overview_path:
        print(f'\nUpdated overview: {result.updated_overview_path}')
    
    if result.errors:
        print(f'\nErrors:')
        for error in result.errors:
            print(f'  - {error}')
    print(f'{"="*60}')

if __name__ == '__main__':
    asyncio.run(main())
