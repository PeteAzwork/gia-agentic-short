"""
Tests for Feedback Protocol
===========================
Tests the feedback data structures and protocols.
"""

import pytest
from datetime import datetime

from src.agents.feedback import (
    Severity,
    IssueCategory,
    Issue,
    QualityScore,
    FeedbackRequest,
    FeedbackResponse,
    RevisionTrigger,
    ConvergenceCriteria,
    AgentCallRequest,
    AgentCallResponse,
)


class TestSeverityAndCategory:
    """Tests for Severity and IssueCategory enums."""
    
    def test_severity_values(self):
        """Test severity enum values."""
        assert Severity.CRITICAL.value == "critical"
        assert Severity.MAJOR.value == "major"
        assert Severity.MINOR.value == "minor"
        assert Severity.SUGGESTION.value == "suggestion"
    
    def test_issue_category_values(self):
        """Test issue category enum values."""
        assert IssueCategory.ACCURACY.value == "accuracy"
        assert IssueCategory.COMPLETENESS.value == "completeness"
        assert IssueCategory.CITATION.value == "citation"
        assert IssueCategory.METHODOLOGY.value == "methodology"


class TestIssue:
    """Tests for Issue dataclass."""
    
    def test_issue_creation(self):
        """Test creating an issue."""
        issue = Issue(
            category=IssueCategory.ACCURACY,
            severity=Severity.CRITICAL,
            description="Missing citation for claim",
            location="Section 2.1",
            suggestion="Add citation to Zingales (1994)",
            affects_downstream=True,
        )
        
        assert issue.category == IssueCategory.ACCURACY
        assert issue.severity == Severity.CRITICAL
        assert issue.affects_downstream is True
    
    def test_issue_to_dict(self):
        """Test issue serialization."""
        issue = Issue(
            category=IssueCategory.COMPLETENESS,
            severity=Severity.MAJOR,
            description="Missing methodology section",
        )
        
        d = issue.to_dict()
        
        assert d["category"] == "completeness"
        assert d["severity"] == "major"
        assert d["description"] == "Missing methodology section"
        assert d["location"] is None
    
    def test_issue_from_dict(self):
        """Test issue deserialization."""
        data = {
            "category": "accuracy",
            "severity": "minor",
            "description": "Typo in hypothesis",
            "location": "Line 45",
            "suggestion": "Fix typo",
            "affects_downstream": False,
        }
        
        issue = Issue.from_dict(data)
        
        assert issue.category == IssueCategory.ACCURACY
        assert issue.severity == Severity.MINOR
        assert issue.location == "Line 45"


class TestQualityScore:
    """Tests for QualityScore dataclass."""
    
    def test_quality_score_creation(self):
        """Test creating a quality score."""
        score = QualityScore(
            overall=0.75,
            accuracy=0.8,
            completeness=0.7,
            clarity=0.9,
            consistency=0.6,
            methodology=0.7,
            contribution=0.75,
        )
        
        assert score.overall == 0.75
        assert score.accuracy == 0.8
    
    def test_quality_score_passes(self):
        """Test quality threshold checking."""
        passing_score = QualityScore(overall=0.8)
        failing_score = QualityScore(overall=0.5)
        
        assert passing_score.passes() is True
        assert failing_score.passes() is False
    
    def test_lowest_dimension(self):
        """Test finding lowest dimension."""
        score = QualityScore(
            overall=0.7,
            accuracy=0.8,
            completeness=0.5,  # Lowest
            clarity=0.9,
            consistency=0.7,
            methodology=0.6,
            contribution=0.75,
            style=0.8,  # Include style field
        )
        
        dim, value = score.lowest_dimension()
        assert dim == "completeness"
        assert value == 0.5
    
    def test_quality_score_serialization(self):
        """Test quality score to/from dict."""
        score = QualityScore(overall=0.75, accuracy=0.8)
        d = score.to_dict()
        restored = QualityScore.from_dict(d)
        
        assert restored.overall == 0.75
        assert restored.accuracy == 0.8


class TestFeedbackResponse:
    """Tests for FeedbackResponse dataclass."""
    
    def test_feedback_response_creation(self):
        """Test creating a feedback response."""
        response = FeedbackResponse(
            request_id="test123",
            reviewer_agent_id="A12",
            quality_score=QualityScore(overall=0.6),
            issues=[
                Issue(
                    category=IssueCategory.ACCURACY,
                    severity=Severity.CRITICAL,
                    description="Error in claim",
                ),
                Issue(
                    category=IssueCategory.CLARITY,
                    severity=Severity.MINOR,
                    description="Unclear phrasing",
                ),
            ],
            summary="Needs improvement",
            revision_required=True,
        )
        
        assert response.request_id == "test123"
        assert response.revision_required is True
    
    def test_critical_issues(self):
        """Test filtering critical issues."""
        response = FeedbackResponse(
            request_id="test",
            reviewer_agent_id="A12",
            quality_score=QualityScore(overall=0.5),
            issues=[
                Issue(IssueCategory.ACCURACY, Severity.CRITICAL, "Critical error"),
                Issue(IssueCategory.CLARITY, Severity.MINOR, "Minor issue"),
                Issue(IssueCategory.COMPLETENESS, Severity.CRITICAL, "Missing data"),
            ],
        )
        
        critical = response.critical_issues
        assert len(critical) == 2
        assert all(i.severity == Severity.CRITICAL for i in critical)
    
    def test_major_issues(self):
        """Test filtering major issues."""
        response = FeedbackResponse(
            request_id="test",
            reviewer_agent_id="A12",
            quality_score=QualityScore(overall=0.6),
            issues=[
                Issue(IssueCategory.ACCURACY, Severity.MAJOR, "Major error"),
                Issue(IssueCategory.CLARITY, Severity.MINOR, "Minor issue"),
            ],
        )
        
        major = response.major_issues
        assert len(major) == 1
        assert major[0].severity == Severity.MAJOR
    
    def test_has_blocking_issues(self):
        """Test checking for blocking issues."""
        blocking = FeedbackResponse(
            request_id="test",
            reviewer_agent_id="A12",
            quality_score=QualityScore(overall=0.3),
            issues=[
                Issue(IssueCategory.ACCURACY, Severity.CRITICAL, "Blocker"),
            ],
        )
        
        non_blocking = FeedbackResponse(
            request_id="test",
            reviewer_agent_id="A12",
            quality_score=QualityScore(overall=0.7),
            issues=[
                Issue(IssueCategory.CLARITY, Severity.MINOR, "Not a blocker"),
            ],
        )
        
        assert blocking.has_blocking_issues is True
        assert non_blocking.has_blocking_issues is False
    
    def test_feedback_response_serialization(self):
        """Test feedback response to/from dict."""
        response = FeedbackResponse(
            request_id="test123",
            reviewer_agent_id="A12",
            quality_score=QualityScore(overall=0.7),
            issues=[
                Issue(IssueCategory.ACCURACY, Severity.MINOR, "Test issue"),
            ],
            summary="Test summary",
            revision_required=False,
        )
        
        d = response.to_dict()
        restored = FeedbackResponse.from_dict(d)
        
        assert restored.request_id == "test123"
        assert restored.quality_score.overall == 0.7
        assert len(restored.issues) == 1


class TestRevisionTrigger:
    """Tests for RevisionTrigger dataclass."""
    
    def test_revision_trigger_creation(self):
        """Test creating a revision trigger."""
        feedback = FeedbackResponse(
            request_id="fb123",
            reviewer_agent_id="A12",
            quality_score=QualityScore(overall=0.5),
            issues=[
                Issue(IssueCategory.COMPLETENESS, Severity.CRITICAL, "Missing section"),
            ],
            summary="Incomplete",
            revision_required=True,
        )
        
        trigger = RevisionTrigger(
            trigger_id="tr123",
            target_agent_id="A05",
            original_content="Original hypothesis...",
            feedback=feedback,
            iteration=1,
            max_iterations=3,
            focus_areas=["Add missing section"],
        )
        
        assert trigger.can_iterate is True
    
    def test_can_iterate_at_max(self):
        """Test iteration limit."""
        feedback = FeedbackResponse(
            request_id="fb",
            reviewer_agent_id="A12",
            quality_score=QualityScore(overall=0.5),
        )
        
        trigger = RevisionTrigger(
            trigger_id="tr",
            target_agent_id="A05",
            original_content="...",
            feedback=feedback,
            iteration=3,
            max_iterations=3,
        )
        
        assert trigger.can_iterate is False
    
    def test_format_feedback_for_agent(self):
        """Test formatting feedback for agent prompt."""
        feedback = FeedbackResponse(
            request_id="fb",
            reviewer_agent_id="A12",
            quality_score=QualityScore(overall=0.5),
            issues=[
                Issue(
                    IssueCategory.ACCURACY,
                    Severity.CRITICAL,
                    "Factual error",
                    suggestion="Fix the error",
                ),
                Issue(
                    IssueCategory.CLARITY,
                    Severity.MINOR,
                    "Unclear phrasing",
                ),
            ],
            summary="Needs work",
        )
        
        trigger = RevisionTrigger(
            trigger_id="tr",
            target_agent_id="A05",
            original_content="...",
            feedback=feedback,
            iteration=1,
            max_iterations=3,
            focus_areas=["Fix critical issues first"],
        )
        
        formatted = trigger.format_feedback_for_agent()
        
        assert "Revision Request" in formatted
        assert "Iteration 1/3" in formatted
        assert "CRITICAL" in formatted
        assert "Factual error" in formatted
        assert "Fix the error" in formatted


class TestConvergenceCriteria:
    """Tests for ConvergenceCriteria dataclass."""
    
    def test_stop_on_quality_threshold(self):
        """Test stopping when quality threshold is met."""
        criteria = ConvergenceCriteria(quality_threshold=0.8)
        
        should_stop, reason = criteria.should_stop(
            current_score=0.85,
            previous_score=0.7,
            iteration=1,
            critical_count=0,
            major_count=0,
        )
        
        assert should_stop is True
        assert "threshold" in reason.lower()
    
    def test_stop_on_max_iterations(self):
        """Test stopping at max iterations."""
        criteria = ConvergenceCriteria(max_iterations=3)
        
        should_stop, reason = criteria.should_stop(
            current_score=0.5,
            previous_score=0.4,
            iteration=3,
            critical_count=1,
            major_count=2,
        )
        
        assert should_stop is True
        assert "maximum" in reason.lower()
    
    def test_continue_with_critical_issues(self):
        """Test continuing when critical issues remain."""
        criteria = ConvergenceCriteria(
            require_no_critical=True,
            quality_threshold=0.8,
        )
        
        should_stop, reason = criteria.should_stop(
            current_score=0.5,
            previous_score=None,
            iteration=1,
            critical_count=2,
            major_count=0,
        )
        
        assert should_stop is False
        assert "critical" in reason.lower()
    
    def test_stop_on_insufficient_improvement(self):
        """Test stopping when improvement is minimal."""
        criteria = ConvergenceCriteria(
            min_improvement=0.05,
            quality_threshold=0.9,  # High threshold
        )
        
        should_stop, reason = criteria.should_stop(
            current_score=0.72,
            previous_score=0.70,  # Only 0.02 improvement
            iteration=2,
            critical_count=0,
            major_count=0,
        )
        
        assert should_stop is True
        assert "improvement" in reason.lower()


class TestAgentCallRequest:
    """Tests for AgentCallRequest dataclass."""
    
    def test_call_request_creation(self):
        """Test creating an agent call request."""
        request = AgentCallRequest(
            call_id="call123",
            caller_agent_id="A03",
            target_agent_id="A01",
            reason="Need data analysis",
            context={"project_folder": "/path/to/project"},
            priority="high",
            timeout_seconds=300,
        )
        
        assert request.call_id == "call123"
        assert request.priority == "high"
    
    def test_call_request_serialization(self):
        """Test call request to dict."""
        request = AgentCallRequest(
            call_id="call123",
            caller_agent_id="A03",
            target_agent_id="A01",
            reason="Need data",
        )
        
        d = request.to_dict()
        
        assert d["call_id"] == "call123"
        assert d["caller_agent_id"] == "A03"


class TestAgentCallResponse:
    """Tests for AgentCallResponse dataclass."""
    
    def test_successful_response(self):
        """Test successful call response."""
        response = AgentCallResponse(
            call_id="call123",
            success=True,
            result={"data": "analysis results"},
            execution_time=5.5,
        )
        
        assert response.success is True
        assert response.error is None
        assert response.result["data"] == "analysis results"
    
    def test_failed_response(self):
        """Test failed call response."""
        response = AgentCallResponse(
            call_id="call123",
            success=False,
            error="Permission denied",
            execution_time=0.1,
        )
        
        assert response.success is False
        assert response.result is None
        assert "Permission" in response.error
