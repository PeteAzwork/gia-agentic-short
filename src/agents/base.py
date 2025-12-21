"""
Base Agent Classes
==================
Foundation for all research agents using Claude API.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.llm.claude_client import ClaudeClient, TaskType, ModelTier
from loguru import logger


@dataclass
class AgentResult:
    """Result from an agent execution."""
    agent_name: str
    task_type: TaskType
    model_tier: ModelTier
    success: bool
    content: str
    structured_data: dict = field(default_factory=dict)
    error: Optional[str] = None
    tokens_used: int = 0
    execution_time: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """Convert result to dictionary for JSON serialization."""
        return {
            "agent_name": self.agent_name,
            "task_type": self.task_type.value,
            "model_tier": self.model_tier.value,
            "success": self.success,
            "content": self.content,
            "structured_data": self.structured_data,
            "error": self.error,
            "tokens_used": self.tokens_used,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp,
        }


class BaseAgent(ABC):
    """Base class for all research agents."""
    
    def __init__(
        self,
        name: str,
        task_type: TaskType,
        system_prompt: str,
        client: Optional[ClaudeClient] = None,
    ):
        """
        Initialize agent with Claude client and configuration.
        
        Args:
            name: Agent identifier
            task_type: Type of task for model selection
            system_prompt: System instructions for the agent
            client: Optional ClaudeClient instance (creates new if not provided)
        """
        self.name = name
        self.task_type = task_type
        self.system_prompt = system_prompt
        self.client = client or ClaudeClient()
        self.model_tier = self.client.get_model_for_task(task_type)
        
        logger.info(f"Initialized {name} agent with {self.model_tier.value} model")
    
    @abstractmethod
    async def execute(self, context: dict) -> AgentResult:
        """
        Execute the agent's task.
        
        Args:
            context: Dictionary containing project data and any prior agent results
            
        Returns:
            AgentResult with the agent's findings
        """
        pass
    
    async def _call_claude(
        self,
        user_message: str,
        use_thinking: bool = False,
        max_tokens: int = 32000,
        budget_tokens: int = 16000,
    ) -> tuple[str, int]:
        """
        Call Claude API with the agent's configuration.
        
        Args:
            user_message: The user message to send
            use_thinking: Whether to use extended thinking mode
            max_tokens: Maximum output tokens (used with thinking mode)
            budget_tokens: Token budget for extended thinking
            
        Returns:
            Tuple of (response content, tokens used)
        """
        import time
        start_time = time.time()
        
        # Format message as list for Claude API
        messages = [{"role": "user", "content": user_message}]
        
        try:
            if use_thinking:
                thinking, response = self.client.chat_with_thinking(
                    messages=messages,
                    system=self.system_prompt,
                    model=self.model_tier,
                    max_tokens=max_tokens,
                    budget_tokens=budget_tokens,
                )
                content = response
                # Token count from usage tracking
                tokens = self.client.usage.output_tokens
            else:
                response = self.client.chat(
                    messages=messages,
                    system=self.system_prompt,
                    task=self.task_type,
                )
                content = response  # chat() returns string directly
                tokens = self.client.usage.output_tokens
            
            elapsed = time.time() - start_time
            logger.debug(f"{self.name} completed in {elapsed:.2f}s, {tokens} tokens")
            
            return content, tokens
            
        except Exception as e:
            logger.error(f"{self.name} error: {e}")
            raise
    
    def _build_result(
        self,
        success: bool,
        content: str,
        structured_data: Optional[dict] = None,
        error: Optional[str] = None,
        tokens_used: int = 0,
        execution_time: float = 0.0,
    ) -> AgentResult:
        """Build an AgentResult with common fields populated."""
        return AgentResult(
            agent_name=self.name,
            task_type=self.task_type,
            model_tier=self.model_tier,
            success=success,
            content=content,
            structured_data=structured_data or {},
            error=error,
            tokens_used=tokens_used,
            execution_time=execution_time,
        )
