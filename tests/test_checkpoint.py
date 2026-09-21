"""Test that scan saves intermediate checkpoints and can resume after crash."""

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from photocheck.cli import scan_command
from photocheck.core.cache import load_cache, save_cache
from photocheck.core.models import PhotoMetadata
from photocheck.cli import get_cache_path


def _make_meta(suffix: str, ok: bool = True) -> PhotoMetadata:
    return PhotoMetadata(
        file_path=Path(f"/fake/{suffix}.ARW"),
        datetime_original=__import__("datetime").datetime(2024, 1, 1),
        error=None if ok else "fake error",
    )


class TestScanCheckpoint:
    """Verify that scan_command saves checkpoints during long extractions."""

    def test_checkpoint_saved_every_batch(self, tmp_path, monkeypatch):
        """Each batch of 5000 files triggers a save_cache call."""
        cache_file = tmp_path / "cache.parquet"
        monkeypatch.setattr("photocheck.cli.get_cache_path", lambda: cache_file)

        # Set up 12,000 fake files (3 batches)
        photos_dir = tmp_path / "photos"
        photos_dir.mkdir()
        file_paths = [photos_dir / f"f{i:06d}.ARW" for i in range(12000)]
        for p in file_paths:
            p.write_bytes(b"II*\x00" + b"\x00" * 100)

        # Mock _process_files to return synthetic records
        call_count = 0
        save_count = 0

        def fake_process(paths, crop_factor, workers):
            nonlocal call_count
            call_count += 1
            return [_make_meta(p.name) for p in paths]

        def counting_save(metadata, path):
            nonlocal save_count
            save_count += 1
            # Use real save_cache so cache file is actually written
            save_cache_orig(metadata, path)

        save_cache_orig = sys.modules["photocheck.cli"].save_cache

        class Args:
            folder = str(photos_dir)
            extensions = None
            crop_factor = 1.0
            workers = 1
            use_cache = True
            dry_run = False

        with patch("photocheck.cli._process_files", fake_process), \
             patch.object(sys.modules["photocheck.cli"], "save_cache", counting_save):
            result = scan_command(Args())

        assert result == 0
        # 12000 files / 5000 batch = 3 batches → 3 batch checkpoints + 1 final save = 4 total
        assert call_count == 3, f"expected 3 batches, got {call_count}"
        assert save_count == 4, f"expected 4 saves (3 batch + 1 final), got {save_count}"

    def test_resume_skips_already_processed(self, tmp_path, monkeypatch):
        """A second scan skips paths already in the cache (from a previous run)."""
        cache_file = tmp_path / "cache.parquet"
        monkeypatch.setattr("photocheck.cli.get_cache_path", lambda: cache_file)

        photos_dir = tmp_path / "photos"
        photos_dir.mkdir()
        # On disk: 5 files
        for i in range(5):
            (photos_dir / f"f{i:06d}.ARW").write_bytes(b"II*\x00" + b"\x00" * 100)

        # Pre-seed cache with 3 records (matching actual disk paths)
        already_done = [
            PhotoMetadata(file_path=photos_dir / f"f{i:06d}.ARW")
            for i in range(3)
        ]
        save_cache(already_done, cache_file)

        processed_paths = []

        def fake_process(paths, crop_factor, workers):
            processed_paths.extend(paths)
            return [PhotoMetadata(file_path=p) for p in paths]

        class Args:
            folder = str(photos_dir)
            extensions = None
            crop_factor = 1.0
            workers = 1
            use_cache = True
            dry_run = False

        with patch("photocheck.cli._process_files", fake_process):
            result = scan_command(Args())

        assert result == 0
        # Only 2 paths should be processed (the 3 already in cache are skipped)
        processed_names = {p.name for p in processed_paths}
        assert processed_names == {"f000003.ARW", "f000004.ARW"}, \
            f"unexpected processed: {processed_names}"

    def test_dry_run_does_not_checkpoint(self, tmp_path, monkeypatch):
        """--dry-run should never save the cache."""
        cache_file = tmp_path / "cache.parquet"
        monkeypatch.setattr("photocheck.cli.get_cache_path", lambda: cache_file)
        assert not cache_file.exists()

        photos_dir = tmp_path / "photos"
        photos_dir.mkdir()
        for i in range(10):
            (photos_dir / f"f{i:06d}.ARW").write_bytes(b"II*\x00" + b"\x00" * 100)

        def fake_process(paths, crop_factor, workers):
            return [_make_meta(p.name) for p in paths]

        class Args:
            folder = str(photos_dir)
            extensions = None
            crop_factor = 1.0
            workers = 1
            use_cache = True
            dry_run = True

        with patch("photocheck.cli._process_files", fake_process):
            result = scan_command(Args())

        assert result == 0
        # Cache file should not exist (dry-run never writes)
        assert not cache_file.exists()
