"""Tests for the simplified focal-length extraction logic.

extract_metadata now uses this simple rule:
- If EXIF FocalLengthIn35mmFilm (0xA405) is present, use it.
- Otherwise use raw FocalLength as-is.

The crop_factor argument is preserved for API compat but ignored.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from photocheck.core.extractor import extract_metadata
from photocheck.core.models import PhotoMetadata


class TestFocalLengthSimpleRule:
    def test_35mm_tag_used_when_present(self, tmp_path):
        fake_exif = {
            "Exif": {
                37386: (200, 1),         # raw 200mm
                41993: (300, 1),         # 35mm equivalent = 300
            },
            "0th": {271: b"SONY", 272: b"ILCE-7CM2"},
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")
        assert m.focal_length == 300.0
        assert m.focal_length_35mm == 300.0

    def test_raw_used_when_no_35mm_tag(self, tmp_path):
        fake_exif = {
            "Exif": {37386: (600, 1)},     # raw 600mm, no 35mm tag
            "0th": {271: b"SONY", 272: b"ILCE-7CM2"},
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")
        assert m.focal_length == 600.0
        assert m.focal_length_35mm is None

    def test_unknown_camera_with_no_35mm_uses_raw(self, tmp_path):
        fake_exif = {
            "Exif": {37386: (35, 1)},
            "0th": {271: b"Foo", 272: b"UnknownModel"},
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")
        assert m.focal_length == 35.0

    def test_crop_factor_arg_is_ignored(self, tmp_path):
        """The crop_factor argument is kept for API compat but no longer
        applied. We use 35mm if present, raw otherwise.
        """
        fake_exif = {
            "Exif": {37386: (200, 1)},     # raw 200mm
            "0th": {271: b"SONY", 272: b"ILCE-7CM2"},
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            # Pass crop_factor=1.5 — should be ignored
            m = extract_metadata(tmp_path / "fake.ARW", crop_factor=1.5)
        assert m.focal_length == 200.0  # not 300

    def test_existing_cache_compat(self):
        """Old cache entries without focal_length_35mm still work."""
        m = PhotoMetadata(
            file_path=Path("/test.ARW"),
            focal_length=200.0,
        )
        assert m.focal_length_35mm is None
        assert m.focal_length == 200.0
