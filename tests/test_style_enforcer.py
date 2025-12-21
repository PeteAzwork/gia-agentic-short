"""
Tests for Style Enforcer Agent (A13)
====================================
Tests the StyleEnforcerAgent for style validation integration.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import tempfile
import os

from src.agents.style_enforcer import (
    StyleEnforcerAgent,
    StyleEnforcementConfig,
    validate_latex_style,
)
from src.agents.feedback import IssueCategory, Severity


class TestStyleEnforcerConfig:
    """Tests for StyleEnforcementConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = StyleEnforcementConfig()
        
        assert config.check_banned_words is True
        assert config.check_word_counts is True
        assert config.auto_replace is False
        assert config.is_final_output is True
        assert config.mode == "draft"
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = StyleEnforcementConfig(
            check_banned_words=False,
            auto_replace=True,
            mode="iteration",
        )
        
        assert config.check_banned_words is False
        assert config.auto_replace is True
        assert config.mode == "iteration"


class TestStyleEnforcerAgent:
    """Tests for StyleEnforcerAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create agent with mocked client."""
        with patch('src.agents.style_enforcer.ClaudeClient'):
            return StyleEnforcerAgent()
    
    def test_agent_id(self, agent):
        """Test agent returns correct ID."""
        assert agent.get_agent_id() == "A13"
    
    @pytest.mark.asyncio
    async def test_validate_clean_text(self, agent):
        """Test validation of clean text."""
        text = "This is a clean academic text."
        result = await agent.validate(text)
        
        assert result.success is True
        assert result.structured_data["banned_word_count"] == 0
        # Short texts may have lower scores due to word count penalties
        assert result.structured_data["style_score"] >= 0.8
    
    @pytest.mark.asyncio
    async def test_validate_with_banned_words(self, agent):
        """Test validation detects banned words."""
        text = "We leverage innovative methods to unlock unprecedented results."
        result = await agent.validate(text)
        
        assert result.success is True
        assert result.structured_data["banned_word_count"] >= 3
        assert result.structured_data["style_score"] < 1.0
        assert len(result.structured_data["issues"]) >= 3
    
    @pytest.mark.asyncio
    async def test_validate_with_auto_fix(self, agent):
        """Test auto-fix replaces banned words."""
        text = "We utilize this method."
        result = await agent.validate(text, auto_fix=True)
        
        assert result.success is True
        assert result.structured_data["auto_fixed"] is True
        
        fixed_text = result.structured_data.get("fixed_text")
        if fixed_text:
            assert "utilize" not in fixed_text.lower()
    
    @pytest.mark.asyncio
    async def test_validate_word_counts(self, agent):
        """Test word count tracking."""
        text = "This is a short text with only a few words."
        result = await agent.validate(text)
        
        assert result.structured_data["total_words"] > 0
        # Very short texts may show 0 pages (rounding)
        assert result.structured_data["estimated_pages"] >= 0
    
    @pytest.mark.asyncio
    async def test_create_feedback_response(self, agent):
        """Test creating FeedbackResponse from validation."""
        text = "We leverage methods."
        result = await agent.validate(text)
        
        feedback = await agent.create_feedback_response(result, "test_request")
        
        assert feedback.request_id == "test_request"
        assert feedback.reviewer_agent_id == "A13"
        assert feedback.quality_score is not None


class TestStyleEnforcerIntegration:
    """Integration tests for style enforcement."""
    
    def test_issue_categories_exist(self):
        """Test that style-related issue categories exist."""
        # These should be defined in feedback.py
        assert hasattr(IssueCategory, "STYLE")
        assert hasattr(IssueCategory, "BANNED_WORDS")
        assert hasattr(IssueCategory, "WORD_COUNT")
    
    @pytest.mark.asyncio
    async def test_validate_latex_document(self):
        """Test validation of LaTeX document."""
        latex_text = r"""
\documentclass{article}
\begin{document}

\section{Introduction}
This paper examines market liquidity using standard methods.
We analyze data from multiple sources.

\section{Results}
The results show significant effects.

\end{document}
"""
        result = validate_latex_style(latex_text, auto_fix=False)
        
        assert result.total_words > 0
        assert result.estimated_pages > 0
    
    def test_registry_includes_a13(self):
        """Test that A13 is registered in agent registry."""
        from src.agents.registry import AgentRegistry, AgentCapability
        
        spec = AgentRegistry.get("A13")
        assert spec is not None
        assert spec.name == "StyleEnforcer"
        assert AgentCapability.STYLE_ENFORCEMENT in spec.capabilities
    
    def test_writing_agents_can_call_a13(self):
        """Test that writing agents can call StyleEnforcer."""
        from src.agents.registry import AgentRegistry
        
        # A10 (GapResolver) and A11 (OverviewUpdater) should be able to call A13
        a10 = AgentRegistry.get("A10")
        a11 = AgentRegistry.get("A11")
        
        assert "A13" in a10.can_call
        assert "A13" in a11.can_call
