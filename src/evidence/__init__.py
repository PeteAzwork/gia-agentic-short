"""Evidence package.

This package intentionally avoids importing submodules at import time.
Doing so prevents circular imports when other parts of the system import
evidence helpers during initialization.

Import what you need directly, for example:
- src.evidence.store.EvidenceStore
- src.evidence.extraction.extract_evidence_items
- src.evidence.gates.enforce_evidence_gate

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

__all__: list[str] = []
