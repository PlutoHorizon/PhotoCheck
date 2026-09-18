"""Test that save_cache auto-creates a single backup before overwriting."""

from datetime import datetime
from pathlib import Path

import pytest

from photocheck.core.cache import save_cache, load_cache
from photocheck.core.models import PhotoMetadata


def _meta(suffix: str) -> PhotoMetadata:
    return PhotoMetadata(
        file_path=Path(f"/test_{suffix}.ARW"),
        datetime_original=datetime(2024, 1, 1),
    )


class TestSaveCacheAutoBackup:
    def test_first_save_creates_no_backup(self, tmp_path):
        """First save: no existing cache, so no backup needed."""
        cache = tmp_path / "cache.parquet"
        save_cache([_meta("a")], cache)
        backup = tmp_path / "cache_backup.parquet"
        assert cache.exists()
        assert not backup.exists()

    def test_second_save_creates_backup(self, tmp_path):
        cache = tmp_path / "cache.parquet"
        backup = tmp_path / "cache_backup.parquet"

        save_cache([_meta("a")], cache)
        save_cache([_meta("a"), _meta("b")], cache)

        assert backup.exists()
        assert len(load_cache(cache)) == 2
        # Backup contains the PREVIOUS state (1 entry)
        assert len(load_cache(backup)) == 1

    def test_backup_always_single_file(self, tmp_path):
        """No accumulation: every save overwrites the same backup slot."""
        cache = tmp_path / "cache.parquet"
        backup = tmp_path / "cache_backup.parquet"
        save_cache([_meta("a")], cache)
        save_cache([_meta("a"), _meta("b")], cache)
        save_cache([_meta("a"), _meta("b"), _meta("c")], cache)
        save_cache([_meta("a")], cache)

        # Only 2 files in tmp_path (cache + backup)
        files = sorted(p.name for p in tmp_path.iterdir())
        assert files == ["cache.parquet", "cache_backup.parquet"]

        # Cache has 1 entry, backup has 3 (the previous state)
        assert len(load_cache(cache)) == 1
        assert len(load_cache(backup)) == 3
