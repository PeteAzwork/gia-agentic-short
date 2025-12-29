"""Paper assembly functions for unified pipeline integration.

Extracted from scripts/run_paper_assembly.py for programmatic use.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from src.paper.artifacts_includes import generate_figures_include_tex, generate_tables_include_tex


_AUTOGEN_INPUT_BEGIN = "% === AUTOGEN: generated sections begin ==="
_AUTOGEN_INPUT_END = "% === AUTOGEN: generated sections end ==="
_AUTOGEN_DISABLE_BEGIN = "% === AUTOGEN: disable template sections begin ==="
_AUTOGEN_DISABLE_END = "% === AUTOGEN: disable template sections end ==="
_AUTOGEN_ARTIFACTS_BEGIN = "% === AUTOGEN: generated artifacts begin ==="
_AUTOGEN_ARTIFACTS_END = "% === AUTOGEN: generated artifacts end ==="


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _issue(kind: str, message: str, *, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"kind": kind, "message": message}
    if details:
        out["details"] = details
    return out


def discover_section_relpaths(project_folder: Path) -> List[str]:
    """Discover section .tex files in outputs/sections."""
    sections_dir = project_folder / "outputs" / "sections"
    if not sections_dir.exists() or not sections_dir.is_dir():
        return []

    paths: List[Path] = [p for p in sections_dir.glob("*.tex") if p.is_file() and not p.name.startswith(".")]

    preferred_order = [
        "introduction.tex",
        "related_work.tex",
        "methods.tex",
        "results.tex",
        "discussion.tex",
    ]
    preferred_rank = {name: idx for idx, name in enumerate(preferred_order)}

    def _sort_key(p: Path) -> tuple:
        return (preferred_rank.get(p.name, 999), p.name)

    rels: List[str] = []
    for p in sorted(paths, key=_sort_key):
        rels.append(str(p.relative_to(project_folder)))
    return rels


def write_generated_sections_tex(project_folder: Path, section_relpaths: List[str]) -> Tuple[Path, List[Dict[str, Any]]]:
    """Write generated_sections.tex include file."""
    issues: List[Dict[str, Any]] = []

    paper_dir = project_folder / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)

    out_path = paper_dir / "generated_sections.tex"

    if not section_relpaths:
        issues.append(
            _issue(
                "no_sections",
                "No generated section files found under outputs/sections",
                details={"expected_dir": str(project_folder / "outputs" / "sections")},
            )
        )

    lines: List[str] = []
    lines.append("% Generated section includes")
    lines.append("% This file is written by paper assembly")
    lines.append("")

    for rel in section_relpaths:
        rel_norm = rel.replace("\\", "/")
        input_path = "../" + rel_norm
        lines.append(f"% --- {rel_norm} ---")
        lines.append(f"\\input{{{input_path}}}")
        lines.append("")

    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return out_path, issues


def write_generated_tables_figures_tex(project_folder: Path) -> Tuple[Tuple[Path, Path], List[Dict[str, Any]]]:
    """Write generated_tables.tex and generated_figures.tex."""
    issues: List[Dict[str, Any]] = []

    paper_dir = project_folder / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)

    tables_path = paper_dir / "generated_tables.tex"
    figures_path = paper_dir / "generated_figures.tex"

    tables_tex, _table_labels = generate_tables_include_tex(project_folder)
    figures_tex, _figure_labels = generate_figures_include_tex(project_folder)

    tables_path.write_text(tables_tex, encoding="utf-8")
    figures_path.write_text(figures_tex, encoding="utf-8")

    return (tables_path, figures_path), issues


def inject_generated_sections_into_main(main_tex: str) -> Tuple[str, bool, Optional[str]]:
    """Inject autogen markers and includes into main.tex."""
    if _AUTOGEN_INPUT_BEGIN in main_tex and _AUTOGEN_DISABLE_BEGIN in main_tex and _AUTOGEN_ARTIFACTS_BEGIN in main_tex:
        return main_tex, False, None

    intro_marker = "%=============================================================================\n% 1. INTRODUCTION"
    refs_marker = "%=============================================================================\n% REFERENCES"

    intro_idx = main_tex.find(intro_marker)
    refs_idx = main_tex.find(refs_marker)

    if intro_idx == -1:
        return main_tex, False, "intro_marker_not_found"
    if refs_idx == -1:
        return main_tex, False, "refs_marker_not_found"

    before = main_tex[:intro_idx]
    template_sections = main_tex[intro_idx:refs_idx]
    after = main_tex[refs_idx:]

    new_tex = (
        before
        + f"\n{_AUTOGEN_INPUT_BEGIN}\n\\input{{generated_sections.tex}}\n{_AUTOGEN_INPUT_END}\n\n"
        + f"\n{_AUTOGEN_ARTIFACTS_BEGIN}\n\\input{{generated_tables.tex}}\n\\input{{generated_figures.tex}}\n{_AUTOGEN_ARTIFACTS_END}\n\n"
        + f"{_AUTOGEN_DISABLE_BEGIN}\n% Original template sections below (disabled):\n"
        + "% " + template_sections.replace("\n", "\n% ")
        + f"\n{_AUTOGEN_DISABLE_END}\n\n"
        + after
    )
    return new_tex, True, None


def assemble_paper(project_folder: Path) -> Dict[str, Any]:
    """Assemble paper sections and artifacts.
    
    Returns a result dict with success status, paths, and issues.
    """
    issues: List[Dict[str, Any]] = []
    
    if not project_folder.exists() or not project_folder.is_dir():
        return {
            "success": False,
            "issues": [_issue("invalid_project_folder", "Project folder does not exist", details={"path": str(project_folder)})],
        }
    
    logger.info(f"Assembling paper for: {project_folder}")
    
    # Discover and write section includes
    section_relpaths = discover_section_relpaths(project_folder)
    generated_path, gen_issues = write_generated_sections_tex(project_folder, section_relpaths)
    issues.extend(gen_issues)
    
    # Write table and figure includes
    (generated_tables_path, generated_figures_path), artifacts_issues = write_generated_tables_figures_tex(project_folder)
    issues.extend(artifacts_issues)
    
    # Check for main.tex
    paper_main_path = project_folder / "paper" / "main.tex"
    main_tex_updated = False
    
    if paper_main_path.exists():
        try:
            main_tex = paper_main_path.read_text(encoding="utf-8")
            new_tex, changed, error_code = inject_generated_sections_into_main(main_tex)
            
            if error_code:
                issues.append(_issue("main_tex_patch_failed", "Could not locate expected markers in paper/main.tex", details={"error": error_code}))
            
            if changed:
                paper_main_path.write_text(new_tex, encoding="utf-8")
                main_tex_updated = True
                logger.info("Updated paper/main.tex with generated sections")
        except Exception as e:
            issues.append(_issue("read_error", "Failed to read/write paper/main.tex", details={"error": f"{type(e).__name__}: {e}"}))
    else:
        issues.append(_issue("missing_paper_main", "paper/main.tex does not exist", details={"path": str(paper_main_path)}))
    
    # Determine success (can proceed even with warnings)
    blocking_issues = [i for i in issues if i["kind"] in ("invalid_project_folder", "missing_paper_main")]
    
    return {
        "success": len(blocking_issues) == 0,
        "generated_sections_tex": str(generated_path),
        "generated_tables_tex": str(generated_tables_path),
        "generated_figures_tex": str(generated_figures_path),
        "main_tex_updated": main_tex_updated,
        "section_relpaths": section_relpaths,
        "issues": issues,
    }
