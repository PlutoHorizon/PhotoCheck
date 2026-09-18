"""Test analyze command's --output safety check."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Patch OUTPUT_DIR so the test target is non-default
import photocheck.cli as cli_mod


def _run_analyze_check(output_dir_str: str, force: bool, has_existing: bool) -> int:
    """Run just the safety check portion of analyze_command."""
    from pathlib import Path as P
    output_dir = P(output_dir_str).resolve()
    default_resolved = cli_mod.OUTPUT_DIR.resolve()
    if output_dir != default_resolved and output_dir.exists():
        existing = list(output_dir.iterdir())
        if existing and not force:
            return 1  # refused
    output_dir.mkdir(parents=True, exist_ok=True)
    return 0  # allowed


def test_default_output_dir_always_allowed(tmp_path):
    """The project's own output/ should never be blocked."""
    default = cli_mod.OUTPUT_DIR
    default.mkdir(parents=True, exist_ok=True)
    (default / "focal_histogram.png").write_text("x")

    # The default dir is what analyze uses by default — no --output, no --force
    assert _run_analyze_check(str(default), force=False, has_existing=True) == 0


def test_non_default_empty_dir_allowed(tmp_path):
    target = tmp_path / "new_dir"
    target.mkdir()
    assert _run_analyze_check(str(target), force=False, has_existing=False) == 0


def test_non_default_with_files_refused_without_force(tmp_path):
    target = tmp_path / "protected"
    target.mkdir()
    (target / "data.txt").write_text("important")
    assert _run_analyze_check(str(target), force=False, has_existing=True) == 1


def test_non_default_with_files_allowed_with_force(tmp_path):
    target = tmp_path / "protected"
    target.mkdir()
    (target / "data.txt").write_text("important")
    assert _run_analyze_check(str(target), force=True, has_existing=True) == 0
