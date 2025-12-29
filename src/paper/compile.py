"""Paper compilation functions for unified pipeline integration.

Extracted from scripts/run_paper_compile.py for programmatic use.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _issue(kind: str, message: str, *, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"kind": kind, "message": message}
    if details:
        out["details"] = details
    return out


def _tail_text(text: str, max_chars: int = 8000) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _run_cmd(cmd: List[str], *, cwd: Path, timeout_s: int = 900) -> Dict[str, Any]:
    """Run a shell command and capture output."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_s,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "cmd": cmd,
            "cwd": str(cwd),
            "stdout_tail": _tail_text(proc.stdout or ""),
            "stderr_tail": _tail_text(proc.stderr or ""),
        }
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, (bytes, bytearray)) else (e.stdout or "")
        stderr = e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, (bytes, bytearray)) else (e.stderr or "")
        return {
            "ok": False,
            "returncode": None,
            "cmd": cmd,
            "cwd": str(cwd),
            "timeout": True,
            "stdout_tail": _tail_text(stdout),
            "stderr_tail": _tail_text(stderr),
        }


def compile_paper(project_folder: Path, timeout_s: int = 900) -> Dict[str, Any]:
    """Compile the LaTeX paper.
    
    Args:
        project_folder: Project folder containing paper/main.tex
        timeout_s: Timeout for compilation in seconds
        
    Returns:
        Dict with success status, pdf_path, steps, and issues.
    """
    issues: List[Dict[str, Any]] = []
    
    if not project_folder.exists() or not project_folder.is_dir():
        return {
            "success": False,
            "pdf_path": None,
            "issues": [_issue("invalid_project_folder", "Project folder does not exist", details={"path": str(project_folder)})],
        }
    
    paper_dir = project_folder / "paper"
    main_tex = paper_dir / "main.tex"
    
    if not main_tex.exists():
        return {
            "success": False,
            "pdf_path": None,
            "issues": [_issue("missing_main_tex", "paper/main.tex does not exist", details={"path": str(main_tex)})],
        }
    
    logger.info(f"Compiling paper for: {project_folder}")
    
    # Find available tools
    latexmk = shutil.which("latexmk")
    pdflatex = shutil.which("pdflatex")
    bibtex = shutil.which("bibtex")
    
    build_dir = paper_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    steps: List[Dict[str, Any]] = []
    
    if latexmk:
        cmd = [
            latexmk,
            "-pdf",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-outdir=build",
            "main.tex",
        ]
        logger.info("Running latexmk")
        steps.append(_run_cmd(cmd, cwd=paper_dir, timeout_s=timeout_s))
    else:
        issues.append(_issue("latexmk_missing", "latexmk not found; falling back to pdflatex/bibtex"))
        if not pdflatex:
            issues.append(_issue("pdflatex_missing", "pdflatex not found; cannot compile"))
            return {
                "success": False,
                "pdf_path": None,
                "build_dir": str(build_dir),
                "steps": steps,
                "issues": issues,
            }
        
        logger.info("Running pdflatex (pass 1)")
        steps.append(_run_cmd([pdflatex, "-interaction=nonstopmode", "-halt-on-error", "-output-directory=build", "main.tex"], cwd=paper_dir, timeout_s=timeout_s))
        
        if bibtex:
            logger.info("Running bibtex")
            steps.append(_run_cmd([bibtex, "main"], cwd=build_dir, timeout_s=timeout_s))
        else:
            issues.append(_issue("bibtex_missing", "bibtex not found; bibliography may fail"))
        
        logger.info("Running pdflatex (pass 2)")
        steps.append(_run_cmd([pdflatex, "-interaction=nonstopmode", "-halt-on-error", "-output-directory=build", "main.tex"], cwd=paper_dir, timeout_s=timeout_s))
        
        logger.info("Running pdflatex (pass 3)")
        steps.append(_run_cmd([pdflatex, "-interaction=nonstopmode", "-halt-on-error", "-output-directory=build", "main.tex"], cwd=paper_dir, timeout_s=timeout_s))
    
    # Check compilation success
    ok = all(bool(s.get("ok")) for s in steps) if steps else False
    
    if not ok:
        issues.append(_issue("compile_failed", "LaTeX compilation failed", details={
            "steps": [{"cmd": s.get("cmd"), "returncode": s.get("returncode"), "timeout": s.get("timeout", False)} for s in steps]
        }))
    
    pdf_path = build_dir / "main.pdf"
    pdf_exists = pdf_path.exists()
    
    if ok and pdf_exists:
        logger.info(f"PDF generated: {pdf_path}")
    elif not pdf_exists:
        logger.warning("PDF was not generated")
        issues.append(_issue("pdf_not_generated", "PDF file was not generated", details={"expected_path": str(pdf_path)}))
    
    return {
        "success": ok and pdf_exists,
        "pdf_path": str(pdf_path) if pdf_exists else None,
        "build_dir": str(build_dir),
        "steps": steps,
        "issues": issues,
    }
