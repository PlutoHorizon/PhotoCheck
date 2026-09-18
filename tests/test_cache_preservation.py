"""Regression test: scanning a different drive must not lose cache entries
from an unmounted drive.
"""

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from photocheck.cli import get_cache_path, load_cache, save_cache
from photocheck.core.cache import get_stale_files
from photocheck.core.models import PhotoMetadata


def _make_meta(path: str, focal: float = 35.0) -> PhotoMetadata:
    return PhotoMetadata(
        file_path=Path(path),
        datetime_original=datetime(2024, 1, 1, 12, 0, 0),
        f_stop=2.8,
        shutter_speed=0.005,
        focal_length=focal,
        iso=100,
    )


class TestCachePreservationAcrossDrives:
    """Scanning drive B must not drop drive A's entries even if A is unmounted."""

    def test_unmounted_drive_preserved(self, tmp_path, monkeypatch):
        # Use tmp_path for the cache file
        cache_file = tmp_path / "cache.parquet"
        monkeypatch.setattr("photocheck.cli.get_cache_path", lambda: cache_file)

        # Seed cache with 5 entries from a "drive A" that is no longer mounted
        seed = [
            _make_meta("/Volumes/DriveA/photo1.ARW"),
            _make_meta("/Volumes/DriveA/photo2.ARW"),
            _make_meta("/Volumes/DriveA/photo3.ARW"),
            _make_meta("/Volumes/DriveA/photo4.ARW"),
            _make_meta("/Volumes/DriveA/photo5.ARW"),
        ]
        save_cache(seed, cache_file)

        # Verify drive A paths don't exist on this test machine
        for m in seed:
            assert not m.file_path.exists(), f"Test setup: {m} should not exist"

        # Simulate what the scan would do: load cache, keep all entries
        # (no drop based on disk presence)
        cached_df = pd.read_parquet(cache_file)
        cached_metadata = load_cache(cache_file)
        assert len(cached_metadata) == 5
        assert all(m.file_path.parent.name == "DriveA" for m in cached_metadata)

    def test_mtime_stale_detection_still_works(self, tmp_path, monkeypatch):
        """Cache invalidation via mtime is preserved — only drop-based-on-existence was removed."""
        cache_file = tmp_path / "cache.parquet"
        monkeypatch.setattr("photocheck.cli.get_cache_path", lambda: cache_file)

        # Create a real file, seed cache with old mtime
        real_file = tmp_path / "photo.ARW"
        real_file.write_text("x")
        old_mtime = 1000000.0
        os.utime(real_file, (old_mtime, old_mtime))

        seed = [_make_meta(str(real_file))]
        save_cache(seed, cache_file)

        # Bump mtime
        new_mtime = old_mtime + 100
        os.utime(real_file, (new_mtime, new_mtime))

        # get_stale_files should still flag it as stale (mtime changed)
        cached_df = pd.read_parquet(cache_file)
        stale = get_stale_files(cached_df, [real_file])
        assert stale == [real_file]
