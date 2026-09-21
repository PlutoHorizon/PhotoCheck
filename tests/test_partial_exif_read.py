"""Tests for the partial header read optimization in the extractor.

EXIF lives in the file head — typically < 64 KB. Reading the whole 30-50 MB
RAW file wastes ~99.7% of I/O. We try the first 256 KB first; if piexif
fails or returns nothing, we fall back to the full read.
"""

import struct
from pathlib import Path
from unittest.mock import patch

import piexif
import pytest

from photocheck.core.extractor import (
    EXIF_HEADER_BYTES,
    _read_exif_bytes,
    extract_metadata,
)


# A real 256 KB ARW header saved from a Sony a7C II .ARW file.
# Contains all the tags we read: Make, Model, FocalLength, ISO, LensModel,
# DateTimeOriginal. Used to build large synthetic files for the partial-read
# path without depending on user file layout.
FIXTURES = Path(__file__).resolve().parent / "fixtures"
ARW_HEADER_PATH = FIXTURES / "arw_header_256k.bin"


def _make_large_arw(tmp_path: Path, name: str = "test.ARW") -> Path:
    """Write a file larger than EXIF_HEADER_BYTES using a real ARW header.

    The header is the first 256 KB of a real Sony ARW file (parsed by piexif
    to verify all our target tags live within those bytes). The tail is
    zero-padded so the file is big enough to trigger the partial-read path.
    """
    arw = tmp_path / name
    header = ARW_HEADER_PATH.read_bytes()
    tail = b"\x00" * (EXIF_HEADER_BYTES + 1000)
    arw.write_bytes(header + tail)
    return arw


class TestReadExifBytes:
    def test_returns_none_for_small_file(self, tmp_path):
        """Files smaller than EXIF_HEADER_BYTES get None (use path read)."""
        f = tmp_path / "small.ARW"
        f.write_bytes(b"II*\x00" + b"\x00" * 100)  # 104 bytes
        assert _read_exif_bytes(f) is None

    def test_returns_header_for_large_file(self, tmp_path):
        """Files larger than EXIF_HEADER_BYTES return the first 256 KB."""
        f = tmp_path / "big.ARW"
        header = b"II*\x00" + b"\x01" * (EXIF_HEADER_BYTES - 4)
        tail = b"\x02" * (1024 * 1024 - EXIF_HEADER_BYTES)
        f.write_bytes(header + tail)

        head = _read_exif_bytes(f)
        assert head is not None
        assert len(head) == EXIF_HEADER_BYTES
        assert head[:4] == b"II*\x00"
        assert head[-1] == 0x01  # last byte of header (not tail)

    def test_returns_none_if_stat_fails(self, tmp_path):
        """If we can't stat the file, return None to use path-based fallback."""
        nonexistent = tmp_path / "missing.ARW"
        assert _read_exif_bytes(nonexistent) is None


class TestExtractMetadataPartialRead:
    def test_partial_read_produces_correct_data(self, tmp_path):
        """Partial header read on a real ARW should give full EXIF data."""
        if not ARW_HEADER_PATH.exists():
            pytest.skip(f"ARW header fixture missing: {ARW_HEADER_PATH}")
        arw = _make_large_arw(tmp_path)

        result = extract_metadata(arw)

        assert result.error is None, f"unexpected error: {result.error}"
        assert result.camera_make == "SONY"
        assert result.camera_model == "ILCE-7CM2"
        assert result.lens_name == "FE 200-600mm F5.6-6.3 G OSS"
        assert result.iso == 250
        # FocalLengthIn35mmFilm (0xA405) = 600 takes precedence over raw
        # FocalLength (0xA432) which has multiple values
        assert result.focal_length == 600.0

    def test_small_file_uses_full_read(self, tmp_path):
        """A file smaller than the header threshold uses the full-read path."""
        if not ARW_HEADER_PATH.exists():
            pytest.skip(f"ARW header fixture missing: {ARW_HEADER_PATH}")
        # Just the 256KB header — file size == EXIF_HEADER_BYTES, no partial
        small = tmp_path / "tiny.ARW"
        small.write_bytes(ARW_HEADER_PATH.read_bytes())

        result = extract_metadata(small)
        assert result.error is None
        assert result.camera_make == "SONY"

    def test_fallback_when_partial_read_returns_none(self, tmp_path):
        """If _read_exif_bytes returns None, fall back to full file read.

        The result should still be correct — this is the small-file or
        stat-failure path.
        """
        if not ARW_HEADER_PATH.exists():
            pytest.skip(f"ARW header fixture missing: {ARW_HEADER_PATH}")
        arw = _make_large_arw(tmp_path)

        with patch(
            "photocheck.core.extractor._read_exif_bytes", return_value=None
        ):
            result = extract_metadata(arw)

        assert result.error is None
        assert result.camera_make == "SONY"
        assert result.lens_name == "FE 200-600mm F5.6-6.3 G OSS"

    def test_fallback_when_partial_read_returns_empty(self, tmp_path):
        """piexif may return an empty dict when the JPEG APP1 marker is
        beyond our buffer. We must fall back to full read in that case.
        """
        if not ARW_HEADER_PATH.exists():
            pytest.skip(f"ARW header fixture missing: {ARW_HEADER_PATH}")
        arw = _make_large_arw(tmp_path)

        empty = {
            "0th": {}, "Exif": {}, "GPS": {},
            "Interop": {}, "1st": {}, "thumbnail": None,
        }
        # First call (partial read on bytes) returns empty;
        # second call (fallback with path string) returns the real dict.
        real = piexif.load(str(arw))  # noqa: F821  — uses real piexif here

        call_log = []

        def selective_load(source):
            call_log.append(source)
            if isinstance(source, bytes):
                return empty
            return real

        with patch(
            "photocheck.core.extractor._read_exif_bytes",
            return_value=b"fake head",
        ), patch(
            "photocheck.core.extractor.piexif.load",
            side_effect=selective_load,
        ):
            result = extract_metadata(arw)

        # Two calls: partial (bytes) + fallback (path string)
        assert len(call_log) == 2
        assert result.error is None
        assert result.camera_make == "SONY"

    def test_fallback_when_piexif_raises_struct_error(self, tmp_path):
        """piexif raises struct.error when IFD offset is past our buffer.
        The fallback to full file read should still succeed.
        """
        if not ARW_HEADER_PATH.exists():
            pytest.skip(f"ARW header fixture missing: {ARW_HEADER_PATH}")
        arw = _make_large_arw(tmp_path)

        real = piexif.load(str(arw))  # noqa: F821  — uses real piexif here
        call_log = []

        def selective_load(source):
            call_log.append(source)
            if isinstance(source, bytes):
                raise struct.error("unpack requires a buffer of 4 bytes")
            return real

        with patch(
            "photocheck.core.extractor._read_exif_bytes",
            return_value=b"fake head",
        ), patch(
            "photocheck.core.extractor.piexif.load",
            side_effect=selective_load,
        ):
            result = extract_metadata(arw)

        assert len(call_log) == 2
        assert result.error is None
        assert result.camera_make == "SONY"

    def test_no_exif_returns_error_message(self, tmp_path):
        """A file with no EXIF should set error rather than crash."""
        arw = tmp_path / "test.ARW"
        arw.write_bytes(b"random garbage" * 1000)

        result = extract_metadata(arw)
        assert result.error is not None
        assert result.file_path == arw


class TestHeaderBytesConstant:
    def test_header_size_is_reasonable(self):
        """256 KB must be big enough for typical Sony MakerNotes but small
        enough to skip the bulk of a 40 MB RAW file.
        """
        assert EXIF_HEADER_BYTES == 256 * 1024
        # 256 KB / 40 MB ≈ 0.6% — meaningful I/O savings
        assert EXIF_HEADER_BYTES < 1024 * 1024  # less than 1 MB