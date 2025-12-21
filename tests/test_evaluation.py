"""
Evaluation Framework Tests
==========================
Tests for test query loading and evaluation utilities.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

import pytest
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEvaluationQueries:
    """Tests for evaluation test query data."""
    
    @pytest.fixture
    def test_queries_path(self):
        """Path to test queries file."""
        return Path(__file__).parent.parent / "evaluation" / "test_queries.json"
    
    @pytest.mark.unit
    def test_test_queries_file_exists(self, test_queries_path):
        """Test queries file should exist."""
        assert test_queries_path.exists(), f"Missing {test_queries_path}"
    
    @pytest.mark.unit
    def test_test_queries_valid_json(self, test_queries_path):
        """Test queries should be valid JSON."""
        with open(test_queries_path) as f:
            queries = json.load(f)
        
        assert isinstance(queries, list)
        assert len(queries) > 0
    
    @pytest.mark.unit
    def test_test_queries_have_required_fields(self, test_queries_path):
        """Each query should have required fields."""
        with open(test_queries_path) as f:
            queries = json.load(f)
        
        required_fields = ["id", "title", "research_question", "target_journal"]
        
        for query in queries:
            for field in required_fields:
                assert field in query, f"Query {query.get('id', 'unknown')} missing {field}"
    
    @pytest.mark.unit
    def test_test_queries_have_unique_ids(self, test_queries_path):
        """All query IDs should be unique."""
        with open(test_queries_path) as f:
            queries = json.load(f)
        
        ids = [q["id"] for q in queries]
        assert len(ids) == len(set(ids)), "Duplicate query IDs found"
    
    @pytest.mark.unit
    def test_test_queries_valid_journals(self, test_queries_path):
        """Target journals should be valid options."""
        with open(test_queries_path) as f:
            queries = json.load(f)
        
        valid_journals = ["RFS", "JFE", "JF", "JFQA"]
        
        for query in queries:
            journal = query.get("target_journal")
            assert journal in valid_journals, f"Invalid journal: {journal}"
    
    @pytest.mark.unit
    def test_test_queries_research_types(self, test_queries_path):
        """Research types should be valid."""
        with open(test_queries_path) as f:
            queries = json.load(f)
        
        valid_types = ["Empirical", "Theoretical", "Review/Survey", "Methodology"]
        
        for query in queries:
            if "research_type" in query and query["research_type"]:
                assert query["research_type"] in valid_types, \
                    f"Invalid research_type: {query['research_type']}"
    
    @pytest.mark.unit
    def test_test_queries_hypothesis_consistency(self, test_queries_path):
        """Queries with has_hypothesis=True should have hypothesis text."""
        with open(test_queries_path) as f:
            queries = json.load(f)
        
        for query in queries:
            if query.get("has_hypothesis"):
                assert query.get("hypothesis"), \
                    f"Query {query['id']} has has_hypothesis=True but no hypothesis"


class TestEvaluationMetrics:
    """Tests for evaluation metric definitions."""
    
    @pytest.mark.unit
    def test_relevance_metric_concept(self):
        """Relevance metric should evaluate response alignment with question."""
        # This is a conceptual test documenting the metric
        metric_definition = {
            "name": "Relevance",
            "description": "Measures how well agent responses address the research question",
            "scale": "1-5",
            "criteria": [
                "Response directly addresses the research question",
                "Suggestions are applicable to the specific topic",
                "No off-topic content",
            ]
        }
        
        assert metric_definition["name"] == "Relevance"
        assert len(metric_definition["criteria"]) >= 2
    
    @pytest.mark.unit
    def test_coherence_metric_concept(self):
        """Coherence metric should evaluate logical flow."""
        metric_definition = {
            "name": "Coherence",
            "description": "Evaluates logical flow and consistency of research overview",
            "scale": "1-5",
            "criteria": [
                "Clear logical structure",
                "Consistent recommendations",
                "Well-organized sections",
            ]
        }
        
        assert metric_definition["name"] == "Coherence"
    
    @pytest.mark.unit
    def test_groundedness_metric_concept(self):
        """Groundedness metric should check for hallucinations."""
        metric_definition = {
            "name": "Groundedness",
            "description": "Checks if outputs are grounded in provided project data",
            "scale": "1-5",
            "criteria": [
                "No fabricated statistics",
                "References actual provided data",
                "Acknowledges limitations",
            ]
        }
        
        assert metric_definition["name"] == "Groundedness"


class TestQueryDataVariety:
    """Tests ensuring test queries cover different scenarios."""
    
    @pytest.fixture
    def queries(self):
        """Load test queries."""
        path = Path(__file__).parent.parent / "evaluation" / "test_queries.json"
        with open(path) as f:
            return json.load(f)
    
    @pytest.mark.unit
    def test_queries_cover_all_journals(self, queries):
        """Queries should cover all target journals."""
        journals = set(q["target_journal"] for q in queries)
        expected = {"RFS", "JFE", "JF", "JFQA"}
        
        assert journals == expected, f"Missing journals: {expected - journals}"
    
    @pytest.mark.unit
    def test_queries_include_with_and_without_hypothesis(self, queries):
        """Should have queries both with and without hypothesis."""
        with_hypothesis = sum(1 for q in queries if q.get("has_hypothesis"))
        without_hypothesis = sum(1 for q in queries if not q.get("has_hypothesis"))
        
        assert with_hypothesis > 0, "No queries with hypothesis"
        assert without_hypothesis > 0, "No queries without hypothesis"
    
    @pytest.mark.unit
    def test_queries_include_with_and_without_data(self, queries):
        """Should have queries both with and without existing data."""
        with_data = sum(1 for q in queries if q.get("has_data"))
        without_data = sum(1 for q in queries if not q.get("has_data"))
        
        assert with_data > 0, "No queries with data"
        assert without_data > 0, "No queries without data"
    
    @pytest.mark.unit
    def test_queries_vary_in_completeness(self, queries):
        """Queries should vary in how many fields are filled."""
        # Count filled optional fields
        optional_fields = ["methodology", "related_literature", "expected_contribution", "deadline"]
        
        completeness_scores = []
        for q in queries:
            score = sum(1 for f in optional_fields if q.get(f))
            completeness_scores.append(score)
        
        # Should have variety (not all same score)
        assert len(set(completeness_scores)) > 1, "All queries have same completeness"
