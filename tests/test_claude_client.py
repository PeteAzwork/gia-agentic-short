"""
Claude Client Unit Tests
========================
Tests for the multi-model Claude client without making actual API calls.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.claude_client import (
    ClaudeClient,
    ModelTier,
    TaskType,
    TASK_MODEL_MAP,
    ModelInfo,
    MODELS,
)


class TestModelTierMapping:
    """Tests for task-to-model mapping logic."""
    
    @pytest.mark.unit
    def test_opus_tasks_map_to_opus(self):
        """Opus-tier tasks should map to Opus model."""
        opus_tasks = [
            TaskType.COMPLEX_REASONING,
            TaskType.SCIENTIFIC_ANALYSIS,
            TaskType.ACADEMIC_WRITING,
            TaskType.MULTI_STEP_RESEARCH,
        ]
        for task in opus_tasks:
            assert TASK_MODEL_MAP[task] == ModelTier.OPUS, f"{task} should map to Opus"
    
    @pytest.mark.unit
    def test_sonnet_tasks_map_to_sonnet(self):
        """Sonnet-tier tasks should map to Sonnet model."""
        sonnet_tasks = [
            TaskType.CODING,
            TaskType.AGENTIC_WORKFLOW,
            TaskType.DATA_ANALYSIS,
            TaskType.GENERAL_CHAT,
            TaskType.DOCUMENT_CREATION,
        ]
        for task in sonnet_tasks:
            assert TASK_MODEL_MAP[task] == ModelTier.SONNET, f"{task} should map to Sonnet"
    
    @pytest.mark.unit
    def test_haiku_tasks_map_to_haiku(self):
        """Haiku-tier tasks should map to Haiku model."""
        haiku_tasks = [
            TaskType.CLASSIFICATION,
            TaskType.SUMMARIZATION,
            TaskType.DATA_EXTRACTION,
            TaskType.QUICK_RESPONSE,
            TaskType.HIGH_VOLUME,
        ]
        for task in haiku_tasks:
            assert TASK_MODEL_MAP[task] == ModelTier.HAIKU, f"{task} should map to Haiku"
    
    @pytest.mark.unit
    def test_all_task_types_have_mapping(self):
        """Every TaskType should have a model mapping."""
        for task in TaskType:
            assert task in TASK_MODEL_MAP, f"{task} missing from TASK_MODEL_MAP"


class TestModelInfo:
    """Tests for model information and configuration."""
    
    @pytest.mark.unit
    def test_all_tiers_have_models(self):
        """Each tier should have a model defined."""
        for tier in ModelTier:
            assert tier in MODELS, f"Missing model for {tier}"
    
    @pytest.mark.unit
    def test_model_info_has_required_fields(self):
        """Model info should have all required fields."""
        for tier, model in MODELS.items():
            assert isinstance(model, ModelInfo)
            assert model.id, f"{tier} model missing id"
            assert model.tier == tier, f"{tier} model tier mismatch"
            assert model.context_window > 0, f"{tier} model invalid context_window"
            assert model.max_output > 0, f"{tier} model invalid max_output"
    
    @pytest.mark.unit
    def test_opus_is_most_expensive(self):
        """Opus should have highest pricing."""
        opus = MODELS[ModelTier.OPUS]
        sonnet = MODELS[ModelTier.SONNET]
        haiku = MODELS[ModelTier.HAIKU]
        
        assert opus.input_price_per_mtok > sonnet.input_price_per_mtok
        assert opus.output_price_per_mtok > sonnet.output_price_per_mtok
        assert sonnet.input_price_per_mtok > haiku.input_price_per_mtok


class TestClaudeClientInit:
    """Tests for ClaudeClient initialization."""
    
    @pytest.mark.unit
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key-123'})
    @patch('src.llm.claude_client.anthropic.Anthropic')
    @patch('src.llm.claude_client.anthropic.AsyncAnthropic')
    def test_client_initializes_with_env_key(self, mock_async_anthropic, mock_anthropic):
        """Client should initialize with API key from environment."""
        client = ClaudeClient()
        mock_anthropic.assert_called_once()
    
    @pytest.mark.unit
    @patch('src.llm.claude_client.anthropic.Anthropic')
    @patch('src.llm.claude_client.anthropic.AsyncAnthropic')
    def test_client_accepts_explicit_key(self, mock_async_anthropic, mock_anthropic):
        """Client should accept explicit API key."""
        client = ClaudeClient(api_key="explicit-test-key")
        mock_anthropic.assert_called_once()
    
    @pytest.mark.unit
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('src.llm.claude_client.anthropic.Anthropic')
    @patch('src.llm.claude_client.anthropic.AsyncAnthropic')
    def test_get_model_for_task(self, mock_async_anthropic, mock_anthropic):
        """get_model_for_task should return correct tier."""
        client = ClaudeClient()
        
        assert client.get_model_for_task(TaskType.COMPLEX_REASONING) == ModelTier.OPUS
        assert client.get_model_for_task(TaskType.CODING) == ModelTier.SONNET
        assert client.get_model_for_task(TaskType.SUMMARIZATION) == ModelTier.HAIKU
    
    @pytest.mark.unit
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('src.llm.claude_client.anthropic.Anthropic')
    @patch('src.llm.claude_client.anthropic.AsyncAnthropic')
    def test_get_model_id(self, mock_async_anthropic, mock_anthropic):
        """get_model_id should return valid model IDs."""
        client = ClaudeClient()
        
        opus_id = client.get_model_id(ModelTier.OPUS)
        sonnet_id = client.get_model_id(ModelTier.SONNET)
        haiku_id = client.get_model_id(ModelTier.HAIKU)
        
        assert "opus" in opus_id.lower()
        assert "sonnet" in sonnet_id.lower()
        assert "haiku" in haiku_id.lower()


class TestTokenTracking:
    """Tests for token usage tracking."""
    
    @pytest.mark.unit
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('src.llm.claude_client.anthropic.Anthropic')
    @patch('src.llm.claude_client.anthropic.AsyncAnthropic')
    def test_initial_token_counts_are_zero(self, mock_async_anthropic, mock_anthropic):
        """New client should have zero token counts."""
        client = ClaudeClient()
        
        assert client.usage.input_tokens == 0
        assert client.usage.output_tokens == 0
    
    @pytest.mark.unit
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('src.llm.claude_client.anthropic.Anthropic')
    @patch('src.llm.claude_client.anthropic.AsyncAnthropic')
    def test_get_usage_summary(self, mock_async_anthropic, mock_anthropic):
        """get_usage_summary should return dict with costs."""
        client = ClaudeClient()
        summary = client.get_usage_summary()
        
        assert "input_tokens" in summary
        assert "output_tokens" in summary
        assert "estimated_cost_usd" in summary
