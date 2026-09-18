"""Tests for in-memory deduplication of PhotoMetadata."""

from datetime import datetime
from pathlib import Path

from photocheck.core.models import PhotoMetadata
from photocheck.core.pairing import deduplicate_metadata_list


def _m(path: str, dt=None, f=None, ss=None, focal=None, iso=None, error=None) -> PhotoMetadata:
    return PhotoMetadata(
        file_path=Path(path),
        datetime_original=dt or datetime(2024, 1, 1, 12, 0, 0),
        f_stop=f or 2.8,
        shutter_speed=ss or 0.005,
        focal_length=focal or 35.0,
        iso=iso or 100,
        error=error,
    )


class TestDeduplicateMetadataList:
    def test_unique_basenames_kept_intact(self):
        a = _m("/a/DSC00001.ARW")
        b = _m("/a/DSC00002.ARW")
        c = _m("/a/DSC00003.ARW")
        result = deduplicate_metadata_list([a, b, c])
        assert result == [a, b, c]

    def test_duplicate_signature_dropped(self):
        a = _m("/a/DSC00001.ARW", f=2.8, focal=35.0)
        b = _m("/a/DSC00001.ARW", f=2.8, focal=35.0)  # identical 5-tuple
        result = deduplicate_metadata_list([a, b])
        assert result == [a]

    def test_different_signatures_kept(self):
        a = _m("/a/DSC00001.ARW", f=2.8)
        b = _m("/a/DSC00001.ARW", f=4.0)  # different aperture
        result = deduplicate_metadata_list([a, b])
        assert result == [a, b]

    def test_different_paths_same_basename_kept(self):
        # Same stem across different dirs is grouped; if signatures differ, both kept
        a = _m("/folder1/DSC00001.ARW", focal=35.0)
        b = _m("/folder2/DSC00001.ARW", focal=85.0)
        result = deduplicate_metadata_list([a, b])
        assert result == [a, b]

    def test_error_records_kept_unchanged(self):
        # Files that failed EXIF read are kept (fail-open)
        a = _m("/a/DSC00001.ARW", error="EXIF read error")
        b = _m("/a/DSC00001.ARW", error="EXIF read error")
        result = deduplicate_metadata_list([a, b])
        # Both kept because we can't form a signature
        assert result == [a, b]

    def test_first_occurrence_wins(self):
        a = _m("/a/DSC00001.ARW", focal=35.0, iso=100)
        b = _m("/b/DSC00001.ARW", focal=35.0, iso=100)
        c = _m("/c/DSC00001.ARW", focal=35.0, iso=100)
        result = deduplicate_metadata_list([a, b, c])
        assert result == [a]

    def test_preserves_input_order(self):
        a = _m("/a/DSC00001.ARW")
        b = _m("/a/DSC00002.ARW")
        c = _m("/a/DSC00003.ARW")
        # Reverse input order
        result = deduplicate_metadata_list([c, a, b])
        assert [m.file_path for m in result] == [c.file_path, a.file_path, b.file_path]

    def test_empty_list(self):
        assert deduplicate_metadata_list([]) == []

    def test_does_not_read_exif(self, monkeypatch):
        """Critical: ensure no EXIF re-read happens inside dedup."""
        from photocheck.core import extractor

        read_count = 0
        original = extractor.piexif.load

        def counting_load(path):
            nonlocal read_count
            read_count += 1
            return original(path)

        monkeypatch.setattr(extractor.piexif, "load", counting_load)

        a = _m("/a/DSC00001.ARW")
        b = _m("/a/DSC00001.ARW")
        # Note: a and b are already-extracted; we pass them directly.
        # The function must NOT re-extract.
        deduplicate_metadata_list([a, b])
        assert read_count == 0, f"EXIF was read {read_count} times — should be 0"
