"""
Critical Review Agent
=====================
Evaluates any agent output against quality criteria and generates
structured feedback for iterative refinement.

Uses Opus 4.5 with extended thinking for thorough analysis.

Quality dimensions assessed:
- Accuracy: Factual correctness, no hallucinations
- Completeness: All required elements present
- Clarity: Clear, unambiguous content
- Consistency: No internal contradictions
- Methodology: Sound approach (for research content)
- Contribution: Clear value-add (for academic content)

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

import time
import json
import re
from typing import Optional, List, Dict, Any

from .base import BaseAgent, AgentResult
from .feedback import (
    FeedbackRequest,
    FeedbackResponse,
    QualityScore,
    Issue,
    IssueCategory,
    Severity,
)
from src.llm.claude_client import TaskType
from loguru import logger


# System prompt for critical review
CRITICAL_REVIEW_PROMPT = """You are a critical review agent for academic research outputs.

Your role is to evaluate content produced by other AI agents with the rigor of a peer reviewer at a top academic journal. You identify issues, assess quality, and provide actionable feedback.

REVIEW PRINCIPLES:

1. BE CRITICAL BUT CONSTRUCTIVE
   - Identify real problems, not imagined ones
   - Distinguish critical issues from minor improvements
   - Provide specific, actionable suggestions

2. ASSESS MULTIPLE DIMENSIONS
   - Accuracy: Are claims factually correct? Any hallucinations?
   - Completeness: Are required elements present?
   - Clarity: Is content clear and unambiguous?
   - Consistency: Is content internally consistent?
   - Methodology: Is the approach sound?
   - Contribution: Is there clear value-add?

3. CALIBRATE SEVERITY
   - CRITICAL: Must fix before proceeding; blocks progress
   - MAJOR: Should fix; significantly impacts quality
   - MINOR: Nice to fix; improves quality
   - SUGGESTION: Optional improvement

4. ACADEMIC STANDARDS
   - Check for proper citations
   - Verify claims are supported
   - Assess logical flow
   - Evaluate positioning relative to literature

OUTPUT FORMAT:

You must respond with valid JSON in this exact format:
{
    "quality_scores": {
        "overall": 0.0-1.0,
        "accuracy": 0.0-1.0,
        "completeness": 0.0-1.0,
        "clarity": 0.0-1.0,
        "consistency": 0.0-1.0,
        "methodology": 0.0-1.0,
        "contribution": 0.0-1.0
    },
    "issues": [
        {
            "category": "accuracy|completeness|clarity|consistency|citation|methodology|logic|contribution|formatting|data|code|scope|dependency",
            "severity": "critical|major|minor|suggestion",
            "description": "Clear description of the issue",
            "location": "Where in the content (optional)",
            "suggestion": "How to fix (required for critical/major)",
            "affects_downstream": true/false
        }
    ],
    "summary": "One paragraph overall assessment",
    "revision_required": true/false,
    "revision_priority": ["First thing to fix", "Second thing to fix"]
}

SCORING GUIDE:
- 0.0-0.3: Poor, requires major revision
- 0.3-0.6: Acceptable, needs improvement  
- 0.6-0.8: Good, minor issues
- 0.8-1.0: Excellent, publication ready

Be honest and calibrated. Do not inflate scores to be nice.
Do not identify problems that don't exist.
Focus on substantive issues, not style preferences."""


# Content type specific criteria
CONTENT_CRITERIA = {
    "hypothesis": {
        "required_elements": [
            "Clear, testable main hypothesis",
            "Economic or theoretical foundation",
            "Testable predictions",
            "Alternative hypotheses",
            "Connection to data availability",
        ],
        "quality_checks": [
            "Is the hypothesis falsifiable?",
            "Is the prediction directional and specific?",
            "Is the theoretical mechanism clear?",
            "Are alternative explanations considered?",
        ],
    },
    "literature_review": {
        "required_elements": [
            "Coverage of key papers",
            "Identification of research streams",
            "Gap identification",
            "Methodological insights",
            "Citation priority list",
        ],
        "quality_checks": [
            "Are seminal papers included?",
            "Is the gap clearly articulated?",
            "Are conflicting findings noted?",
            "Is positioning clear?",
        ],
    },
    "methodology": {
        "required_elements": [
            "Variable definitions",
            "Data requirements",
            "Identification strategy",
            "Regression specifications",
            "Robustness approach",
        ],
        "quality_checks": [
            "Is identification clean?",
            "Are standard errors appropriate?",
            "Is replication possible?",
            "Are alternative specifications considered?",
        ],
    },
    "project_plan": {
        "required_elements": [
            "Phase breakdown",
            "Time estimates",
            "Deliverables",
            "Dependencies",
            "Risk assessment",
        ],
        "quality_checks": [
            "Are estimates realistic?",
            "Are dependencies identified?",
            "Are milestones measurable?",
            "Is critical path clear?",
        ],
    },
    "paper_structure": {
        "required_elements": [
            "All major sections",
            "LaTeX formatting",
            "Citation setup",
            "Table/figure placeholders",
        ],
        "quality_checks": [
            "Does structure match journal requirements?",
            "Is section balance appropriate?",
            "Are all components present?",
        ],
    },
    "general": {
        "required_elements": [],
        "quality_checks": [
            "Is content accurate?",
            "Is content complete?",
            "Is content clear?",
        ],
    },
}


class CriticalReviewAgent(BaseAgent):
    """
    Agent that evaluates other agents' outputs for quality.
    
    Uses Opus 4.5 with extended thinking for thorough analysis.
    Produces structured feedback that can trigger revision loops.
    """
    
    def __init__(self, client: Optional[Any] = None):
        super().__init__(
            name="CriticalReviewer",
            task_type=TaskType.COMPLEX_REASONING,  # Uses Opus
            system_prompt=CRITICAL_REVIEW_PROMPT,
            client=client,
        )
    
    async def execute(self, context: dict) -> AgentResult:
        """
        Review content and produce quality assessment.
        
        Args:
            context: Must contain:
                - 'content': The content to review
                - 'content_type': Type of content (hypothesis, literature_review, etc.)
                Optional:
                - 'quality_criteria': Specific criteria to check
                - 'source_agent_id': Which agent produced the content
            
        Returns:
            AgentResult with FeedbackResponse in structured_data
        """
        start_time = time.time()
        
        content = context.get("content")
        content_type = context.get("content_type", "general")
        source_agent_id = context.get("source_agent_id", "unknown")
        custom_criteria = context.get("quality_criteria", [])
        
        if not content:
            return AgentResult(
                agent_name=self.name,
                task_type=self.task_type,
                model_tier=self.model_tier,
                success=False,
                content="",
                error="No content provided for review",
                execution_time=time.time() - start_time,
            )
        
        # Build review prompt
        user_message = self._build_review_prompt(
            content=content,
            content_type=content_type,
            custom_criteria=custom_criteria,
        )
        
        try:
            # Use extended thinking for thorough analysis
            response, tokens = await self._call_claude(
                user_message=user_message,
                use_thinking=True,
                max_tokens=16000,
                budget_tokens=10000,
            )
            
            # Parse response into FeedbackResponse
            feedback = self._parse_feedback(
                response=response,
                source_agent_id=source_agent_id,
            )
            
            return AgentResult(
                agent_name=self.name,
                task_type=self.task_type,
                model_tier=self.model_tier,
                success=True,
                content=response,
                tokens_used=tokens,
                execution_time=time.time() - start_time,
                structured_data={
                    "feedback": feedback.to_dict(),
                    "quality_score": feedback.quality_score.overall,
                    "revision_required": feedback.revision_required,
                    "critical_issues_count": len(feedback.critical_issues),
                    "major_issues_count": len(feedback.major_issues),
                },
            )
            
        except Exception as e:
            logger.error(f"Critical review error: {e}")
            return AgentResult(
                agent_name=self.name,
                task_type=self.task_type,
                model_tier=self.model_tier,
                success=False,
                content="",
                error=str(e),
                execution_time=time.time() - start_time,
            )
    
    def _build_review_prompt(
        self,
        content: str,
        content_type: str,
        custom_criteria: List[str],
    ) -> str:
        """Build the review prompt with content-specific criteria."""
        # Get criteria for content type
        criteria = CONTENT_CRITERIA.get(content_type, CONTENT_CRITERIA["general"])
        
        # Build criteria section
        criteria_text = []
        
        if criteria["required_elements"]:
            criteria_text.append("**Required Elements:**")
            for elem in criteria["required_elements"]:
                criteria_text.append(f"- {elem}")
        
        if criteria["quality_checks"]:
            criteria_text.append("\n**Quality Checks:**")
            for check in criteria["quality_checks"]:
                criteria_text.append(f"- {check}")
        
        if custom_criteria:
            criteria_text.append("\n**Custom Criteria:**")
            for crit in custom_criteria:
                criteria_text.append(f"- {crit}")
        
        criteria_section = "\n".join(criteria_text)
        
        return f"""## Critical Review Request

**Content Type:** {content_type}

### Content to Review:

---
{content}
---

### Evaluation Criteria:

{criteria_section}

### Instructions:

1. Read the content carefully
2. Evaluate against each criterion
3. Identify specific issues with locations
4. Assign calibrated quality scores
5. Determine if revision is required
6. Provide prioritized feedback

Respond with valid JSON as specified in your instructions."""
    
    def _parse_feedback(
        self,
        response: str,
        source_agent_id: str,
    ) -> FeedbackResponse:
        """Parse Claude response into FeedbackResponse."""
        import uuid
        
        # Try to extract JSON from response
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse review JSON: {e}")
            # Return default feedback
            return FeedbackResponse(
                request_id=str(uuid.uuid4())[:8],
                reviewer_agent_id="A12",
                quality_score=QualityScore(overall=0.5),
                issues=[],
                summary="Unable to parse review response",
                revision_required=True,
            )
        
        # Parse quality scores
        scores_data = data.get("quality_scores", {})
        quality_score = QualityScore(
            overall=scores_data.get("overall", 0.5),
            accuracy=scores_data.get("accuracy", 0.5),
            completeness=scores_data.get("completeness", 0.5),
            clarity=scores_data.get("clarity", 0.5),
            consistency=scores_data.get("consistency", 0.5),
            methodology=scores_data.get("methodology", 0.5),
            contribution=scores_data.get("contribution", 0.5),
        )
        
        # Parse issues
        issues = []
        for issue_data in data.get("issues", []):
            try:
                # Map category string to enum
                category_str = issue_data.get("category", "accuracy").lower()
                category_map = {
                    "accuracy": IssueCategory.ACCURACY,
                    "completeness": IssueCategory.COMPLETENESS,
                    "consistency": IssueCategory.CONSISTENCY,
                    "clarity": IssueCategory.CLARITY,
                    "citation": IssueCategory.CITATION,
                    "methodology": IssueCategory.METHODOLOGY,
                    "logic": IssueCategory.LOGIC,
                    "contribution": IssueCategory.CONTRIBUTION,
                    "formatting": IssueCategory.FORMATTING,
                    "data": IssueCategory.DATA,
                    "code": IssueCategory.CODE,
                    "scope": IssueCategory.SCOPE,
                    "dependency": IssueCategory.DEPENDENCY,
                }
                category = category_map.get(category_str, IssueCategory.ACCURACY)
                
                # Map severity string to enum
                severity_str = issue_data.get("severity", "minor").lower()
                severity_map = {
                    "critical": Severity.CRITICAL,
                    "major": Severity.MAJOR,
                    "minor": Severity.MINOR,
                    "suggestion": Severity.SUGGESTION,
                }
                severity = severity_map.get(severity_str, Severity.MINOR)
                
                issues.append(Issue(
                    category=category,
                    severity=severity,
                    description=issue_data.get("description", ""),
                    location=issue_data.get("location"),
                    suggestion=issue_data.get("suggestion"),
                    affects_downstream=issue_data.get("affects_downstream", False),
                ))
            except Exception as e:
                logger.debug(f"Failed to parse issue: {e}")
                continue
        
        return FeedbackResponse(
            request_id=str(uuid.uuid4())[:8],
            reviewer_agent_id="A12",
            quality_score=quality_score,
            issues=issues,
            summary=data.get("summary", ""),
            revision_required=data.get("revision_required", False),
            revision_priority=data.get("revision_priority", []),
        )
    
    async def review_agent_result(
        self,
        result: AgentResult,
        content_type: str = "general",
    ) -> FeedbackResponse:
        """
        Convenience method to review an AgentResult directly.
        
        Args:
            result: AgentResult to review
            content_type: Type of content for criteria selection
            
        Returns:
            FeedbackResponse with quality assessment
        """
        context = {
            "content": result.content,
            "content_type": content_type,
            "source_agent_id": result.agent_name,
        }
        
        review_result = await self.execute(context)
        
        if review_result.success:
            return FeedbackResponse.from_dict(
                review_result.structured_data.get("feedback", {})
            )
        else:
            # Return a default response indicating review failed
            return FeedbackResponse(
                request_id="error",
                reviewer_agent_id="A12",
                quality_score=QualityScore(overall=0.0),
                issues=[Issue(
                    category=IssueCategory.ACCURACY,
                    severity=Severity.CRITICAL,
                    description=f"Review failed: {review_result.error}",
                )],
                summary="Critical review failed",
                revision_required=True,
            )
    
    def supports_revision(self) -> bool:
        """Critical reviewer doesn't revise its own output."""
        return False
