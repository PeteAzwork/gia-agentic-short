"""
Style Validation Utilities
==========================
Functions for validating text against the writing style guide,
including banned words detection, word count validation, and
page estimation for LaTeX output.

This module is designed for final LaTeX output validation,
not intermediate process files.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from loguru import logger

from src.agents.best_practices import BANNED_WORDS


# =============================================================================
# BANNED WORDS WITH REPLACEMENTS
# =============================================================================

# Mapping of banned words to suggested replacements
# Format: banned_word -> list of acceptable alternatives
BANNED_WORD_REPLACEMENTS: Dict[str, List[str]] = {
    # Overused academic buzzwords
    'delve': ['examine', 'investigate', 'explore', 'analyze'],
    'realm': ['area', 'field', 'domain', 'context'],
    'harness': ['use', 'employ', 'apply', 'take advantage of'],
    'unlock': ['reveal', 'enable', 'discover', 'access'],
    'tapestry': ['combination', 'mix', 'set', 'collection'],
    'paradigm': ['framework', 'model', 'approach', 'method'],
    'cutting-edge': ['recent', 'current', 'modern', 'new'],
    'revolutionize': ['change', 'improve', 'modify', 'advance'],
    'landscape': ['environment', 'context', 'setting', 'field'],
    'potential': ['possible', 'may', 'could', 'likely'],
    'findings': ['results', 'evidence', 'observations', 'data'],
    'intricate': ['complex', 'detailed', 'elaborate', 'involved'],
    'showcasing': ['showing', 'demonstrating', 'presenting', 'displaying'],
    'crucial': ['important', 'essential', 'necessary', 'key'],
    'pivotal': ['important', 'central', 'key', 'significant'],
    'surpass': ['exceed', 'outperform', 'beat', 'improve upon'],
    'meticulously': ['carefully', 'precisely', 'thoroughly', 'rigorously'],
    'vibrant': ['active', 'lively', 'energetic', 'thriving'],
    'unparalleled': ['exceptional', 'notable', 'significant', 'substantial'],
    'underscore': ['indicate', 'show', 'demonstrate', 'reveal'],
    'leverage': ['use', 'employ', 'apply', 'take advantage of'],
    'synergy': ['combination', 'cooperation', 'interaction', 'joint effect'],
    'innovative': ['new', 'different', 'original', 'creative'],
    'game-changer': ['significant development', 'major advance', 'important change'],
    'testament': ['evidence', 'proof', 'indication', 'demonstration'],
    'commendable': ['notable', 'worthy', 'praiseworthy', 'good'],
    'meticulous': ['careful', 'precise', 'thorough', 'rigorous'],
    'highlight': ['show', 'demonstrate', 'indicate', 'reveal'],
    'emphasize': ['show', 'stress', 'note', 'indicate'],
    'boast': ['have', 'feature', 'include', 'contain'],
    'groundbreaking': ['new', 'significant', 'important', 'notable'],
    'align': ['match', 'correspond', 'agree', 'fit'],
    'foster': ['encourage', 'promote', 'support', 'develop'],
    'showcase': ['show', 'present', 'display', 'demonstrate'],
    'enhance': ['improve', 'increase', 'strengthen', 'augment'],
    'holistic': ['comprehensive', 'complete', 'overall', 'full'],
    'garner': ['receive', 'obtain', 'get', 'attract'],
    'accentuate': ['stress', 'show', 'intensify', 'underline'],
    'pioneering': ['early', 'first', 'initial', 'original'],
    'trailblazing': ['early', 'first', 'original', 'leading'],
    'unleash': ['release', 'enable', 'trigger', 'activate'],
    'versatile': ['flexible', 'adaptable', 'useful', 'multipurpose'],
    'transformative': ['significant', 'substantial', 'major', 'important'],
    'redefine': ['change', 'modify', 'alter', 'reshape'],
    'seamless': ['smooth', 'easy', 'continuous', 'unified'],
    'optimize': ['improve', 'adjust', 'refine', 'tune'],
    'scalable': ['expandable', 'flexible', 'adaptable', 'extensible'],
    'robust': ['strong', 'stable', 'consistent', 'solid'],
    'breakthrough': ['advance', 'discovery', 'development', 'progress'],
    'empower': ['enable', 'allow', 'help', 'support'],
    'streamline': ['simplify', 'improve', 'organize', 'refine'],
    'intelligent': ['capable', 'advanced', 'sophisticated', 'clever'],
    'smart': ['capable', 'advanced', 'effective', 'clever'],
    'next-gen': ['new', 'modern', 'current', 'recent'],
    'frictionless': ['smooth', 'easy', 'simple', 'straightforward'],
    'elevate': ['raise', 'improve', 'increase', 'lift'],
    'adaptive': ['flexible', 'responsive', 'adjustable', 'changeable'],
    'effortless': ['easy', 'simple', 'straightforward', 'smooth'],
    'data-driven': ['evidence-based', 'empirical', 'quantitative', 'analytical'],
    'insightful': ['informative', 'useful', 'valuable', 'revealing'],
    'proactive': ['active', 'forward-looking', 'anticipatory', 'preventive'],
    'mission-critical': ['essential', 'vital', 'important', 'necessary'],
    'visionary': ['forward-looking', 'ambitious', 'bold', 'imaginative'],
    'disruptive': ['significant', 'major', 'substantial', 'important'],
    'reimagine': ['reconsider', 'rethink', 'redesign', 'revise'],
    'agile': ['flexible', 'adaptable', 'responsive', 'nimble'],
    'customizable': ['adjustable', 'configurable', 'flexible', 'adaptable'],
    'personalized': ['customized', 'tailored', 'individual', 'specific'],
    'unprecedented': ['unusual', 'exceptional', 'rare', 'uncommon'],
    'intuitive': ['easy', 'simple', 'natural', 'straightforward'],
    'leading-edge': ['advanced', 'modern', 'current', 'recent'],
    'synergize': ['combine', 'coordinate', 'integrate', 'cooperate'],
    'democratize': ['expand access', 'make available', 'open up', 'spread'],
    'automate': ['mechanize', 'systematize', 'computerize'],
    'accelerate': ['speed up', 'quicken', 'hasten', 'expedite'],
    'state-of-the-art': ['current', 'modern', 'advanced', 'recent'],
    'dynamic': ['changing', 'active', 'evolving', 'variable'],
    'reliable': ['dependable', 'consistent', 'stable', 'trustworthy'],
    'efficient': ['effective', 'productive', 'economical', 'optimal'],
    'cloud-native': ['cloud-based', 'distributed', 'modern'],
    'immersive': ['engaging', 'interactive', 'comprehensive'],
    'predictive': ['forecasting', 'anticipatory', 'forward-looking'],
    'transparent': ['clear', 'open', 'visible', 'explicit'],
    'proprietary': ['exclusive', 'private', 'owned', 'custom'],
    'integrated': ['combined', 'unified', 'connected', 'linked'],
    'plug-and-play': ['ready-to-use', 'compatible', 'easy-to-use'],
    'turnkey': ['complete', 'ready-to-use', 'comprehensive'],
    'future-proof': ['durable', 'long-lasting', 'adaptable', 'sustainable'],
    'open-ended': ['flexible', 'unrestricted', 'broad', 'general'],
    'AI-powered': ['AI-based', 'automated', 'machine-learning'],
    'next-generation': ['new', 'modern', 'advanced', 'recent'],
    'always-on': ['continuous', 'constant', 'persistent', 'ongoing'],
    'hyper-personalized': ['highly customized', 'tailored', 'individualized'],
    'results-driven': ['outcome-focused', 'goal-oriented', 'effective'],
    'machine-first': ['automated', 'machine-oriented', 'algorithmic'],
    'paradigm-shifting': ['significant', 'major', 'important', 'substantial'],
    'novel': ['new', 'original', 'different', 'fresh'],
    'unique': ['distinct', 'specific', 'particular', 'individual'],
    'utilize': ['use', 'employ', 'apply'],
    'impactful': ['effective', 'significant', 'influential', 'important'],
}


# =============================================================================
# WORD COUNT TARGETS FOR SHORT PAPERS
# =============================================================================

# Section word count targets from writing_style_guide.md
SECTION_WORD_TARGETS: Dict[str, Tuple[int, int]] = {
    'abstract': (50, 75),
    'introduction': (500, 800),
    'data': (400, 700),
    'methodology': (400, 700),
    'methods': (400, 700),
    'data and methodology': (400, 700),
    'results': (800, 1200),
    'discussion': (400, 600),
    'conclusion': (200, 400),
    'conclusions': (200, 400),
}

# Total word count range for short papers
TOTAL_WORD_TARGET: Tuple[int, int] = (2000, 3200)

# Page estimation constants (double-spaced, 12pt Times New Roman)
WORDS_PER_PAGE: int = 250  # Standard academic estimate


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BannedWordMatch:
    """A single banned word found in text."""
    word: str
    location: int  # Character position in text
    context: str  # Surrounding text for context
    replacements: List[str]
    
    def to_dict(self) -> dict:
        return {
            'word': self.word,
            'location': self.location,
            'context': self.context,
            'replacements': self.replacements,
        }


@dataclass
class SectionWordCount:
    """Word count for a specific section."""
    section_name: str
    word_count: int
    target_min: int
    target_max: int
    status: str  # 'ok', 'under', 'over'
    
    @property
    def is_compliant(self) -> bool:
        return self.status == 'ok'
    
    def to_dict(self) -> dict:
        return {
            'section_name': self.section_name,
            'word_count': self.word_count,
            'target_min': self.target_min,
            'target_max': self.target_max,
            'status': self.status,
        }


@dataclass
class StyleValidationResult:
    """Complete result of style validation."""
    is_valid: bool
    banned_words: List[BannedWordMatch] = field(default_factory=list)
    section_counts: List[SectionWordCount] = field(default_factory=list)
    total_words: int = 0
    estimated_pages: float = 0.0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            'is_valid': self.is_valid,
            'banned_words': [bw.to_dict() for bw in self.banned_words],
            'section_counts': [sc.to_dict() for sc in self.section_counts],
            'total_words': self.total_words,
            'estimated_pages': self.estimated_pages,
            'issues': self.issues,
            'suggestions': self.suggestions,
        }


# =============================================================================
# SECTION DETECTION (LATEX-FOCUSED)
# =============================================================================

# Regex patterns for detecting sections in LaTeX
LATEX_SECTION_PATTERNS = [
    # \section{Title} or \section*{Title}
    r'\\section\*?\{([^}]+)\}',
    # \subsection{Title}
    r'\\subsection\*?\{([^}]+)\}',
]

# Regex patterns for detecting sections in Markdown/plain text
MARKDOWN_SECTION_PATTERNS = [
    # # Title or ## Title
    r'^#{1,2}\s+(.+)$',
    # **Title** at start of line
    r'^\*\*([^*]+)\*\*$',
]

# Known section name variations (normalized to lowercase)
SECTION_ALIASES: Dict[str, str] = {
    'intro': 'introduction',
    'lit review': 'literature review',
    'literature': 'literature review',
    'related work': 'literature review',
    'data and methods': 'data and methodology',
    'data & methodology': 'data and methodology',
    'empirical strategy': 'methodology',
    'empirical methodology': 'methodology',
    'results and discussion': 'results',
    'findings': 'results',
    'empirical results': 'results',
    'concluding remarks': 'conclusion',
    'summary': 'conclusion',
}


def normalize_section_name(name: str) -> str:
    """Normalize section name for matching against targets."""
    name = name.lower().strip()
    return SECTION_ALIASES.get(name, name)


def detect_sections_latex(text: str) -> List[Tuple[str, int, int]]:
    """
    Detect section boundaries in LaTeX text.
    
    Returns:
        List of (section_name, start_pos, end_pos) tuples
    """
    sections = []
    
    # Find all section markers
    markers = []
    for pattern in LATEX_SECTION_PATTERNS:
        for match in re.finditer(pattern, text, re.MULTILINE):
            markers.append((match.start(), match.group(1)))
    
    # Sort by position
    markers.sort(key=lambda x: x[0])
    
    # Create sections with boundaries
    for i, (pos, name) in enumerate(markers):
        end_pos = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        sections.append((normalize_section_name(name), pos, end_pos))
    
    return sections


def detect_sections_markdown(text: str) -> List[Tuple[str, int, int]]:
    """
    Detect section boundaries in Markdown/plain text.
    
    Returns:
        List of (section_name, start_pos, end_pos) tuples
    """
    sections = []
    markers = []
    
    for pattern in MARKDOWN_SECTION_PATTERNS:
        for match in re.finditer(pattern, text, re.MULTILINE):
            markers.append((match.start(), match.group(1)))
    
    markers.sort(key=lambda x: x[0])
    
    for i, (pos, name) in enumerate(markers):
        end_pos = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        sections.append((normalize_section_name(name), pos, end_pos))
    
    return sections


def is_latex_document(text: str) -> bool:
    """Check if text appears to be LaTeX."""
    latex_indicators = [
        r'\\documentclass',
        r'\\begin\{document\}',
        r'\\section',
        r'\\usepackage',
        r'\\maketitle',
    ]
    return any(re.search(p, text) for p in latex_indicators)


# =============================================================================
# CORE VALIDATION FUNCTIONS
# =============================================================================

def check_banned_words(
    text: str,
    context_chars: int = 50,
) -> List[BannedWordMatch]:
    """
    Check text for banned words and return matches with suggestions.
    
    Args:
        text: Text to check
        context_chars: Number of characters of context to include
        
    Returns:
        List of BannedWordMatch objects for each occurrence
    """
    matches = []
    text_lower = text.lower()
    
    for word in BANNED_WORDS:
        # Create pattern that matches whole words only
        # Handle hyphenated words specially
        if '-' in word:
            pattern = re.escape(word)
        else:
            pattern = r'\b' + re.escape(word) + r'\b'
        
        for match in re.finditer(pattern, text_lower, re.IGNORECASE):
            start = match.start()
            end = match.end()
            
            # Extract context
            ctx_start = max(0, start - context_chars)
            ctx_end = min(len(text), end + context_chars)
            context = text[ctx_start:ctx_end]
            if ctx_start > 0:
                context = '...' + context
            if ctx_end < len(text):
                context = context + '...'
            
            # Get replacements
            replacements = BANNED_WORD_REPLACEMENTS.get(word, ['[consider rephrasing]'])
            
            matches.append(BannedWordMatch(
                word=word,
                location=start,
                context=context,
                replacements=replacements,
            ))
    
    return matches


def count_words(text: str) -> int:
    """
    Count words in text, excluding LaTeX commands.
    
    Args:
        text: Text to count
        
    Returns:
        Word count
    """
    # Remove LaTeX commands
    clean = re.sub(r'\\[a-zA-Z]+\*?\{[^}]*\}', '', text)
    clean = re.sub(r'\\[a-zA-Z]+\*?', '', clean)
    clean = re.sub(r'\{|\}', '', clean)
    clean = re.sub(r'%.*$', '', clean, flags=re.MULTILINE)  # Remove comments
    
    # Count words
    words = re.findall(r'\b\w+\b', clean)
    return len(words)


def count_words_by_section(text: str) -> List[SectionWordCount]:
    """
    Count words in each detected section.
    
    Args:
        text: Document text (LaTeX or Markdown)
        
    Returns:
        List of SectionWordCount objects
    """
    # Detect document type and sections
    if is_latex_document(text):
        sections = detect_sections_latex(text)
    else:
        sections = detect_sections_markdown(text)
    
    results = []
    
    for section_name, start, end in sections:
        section_text = text[start:end]
        word_count = count_words(section_text)
        
        # Get target range if known
        target = SECTION_WORD_TARGETS.get(section_name)
        if target:
            target_min, target_max = target
            if word_count < target_min:
                status = 'under'
            elif word_count > target_max:
                status = 'over'
            else:
                status = 'ok'
        else:
            # Unknown section, use reasonable defaults
            target_min, target_max = 0, 10000
            status = 'ok'
        
        results.append(SectionWordCount(
            section_name=section_name,
            word_count=word_count,
            target_min=target_min,
            target_max=target_max,
            status=status,
        ))
    
    return results


def estimate_page_count(word_count: int) -> float:
    """
    Estimate page count for double-spaced academic paper.
    
    Args:
        word_count: Total word count
        
    Returns:
        Estimated page count
    """
    return round(word_count / WORDS_PER_PAGE, 1)


def validate_word_counts(
    section_counts: List[SectionWordCount],
    total_words: int,
) -> Tuple[List[str], List[str]]:
    """
    Validate word counts against targets.
    
    Returns:
        Tuple of (issues, suggestions)
    """
    issues = []
    suggestions = []
    
    # Check section lengths
    for sc in section_counts:
        if sc.status == 'under':
            diff = sc.target_min - sc.word_count
            issues.append(
                f"{sc.section_name.title()}: {sc.word_count} words "
                f"(target: {sc.target_min}-{sc.target_max})"
            )
            suggestions.append(
                f"Expand {sc.section_name} by approximately {diff} words"
            )
        elif sc.status == 'over':
            diff = sc.word_count - sc.target_max
            issues.append(
                f"{sc.section_name.title()}: {sc.word_count} words "
                f"(target: {sc.target_min}-{sc.target_max})"
            )
            suggestions.append(
                f"Reduce {sc.section_name} by approximately {diff} words"
            )
    
    # Check total length
    min_total, max_total = TOTAL_WORD_TARGET
    if total_words < min_total:
        issues.append(f"Total word count ({total_words}) below target ({min_total})")
        suggestions.append(f"Add approximately {min_total - total_words} words")
    elif total_words > max_total:
        issues.append(f"Total word count ({total_words}) exceeds target ({max_total})")
        suggestions.append(f"Remove approximately {total_words - max_total} words")
    
    return issues, suggestions


# =============================================================================
# MAIN VALIDATION FUNCTION
# =============================================================================

def validate_style(
    text: str,
    check_words: bool = True,
    check_counts: bool = True,
    is_final_output: bool = True,
) -> StyleValidationResult:
    """
    Perform complete style validation on text.
    
    This is designed for final LaTeX output validation, not intermediate files.
    
    Args:
        text: Text to validate
        check_words: Check for banned words
        check_counts: Check word counts by section
        is_final_output: Whether this is final LaTeX output (affects validation strictness)
        
    Returns:
        StyleValidationResult with all findings
    """
    issues = []
    suggestions = []
    banned_matches = []
    section_counts = []
    total_words = count_words(text)
    estimated_pages = estimate_page_count(total_words)
    
    # Check banned words
    if check_words:
        banned_matches = check_banned_words(text)
        for bw in banned_matches:
            issues.append(f"Banned word '{bw.word}' found")
            if bw.replacements:
                suggestions.append(
                    f"Replace '{bw.word}' with: {', '.join(bw.replacements[:3])}"
                )
    
    # Check word counts (only for final output)
    if check_counts and is_final_output:
        section_counts = count_words_by_section(text)
        count_issues, count_suggestions = validate_word_counts(
            section_counts, total_words
        )
        issues.extend(count_issues)
        suggestions.extend(count_suggestions)
    
    # Determine overall validity
    # Banned words are flagged but don't invalidate (MAJOR, not CRITICAL)
    # Word count issues are warnings
    is_valid = len([i for i in issues if 'Banned word' not in i]) == 0
    
    return StyleValidationResult(
        is_valid=is_valid,
        banned_words=banned_matches,
        section_counts=section_counts,
        total_words=total_words,
        estimated_pages=estimated_pages,
        issues=issues,
        suggestions=suggestions,
    )


def suggest_replacement(text: str, word: str) -> Optional[str]:
    """
    Suggest a replacement for a banned word in context.
    
    Args:
        text: Full text containing the word
        word: Banned word to replace
        
    Returns:
        Suggested replacement text or None if no suggestion
    """
    replacements = BANNED_WORD_REPLACEMENTS.get(word.lower())
    if not replacements:
        return None
    
    # Return first replacement (most common/neutral option)
    return replacements[0]


def auto_replace_banned_words(text: str) -> Tuple[str, List[Tuple[str, str, str]]]:
    """
    Automatically replace banned words with suggestions.
    
    Args:
        text: Text to process
        
    Returns:
        Tuple of (modified_text, list of (original, replacement, context))
    """
    replacements_made = []
    result = text
    
    for word in BANNED_WORDS:
        if '-' in word:
            pattern = re.escape(word)
        else:
            pattern = r'\b' + re.escape(word) + r'\b'
        
        replacement = suggest_replacement(text, word)
        if not replacement:
            continue
        
        def replace_match(match):
            original = match.group(0)
            # Preserve case
            if original.isupper():
                return replacement.upper()
            elif original[0].isupper():
                return replacement.capitalize()
            return replacement
        
        # Find matches before replacing
        for match in re.finditer(pattern, result, re.IGNORECASE):
            start = max(0, match.start() - 30)
            end = min(len(result), match.end() + 30)
            context = result[start:end]
            replacements_made.append((match.group(0), replacement, context))
        
        # Perform replacement
        result = re.sub(pattern, replace_match, result, flags=re.IGNORECASE)
    
    return result, replacements_made
