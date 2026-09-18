"""Tests for in-memory deduplication of PhotoMetadata."""

from datetime import datetime, timedelta
from pathlib import Path

from photocheck.core.models import PhotoMetadata
from photocheck.core.pairing import deduplicate_metadata_list


# Counter for unique datetime in default test metadata
_test_counter = [0]


def _m(path: str, dt=None, f=None, ss=None, focal=None, iso=None, error=None) -> PhotoMetadata:
    """Make a test PhotoMetadata. By default each call gets a unique
    datetime (1-second increments) so all photos are distinct unless
    the caller explicitly forces a duplicate signature.
    """
    if dt is None:
        _test_counter[0] += 1
        dt = datetime(2024, 1, 1, 12, 0, _test_counter[0])
    return PhotoMetadata(
        file_path=Path(path),
        datetime_original=dt,
        f_stop=f if f is not None else 2.8,
        shutter_speed=ss if ss is not None else 0.005,
        focal_length=focal if focal is not None else 35.0,
        iso=iso if iso is not None else 100,
        error=error,
    )


class TestDeduplicateMetadataList:
    def test_unique_records_kept_intact(self):
        """Each photo has unique EXIF (auto-generated datetime), all kept."""
        a = _m("/a/DSC00001.ARW")
        b = _m("/a/DSC00002.ARW")
        c = _m("/a/DSC00003.ARW")
        result = deduplicate_metadata_list([a, b, c])
        assert result == [a, b, c]

    def test_duplicate_signature_dropped(self):
        """Two photos with identical EXIF are deduped (first kept)."""
        common_dt = datetime(2024, 1, 1, 12, 0, 0)
        a = _m("/a/DSC00001.ARW", dt=common_dt, f=2.8, focal=35.0)
        b = _m("/a/DSC00001.ARW", dt=common_dt, f=2.8, focal=35.0)  # identical 5-tuple
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
        common_dt = datetime(2024, 1, 1, 12, 0, 0)
        a = _m("/a/DSC00001.ARW", dt=common_dt, focal=35.0, iso=100)
        b = _m("/b/DSC00001.ARW", dt=common_dt, focal=35.0, iso=100)
        c = _m("/c/DSC00001.ARW", dt=common_dt, focal=35.0, iso=100)
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

    def test_content_hash_catches_cross_format_duplicates(self):
        """Two photos with the same EXIF but different filenames AND
        different extensions (e.g., .ARW + .JPG of the same shot) are
        recognized as duplicates. The previous basename-grouped dedup
        would miss this if filenames differed.
        """
        common_dt = datetime(2024, 1, 1, 12, 0, 0)
        raw = _m("/photos/raw/DSC00001.ARW", dt=common_dt, f=2.8, focal=85.0)
        jpg = _m("/photos/edited/vacation_001.JPG", dt=common_dt, f=2.8, focal=85.0)
        result = deduplicate_metadata_list([raw, jpg])
        assert result == [raw]  # raw kept (first), jpg dropped

    def test_content_hash_o_n(self):
        """Verify dedup runs in linear time — no N² comparison."""
        import time
        n = 5000
        # All unique (datetime varies)
        items = [
            _m(f"/p/{i}.ARW", dt=datetime(2024, 1, 1) + timedelta(seconds=i))
            for i in range(n)
        ]
        t0 = time.perf_counter()
        result = deduplicate_metadata_list(items)
        elapsed = time.perf_counter() - t0
        assert len(result) == n
        # 5000 items should complete in well under a second on any modern machine.
        # If we had N² comparison, this would take 10+ seconds.
        assert elapsed < 2.0, f"dedup too slow: {elapsed:.2f}s for {n} items"

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
