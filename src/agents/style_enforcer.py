"""
Style Enforcer Agent (A13)
==========================
Validates text output against the writing style guide,
enforcing banned words, word counts, and journal-specific formatting.

This agent validates final LaTeX output, not intermediate process files.
It flags issues (MAJOR severity) but allows output to proceed.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from loguru import logger

from src.agents.base import BaseAgent, AgentResult
from src.agents.feedback import (
    Issue,
    Severity,
    IssueCategory,
    QualityScore,
    FeedbackResponse,
)
from src.llm.claude_client import ClaudeClient, TaskType, ModelTier
from src.utils.style_validation import (
    validate_style,
    auto_replace_banned_words,
    StyleValidationResult,
    BannedWordMatch,
    SectionWordCount,
    SECTION_WORD_TARGETS,
    TOTAL_WORD_TARGET,
)


# Path to writing style guide
WRITING_STYLE_GUIDE_PATH = Path(__file__).parent.parent.parent / "docs" / "writing_style_guide.md"


@dataclass
class StyleEnforcementConfig:
    """Configuration for style enforcement behavior."""
    # What to check
    check_banned_words: bool = True
    check_word_counts: bool = True
    check_formatting: bool = True
    
    # Behavior settings
    auto_replace: bool = False  # Automatically replace banned words
    is_final_output: bool = True  # Whether validating final LaTeX
    
    # Strictness (for iterations vs drafts)
    mode: str = "draft"  # "draft" (automatic) or "iteration" (on-demand)
    
    # Word count flexibility (percentage over/under allowed)
    word_count_tolerance: float = 0.1  # 10% tolerance


class StyleEnforcerAgent(BaseAgent):
    """
    Agent that validates text against writing style guidelines.
    
    Features:
    - Banned word detection with replacement suggestions
    - Section-by-section word count validation
    - Page estimation for LaTeX output
    - Journal-specific formatting checks
    
    Modes:
    - Draft mode: Automatic validation, flags issues
    - Iteration mode: On-demand validation, more lenient
    """
    
    SYSTEM_PROMPT = """You are a style enforcement agent for academic finance papers.
Your role is to validate text against the writing style guide for top finance journals
(Review of Financial Studies, Journal of Financial Economics, Journal of Finance, JFQA).

You will receive text content and must identify:
1. Banned words that should be replaced
2. Word count compliance by section
3. Formatting issues for LaTeX output
4. Academic tone and style violations

For each issue found:
- Explain why it's problematic
- Suggest specific improvements
- Provide replacement text where applicable

Focus on actionable feedback. Be precise about locations and provide concrete fixes.
Do not block output for style issues; flag them for revision."""

    def __init__(
        self,
        client: Optional[ClaudeClient] = None,
        config: Optional[StyleEnforcementConfig] = None,
    ):
        super().__init__(
            name="StyleEnforcer",
            task_type=TaskType.QUICK_RESPONSE,  # Fast validation using Haiku
            system_prompt=self.SYSTEM_PROMPT,
            client=client,
        )
        self.config = config or StyleEnforcementConfig()
        self._style_guide = self._load_style_guide()
    
    def _load_style_guide(self) -> str:
        """Load writing style guide content."""
        try:
            if WRITING_STYLE_GUIDE_PATH.exists():
                return WRITING_STYLE_GUIDE_PATH.read_text()
        except Exception as e:
            logger.warning(f"Failed to load style guide: {e}")
        return ""
    
    def get_agent_id(self) -> str:
        """Return agent ID for registry."""
        return "A13"
    
    async def execute(self, context: dict) -> AgentResult:
        """
        Execute style validation on content from context.
        
        Args:
            context: Dictionary with 'text' or 'content' key containing text to validate
            
        Returns:
            AgentResult with validation findings
        """
        # Get text from context
        text = context.get("text") or context.get("content", "")
        content_type = context.get("content_type", "paper")
        auto_fix = context.get("auto_fix", self.config.auto_replace)
        
        if not text:
            return AgentResult(
                agent_name=self.name,
                task_type=self.task_type,
                model_tier=ModelTier.HAIKU,
                success=False,
                content="No text provided for validation",
                structured_data={},
                error="Missing 'text' or 'content' in context",
                tokens_used=0,
                execution_time=0.0,
            )
        
        return await self.validate(text, content_type, auto_fix)
    
    async def validate(
        self,
        text: str,
        content_type: str = "paper",
        auto_fix: bool = False,
    ) -> AgentResult:
        """
        Validate text against style guidelines.
        
        Args:
            text: Text to validate (LaTeX or Markdown)
            content_type: Type of content (paper, section, abstract)
            auto_fix: Whether to automatically fix banned words
            
        Returns:
            AgentResult with validation findings
        """
        logger.info(f"Validating {content_type} style ({len(text)} chars)")
        
        # Perform programmatic validation
        validation_result = validate_style(
            text=text,
            check_words=self.config.check_banned_words,
            check_counts=self.config.check_word_counts,
            is_final_output=self.config.is_final_output,
        )
        
        # Auto-replace if requested
        fixed_text = None
        replacements_made = []
        if auto_fix and validation_result.banned_words:
            fixed_text, replacements_made = auto_replace_banned_words(text)
        
        # Convert to Issues for feedback protocol
        issues = self._convert_to_issues(validation_result)
        
        # Calculate style score
        style_score = self._calculate_style_score(validation_result)
        
        # Build result
        structured_data = {
            "validation_result": validation_result.to_dict(),
            "issues": [i.to_dict() for i in issues],
            "style_score": style_score,
            "total_words": validation_result.total_words,
            "estimated_pages": validation_result.estimated_pages,
            "banned_word_count": len(validation_result.banned_words),
            "auto_fixed": auto_fix and len(replacements_made) > 0,
            "replacements_made": replacements_made if replacements_made else None,
            "fixed_text": fixed_text,
        }
        
        # Generate summary
        summary = self._generate_summary(validation_result, issues)
        
        return AgentResult(
            agent_name=self.name,
            task_type=self.task_type,
            model_tier=ModelTier.HAIKU,
            success=True,
            content=summary,
            structured_data=structured_data,
            tokens_used=0,  # No LLM call for programmatic validation
            execution_time=0.0,
        )
    
    async def validate_with_llm(
        self,
        text: str,
        content_type: str = "paper",
        focus_areas: Optional[List[str]] = None,
    ) -> AgentResult:
        """
        Validate text using LLM for nuanced style checking.
        
        This provides deeper analysis beyond programmatic checks,
        including tone, flow, and academic appropriateness.
        
        Args:
            text: Text to validate
            content_type: Type of content
            focus_areas: Specific areas to focus on (e.g., "tone", "clarity")
            
        Returns:
            AgentResult with detailed style feedback
        """
        # First do programmatic validation
        prog_result = await self.validate(text, content_type, auto_fix=False)
        
        # Build prompt for LLM analysis
        focus_str = ", ".join(focus_areas) if focus_areas else "overall style"
        prompt = f"""Analyze this {content_type} for style issues, focusing on: {focus_str}

CONTENT TO REVIEW:
{text[:8000]}  # Truncate for context window

PROGRAMMATIC FINDINGS:
- Total words: {prog_result.structured_data['total_words']}
- Estimated pages: {prog_result.structured_data['estimated_pages']}
- Banned words found: {prog_result.structured_data['banned_word_count']}

STYLE GUIDE EXCERPT:
{self._style_guide[:3000]}

Provide detailed feedback on:
1. Academic tone appropriateness
2. Sentence structure and flow
3. Paragraph organization
4. Technical precision
5. Any stylistic improvements needed

Format your response as JSON with keys: tone_issues, structure_issues, suggestions, overall_assessment"""

        try:
            response = await self.client.call_async(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=self.system_prompt,
                task_type=TaskType.DOCUMENT_CREATION,
            )
            
            # Parse LLM response
            try:
                llm_analysis = json.loads(response.content)
            except json.JSONDecodeError:
                llm_analysis = {"raw_response": response.content}
            
            # Merge with programmatic results
            merged_data = prog_result.structured_data.copy()
            merged_data["llm_analysis"] = llm_analysis
            
            return AgentResult(
                agent_name=self.name,
                task_type=TaskType.DOCUMENT_CREATION,
                model_tier=response.model_tier,
                success=True,
                content=response.content,
                structured_data=merged_data,
                tokens_used=response.tokens_used,
                execution_time=response.execution_time,
            )
            
        except Exception as e:
            logger.error(f"LLM style validation failed: {e}")
            # Fall back to programmatic result
            return prog_result
    
    def _convert_to_issues(self, result: StyleValidationResult) -> List[Issue]:
        """Convert validation result to Issue objects."""
        issues = []
        
        # Banned words -> MAJOR issues (flag but allow)
        for bw in result.banned_words:
            issues.append(Issue(
                category=IssueCategory.FORMATTING,  # Using FORMATTING until we add BANNED_WORDS
                severity=Severity.MAJOR,
                description=f"Banned word '{bw.word}' found: {bw.context}",
                location=f"char {bw.location}",
                suggestion=f"Replace with: {', '.join(bw.replacements[:3])}",
                affects_downstream=False,
            ))
        
        # Word count issues -> MINOR issues (suggestions)
        for sc in result.section_counts:
            if sc.status == 'under':
                issues.append(Issue(
                    category=IssueCategory.COMPLETENESS,
                    severity=Severity.MINOR,
                    description=f"{sc.section_name.title()} is under target word count ({sc.word_count}/{sc.target_min})",
                    location=sc.section_name,
                    suggestion=f"Expand by approximately {sc.target_min - sc.word_count} words",
                    affects_downstream=False,
                ))
            elif sc.status == 'over':
                issues.append(Issue(
                    category=IssueCategory.SCOPE,
                    severity=Severity.MINOR,
                    description=f"{sc.section_name.title()} exceeds target word count ({sc.word_count}/{sc.target_max})",
                    location=sc.section_name,
                    suggestion=f"Reduce by approximately {sc.word_count - sc.target_max} words",
                    affects_downstream=False,
                ))
        
        return issues
    
    def _calculate_style_score(self, result: StyleValidationResult) -> float:
        """Calculate overall style score (0.0 to 1.0)."""
        score = 1.0
        
        # Deduct for banned words (0.02 per word, max 0.3 deduction)
        banned_penalty = min(len(result.banned_words) * 0.02, 0.3)
        score -= banned_penalty
        
        # Deduct for word count issues (0.05 per section, max 0.2 deduction)
        count_issues = sum(1 for sc in result.section_counts if not sc.is_compliant)
        count_penalty = min(count_issues * 0.05, 0.2)
        score -= count_penalty
        
        # Deduct for total length issues
        min_total, max_total = TOTAL_WORD_TARGET
        if result.total_words < min_total * 0.8:
            score -= 0.15
        elif result.total_words > max_total * 1.2:
            score -= 0.1
        
        return max(0.0, round(score, 2))
    
    def _generate_summary(
        self,
        result: StyleValidationResult,
        issues: List[Issue],
    ) -> str:
        """Generate human-readable summary."""
        lines = [
            "## Style Validation Summary",
            "",
            f"**Total Words:** {result.total_words}",
            f"**Estimated Pages:** {result.estimated_pages}",
            f"**Style Score:** {self._calculate_style_score(result):.0%}",
            "",
        ]
        
        if result.banned_words:
            lines.append(f"### Banned Words Found: {len(result.banned_words)}")
            for bw in result.banned_words[:5]:  # Show first 5
                lines.append(f"- **{bw.word}** -> {', '.join(bw.replacements[:2])}")
            if len(result.banned_words) > 5:
                lines.append(f"  ... and {len(result.banned_words) - 5} more")
            lines.append("")
        
        if result.section_counts:
            lines.append("### Section Word Counts")
            for sc in result.section_counts:
                status_icon = "✓" if sc.is_compliant else "⚠"
                lines.append(
                    f"- {status_icon} {sc.section_name.title()}: {sc.word_count} "
                    f"(target: {sc.target_min}-{sc.target_max})"
                )
            lines.append("")
        
        if result.suggestions:
            lines.append("### Suggestions")
            for suggestion in result.suggestions[:5]:
                lines.append(f"- {suggestion}")
            lines.append("")
        
        return "\n".join(lines)
    
    async def create_feedback_response(
        self,
        validation_result: AgentResult,
        request_id: str,
    ) -> FeedbackResponse:
        """
        Create a FeedbackResponse from validation results.
        
        This allows StyleEnforcer to integrate with the feedback protocol.
        """
        data = validation_result.structured_data
        
        # Build quality score with style dimension
        quality_score = QualityScore(
            overall=data.get("style_score", 0.7),
            clarity=data.get("style_score", 0.7),  # Style affects clarity
            completeness=1.0 if not any(
                sc["status"] == "under" 
                for sc in data.get("validation_result", {}).get("section_counts", [])
            ) else 0.7,
        )
        
        # Get issues
        issues = [
            Issue.from_dict(i) for i in data.get("issues", [])
        ]
        
        # Determine if revision is required
        # Banned words -> revision suggested but not required
        # Severe word count issues -> revision suggested
        revision_required = (
            data.get("banned_word_count", 0) > 5 or
            data.get("style_score", 1.0) < 0.6
        )
        
        return FeedbackResponse(
            request_id=request_id,
            reviewer_agent_id=self.get_agent_id(),
            quality_score=quality_score,
            issues=issues,
            summary=validation_result.content,
            revision_required=revision_required,
            revision_priority=[
                "Replace banned words",
                "Adjust section lengths",
            ] if revision_required else [],
        )


# Convenience function for quick validation
def validate_latex_style(
    text: str,
    auto_fix: bool = False,
) -> StyleValidationResult:
    """
    Quick function to validate LaTeX text style.
    
    Args:
        text: LaTeX content to validate
        auto_fix: Whether to auto-replace banned words
        
    Returns:
        StyleValidationResult
    """
    from src.utils.style_validation import validate_style, auto_replace_banned_words
    
    result = validate_style(text, is_final_output=True)
    
    if auto_fix and result.banned_words:
        fixed_text, _ = auto_replace_banned_words(text)
        # Re-validate fixed text
        result = validate_style(fixed_text, is_final_output=True)
    
    return result
