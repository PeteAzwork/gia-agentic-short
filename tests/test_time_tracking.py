"""
Tests for Time Tracking Module
==============================
Unit tests for the time tracking utilities that track agent execution
against PROJECT_PLAN.md estimates.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta

from src.utils.time_tracking import (
    TimeEstimate,
    ExecutionBudget,
    TrackedTask,
    TimeTrackingReport,
    TaskStatus,
    TaskLevel,
    parse_duration,
    parse_project_plan,
    save_tracking_report,
    load_tracking_report,
)


class TestTimeEstimate:
    """Tests for TimeEstimate dataclass."""
    
    @pytest.mark.unit
    def test_time_estimate_creation(self):
        """Test basic TimeEstimate creation."""
        estimate = TimeEstimate(
            min_hours=1.0,
            max_hours=2.0,
            source_text="1-2 hours"
        )
        assert estimate.min_hours == 1.0
        assert estimate.max_hours == 2.0
        assert estimate.source_text == "1-2 hours"
    
    @pytest.mark.unit
    def test_time_estimate_avg_hours(self):
        """Test average hours property."""
        estimate = TimeEstimate(min_hours=1.0, max_hours=3.0, source_text="1-3 hours")
        assert estimate.avg_hours == 2.0
    
    @pytest.mark.unit
    def test_time_estimate_seconds(self):
        """Test seconds conversion properties."""
        estimate = TimeEstimate(min_hours=1.0, max_hours=2.0, source_text="1-2 hours")
        assert estimate.min_seconds == 3600
        assert estimate.max_seconds == 7200
    
    @pytest.mark.unit
    def test_time_estimate_to_dict(self):
        """Test serialization to dictionary."""
        estimate = TimeEstimate(min_hours=1.0, max_hours=2.0, source_text="1-2 hours")
        d = estimate.to_dict()
        assert d["min_hours"] == 1.0
        assert d["max_hours"] == 2.0
        assert d["avg_hours"] == 1.5


class TestExecutionBudget:
    """Tests for ExecutionBudget class."""
    
    @pytest.mark.unit
    def test_budget_creation(self):
        """Test budget creation with seconds."""
        budget = ExecutionBudget(budget_seconds=60, warning_threshold=0.8)
        assert budget.budget_seconds == 60
        assert budget.warning_threshold == 0.8
    
    @pytest.mark.unit
    def test_budget_check_within_budget(self):
        """Test check when within budget."""
        budget = ExecutionBudget(budget_seconds=60)
        result = budget.check_budget(30.0, "TestAgent")
        assert result is None  # No warning when within budget
    
    @pytest.mark.unit
    def test_budget_check_warning(self):
        """Test check at warning threshold."""
        budget = ExecutionBudget(budget_seconds=100, warning_threshold=0.8)
        result = budget.check_budget(85.0, "TestAgent")  # 85% used
        assert result is not None
        assert "WARNING" in result
    
    @pytest.mark.unit
    def test_budget_check_exceeded(self):
        """Test check when exceeded."""
        budget = ExecutionBudget(budget_seconds=60)
        result = budget.check_budget(70.0, "TestAgent")
        assert result is not None
        assert "EXCEEDED" in result


class TestParseDuration:
    """Tests for duration parsing."""
    
    @pytest.mark.unit
    def test_parse_range_hours(self):
        """Test parsing hour ranges like '2-3 hours'."""
        estimate = parse_duration("2-3 hours")
        assert estimate is not None
        assert estimate.min_hours == 2.0
        assert estimate.max_hours == 3.0
    
    @pytest.mark.unit
    def test_parse_single_hour(self):
        """Test parsing single hour like '1 hour'."""
        estimate = parse_duration("1 hour")
        assert estimate is not None
        assert estimate.min_hours == 1.0
        assert estimate.max_hours == 1.0
    
    @pytest.mark.unit
    def test_parse_half_hour(self):
        """Test parsing half hour like '0.5 hours'."""
        estimate = parse_duration("0.5 hours")
        assert estimate is not None
        assert estimate.min_hours == 0.5
        assert estimate.max_hours == 0.5
    
    @pytest.mark.unit
    def test_parse_invalid(self):
        """Test parsing invalid duration."""
        estimate = parse_duration("unknown")
        assert estimate is None


class TestTrackedTask:
    """Tests for TrackedTask dataclass."""
    
    @pytest.mark.unit
    def test_task_creation(self):
        """Test basic task creation."""
        task = TrackedTask(
            task_id="phase1.step1",
            title="Test Task",
            level=TaskLevel.STEP,
            status=TaskStatus.NOT_STARTED,
        )
        assert task.task_id == "phase1.step1"
        assert task.title == "Test Task"
        assert task.level == TaskLevel.STEP
        assert task.status == TaskStatus.NOT_STARTED
    
    @pytest.mark.unit
    def test_task_mark_started(self):
        """Test starting a task."""
        task = TrackedTask(
            task_id="test",
            title="Test",
            level=TaskLevel.STEP,
            status=TaskStatus.NOT_STARTED,
        )
        task.mark_started()
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.start_time is not None
    
    @pytest.mark.unit
    def test_task_mark_completed(self):
        """Test completing a task."""
        task = TrackedTask(
            task_id="test",
            title="Test",
            level=TaskLevel.STEP,
            status=TaskStatus.NOT_STARTED,
        )
        task.mark_started()
        task.mark_completed()
        assert task.status == TaskStatus.COMPLETED
        assert task.end_time is not None
    
    @pytest.mark.unit
    def test_task_add_execution(self):
        """Test adding agent execution to task."""
        task = TrackedTask(
            task_id="test",
            title="Test",
            level=TaskLevel.STEP,
        )
        task.add_execution("TestAgent", 10.5, tokens_used=100, success=True)
        assert len(task.agent_executions) == 1
        assert task.actual_seconds == 10.5
        assert task.agent_name == "TestAgent"


class TestTimeTrackingReport:
    """Tests for TimeTrackingReport."""
    
    @pytest.mark.unit
    def test_report_creation(self):
        """Test creating empty report."""
        report = TimeTrackingReport(project_id="test-project", project_folder="/tmp/test")
        assert report.project_id == "test-project"
        assert len(report.tasks) == 0
    
    @pytest.mark.unit
    def test_report_add_task(self):
        """Test adding tasks to report."""
        report = TimeTrackingReport(project_id="test", project_folder="/tmp/test")
        task = TrackedTask(
            task_id="task1",
            title="Task 1",
            level=TaskLevel.PHASE,
            status=TaskStatus.NOT_STARTED,
        )
        report.tasks.append(task)
        assert len(report.tasks) == 1
    
    @pytest.mark.unit
    def test_report_completion_rate(self):
        """Test completion rate property."""
        report = TimeTrackingReport(project_id="test", project_folder="/tmp/test")
        
        # Add 3 tasks: 1 completed, 1 in progress, 1 not started
        for i, status in enumerate([TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS, TaskStatus.NOT_STARTED]):
            task = TrackedTask(
                task_id=f"task{i}",
                title=f"Task {i}",
                level=TaskLevel.STEP,
                status=status,
            )
            report.tasks.append(task)
        
        assert len(report.completed_tasks) == 1
        assert len(report.in_progress_tasks) == 1
        assert len(report.not_started_tasks) == 1
        assert report.overall_completion_rate == pytest.approx(1/3, 0.01)
    
    @pytest.mark.unit
    def test_report_filter_by_level(self):
        """Test filtering tasks by level."""
        report = TimeTrackingReport(project_id="test", project_folder="/tmp/test")
        
        # Add phase and step
        report.tasks.append(TrackedTask("phase1", "Phase 1", TaskLevel.PHASE))
        report.tasks.append(TrackedTask("step1.1", "Step 1.1", TaskLevel.STEP))
        report.tasks.append(TrackedTask("step1.2", "Step 1.2", TaskLevel.STEP))
        
        assert len(report.phases) == 1
        assert len(report.steps) == 2


class TestParseProjectPlan:
    """Tests for PROJECT_PLAN.md parsing."""
    
    @pytest.mark.unit
    def test_parse_project_plan(self, tmp_path):
        """Test parsing a project plan file."""
        # Create sample PROJECT_PLAN.md
        plan_content = """# Project Plan

## Phase 1: Data Collection

**Duration:** 2-4 hours

### Step 1.1: Download Data

**Duration:** 1 hour

**Acceptance Criteria:**
- [ ] Raw data files downloaded
- [ ] Files validated for completeness

### Step 1.2: Clean Data

**Duration:** 1-3 hours

**Acceptance Criteria:**
- [x] Missing values handled
- [ ] Outliers identified

## Phase 2: Analysis

**Duration:** 4-6 hours

### Step 2.1: Exploratory Analysis

**Duration:** 2 hours
"""
        plan_path = tmp_path / "PROJECT_PLAN.md"
        plan_path.write_text(plan_content)
        
        # parse_project_plan takes content, project_id, and project_folder
        report = parse_project_plan(plan_content, "test-project", str(tmp_path))
        
        # Should have phases and steps
        assert len(report.tasks) > 0
        
        # Check for phase-level tasks
        phase_tasks = [t for t in report.tasks if t.level == TaskLevel.PHASE]
        assert len(phase_tasks) >= 1
        
        # Check for step-level tasks
        step_tasks = [t for t in report.tasks if t.level == TaskLevel.STEP]
        assert len(step_tasks) >= 2


class TestReportPersistence:
    """Tests for saving and loading reports."""
    
    @pytest.mark.unit
    def test_save_and_load_report(self, tmp_path):
        """Test saving and loading a tracking report."""
        report = TimeTrackingReport(project_id="test", project_folder=str(tmp_path))
        task = TrackedTask(
            task_id="phase1",
            title="Phase 1",
            level=TaskLevel.PHASE,
            status=TaskStatus.COMPLETED,
            estimate=TimeEstimate(1.0, 2.0, "1-2 hours"),
        )
        task.actual_seconds = 3600
        report.tasks.append(task)
        
        # Save - uses report.project_folder internally
        save_tracking_report(report)
        
        # Load
        loaded = load_tracking_report(str(tmp_path))
        assert loaded is not None
        assert loaded.project_id == "test"
        assert len(loaded.tasks) == 1
        assert loaded.tasks[0].actual_seconds == 3600


class TestVarianceCalculation:
    """Tests for variance calculations."""
    
    @pytest.mark.unit
    def test_variance_over_estimate(self):
        """Test variance when over estimate."""
        task = TrackedTask(
            task_id="test",
            title="Test",
            level=TaskLevel.STEP,
            estimate=TimeEstimate(1.0, 1.0, "1 hour"),  # 3600 seconds expected
        )
        task.actual_seconds = 7200  # 2 hours actual
        
        # Should be 100% over
        assert task.variance_percent == pytest.approx(100.0, 0.01)
    
    @pytest.mark.unit
    def test_variance_under_estimate(self):
        """Test variance when under estimate."""
        task = TrackedTask(
            task_id="test",
            title="Test",
            level=TaskLevel.STEP,
            estimate=TimeEstimate(2.0, 2.0, "2 hours"),  # 7200 seconds expected
        )
        task.actual_seconds = 3600  # 1 hour actual
        
        # Should be -50% (under estimate)
        assert task.variance_percent == pytest.approx(-50.0, 0.01)

