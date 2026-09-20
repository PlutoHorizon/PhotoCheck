"""Tests for file format detection via magic bytes."""

import os
from pathlib import Path

import pytest

from photocheck.core.pairing import (
    DEFAULT_EXTENSIONS,
    _is_supported_image,
    find_files_by_extensions,
)


def _touch(path: Path, content: bytes = b"") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


class TestMagicBytes:
    def test_jpeg_recognized(self, tmp_path):
        f = tmp_path / "test.jpg"
        _touch(f, b"\xff\xd8\xff\xe0\x00\x10JFIF")
        assert _is_supported_image(f) is True

    def test_tiff_le_recognized(self, tmp_path):
        f = tmp_path / "test.tiff"
        _touch(f, b"II*\x00\x08\x00\x00\x00")
        assert _is_supported_image(f) is True

    def test_tiff_be_recognized(self, tmp_path):
        f = tmp_path / "test.tiff"
        _touch(f, b"MM\x00*\x00\x00\x00\x08")
        assert _is_supported_image(f) is True

    def test_arw_recognized(self, tmp_path):
        # ARW is TIFF-based, starts with II*\x00
        f = tmp_path / "test.ARW"
        _touch(f, b"II*\x00\x20\x00\x00\x00" + b"\x00" * 100)
        assert _is_supported_image(f) is True

    def test_raf_recognized(self, tmp_path):
        f = tmp_path / "test.RAF"
        _touch(f, b"FUJIFOTO\x00\x00\x00")
        assert _is_supported_image(f) is True

    def test_webp_recognized(self, tmp_path):
        f = tmp_path / "test.webp"
        _touch(f, b"RIFF\x00\x00\x00\x00WEBPVP8")
        assert _is_supported_image(f) is True

    def test_txt_rejected(self, tmp_path):
        f = tmp_path / "test.txt"
        _touch(f, b"This is plain text content")
        assert _is_supported_image(f) is False

    def test_empty_file_rejected(self, tmp_path):
        f = tmp_path / "empty.jpg"
        _touch(f, b"")
        assert _is_supported_image(f) is False

    def test_random_bytes_rejected(self, tmp_path):
        f = tmp_path / "fake.jpg"
        _touch(f, b"\x00\x01\x02\x03\x04\x05\x06\x07")
        assert _is_supported_image(f) is False


class TestFindFilesByExtensions:
    def test_default_extensions_include_raw_and_jpg(self):
        """The default set covers common RAW + JPG formats."""
        for ext in (".arw", ".nef", ".cr2", ".cr3", ".dng", ".raf",
                    ".orf", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"):
            assert ext in DEFAULT_EXTENSIONS, f"missing {ext}"
        # Case-insensitive pairs
        for ext in (".ARW", ".NEF", ".CR2", ".JPG"):
            assert ext in DEFAULT_EXTENSIONS, f"missing uppercase {ext}"

    def test_finds_arw_by_magic(self, tmp_path):
        (tmp_path / "a.ARW").write_bytes(b"II*\x00" + b"\x00" * 100)
        (tmp_path / "b.ARW").write_bytes(b"II*\x00" + b"\x00" * 100)
        # An ARW-named file with invalid content should be rejected
        (tmp_path / "fake.ARW").write_bytes(b"not a real ARW")
        # A JPG with valid magic
        (tmp_path / "c.jpg").write_bytes(b"\xff\xd8\xff\xe0")

        result = find_files_by_extensions(tmp_path)
        names = sorted(p.name for p in result)
        # a.ARW and b.ARW accepted, fake.ARW rejected
        assert "a.ARW" in names
        assert "b.ARW" in names
        assert "fake.ARW" not in names

    def test_empty_dir(self, tmp_path):
        assert find_files_by_extensions(tmp_path) == []

    def test_explicit_extensions_override_default(self, tmp_path):
        (tmp_path / "a.ARW").write_bytes(b"II*\x00" + b"\x00" * 100)
        (tmp_path / "b.jpg").write_bytes(b"\xff\xd8\xff")
        # Only request jpg
        result = find_files_by_extensions(tmp_path, [".jpg"])
        assert len(result) == 1
        assert result[0].name == "b.jpg"

    def test_system_folders_are_skipped(self, tmp_path):
        """System/hidden folders (recycle bin, Spotlight, etc.) are skipped
        even if they contain files with valid image extensions.
        """
        # Real image in normal location
        (tmp_path / "photos").mkdir()
        (tmp_path / "photos" / "real.ARW").write_bytes(b"II*\x00" + b"\x00" * 100)
        # System folders that should be skipped
        for sysdir in ("$RECYCLE.BIN", "System Volume Information",
                       ".Spotlight-V100", ".Trashes"):
            (tmp_path / sysdir).mkdir(exist_ok=True)
            (tmp_path / sysdir / "garbage.ARW").write_bytes(b"II*\x00" + b"\x00" * 100)
        result = find_files_by_extensions(tmp_path)
        names = sorted(p.name for p in result)
        assert names == ["real.ARW"]

    def test_macos_apple_double_files_are_skipped(self, tmp_path):
        """macOS creates ._AppleDouble files (e.g., ._DSC0001.ARW) that
        contain resource fork metadata, not actual image data. They have
        an image-like extension but are not parseable by EXIF tools.
        """
        (tmp_path / "DSC0001.ARW").write_bytes(b"II*\x00" + b"\x00" * 100)
        # AppleDouble file with the same base name
        (tmp_path / "._DSC0001.ARW").write_bytes(b"not real ARW\0" * 10)
        result = find_files_by_extensions(tmp_path)
        names = sorted(p.name for p in result)
        assert names == ["DSC0001.ARW"]
