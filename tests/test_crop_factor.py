"""Tests for the camera-body crop factor lookup and focal-length resolution."""

from pathlib import Path
from unittest.mock import patch

import pytest

from photocheck.core.extractor import (
    extract_metadata,
    get_crop_factor,
)


class TestGetCropFactor:
    """The lookup table itself."""

    def test_sony_aps_c_models(self):
        """All Sony APS-C bodies (ILCE-6xxx) map to 1.5x."""
        for model in ("ILCE-6000", "ILCE-6100", "ILCE-6300", "ILCE-6400",
                      "ILCE-6500", "ILCE-6600", "ILCE-6700"):
            assert get_crop_factor(model) == 1.5, f"{model} should be 1.5"

    def test_sony_full_frame_models(self):
        """Sony FF bodies (ILCE-7/9/1) map to 1.0x."""
        for model in ("ILCE-7", "ILCE-7M2", "ILCE-7M3", "ILCE-7CM2",
                      "ILCE-7RM5", "ILCE-9", "ILCE-1"):
            assert get_crop_factor(model) == 1.0, f"{model} should be 1.0"

    def test_sony_nex_aps_c(self):
        """Sony NEX series (early APS-C mirrorless) is 1.5x."""
        assert get_crop_factor("NEX-C3") == 1.5
        assert get_crop_factor("NEX-5") == 1.5
        assert get_crop_factor("NEX-7") == 1.5

    def test_canon_aps_c_dslr(self):
        """Canon EF-S bodies are 1.6x (Canon APS-C DSLR crop)."""
        for model in ("Canon EOS 80D", "Canon EOS 90D", "Canon EOS 7D",
                      "Canon EOS 100D", "Canon EOS 600D", "Canon EOS 1300D"):
            assert get_crop_factor(model) == 1.6, f"{model} should be 1.6"

    def test_canon_aps_c_mirrorless(self):
        """Canon RF APS-C and EOS-M APS-C are 1.6x."""
        for model in ("Canon EOS R7", "Canon EOS R10", "Canon EOS R50",
                      "Canon EOS M50", "Canon EOS M6"):
            assert get_crop_factor(model) == 1.6

    def test_mft_cameras_are_2x(self):
        """Olympus/OM and Panasonic MFT bodies are 2.0x."""
        for model in ("E-M1", "E-M1 Mark II", "E-M5 Mark III",
                      "DC-GH5", "DC-GH6", "DMC-G85"):
            assert get_crop_factor(model) == 2.0, f"{model} should be 2.0"

    def test_unknown_camera_returns_1(self):
        """Unknown cameras default to 1.0 (assumes FF, no conversion)."""
        assert get_crop_factor("FooCam X1000") == 1.0
        assert get_crop_factor(None) == 1.0
        assert get_crop_factor("") == 1.0

    def test_longer_prefix_wins(self):
        """When multiple prefixes match, the longer one wins.

        'ILCE-6000' is longer than 'ILCE-6'; if the table is correctly
        sorted, an exact match for 'ILCE-6400' falls through to 'ILCE-6'.
        The point of this test is that we never accidentally pick a
        1.0x prefix for an APS-C body.
        """
        # ILCE-6400 must always resolve to 1.5 regardless of table order
        assert get_crop_factor("ILCE-6400") == 1.5


class TestFocalLengthWithCropFactor:
    """End-to-end: extract_metadata applies crop factor when 35mm tag missing."""

    def test_aps_c_body_multiplies_raw_focal(self, tmp_path):
        """a6400 with E 18-135 at 135mm physical → 202.5mm equivalent."""
        fake_exif = {
            "Exif": {37386: (135, 1)},     # raw 135mm
            "0th": {271: b"SONY", 272: b"ILCE-6400"},
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")
        # 135 * 1.5 = 202.5
        assert m.focal_length == 202.5
        assert m.focal_length_35mm is None

    def test_ff_body_leaves_raw_focal_unchanged(self, tmp_path):
        """a7C II at 50mm physical → 50mm equivalent (1.0x)."""
        fake_exif = {
            "Exif": {37386: (50, 1)},
            "0th": {271: b"SONY", 272: b"ILCE-7CM2"},
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")
        assert m.focal_length == 50.0

    def test_canon_aps_c_uses_1_6(self, tmp_path):
        """Canon EOS 80D at 50mm physical → 80mm equivalent (1.6x)."""
        fake_exif = {
            "Exif": {37386: (50, 1)},
            "0th": {271: b"Canon", 272: b"Canon EOS 80D"},
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")
        # 50 * 1.6 = 80
        assert m.focal_length == 80.0

    def test_mft_uses_2x(self, tmp_path):
        """MFT body at 25mm physical → 50mm equivalent (2.0x)."""
        fake_exif = {
            "Exif": {37386: (25, 1)},
            "0th": {271: b"OLYMPUS", 272: b"E-M5 Mark III"},
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")
        # 25 * 2.0 = 50
        assert m.focal_length == 50.0

    def test_unknown_camera_leaves_raw_focal(self, tmp_path):
        """Unknown body falls back to raw focal as-is."""
        fake_exif = {
            "Exif": {37386: (35, 1)},
            "0th": {271: b"Foo", 272: b"Unknown Model"},
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")
        assert m.focal_length == 35.0

    def test_35mm_tag_overrides_crop_factor(self, tmp_path):
        """If 35mm tag is present, it wins over crop factor.

        Sony a6400 doesn't write 35mm tag, but if a hypothetical custom
        firmware did, the 35mm value would be used as-is.
        """
        fake_exif = {
            "Exif": {
                37386: (135, 1),         # raw 135mm
                41993: (300, 1),         # 35mm tag says 300mm equivalent
            },
            "0th": {271: b"SONY", 272: b"ILCE-6400"},
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")
        # 35mm tag wins: 300, NOT 135*1.5=202.5
        assert m.focal_length == 300.0
        assert m.focal_length_35mm == 300.0

    def test_no_focal_length_at_all_stays_none(self, tmp_path):
        """Missing both FocalLength and 35mm tag → focal_length stays None."""
        fake_exif = {
            "Exif": {},
            "0th": {271: b"SONY", 272: b"ILCE-6400"},
        }
        with patch("photocheck.core.extractor.piexif.load", return_value=fake_exif):
            m = extract_metadata(tmp_path / "fake.ARW")
        assert m.focal_length is None