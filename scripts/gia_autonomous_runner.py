#!/usr/bin/env python3
"""GIA Autonomous Research Pipeline Runner.

A production-ready orchestrator for end-to-end autonomous execution of the
GIA Agentic Research Pipeline. Manages the complete lifecycle from cleanup
to final evaluation with comprehensive logging and graceful degradation.

Features:
- Pre-flight environment purge (pycache, temp, archive old outputs)
- Sequential phase execution with subprocess isolation (-I -B flags)
- Real-time log monitoring for ERROR, WARNING, CRITICAL, DEGRADATION
- Graceful degradation protocol (continue on non-critical failures)
- Post-run success matrix and readiness scoring

Usage:
    python scripts/gia_autonomous_runner.py <project_folder> [--dry-run] [--skip-purge]

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Tuple


# ==============================================================================
# CONSTANTS
# ==============================================================================

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
LOGS_DIR = ROOT_DIR / "logs"

# Phase definitions: (script_name, phase_id, description, is_critical)
PIPELINE_PHASES: List[Tuple[str, str, str, bool]] = [
    ("run_workflow.py", "phase_1", "Research Workflow (Intake)", True),
    ("run_literature_workflow.py", "phase_2", "Literature Workflow", False),
    ("run_gap_resolution.py", "phase_3", "Gap Resolution Workflow", False),
    ("run_writing_review_stage.py", "phase_4", "Writing Review Stage", False),
    ("run_paper_assembly.py", "phase_5a", "Paper Assembly", False),
    ("run_paper_compile.py", "phase_5b", "Paper Compilation", False),
]

# Keywords to monitor in subprocess output
MONITOR_KEYWORDS = {"ERROR", "WARNING", "CRITICAL", "DEGRADATION"}

# Default timeouts (seconds)
DEFAULT_PHASE_TIMEOUT = 3600  # 1 hour per phase


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class PhaseResult:
    """Result from executing a single pipeline phase."""
    phase_id: str
    phase_name: str
    success: bool
    exit_code: int
    execution_time: float
    degraded: bool = False
    degradation_reasons: List[str] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    critical_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "phase_name": self.phase_name,
            "success": self.success,
            "exit_code": self.exit_code,
            "execution_time": round(self.execution_time, 2),
            "degraded": self.degraded,
            "degradation_reasons": self.degradation_reasons,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "critical_count": self.critical_count,
        }


@dataclass
class PipelineResult:
    """Aggregate result from the entire pipeline run."""
    run_id: str
    project_folder: str
    started_at: str
    finished_at: str = ""
    total_execution_time: float = 0.0
    overall_success: bool = True
    phases: List[PhaseResult] = field(default_factory=list)
    evidence_items_count: int = 0
    readiness_score: float = 0.0
    degradation_summary: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_folder": self.project_folder,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_execution_time": round(self.total_execution_time, 2),
            "overall_success": self.overall_success,
            "phases": [p.to_dict() for p in self.phases],
            "evidence_items_count": self.evidence_items_count,
            "readiness_score": self.readiness_score,
            "degradation_summary": self.degradation_summary,
        }


# ==============================================================================
# LOGGING UTILITIES
# ==============================================================================

class DualLogger:
    """Logger that writes to both console and file with keyword monitoring."""

    def __init__(self, log_path: Path, remedy_path: Path):
        self.log_path = log_path
        self.remedy_path = remedy_path
        self.log_file: Optional[TextIO] = None
        self.remedy_file: Optional[TextIO] = None
        self._lock = threading.Lock()

        # Counters for keyword occurrences
        self.error_count = 0
        self.warning_count = 0
        self.critical_count = 0
        self.degradation_reasons: List[str] = []

    def __enter__(self) -> "DualLogger":
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file = open(self.log_path, "w", encoding="utf-8")
        self.remedy_file = open(self.remedy_path, "a", encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.log_file:
            self.log_file.close()
        if self.remedy_file:
            self.remedy_file.close()

    def write(self, message: str, *, console: bool = True, timestamp: bool = True):
        """Write message to log file and optionally console."""
        with self._lock:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if timestamp else ""
            line = f"[{ts}] {message}" if ts else message

            if self.log_file:
                self.log_file.write(line + "\n")
                self.log_file.flush()

            if console:
                print(line)

    def process_output_line(self, line: str, *, phase_id: str = ""):
        """Process a line of subprocess output, monitoring for keywords."""
        with self._lock:
            # Write to log file
            if self.log_file:
                self.log_file.write(line + "\n")
                self.log_file.flush()

            # Check for keywords
            upper_line = line.upper()

            if "ERROR" in upper_line:
                self.error_count += 1

            if "WARNING" in upper_line:
                self.warning_count += 1

            if "CRITICAL" in upper_line:
                self.critical_count += 1

            if "DEGRADATION" in upper_line or "DEGRADED" in upper_line:
                # Extract reason code if present
                reason = self._extract_degradation_reason(line)
                if reason:
                    self.degradation_reasons.append(f"[{phase_id}] {reason}")
                    if self.remedy_file:
                        self.remedy_file.write(f"{datetime.now(timezone.utc).isoformat()} | {phase_id} | {reason}\n")
                        self.remedy_file.flush()

    def _extract_degradation_reason(self, line: str) -> str:
        """Extract degradation reason code from log line."""
        # Pattern: reason_code="xxx" or reason_code: xxx or "reason_code": "xxx"
        patterns = [
            r'reason_code["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]+)',
            r'degradation.*?:\s*(.+?)(?:\.|$)',
            r'degraded.*?(?:due to|because|reason):\s*(.+?)(?:\.|$)',
        ]
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return line.strip()[:100]  # Fallback: first 100 chars

    def get_counts(self) -> Tuple[int, int, int]:
        """Return (error_count, warning_count, critical_count)."""
        with self._lock:
            return self.error_count, self.warning_count, self.critical_count

    def reset_counts(self):
        """Reset counters for a new phase."""
        with self._lock:
            self.error_count = 0
            self.warning_count = 0
            self.critical_count = 0


# ==============================================================================
# ENVIRONMENT PURGE
# ==============================================================================

def purge_pycache(root: Path, logger: DualLogger) -> int:
    """Recursively delete __pycache__ folders and .pyc files."""
    deleted_count = 0

    # Delete __pycache__ directories
    for pycache_dir in root.rglob("__pycache__"):
        if pycache_dir.is_dir():
            try:
                shutil.rmtree(pycache_dir)
                deleted_count += 1
            except OSError as e:
                logger.write(f"  WARNING: Could not delete {pycache_dir}: {e}")

    # Delete stray .pyc files
    for pyc_file in root.rglob("*.pyc"):
        if pyc_file.is_file():
            try:
                pyc_file.unlink()
                deleted_count += 1
            except OSError as e:
                logger.write(f"  WARNING: Could not delete {pyc_file}: {e}")

    return deleted_count


def clear_temp_directory(root: Path, logger: DualLogger) -> int:
    """Clear the temp/ directory contents."""
    temp_dir = root / "temp"
    if not temp_dir.exists():
        return 0

    deleted_count = 0
    for item in temp_dir.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            deleted_count += 1
        except OSError as e:
            logger.write(f"  WARNING: Could not delete {item}: {e}")

    return deleted_count


def archive_existing_outputs(project_folder: Path, logger: DualLogger) -> Optional[Path]:
    """Archive existing outputs folder if present."""
    outputs_dir = project_folder / "outputs"
    if not outputs_dir.exists() or not any(outputs_dir.iterdir()):
        return None

    # Create archive name with timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_name = f"outputs_archive_{timestamp}"
    archive_dir = project_folder / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / archive_name

    try:
        # Move outputs to archive
        shutil.move(str(outputs_dir), str(archive_path))
        # Recreate empty outputs directory
        outputs_dir.mkdir(parents=True, exist_ok=True)
        return archive_path
    except OSError as e:
        logger.write(f"  WARNING: Could not archive outputs: {e}")
        return None


def run_environment_purge(project_folder: Path, logger: DualLogger) -> Dict[str, Any]:
    """Execute the full pre-flight environment purge."""
    logger.write("=" * 60)
    logger.write("PRE-FLIGHT ENVIRONMENT PURGE")
    logger.write("=" * 60)

    result = {
        "pycache_deleted": 0,
        "temp_cleared": 0,
        "outputs_archived": None,
    }

    # 1. Purge pycache from both root and project
    logger.write("Step 1: Purging __pycache__ and .pyc files...")
    result["pycache_deleted"] = purge_pycache(ROOT_DIR, logger)
    result["pycache_deleted"] += purge_pycache(project_folder, logger)
    logger.write(f"  Deleted {result['pycache_deleted']} pycache items")

    # 2. Clear temp directory
    logger.write("Step 2: Clearing temp/ directory...")
    result["temp_cleared"] = clear_temp_directory(ROOT_DIR, logger)
    logger.write(f"  Cleared {result['temp_cleared']} temp items")

    # 3. Archive existing outputs
    logger.write("Step 3: Archiving existing outputs...")
    archive_path = archive_existing_outputs(project_folder, logger)
    if archive_path:
        result["outputs_archived"] = str(archive_path)
        logger.write(f"  Archived to: {archive_path}")
    else:
        logger.write("  No outputs to archive (Day Zero state)")

    logger.write("Environment purge complete.")
    logger.write("")

    return result


# ==============================================================================
# SUBPROCESS EXECUTION
# ==============================================================================

def stream_subprocess_output(
    process: subprocess.Popen,
    logger: DualLogger,
    phase_id: str,
) -> None:
    """Stream subprocess output to logger in real-time."""
    if process.stdout is None:
        return

    for line in iter(process.stdout.readline, ""):
        if not line:
            break
        line = line.rstrip("\n\r")
        logger.process_output_line(line, phase_id=phase_id)


def execute_phase(
    script_name: str,
    phase_id: str,
    phase_name: str,
    project_folder: Path,
    logger: DualLogger,
    timeout: int = DEFAULT_PHASE_TIMEOUT,
) -> PhaseResult:
    """Execute a single pipeline phase with monitoring."""
    script_path = SCRIPTS_DIR / script_name

    if not script_path.exists():
        logger.write(f"ERROR: Script not found: {script_path}")
        return PhaseResult(
            phase_id=phase_id,
            phase_name=phase_name,
            success=False,
            exit_code=-1,
            execution_time=0.0,
            error_count=1,
        )

    logger.write("-" * 60)
    logger.write(f"PHASE: {phase_id.upper()} - {phase_name}")
    logger.write(f"Script: {script_name}")
    logger.write("-" * 60)

    # Reset counters for this phase
    logger.reset_counts()

    start_time = time.time()

    try:
        # Build command with isolation flags
        cmd = [
            sys.executable,
            "-I",  # Isolated mode (no PYTHONPATH, no user site)
            "-B",  # Don't write .pyc files
            str(script_path),
            str(project_folder),
        ]

        # Execute with output streaming
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT_DIR),
            env=_build_subprocess_env(),
        )

        # Stream output in real-time
        stream_subprocess_output(process, logger, phase_id)

        # Wait for completion
        exit_code = process.wait(timeout=timeout)

        execution_time = time.time() - start_time
        error_count, warning_count, critical_count = logger.get_counts()

        success = exit_code == 0
        degraded = len(logger.degradation_reasons) > 0 or (not success and error_count > 0)

        result = PhaseResult(
            phase_id=phase_id,
            phase_name=phase_name,
            success=success,
            exit_code=exit_code,
            execution_time=execution_time,
            degraded=degraded,
            degradation_reasons=list(logger.degradation_reasons),
            error_count=error_count,
            warning_count=warning_count,
            critical_count=critical_count,
        )

        # Log phase summary
        status = "SUCCESS" if success else ("DEGRADED" if degraded else "FAILED")
        logger.write(f"\n{phase_id.upper()} Status: {status}")
        logger.write(f"  Exit Code: {exit_code}")
        logger.write(f"  Execution Time: {execution_time:.2f}s")
        logger.write(f"  Errors: {error_count}, Warnings: {warning_count}, Critical: {critical_count}")
        if degraded and logger.degradation_reasons:
            logger.write(f"  Degradation Reasons: {len(logger.degradation_reasons)}")
        logger.write("")

        # Clear degradation reasons for next phase
        logger.degradation_reasons = []

        return result

    except subprocess.TimeoutExpired:
        process.kill()
        execution_time = time.time() - start_time
        logger.write(f"ERROR: Phase {phase_id} timed out after {timeout}s")
        return PhaseResult(
            phase_id=phase_id,
            phase_name=phase_name,
            success=False,
            exit_code=-1,
            execution_time=execution_time,
            error_count=1,
        )

    except Exception as e:
        execution_time = time.time() - start_time
        logger.write(f"ERROR: Phase {phase_id} failed with exception: {e}")
        return PhaseResult(
            phase_id=phase_id,
            phase_name=phase_name,
            success=False,
            exit_code=-1,
            execution_time=execution_time,
            error_count=1,
        )


def _build_subprocess_env() -> Dict[str, str]:
    """Build a minimal environment for subprocess execution."""
    # Inherit minimal env vars needed for Python to run
    base_allowlist = {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TMPDIR",
        "TEMP",
        "TMP",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        # Allow API keys for LLM calls
        "ANTHROPIC_API_KEY",
        "EDISON_API_KEY",
        "OPENAI_API_KEY",
    }

    env: Dict[str, str] = {}
    for key in base_allowlist:
        value = os.environ.get(key)
        if value is not None:
            env[key] = value

    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"

    return env


# ==============================================================================
# POST-RUN EVALUATION
# ==============================================================================

def count_evidence_items(project_folder: Path) -> int:
    """Count evidence items in sources/*/evidence.json."""
    sources_dir = project_folder / "sources"
    if not sources_dir.exists():
        return 0

    total = 0
    for evidence_file in sources_dir.glob("*/evidence.json"):
        try:
            data = json.loads(evidence_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                total += len(data)
        except (OSError, json.JSONDecodeError):
            continue

    return total


def get_readiness_score(project_folder: Path) -> float:
    """Extract readiness score from assessment reports."""
    # Try readiness_report.json first
    readiness_path = project_folder / "readiness_report.json"
    if readiness_path.exists():
        try:
            data = json.loads(readiness_path.read_text(encoding="utf-8"))
            score = data.get("readiness", {}).get("overall_score")
            if score is not None:
                return float(score)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    # Try assessment_report.json
    assessment_path = project_folder / "assessment_report.json"
    if assessment_path.exists():
        try:
            data = json.loads(assessment_path.read_text(encoding="utf-8"))
            score = data.get("readiness", {}).get("overall_score")
            if score is not None:
                return float(score)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    # Try full_pipeline_context.json
    context_path = project_folder / "full_pipeline_context.json"
    if context_path.exists():
        try:
            data = json.loads(context_path.read_text(encoding="utf-8"))
            # Look in phase results
            for phase_key, phase_data in data.get("phase_results", {}).items():
                if isinstance(phase_data, dict):
                    agents = phase_data.get("agents", {})
                    ra = agents.get("readiness_assessment", {})
                    if isinstance(ra, dict):
                        score = ra.get("structured_data", {}).get("overall_score")
                        if score is not None:
                            return float(score)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    return 0.0


def print_success_matrix(result: PipelineResult):
    """Print the step-by-step success matrix to console."""
    print("\n")
    print("=" * 70)
    print("              GIA AUTONOMOUS RUNNER - SUCCESS MATRIX")
    print("=" * 70)
    print(f"Run ID:          {result.run_id}")
    print(f"Project:         {result.project_folder}")
    print(f"Started:         {result.started_at}")
    print(f"Finished:        {result.finished_at}")
    print(f"Total Time:      {result.total_execution_time:.2f}s")
    print("-" * 70)

    # Phase summary table
    print(f"{'Phase':<12} {'Status':<10} {'Time (s)':<10} {'Errors':<8} {'Warnings':<10}")
    print("-" * 70)

    for phase in result.phases:
        if phase.success:
            status = "SUCCESS" if not phase.degraded else "DEGRADED"
        else:
            status = "FAILED"

        status_color = ""
        if status == "SUCCESS":
            status_color = "\033[92m"  # Green
        elif status == "DEGRADED":
            status_color = "\033[93m"  # Yellow
        else:
            status_color = "\033[91m"  # Red
        reset_color = "\033[0m"

        print(
            f"{phase.phase_id:<12} "
            f"{status_color}{status:<10}{reset_color} "
            f"{phase.execution_time:<10.2f} "
            f"{phase.error_count:<8} "
            f"{phase.warning_count:<10}"
        )

    print("-" * 70)

    # Summary metrics
    print(f"\nEvidence Items Extracted: {result.evidence_items_count}")
    print(f"Final Readiness Score:    {result.readiness_score:.1%}")

    # Overall status
    overall_status = "SUCCESS" if result.overall_success else "DEGRADED" if any(p.degraded for p in result.phases) else "FAILED"
    if overall_status == "SUCCESS":
        print(f"\n\033[92m{'=' * 70}\033[0m")
        print(f"\033[92m          PIPELINE COMPLETED SUCCESSFULLY\033[0m")
    elif overall_status == "DEGRADED":
        print(f"\n\033[93m{'=' * 70}\033[0m")
        print(f"\033[93m          PIPELINE COMPLETED WITH DEGRADATION\033[0m")
    else:
        print(f"\n\033[91m{'=' * 70}\033[0m")
        print(f"\033[91m          PIPELINE FAILED\033[0m")

    print("=" * 70)

    # Degradation summary
    if result.degradation_summary:
        print("\nDEGRADATION SUMMARY:")
        for reason in result.degradation_summary[:10]:
            print(f"  - {reason}")
        if len(result.degradation_summary) > 10:
            print(f"  ... and {len(result.degradation_summary) - 10} more (see REMEDY_LIST.txt)")

    print("")


# ==============================================================================
# MAIN ORCHESTRATOR
# ==============================================================================

def run_autonomous_pipeline(
    project_folder: Path,
    *,
    skip_purge: bool = False,
    dry_run: bool = False,
) -> PipelineResult:
    """Run the complete GIA autonomous pipeline."""
    # Generate run ID and timestamps
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    started_at = datetime.now(timezone.utc).isoformat()

    # Setup log files
    log_path = LOGS_DIR / f"AUTONOMOUS_RUN_{run_id}.log"
    remedy_path = LOGS_DIR / "REMEDY_LIST.txt"

    # Initialize result
    pipeline_result = PipelineResult(
        run_id=run_id,
        project_folder=str(project_folder),
        started_at=started_at,
    )

    with DualLogger(log_path, remedy_path) as logger:
        logger.write("=" * 70)
        logger.write("          GIA AUTONOMOUS RESEARCH PIPELINE RUNNER")
        logger.write("=" * 70)
        logger.write(f"Run ID:          {run_id}")
        logger.write(f"Project Folder:  {project_folder}")
        logger.write(f"Started:         {started_at}")
        logger.write(f"Log File:        {log_path}")
        logger.write(f"Dry Run:         {dry_run}")
        logger.write("")

        # Validate project folder
        if not project_folder.exists():
            logger.write(f"ERROR: Project folder does not exist: {project_folder}")
            pipeline_result.overall_success = False
            return pipeline_result

        # Pre-flight environment purge
        if not skip_purge:
            run_environment_purge(project_folder, logger)
        else:
            logger.write("Skipping environment purge (--skip-purge)")
            logger.write("")

        # Dry run check
        if dry_run:
            logger.write("DRY RUN: Would execute the following phases:")
            for script, phase_id, phase_name, is_critical in PIPELINE_PHASES:
                logger.write(f"  - {phase_id}: {phase_name} ({script})")
            logger.write("\nDry run complete. No phases executed.")
            pipeline_result.finished_at = datetime.now(timezone.utc).isoformat()
            return pipeline_result

        # Execute phases sequentially
        total_start = time.time()

        for script_name, phase_id, phase_name, is_critical in PIPELINE_PHASES:
            phase_result = execute_phase(
                script_name=script_name,
                phase_id=phase_id,
                phase_name=phase_name,
                project_folder=project_folder,
                logger=logger,
            )

            pipeline_result.phases.append(phase_result)
            pipeline_result.degradation_summary.extend(phase_result.degradation_reasons)

            # Check for critical phase failure
            if not phase_result.success and is_critical:
                logger.write(f"\nCRITICAL: Phase {phase_id} ({phase_name}) failed.")
                logger.write("Pipeline cannot continue without this foundation.")
                pipeline_result.overall_success = False
                break

            # Update overall success (but continue on non-critical failures)
            if not phase_result.success and not phase_result.degraded:
                pipeline_result.overall_success = False

        # Calculate totals
        pipeline_result.total_execution_time = time.time() - total_start
        pipeline_result.finished_at = datetime.now(timezone.utc).isoformat()

        # Post-run evaluation
        logger.write("=" * 60)
        logger.write("POST-RUN EVALUATION")
        logger.write("=" * 60)

        pipeline_result.evidence_items_count = count_evidence_items(project_folder)
        logger.write(f"Evidence Items: {pipeline_result.evidence_items_count}")

        pipeline_result.readiness_score = get_readiness_score(project_folder)
        logger.write(f"Readiness Score: {pipeline_result.readiness_score:.1%}")

        # Determine overall success
        successful_phases = sum(1 for p in pipeline_result.phases if p.success)
        total_phases = len(pipeline_result.phases)
        degraded_phases = sum(1 for p in pipeline_result.phases if p.degraded)

        if successful_phases == total_phases and degraded_phases == 0:
            pipeline_result.overall_success = True
        elif successful_phases > 0:
            # At least some phases succeeded; consider it partial success
            pipeline_result.overall_success = successful_phases >= (total_phases // 2)

        logger.write(f"\nPhases Completed: {successful_phases}/{total_phases}")
        logger.write(f"Degraded Phases: {degraded_phases}")
        logger.write(f"Overall Success: {pipeline_result.overall_success}")

        # Write result to JSON
        result_path = project_folder / "autonomous_run_result.json"
        try:
            result_path.write_text(
                json.dumps(pipeline_result.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            logger.write(f"\nResults written to: {result_path}")
        except OSError as e:
            logger.write(f"WARNING: Could not write results: {e}")

        logger.write("")
        logger.write("=" * 70)
        logger.write("          AUTONOMOUS RUN COMPLETE")
        logger.write("=" * 70)

    # Print success matrix to console
    print_success_matrix(pipeline_result)

    return pipeline_result


# ==============================================================================
# CLI ENTRYPOINT
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="GIA Autonomous Research Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/gia_autonomous_runner.py /path/to/project
  python scripts/gia_autonomous_runner.py /path/to/project --dry-run
  python scripts/gia_autonomous_runner.py /path/to/project --skip-purge

For more information, see: https://giatenica.com
        """,
    )

    parser.add_argument(
        "project_folder",
        type=str,
        help="Path to the project folder containing research data",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without running phases",
    )

    parser.add_argument(
        "--skip-purge",
        action="store_true",
        help="Skip the pre-flight environment purge",
    )

    args = parser.parse_args()

    # Resolve project folder path
    project_folder = Path(args.project_folder).expanduser().resolve()

    # Run the pipeline
    result = run_autonomous_pipeline(
        project_folder,
        skip_purge=args.skip_purge,
        dry_run=args.dry_run,
    )

    # Exit with appropriate code
    sys.exit(0 if result.overall_success else 1)


if __name__ == "__main__":
    main()
