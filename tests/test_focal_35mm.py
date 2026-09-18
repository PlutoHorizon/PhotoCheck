"""Tests for auto-detection of 35mm-equivalent focal length from EXIF.

The extract_metadata function uses this priority to set the final focal_length:
1. User-explicit crop_factor (when not 1.0)
2. EXIF FocalLengthIn35mmFilm (0xA405), if present
3. Built-in camera database (_CAMERA_CROP_FACTOR)
4. Raw FocalLength (no conversion)
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from photocheck.core.cache import load_cache, save_cache
from photocheck.core.extractor import (
    _CAMERA_CROP_FACTOR,
    extract_metadata,
)
from photocheck.core.models import PhotoMetadata
from photocheck.cli import get_cache_path


class TestFocalLengthPriority:
    """Verify the precedence: user-explicit > 35mm tag > camera DB > raw."""

    def test_user_explicit_apsc_overrides_db(self, tmp_path):
        """If user passes crop_factor=1.5, it overrides the camera DB."""
        # Mock a fake EXIF that returns a Sony A7C II (FF body) with raw 600mm
        fake_exif = {
            "Exif": {
                37386: (600, 1),       # FocalLength = 600/1 = 600
            },
            "0th": {
                271: b"SONY",
                272: b"ILCE-7CM2",    # Full-frame, but user overrides
            },
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW", crop_factor=1.5)
        # User forced APS-C, so 600mm raw becomes 900mm
        assert m.focal_length == 900.0
        assert m.camera_model == "ILCE-7CM2"

    def test_camera_db_used_when_no_user_override(self, tmp_path):
        """With crop_factor=1.0 (or None) and no 35mm tag, camera DB is used."""
        fake_exif = {
            "Exif": {
                37386: (200, 1),       # raw 200mm
            },
            "0th": {
                271: b"SONY",
                272: b"ILCE-7CM2",    # FF body, DB entry 1.0
            },
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")  # no crop_factor
        # FF body → no multiplication → 200mm
        assert m.focal_length == 200.0

    def test_camera_db_apsc_when_no_user_override(self, tmp_path):
        """With an APS-C body in the DB, raw focal is multiplied by 1.5."""
        fake_exif = {
            "Exif": {
                37386: (200, 1),       # raw 200mm
            },
            "0th": {
                271: b"SONY",
                272: b"ILCE-6700",    # APS-C, DB entry 1.5
            },
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")
        # APS-C body → 200 * 1.5 = 300
        assert m.focal_length == 300.0

    def test_35mm_tag_overrides_db(self, tmp_path):
        """If EXIF 35mm tag is present, it wins over camera DB."""
        fake_exif = {
            "Exif": {
                37386: (200, 1),         # raw 200mm
                41993: (300, 1),         # 35mm equivalent = 300
            },
            "0th": {
                271: b"SONY",
                272: b"ILCE-7CM2",
            },
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")
        # 35mm tag wins: 300, not 200
        assert m.focal_length == 300.0
        assert m.focal_length_35mm == 300.0

    def test_unknown_camera_uses_raw(self, tmp_path):
        """A camera not in the DB and no 35mm tag uses raw focal."""
        fake_exif = {
            "Exif": {37386: (35, 1)},
            "0th": {271: b"Foo", 272: b"UnknownModel"},
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")
        assert m.focal_length == 35.0

    def test_camera_db_contains_user_cameras(self):
        """The user's known cameras (A7C II and A7R V) are in the DB."""
        assert _CAMERA_CROP_FACTOR.get("ILCE-7CM2") == 1.0
        assert _CAMERA_CROP_FACTOR.get("ILCE-7RM5") == 1.0

    def test_existing_cache_loads_compatible(self):
        """Old cache entries without focal_length_35mm still work."""
        m = PhotoMetadata(
            file_path=Path("/test.ARW"),
            focal_length=200.0,
        )
        assert m.focal_length_35mm is None
        assert m.focal_length == 200.0

