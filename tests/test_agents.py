"""
Agent Unit Tests
================
Tests for base agent and specialized agents without API calls.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.base import AgentResult, BaseAgent
from src.llm.claude_client import TaskType, ModelTier


class TestAgentResult:
    """Tests for AgentResult dataclass."""
    
    @pytest.mark.unit
    def test_agent_result_creation(self):
        """AgentResult should be created with required fields."""
        result = AgentResult(
            agent_name="TestAgent",
            task_type=TaskType.DATA_ANALYSIS,
            model_tier=ModelTier.SONNET,
            success=True,
            content="Test content",
        )
        
        assert result.agent_name == "TestAgent"
        assert result.success is True
        assert result.content == "Test content"
        assert result.error is None
    
    @pytest.mark.unit
    def test_agent_result_to_dict(self):
        """to_dict should serialize all fields."""
        result = AgentResult(
            agent_name="TestAgent",
            task_type=TaskType.DATA_ANALYSIS,
            model_tier=ModelTier.SONNET,
            success=True,
            content="Test content",
            tokens_used=150,
        )
        
        d = result.to_dict()
        
        assert d["agent_name"] == "TestAgent"
        assert d["task_type"] == "data_analysis"
        assert d["model_tier"] == "sonnet"
        assert d["success"] is True
        assert d["tokens_used"] == 150
    
    @pytest.mark.unit
    def test_agent_result_with_error(self):
        """AgentResult should handle error state."""
        result = AgentResult(
            agent_name="TestAgent",
            task_type=TaskType.DATA_ANALYSIS,
            model_tier=ModelTier.SONNET,
            success=False,
            content="",
            error="Something went wrong",
        )
        
        assert result.success is False
        assert result.error == "Something went wrong"
    
    @pytest.mark.unit
    def test_agent_result_structured_data(self):
        """AgentResult should accept structured data."""
        result = AgentResult(
            agent_name="DataAnalyst",
            task_type=TaskType.DATA_EXTRACTION,
            model_tier=ModelTier.HAIKU,
            success=True,
            content="Found 3 files",
            structured_data={"files": ["a.csv", "b.csv"], "total_rows": 1000},
        )
        
        assert result.structured_data["files"] == ["a.csv", "b.csv"]
        assert result.structured_data["total_rows"] == 1000


class TestDataAnalystAgent:
    """Tests for DataAnalystAgent."""
    
    @pytest.mark.unit
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('src.llm.claude_client.anthropic.Anthropic')
    @patch('src.llm.claude_client.anthropic.AsyncAnthropic')
    def test_data_analyst_uses_haiku(self, mock_async_anthropic, mock_anthropic):
        """DataAnalystAgent should use Haiku model."""
        from src.agents.data_analyst import DataAnalystAgent
        
        agent = DataAnalystAgent()
        assert agent.model_tier == ModelTier.HAIKU
        assert agent.task_type == TaskType.DATA_EXTRACTION
    
    @pytest.mark.unit
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('src.llm.claude_client.anthropic.Anthropic')
    @patch('src.llm.claude_client.anthropic.AsyncAnthropic')
    async def test_data_analyst_no_folder(self, mock_async_anthropic, mock_anthropic):
        """DataAnalystAgent should handle missing folder."""
        from src.agents.data_analyst import DataAnalystAgent
        
        agent = DataAnalystAgent()
        result = await agent.execute({})
        
        assert result.success is False
        assert "project_folder" in result.error.lower()
    
    @pytest.mark.unit
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('src.llm.claude_client.anthropic.Anthropic')
    @patch('src.llm.claude_client.anthropic.AsyncAnthropic')
    async def test_data_analyst_no_data_folder(self, mock_async_anthropic, mock_anthropic, tmp_path):
        """DataAnalystAgent should handle project without data folder."""
        from src.agents.data_analyst import DataAnalystAgent
        
        project_folder = tmp_path / "test_project"
        project_folder.mkdir()
        
        agent = DataAnalystAgent()
        result = await agent.execute({"project_folder": str(project_folder)})
        
        assert result.success is True
        assert result.structured_data.get("has_data") is False


class TestResearchExplorerAgent:
    """Tests for ResearchExplorerAgent."""
    
    @pytest.mark.unit
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('src.llm.claude_client.anthropic.Anthropic')
    @patch('src.llm.claude_client.anthropic.AsyncAnthropic')
    def test_research_explorer_uses_sonnet(self, mock_async_anthropic, mock_anthropic):
        """ResearchExplorerAgent should use Sonnet model."""
        from src.agents.research_explorer import ResearchExplorerAgent
        
        agent = ResearchExplorerAgent()
        assert agent.model_tier == ModelTier.SONNET
        assert agent.task_type == TaskType.DATA_ANALYSIS  # Uses Sonnet via DATA_ANALYSIS


class TestGapAnalysisAgent:
    """Tests for GapAnalysisAgent."""
    
    @pytest.mark.unit
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('src.llm.claude_client.anthropic.Anthropic')
    @patch('src.llm.claude_client.anthropic.AsyncAnthropic')
    def test_gap_analyst_uses_opus(self, mock_async_anthropic, mock_anthropic):
        """GapAnalysisAgent should use Opus model for complex reasoning."""
        from src.agents.gap_analyst import GapAnalysisAgent
        
        agent = GapAnalysisAgent()
        assert agent.model_tier == ModelTier.OPUS
        assert agent.task_type == TaskType.COMPLEX_REASONING


class TestOverviewGeneratorAgent:
    """Tests for OverviewGeneratorAgent."""
    
    @pytest.mark.unit
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('src.llm.claude_client.anthropic.Anthropic')
    @patch('src.llm.claude_client.anthropic.AsyncAnthropic')
    def test_overview_generator_uses_sonnet(self, mock_async_anthropic, mock_anthropic):
        """OverviewGeneratorAgent should use Sonnet model."""
        from src.agents.overview_generator import OverviewGeneratorAgent
        
        agent = OverviewGeneratorAgent()
        assert agent.model_tier == ModelTier.SONNET


class TestAgentModelSelection:
    """Tests verifying correct model selection across agents."""
    
    @pytest.mark.unit
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('src.llm.claude_client.anthropic.Anthropic')
    @patch('src.llm.claude_client.anthropic.AsyncAnthropic')
    def test_agent_model_tiers_follow_design(self, mock_async_anthropic, mock_anthropic):
        """All agents should use their designed model tiers."""
        from src.agents.data_analyst import DataAnalystAgent
        from src.agents.research_explorer import ResearchExplorerAgent
        from src.agents.gap_analyst import GapAnalysisAgent
        from src.agents.overview_generator import OverviewGeneratorAgent
        
        # Haiku for fast data extraction
        data_agent = DataAnalystAgent()
        assert data_agent.model_tier == ModelTier.HAIKU
        
        # Sonnet for agentic workflows
        research_agent = ResearchExplorerAgent()
        assert research_agent.model_tier == ModelTier.SONNET
        
        # Opus for complex reasoning (gap analysis)
        gap_agent = GapAnalysisAgent()
        assert gap_agent.model_tier == ModelTier.OPUS
        
        # Sonnet for document creation
        overview_agent = OverviewGeneratorAgent()
        assert overview_agent.model_tier == ModelTier.SONNET
