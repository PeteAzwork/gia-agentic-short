"""
Tests for Readiness Scoring Module
==================================
Unit tests for the project readiness scoring and checklist system.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

import pytest
import tempfile
import os
from pathlib import Path

from src.utils.readiness_scoring import (
    ReadinessCategory,
    CheckStatus,
    AutomationCapability,
    ChecklistItem,
    PhaseReadiness,
    ReadinessReport,
    STANDARD_CHECKLIST,
    save_readiness_report,
    load_readiness_report,
)


class TestChecklistItem:
    """Tests for ChecklistItem dataclass."""
    
    @pytest.mark.unit
    def test_item_creation(self):
        """Test basic item creation."""
        item = ChecklistItem(
            item_id="test_item",
            category=ReadinessCategory.DATA,
            description="Test description",
            status=CheckStatus.NOT_STARTED,
            automation_capability=AutomationCapability.FULLY_AUTOMATED,
            assigned_agent="A6",
        )
        assert item.item_id == "test_item"
        assert item.category == ReadinessCategory.DATA
        assert item.assigned_agent == "A6"
    
    @pytest.mark.unit
    def test_item_to_dict(self):
        """Test converting item to dictionary."""
        item = ChecklistItem(
            item_id="test",
            category=ReadinessCategory.DATA,
            description="Test",
            status=CheckStatus.COMPLETE,
            automation_capability=AutomationCapability.FULLY_AUTOMATED,
            assigned_agent="A6",
        )
        d = item.to_dict()
        assert d["item_id"] == "test"
        assert d["status"] == "complete"
        assert d["assigned_agent"] == "A6"
    
    @pytest.mark.unit
    def test_item_mark_complete(self):
        """Test marking item complete."""
        item = ChecklistItem(
            item_id="test",
            category=ReadinessCategory.DATA,
            description="Test",
        )
        item.mark_complete(agent_name="TestAgent", evidence="File exists")
        assert item.status == CheckStatus.COMPLETE
        assert item.completion_percentage == 100.0
        assert item.last_updated_by == "TestAgent"
    
    @pytest.mark.unit
    def test_item_mark_partial(self):
        """Test marking item partially complete."""
        item = ChecklistItem(
            item_id="test",
            category=ReadinessCategory.DATA,
            description="Test",
        )
        item.mark_partial(50.0, agent_name="TestAgent")
        assert item.status == CheckStatus.PARTIAL
        assert item.completion_percentage == 50.0


class TestPhaseReadiness:
    """Tests for PhaseReadiness class."""
    
    @pytest.mark.unit
    def test_phase_creation(self):
        """Test creating phase readiness."""
        phase = PhaseReadiness(phase_id="phase1", phase_name="Phase 1: Data")
        assert phase.phase_name == "Phase 1: Data"
        assert len(phase.items) == 0
    
    @pytest.mark.unit
    def test_add_item(self):
        """Test adding items to phase."""
        phase = PhaseReadiness(phase_id="phase1", phase_name="Test Phase")
        item = ChecklistItem(
            item_id="item1",
            category=ReadinessCategory.DATA,
            description="Test item",
            status=CheckStatus.NOT_STARTED,
            automation_capability=AutomationCapability.FULLY_AUTOMATED,
        )
        phase.items.append(item)
        assert len(phase.items) == 1
    
    @pytest.mark.unit
    def test_completion_rate(self):
        """Test completion rate calculation."""
        phase = PhaseReadiness(phase_id="test", phase_name="Test")
        
        # Add items: 2 complete (100%), 1 partial (50%)
        item1 = ChecklistItem("item1", ReadinessCategory.DATA, "Item 1")
        item1.mark_complete()
        phase.items.append(item1)
        
        item2 = ChecklistItem("item2", ReadinessCategory.DATA, "Item 2")
        item2.mark_complete()
        phase.items.append(item2)
        
        item3 = ChecklistItem("item3", ReadinessCategory.DATA, "Item 3")
        item3.mark_partial(50.0)
        phase.items.append(item3)
        
        # (100 + 100 + 50) / 3 / 100 = 0.833
        assert phase.completion_rate == pytest.approx(0.833, 0.01)
    
    @pytest.mark.unit
    def test_automation_counts(self):
        """Test automation count updates."""
        phase = PhaseReadiness(phase_id="test", phase_name="Test")
        
        phase.items.append(ChecklistItem(
            "item1", ReadinessCategory.DATA, "Item 1",
            automation_capability=AutomationCapability.FULLY_AUTOMATED
        ))
        phase.items.append(ChecklistItem(
            "item2", ReadinessCategory.DATA, "Item 2",
            automation_capability=AutomationCapability.NEEDS_CAPABILITY
        ))
        phase.items.append(ChecklistItem(
            "item3", ReadinessCategory.DATA, "Item 3",
            automation_capability=AutomationCapability.FULLY_AUTOMATED
        ))
        
        phase.update_automation_counts()
        assert phase.fully_automated_count == 2
        assert phase.needs_capability_count == 1


class TestReadinessReport:
    """Tests for ReadinessReport class."""
    
    @pytest.mark.unit
    def test_report_creation(self):
        """Test creating empty report."""
        report = ReadinessReport(project_id="test-project", project_folder="/tmp/test")
        assert report.project_id == "test-project"
        assert len(report.phases) == 0
    
    @pytest.mark.unit
    def test_add_phase(self):
        """Test adding phases to report."""
        report = ReadinessReport(project_id="test", project_folder="/tmp/test")
        phase = PhaseReadiness(phase_id="phase1", phase_name="Phase 1")
        report.phases.append(phase)
        assert len(report.phases) == 1
    
    @pytest.mark.unit
    def test_overall_completion(self):
        """Test overall completion calculation."""
        report = ReadinessReport(project_id="test", project_folder="/tmp/test")
        
        phase = PhaseReadiness(phase_id="test", phase_name="Test Phase")
        for i in range(4):
            item = ChecklistItem(f"item{i}", ReadinessCategory.DATA, f"Item {i}")
            if i < 3:
                item.mark_complete()
            phase.items.append(item)
        report.phases.append(phase)
        
        report.calculate_overall_completion()
        assert report.overall_completion == pytest.approx(75.0, 0.01)
    
    @pytest.mark.unit
    def test_identify_automation_gaps(self):
        """Test identifying automation gaps."""
        report = ReadinessReport(project_id="test", project_folder="/tmp/test")
        
        phase = PhaseReadiness(phase_id="test", phase_name="Test Phase")
        
        # Add item that needs capability
        gap_item = ChecklistItem(
            item_id="gap1",
            category=ReadinessCategory.DATA,
            description="Needs automation",
            automation_capability=AutomationCapability.NEEDS_CAPABILITY,
        )
        phase.items.append(gap_item)
        
        # Add fully automated item
        auto_item = ChecklistItem(
            item_id="auto1",
            category=ReadinessCategory.DATA,
            description="Already automated",
            automation_capability=AutomationCapability.FULLY_AUTOMATED,
        )
        phase.items.append(auto_item)
        
        report.phases.append(phase)
        report.identify_automation_gaps()
        
        assert len(report.automation_gaps) == 1
        assert report.automation_gaps[0]["item_id"] == "gap1"
    
    @pytest.mark.unit
    def test_get_phase(self):
        """Test getting phase by ID."""
        report = ReadinessReport(project_id="test", project_folder="/tmp/test")
        phase1 = PhaseReadiness(phase_id="phase1", phase_name="Phase 1")
        phase2 = PhaseReadiness(phase_id="phase2", phase_name="Phase 2")
        report.phases.extend([phase1, phase2])
        
        found = report.get_phase("phase2")
        assert found is not None
        assert found.phase_name == "Phase 2"
    
    @pytest.mark.unit
    def test_get_item(self):
        """Test getting item by ID."""
        report = ReadinessReport(project_id="test", project_folder="/tmp/test")
        phase = PhaseReadiness(phase_id="phase1", phase_name="Phase 1")
        item = ChecklistItem("item1", ReadinessCategory.DATA, "Test item")
        phase.items.append(item)
        report.phases.append(phase)
        
        found = report.get_item("item1")
        assert found is not None
        assert found.description == "Test item"


class TestStandardChecklist:
    """Tests for the standard checklist."""
    
    @pytest.mark.unit
    def test_checklist_exists(self):
        """Test that standard checklist is defined."""
        assert STANDARD_CHECKLIST is not None
        assert len(STANDARD_CHECKLIST) > 0
    
    @pytest.mark.unit
    def test_checklist_has_phases(self):
        """Test checklist has phase structure."""
        # STANDARD_CHECKLIST is a list of phase dicts
        for phase in STANDARD_CHECKLIST:
            assert "phase_id" in phase
            assert "phase_name" in phase
            assert "items" in phase
    
    @pytest.mark.unit
    def test_items_have_structure(self):
        """Test all items have required fields."""
        for phase in STANDARD_CHECKLIST:
            for item in phase["items"]:
                assert "item_id" in item
                assert "category" in item
                assert "description" in item


class TestReportPersistence:
    """Tests for saving and loading reports."""
    
    @pytest.mark.unit
    def test_save_and_load_report(self, tmp_path):
        """Test saving and loading a readiness report."""
        report = ReadinessReport(project_id="test", project_folder=str(tmp_path))
        
        phase = PhaseReadiness(phase_id="phase1", phase_name="Phase 1")
        item = ChecklistItem("item1", ReadinessCategory.DATA, "Test item")
        item.mark_complete()
        phase.items.append(item)
        report.phases.append(phase)
        
        # Save - uses report.project_folder internally
        save_readiness_report(report)
        
        # Load
        loaded = load_readiness_report(str(tmp_path))
        assert loaded is not None
        assert loaded.project_id == "test"
        assert len(loaded.phases) == 1
        assert loaded.phases[0].items[0].status == CheckStatus.COMPLETE


class TestCategoryScores:
    """Tests for category scoring."""
    
    @pytest.mark.unit
    def test_calculate_category_scores(self):
        """Test category score calculation."""
        report = ReadinessReport(project_id="test", project_folder="/tmp/test")
        
        phase = PhaseReadiness(phase_id="phase1", phase_name="Phase 1")
        
        # Add 2 DATA items (one complete, one not)
        data_item1 = ChecklistItem("data1", ReadinessCategory.DATA, "Data 1")
        data_item1.mark_complete()
        phase.items.append(data_item1)
        
        data_item2 = ChecklistItem("data2", ReadinessCategory.DATA, "Data 2")
        phase.items.append(data_item2)  # 0% complete
        
        # Add 1 LITERATURE item (complete)
        lit_item = ChecklistItem("lit1", ReadinessCategory.LITERATURE, "Lit 1")
        lit_item.mark_complete()
        phase.items.append(lit_item)
        
        report.phases.append(phase)
        report.calculate_category_scores()
        
        # DATA: (100 + 0) / 2 = 50
        assert report.category_scores["data"] == pytest.approx(50.0, 0.01)
        # LITERATURE: 100 / 1 = 100
        assert report.category_scores["literature"] == pytest.approx(100.0, 0.01)


class TestAgentContributions:
    """Tests for tracking agent contributions."""
    
    @pytest.mark.unit
    def test_add_agent_contribution(self):
        """Test adding agent contribution."""
        report = ReadinessReport(project_id="test", project_folder="/tmp/test")
        
        report.add_agent_contribution(
            agent_name="A1",
            items_completed=["item1", "item2"],
            execution_time=10.5,
            tokens_used=500,
        )
        
        assert "A1" in report.agent_contributions
        assert len(report.agent_contributions["A1"]["items_completed"]) == 2
        assert report.agent_contributions["A1"]["total_execution_time"] == 10.5
        assert report.agent_contributions["A1"]["total_tokens"] == 500
    
    @pytest.mark.unit
    def test_multiple_contributions(self):
        """Test multiple contributions from same agent."""
        report = ReadinessReport(project_id="test", project_folder="/tmp/test")
        
        report.add_agent_contribution("A1", ["item1"], 5.0, 200)
        report.add_agent_contribution("A1", ["item2"], 7.0, 300)
        
        assert len(report.agent_contributions["A1"]["items_completed"]) == 2
        assert report.agent_contributions["A1"]["total_execution_time"] == 12.0
        assert report.agent_contributions["A1"]["total_tokens"] == 500
        assert len(report.agent_contributions["A1"]["executions"]) == 2
