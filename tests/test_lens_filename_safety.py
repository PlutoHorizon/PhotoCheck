"""Tests for plot_lens_detail's lens-name → filename sanitization.

Lens names containing Windows-illegal characters (`\\ / : * ? " < > |`)
must be stripped before being used as a filename. Without sanitization,
Sigma lenses like "10-18mm F2.8 DC DN | Contemporary" make savefig
crash with `OSError: [Errno 22] Invalid argument` on Windows.
"""

from pathlib import Path

import pytest

from photocheck.core.models import PhotoMetadata
from photocheck.viz.histograms import plot_lens_detail


def _meta(path: str, lens: str, focal: float = 50.0) -> PhotoMetadata:
    return PhotoMetadata(
        file_path=Path(path),
        lens_name=lens,
        focal_length=focal,
    )


class TestLensFilenameSanitization:
    """plot_lens_detail must produce filenames that are valid on Windows."""

    def test_pipe_in_lens_name_does_not_crash(self, tmp_path):
        """Sigma lens with '|' must produce a sanitized filename."""
        lens = "10-18mm F2.8 DC DN | Contemporary"
        meta = [_meta("/a.ARW", lens, focal=14.0)]
        # Should not raise OSError Errno 22 (Windows-illegal char)
        plot_lens_detail(meta, str(tmp_path))

    def test_various_illegal_chars_replaced(self, tmp_path):
        """Each Windows-illegal char in a lens name must be replaced."""
        for ch in '\\/:*?"<>|':
            lens = f"Test{ch}Lens"
            meta = [_meta(f"/{ch}.ARW", lens, focal=50.0)]
            # Must complete without OSError
            plot_lens_detail(meta, str(tmp_path))

    def test_sanitized_file_exists(self, tmp_path):
        """After sanitization, the chart file must be created on disk."""
        lens = "FE 24-70mm F2.8 GM | II"
        meta = [_meta("/a.ARW", lens, focal=35.0)]
        plot_lens_detail(meta, str(tmp_path))

        # The pipe must have been replaced with '-' in the filename
        # (chart name is lens_<sanitized>_focal.png)
        created = list(tmp_path.glob("*.png"))
        assert created, "no chart file created"
        # No file should contain a pipe character in its name
        for f in created:
            assert "|" not in f.name, f"pipe leaked into filename: {f.name}"

    def test_legal_chars_preserved(self, tmp_path):
        """Sanitization must not affect legal filename characters."""
        lens = "FE 24-70mm F2.8 GM"
        meta = [_meta("/a.ARW", lens, focal=35.0)]
        plot_lens_detail(meta, str(tmp_path))

        # The lens name should appear (possibly truncated to 30 chars)
        created = list(tmp_path.glob("*.png"))
        assert created
        # Spaces and dashes should be preserved
        assert any("FE" in f.name and "24-70mm" in f.name for f in created)

    def test_long_lens_name_truncated_to_30(self, tmp_path):
        """Lens names longer than 30 chars get truncated before sanitization."""
        lens = "This is a very long lens name that exceeds thirty chars"
        meta = [_meta("/a.ARW", lens, focal=35.0)]
        plot_lens_detail(meta, str(tmp_path))
        created = list(tmp_path.glob("*.png"))
        assert created
        # lens_<filename>_focal.png — filename part is at most 30 chars
        for f in created:
            # Strip "lens_" prefix and "_focal.png" suffix to check stem
            stem = f.stem  # e.g. "lens_This is a very long lens_focal"
            inner = stem.replace("lens_", "").rsplit("_focal", 1)[0]
            assert len(inner) <= 30, f"filename stem too long: {inner!r}"