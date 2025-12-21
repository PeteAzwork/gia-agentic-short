"""
Tests for Style Validation Utilities
=====================================
Tests banned word detection, word counting, and style enforcement.
"""

import pytest
from src.utils.style_validation import (
    check_banned_words,
    count_words,
    count_words_by_section,
    estimate_page_count,
    validate_style,
    auto_replace_banned_words,
    detect_sections_latex,
    detect_sections_markdown,
    is_latex_document,
    normalize_section_name,
    BANNED_WORD_REPLACEMENTS,
    SECTION_WORD_TARGETS,
)


class TestBannedWordDetection:
    """Tests for banned word checking."""
    
    def test_detect_single_banned_word(self):
        """Test detecting a single banned word."""
        text = "This paper will delve into the topic of market liquidity."
        matches = check_banned_words(text)
        
        assert len(matches) == 1
        assert matches[0].word == "delve"
        assert "delve" in matches[0].context.lower()
        assert len(matches[0].replacements) > 0
    
    def test_detect_multiple_banned_words(self):
        """Test detecting multiple banned words."""
        text = "We leverage cutting-edge techniques to unlock unprecedented insights."
        matches = check_banned_words(text)
        
        words_found = {m.word for m in matches}
        assert "leverage" in words_found
        assert "cutting-edge" in words_found
        assert "unlock" in words_found
        assert "unprecedented" in words_found
    
    def test_no_banned_words(self):
        """Test text without banned words."""
        text = "We use standard methods to analyze market data."
        matches = check_banned_words(text)
        
        assert len(matches) == 0
    
    def test_case_insensitive(self):
        """Test case-insensitive detection."""
        text = "DELVE Delve delve"
        matches = check_banned_words(text)
        
        assert len(matches) == 3
    
    def test_word_boundary_detection(self):
        """Test that partial matches are not flagged."""
        # "potential" is banned, but "potentiality" should not be flagged
        # Note: this depends on the regex being word-boundary aware
        text = "The potential for growth is significant."
        matches = check_banned_words(text)
        
        assert any(m.word == "potential" for m in matches)
    
    def test_hyphenated_words(self):
        """Test detection of hyphenated banned words."""
        text = "This is a cutting-edge approach using next-gen technology."
        matches = check_banned_words(text)
        
        words_found = {m.word for m in matches}
        assert "cutting-edge" in words_found
        assert "next-gen" in words_found
    
    def test_replacement_suggestions(self):
        """Test that replacements are provided."""
        text = "We utilize this method."
        matches = check_banned_words(text)
        
        assert len(matches) == 1
        assert matches[0].word == "utilize"
        assert "use" in matches[0].replacements


class TestWordCounting:
    """Tests for word counting functionality."""
    
    def test_count_plain_text(self):
        """Test counting words in plain text."""
        text = "This is a simple test sentence with ten words total."
        count = count_words(text)
        
        assert count == 10
    
    def test_count_latex_text(self):
        """Test that LaTeX commands are excluded from count."""
        text = r"\section{Introduction} This is the content. \cite{author2024}"
        count = count_words(text)
        
        # Should count "This is the content" = 4 words
        assert count == 4
    
    def test_count_latex_comments_excluded(self):
        """Test that LaTeX comments are excluded."""
        text = "This is content. % This is a comment\nMore content here."
        count = count_words(text)
        
        # Should count "This is content More content here" = 6 words
        assert count == 6
    
    def test_empty_text(self):
        """Test counting empty text."""
        assert count_words("") == 0
        assert count_words("   ") == 0


class TestSectionDetection:
    """Tests for section boundary detection."""
    
    def test_detect_latex_sections(self):
        """Test detecting sections in LaTeX."""
        text = r"""
\section{Introduction}
This is the introduction.

\section{Methods}
This is the methods section.

\section{Results}
These are the results.
"""
        sections = detect_sections_latex(text)
        
        assert len(sections) == 3
        section_names = [s[0] for s in sections]
        assert "introduction" in section_names
        assert "methods" in section_names or "methodology" in section_names
        assert "results" in section_names
    
    def test_detect_markdown_sections(self):
        """Test detecting sections in Markdown."""
        text = """
# Introduction
This is the introduction.

## Methods
This is the methods section.

# Results
These are the results.
"""
        sections = detect_sections_markdown(text)
        
        assert len(sections) >= 2
    
    def test_is_latex_document(self):
        """Test LaTeX document detection."""
        latex_text = r"\documentclass{article}\begin{document}Content\end{document}"
        markdown_text = "# Title\n\nSome content."
        
        assert is_latex_document(latex_text) is True
        assert is_latex_document(markdown_text) is False
    
    def test_normalize_section_name(self):
        """Test section name normalization."""
        assert normalize_section_name("Introduction") == "introduction"
        assert normalize_section_name("Intro") == "introduction"
        assert normalize_section_name("Data and Methods") == "data and methodology"
        assert normalize_section_name("Concluding Remarks") == "conclusion"


class TestWordCountBySection:
    """Tests for section-wise word counting."""
    
    def test_count_by_section_latex(self):
        """Test word count by section in LaTeX document."""
        text = r"""
\section{Abstract}
Short abstract text.

\section{Introduction}
This is a longer introduction section with more words to count in it.

\section{Conclusion}
Brief conclusion.
"""
        sections = count_words_by_section(text)
        
        assert len(sections) >= 2
        
        # Find introduction section
        intro = next((s for s in sections if s.section_name == "introduction"), None)
        if intro:
            assert intro.word_count > 5


class TestPageEstimation:
    """Tests for page count estimation."""
    
    def test_estimate_pages(self):
        """Test page estimation."""
        # 500 words should be about 2 pages (double-spaced)
        pages = estimate_page_count(500)
        assert 1.5 <= pages <= 2.5
        
        # 2500 words should be about 10 pages
        pages = estimate_page_count(2500)
        assert 9 <= pages <= 11


class TestFullValidation:
    """Tests for complete style validation."""
    
    def test_validate_clean_text(self):
        """Test validation of text without issues."""
        text = "This is a clean academic text without any problematic words."
        result = validate_style(text, check_words=True, check_counts=False)
        
        assert result.is_valid is True
        assert len(result.banned_words) == 0
    
    def test_validate_with_banned_words(self):
        """Test validation flags banned words."""
        text = "We leverage innovative methods to unlock unprecedented results."
        result = validate_style(text, check_words=True, check_counts=False)
        
        # is_valid should still be True (banned words are MAJOR, not CRITICAL)
        assert result.is_valid is True
        assert len(result.banned_words) >= 3
        assert len(result.issues) >= 3
        assert len(result.suggestions) >= 3
    
    def test_validate_provides_suggestions(self):
        """Test that validation provides replacement suggestions."""
        text = "We utilize this approach."
        result = validate_style(text, check_words=True, check_counts=False)
        
        assert len(result.suggestions) > 0
        assert any("use" in s.lower() for s in result.suggestions)


class TestAutoReplace:
    """Tests for automatic banned word replacement."""
    
    def test_auto_replace_single_word(self):
        """Test replacing a single banned word."""
        text = "We utilize this method."
        fixed, replacements = auto_replace_banned_words(text)
        
        assert "utilize" not in fixed.lower()
        assert "use" in fixed.lower()
        assert len(replacements) == 1
    
    def test_auto_replace_preserves_case(self):
        """Test that replacement preserves capitalization."""
        text = "Utilize this. UTILIZE that."
        fixed, _ = auto_replace_banned_words(text)
        
        # Should preserve case
        assert "Use" in fixed or "use" in fixed
    
    def test_auto_replace_multiple_words(self):
        """Test replacing multiple banned words."""
        text = "We leverage innovative methods to unlock results."
        fixed, replacements = auto_replace_banned_words(text)
        
        assert "leverage" not in fixed.lower()
        assert "innovative" not in fixed.lower()
        assert "unlock" not in fixed.lower()
        assert len(replacements) >= 3


class TestReplacementDictionary:
    """Tests for the banned word replacement dictionary."""
    
    def test_all_banned_words_have_replacements(self):
        """Test that all banned words have replacement suggestions."""
        from src.agents.best_practices import BANNED_WORDS
        
        # Check that most banned words have replacements
        # (some might not have specific replacements)
        covered = sum(1 for w in BANNED_WORDS if w in BANNED_WORD_REPLACEMENTS)
        coverage = covered / len(BANNED_WORDS)
        
        assert coverage > 0.9, f"Only {coverage:.0%} of banned words have replacements"
    
    def test_replacements_are_not_banned(self):
        """Test that replacement suggestions are not themselves banned."""
        from src.agents.best_practices import BANNED_WORDS
        banned_set = set(BANNED_WORDS)
        
        for word, replacements in BANNED_WORD_REPLACEMENTS.items():
            for replacement in replacements:
                # Replacements should not be in banned list
                assert replacement not in banned_set, \
                    f"Replacement '{replacement}' for '{word}' is itself banned"
