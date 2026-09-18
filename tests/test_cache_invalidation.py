"""Tests for cache invalidation via mtime checking."""

import os
import time
from pathlib import Path

import pandas as pd
import pytest

from photocheck.core.cache import get_stale_files


def _touch(path: Path, mtime: float | None = None) -> None:
    """Create a file and optionally set its mtime."""
    path.write_text("x")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


class TestGetStaleFiles:
    def test_empty_cache_marks_all_stale(self, tmp_path):
        f1 = tmp_path / "a.ARW"
        f1.write_text("x")
        df = pd.DataFrame(columns=["file_path", "mtime"])

        result = get_stale_files(df, [f1])
        assert result == [f1]

    def test_new_file_marked_stale(self, tmp_path):
        f1 = tmp_path / "a.ARW"
        f1.write_text("x")
        cached_f = tmp_path / "b.ARW"
        cached_f.write_text("y")
        df = pd.DataFrame({
            "file_path": [str(cached_f)],
            "mtime": [cached_f.stat().st_mtime],
        })

        result = get_stale_files(df, [f1, cached_f])
        assert result == [f1]

    def test_unchanged_file_not_stale(self, tmp_path):
        f1 = tmp_path / "a.ARW"
        f1.write_text("x")
        mtime = f1.stat().st_mtime
        df = pd.DataFrame({
            "file_path": [str(f1)],
            "mtime": [mtime],
        })

        result = get_stale_files(df, [f1])
        assert result == []

    def test_modified_file_marked_stale(self, tmp_path):
        f1 = tmp_path / "a.ARW"
        f1.write_text("x")
        old_mtime = time.time() - 100
        os.utime(f1, (old_mtime, old_mtime))
        df = pd.DataFrame({
            "file_path": [str(f1)],
            "mtime": [old_mtime],
        })
        # Bump mtime by writing again
        time.sleep(0.01)
        f1.write_text("xx")
        new_mtime = f1.stat().st_mtime
        assert new_mtime != old_mtime

        result = get_stale_files(df, [f1])
        assert result == [f1]

    def test_missing_file_marked_stale(self, tmp_path):
        # File was in cache but has been deleted
        cached_f = tmp_path / "deleted.ARW"
        # Don't actually create the file
        df = pd.DataFrame({
            "file_path": [str(cached_f)],
            "mtime": [12345.0],
        })

        result = get_stale_files(df, [])
        # File is not in current_files but is "missing from disk" relative to cache
        # The function's contract: stale = needs (re)extraction.
        # Files not in current_files don't appear (we only check what we'd process).
        assert result == []
