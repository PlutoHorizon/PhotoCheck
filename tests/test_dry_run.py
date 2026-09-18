"""Test the --dry-run flag on the scan command."""

import sys
from datetime import datetime
from pathlib import Path

import pytest

from photocheck.cli import get_cache_path, load_cache, scan_command
from photocheck.core.cache import save_cache
from photocheck.core.models import PhotoMetadata


def test_dry_run_does_not_write_cache(tmp_path, monkeypatch):

    # Use a tmp cache
    cache_file = tmp_path / "cache.parquet"
    monkeypatch.setattr("photocheck.cli.get_cache_path", lambda: cache_file)

    # Seed an existing cache with a known entry
    seed = [
        PhotoMetadata(
            file_path=Path("/old.ARW"),
            datetime_original=datetime(2024, 1, 1),
        )
    ]
    save_cache(seed, cache_file)
    before = load_cache(cache_file)
    assert len(before) == 1

    # Create a fake "scan target" with one new ARW
    scan_target = tmp_path / "photos"
    scan_target.mkdir()
    (scan_target / "new.ARW").write_bytes(b"II*\x00" + b"\x00" * 100)

    class Args:
        folder = str(scan_target)
        extensions = None
        crop_factor = 1.0
        workers = 1
        use_cache = True
        dry_run = True

    result = scan_command(Args())
    assert result == 0

    # Cache should be unchanged
    after = load_cache(cache_file)
    assert len(after) == 1
    assert after[0].file_path == Path("/old.ARW")
    # The new file must not have been added
    assert all(m.file_path != Path("/new.ARW") for m in after)


def test_dry_run_no_cache_file(tmp_path, monkeypatch):
    """--dry-run on a fresh setup (no existing cache) should still work."""
    cache_file = tmp_path / "cache.parquet"
    monkeypatch.setattr("photocheck.cli.get_cache_path", lambda: cache_file)
    assert not cache_file.exists()

    scan_target = tmp_path / "photos"
    scan_target.mkdir()
    (scan_target / "x.ARW").write_bytes(b"II*\x00" + b"\x00" * 100)

    class Args:
        folder = str(scan_target)
        extensions = None
        crop_factor = 1.0
        workers = 1
        use_cache = True
        dry_run = True

    result = scan_command(Args())
    assert result == 0
    # Cache should not be created
    assert not cache_file.exists()
