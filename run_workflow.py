#!/usr/bin/env python3
"""Run the research workflow for a project folder."""
import asyncio
import sys
from src.agents.workflow import ResearchWorkflow

async def main():
    if len(sys.argv) < 2:
        print("Usage: python run_workflow.py <project_folder>")
        sys.exit(1)
    
    project_folder = sys.argv[1]
    print(f'Starting workflow for: {project_folder}', flush=True)
    
    workflow = ResearchWorkflow()
    result = await workflow.run(project_folder)
    
    print(f'\n{"="*60}')
    print(f'WORKFLOW COMPLETE')
    print(f'{"="*60}')
    print(f'Success: {result.success}')
    print(f'Total tokens: {result.total_tokens}')
    print(f'Total time: {result.total_time:.2f}s')
    print(f'Overview path: {result.overview_path}')
    if result.errors:
        print(f'\nErrors:')
        for error in result.errors:
            print(f'  - {error}')
    print(f'{"="*60}')

if __name__ == '__main__':
    asyncio.run(main())
