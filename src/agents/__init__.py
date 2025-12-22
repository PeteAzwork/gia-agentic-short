"""Agents package.

This package intentionally avoids importing all agent modules at import time.
Eager imports can create circular dependencies (for example when utility
modules import `src.agents.best_practices`).

Import agents directly from their modules, for example:
- src.agents.base.BaseAgent
- src.agents.literature_workflow.LiteratureWorkflow
- src.agents.best_practices.BANNED_WORDS

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

__all__: list[str] = []
