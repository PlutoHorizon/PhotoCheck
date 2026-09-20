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

    def test_burst_mode_photos_not_deduped(self):
        """Burst-mode photos share EXIF but have different file numbers.
        They must be kept as distinct photos.
        """
        common_dt = datetime(2024, 1, 1, 12, 0, 0)
        a = _m("/a/DSC05898.ARW", dt=common_dt, f=2.8, focal=50.0, ss=0.001, iso=200)
        b = _m("/a/DSC05899.ARW", dt=common_dt, f=2.8, focal=50.0, ss=0.001, iso=200)
        c = _m("/a/DSC05900.ARW", dt=common_dt, f=2.8, focal=50.0, ss=0.001, iso=200)
        result = deduplicate_metadata_list([a, b, c])
        assert result == [a, b, c]  # all three kept (different file numbers)

    def test_arw_jpg_pair_with_same_number_deduped(self):
        """ARW + JPG of the same photo: same EXIF AND same file number.
        Must be deduped.
        """
        common_dt = datetime(2024, 1, 1, 12, 0, 0)
        raw = _m("/photos/raw/DSC05833.ARW", dt=common_dt, f=2.8, focal=85.0)
        jpg = _m("/photos/edited/DSC05833.JPG", dt=common_dt, f=2.8, focal=85.0)
        result = deduplicate_metadata_list([raw, jpg])
        assert result == [raw]

    def test_burst_mixed_with_pair_dedups_correctly(self):
        """Mixed scenario: burst photos + a JPG export of the first one.
        Burst photos stay distinct; JPG merges with the matching ARW.
        """
        common_dt = datetime(2024, 1, 1, 12, 0, 0)
        b1 = _m("/raw/DSC05833.ARW", dt=common_dt, f=2.8, focal=50.0)
        b2 = _m("/raw/DSC05834.ARW", dt=common_dt, f=2.8, focal=50.0)
        b3 = _m("/raw/DSC05835.ARW", dt=common_dt, f=2.8, focal=50.0)
        # JPG export of b1 (same stem, same EXIF, different format)
        jpg_b1 = _m("/jpg/DSC05833.JPG", dt=common_dt, f=2.8, focal=50.0)

        result = deduplicate_metadata_list([b1, b2, b3, jpg_b1])
        # b1 kept, b2 kept, b3 kept, jpg_b1 dropped (matches b1)
        assert len(result) == 3
        assert b1 in result
        assert b2 in result
        assert b3 in result
        assert jpg_b1 not in result

    def test_no_file_number_in_stem_uses_none(self):
        """Stems without trailing digits use None for file_number.
        Two such files with identical EXIF are treated as duplicates
        (no way to distinguish them without a number).
        """
        common_dt = datetime(2024, 1, 1, 12, 0, 0)
        a = _m("/photos/vacation_sunset.ARW", dt=common_dt, f=5.6, focal=24.0)
        b = _m("/photos/vacation_sunset.ARW", dt=common_dt, f=5.6, focal=24.0)
        result = deduplicate_metadata_list([a, b])
        assert result == [a]

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
