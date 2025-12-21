"""
Pytest Configuration and Shared Fixtures
=========================================
Common fixtures and configuration for all tests.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

import os
import sys
import json
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import dataclass

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Fixtures: Mock Claude Client
# =============================================================================

@dataclass
class MockMessage:
    """Mock Claude API message response."""
    content: list
    model: str = "claude-sonnet-4-5-20250929"
    usage: dict = None
    
    def __post_init__(self):
        if self.usage is None:
            self.usage = {"input_tokens": 100, "output_tokens": 50}


@dataclass 
class MockTextBlock:
    """Mock text block in message content."""
    text: str
    type: str = "text"


@pytest.fixture
def mock_claude_response():
    """Create a mock Claude API response."""
    def _create_response(text: str, model: str = "claude-sonnet-4-5-20250929"):
        return MockMessage(
            content=[MockTextBlock(text=text)],
            model=model,
            usage={"input_tokens": 100, "output_tokens": len(text.split())}
        )
    return _create_response


@pytest.fixture
def mock_anthropic_client(mock_claude_response):
    """Mock Anthropic client for testing without API calls."""
    mock_client = Mock()
    mock_client.messages = Mock()
    mock_client.messages.create = Mock(
        return_value=mock_claude_response("Test response from Claude.")
    )
    return mock_client


# =============================================================================
# Fixtures: Sample Project Data
# =============================================================================

@pytest.fixture
def sample_project_data():
    """Sample research project submission data."""
    return {
        "id": "test_project_001",
        "title": "Test Research Project",
        "research_question": "Does X affect Y in financial markets?",
        "has_hypothesis": True,
        "hypothesis": "X positively affects Y due to Z mechanism.",
        "target_journal": "JFE",
        "paper_type": "Full Paper (30-45 pages)",
        "research_type": "Empirical",
        "has_data": False,
        "data_description": "",
        "data_sources": "CRSP, Compustat",
        "key_variables": "Return, Market Cap, Volume",
        "methodology": "Panel regression with fixed effects",
        "related_literature": "Author1 (2020), Author2 (2019)",
        "expected_contribution": "First paper to examine X-Y relationship",
        "constraints": "",
        "deadline": "2026-06-01"
    }


@pytest.fixture
def sample_evaluation_query():
    """Sample evaluation test query."""
    return {
        "id": "eval_001",
        "title": "CEO Overconfidence and Corporate Innovation Investment",
        "research_question": "Does CEO overconfidence lead to greater corporate R&D investment?",
        "has_hypothesis": True,
        "hypothesis": "Overconfident CEOs invest more in R&D.",
        "target_journal": "JFE",
        "paper_type": "Full Paper (30-45 pages)",
        "research_type": "Empirical",
        "has_data": False,
        "data_description": "",
        "data_sources": "Compustat, CRSP, USPTO patent database",
        "key_variables": "R&D intensity, patent count",
        "methodology": "Panel regression with firm fixed effects",
        "related_literature": "Malmendier and Tate (2005)",
        "expected_contribution": "First paper on overconfidence and innovation quality",
        "constraints": "",
        "deadline": "2026-03-15"
    }


@pytest.fixture
def temp_project_folder(tmp_path, sample_project_data):
    """Create a temporary project folder structure."""
    project_folder = tmp_path / "test_project"
    project_folder.mkdir()
    
    # Create project.json
    project_json = project_folder / "project.json"
    project_json.write_text(json.dumps(sample_project_data, indent=2))
    
    # Create data folder
    data_folder = project_folder / "data"
    data_folder.mkdir()
    
    return project_folder


@pytest.fixture
def temp_project_with_data(temp_project_folder):
    """Temporary project folder with sample CSV data."""
    data_folder = temp_project_folder / "data"
    
    # Create sample CSV
    csv_content = """date,ticker,return,volume,market_cap
2024-01-01,AAPL,0.015,1000000,3000000000000
2024-01-02,AAPL,-0.008,1200000,2990000000000
2024-01-03,AAPL,0.022,900000,3050000000000
2024-01-01,MSFT,0.010,800000,2800000000000
2024-01-02,MSFT,0.005,750000,2810000000000
"""
    (data_folder / "stock_returns.csv").write_text(csv_content)
    
    return temp_project_folder


# =============================================================================
# Fixtures: Event Loop
# =============================================================================

@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Markers Registration
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests without external deps")
    config.addinivalue_line("markers", "integration: Tests requiring API keys")
    config.addinivalue_line("markers", "slow: Slow running tests")
