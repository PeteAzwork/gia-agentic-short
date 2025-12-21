"""
LLM Client Module
=================
Provides unified access to Claude and other LLM APIs.

Available Models (Claude 4.5):
- Opus: Maximum intelligence for complex reasoning
- Sonnet: Balanced performance for agents and coding  
- Haiku: Fastest for high-volume tasks
"""

from .claude_client import (
    ClaudeClient,
    get_claude_client,
    get_model_for_task,
    BatchRequest,
    BatchResult,
    ModelTier,
    TaskType,
    ModelInfo,
    TokenUsage,
    MODELS,
    TASK_MODEL_MAP,
)

__all__ = [
    # Main client
    "ClaudeClient",
    "get_claude_client",
    "get_model_for_task",
    # Request/Response types
    "BatchRequest",
    "BatchResult",
    "TokenUsage",
    # Model configuration
    "ModelTier",
    "TaskType",
    "ModelInfo",
    "MODELS",
    "TASK_MODEL_MAP",
]
