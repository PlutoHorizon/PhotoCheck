"""EXIF metadata extractor for PhotoCheck."""

import piexif
from pathlib import Path
from typing import Optional
from datetime import datetime

from .models import PhotoMetadata


# Camera model -> crop factor. Used as a fallback when EXIF doesn't provide
# FocalLengthIn35mmFilm (tag 0xA405). Common Sony/Fuji/etc models.
# Sources:
#   - Sony ILCE-7* / ILCE-9* = full-frame (1.0)
#   - Sony ILCE-6* / ILCE-5* / ILCE-6xxx (except 7C) = APS-C (1.5)
#   - Fuji X-Trans = APS-C (1.5)
#   - etc.
_CAMERA_CROP_FACTOR: dict[str, float] = {
    # Sony full-frame (Alpha 7/9 series, except 7xxx APS-C models)
    "ILCE-7": 1.0, "ILCE-7M2": 1.0, "ILCE-7M3": 1.0, "ILCE-7M4": 1.0,
    "ILCE-7RM2": 1.0, "ILCE-7RM3": 1.0, "ILCE-7RM4": 1.0, "ILCE-7RM5": 1.0,
    "ILCE-7C": 1.0, "ILCE-7CM2": 1.0,
    "ILCE-9": 1.0, "ILCE-9M2": 1.0,
    "ILCE-1": 1.0,
    # Sony APS-C (Alpha 6000 series, 5000 series, 7000 series)
    "ILCE-6000": 1.5, "ILCE-6100": 1.5, "ILCE-6300": 1.5, "ILCE-6400": 1.5,
    "ILCE-6500": 1.5, "ILCE-6600": 1.5, "ILCE-6700": 1.5,
    "ILCE-5100": 1.5, "ILCE-5000": 1.5,
    "ILCE-7M": 1.5, "ILCE-7RM": 1.5,    # original NEX-7
    "NEX-5": 1.5, "NEX-6": 1.5, "NEX-7": 1.5,
    # Fuji X-Trans (APS-C)
    "X-T1": 1.5, "X-T2": 1.5, "X-T3": 1.5, "X-T4": 1.5, "X-T5": 1.5,
    "X-H1": 1.5, "X-H2": 1.5, "X-H2S": 1.5,
    "X-Pro1": 1.5, "X-Pro2": 1.5, "X-Pro3": 1.5,
    "X-E1": 1.5, "X-E2": 1.5, "X-E3": 1.5, "X-E4": 1.5,
    # Fuji medium format (GFX series, 0.79x)
    "GFX-50S": 0.79, "GFX-50R": 0.79, "GFX-100": 0.79, "GFX-100S": 0.79, "GFX-100II": 0.79,
}


# EXIF tag mappings: tag_id -> (parent_key, field_name)
EXIF_TAGS = {
    37386: ("Exif", "focal_length"),         # FocalLength
    41993: ("Exif", "focal_length_35mm"),   # FocalLengthIn35mmFilm
    33437: ("Exif", "f_stop"),                # FNumber
    34855: ("Exif", "iso"),                  # ISOSpeedRatings
    33434: ("Exif", "shutter_speed"),        # ExposureTime
    42036: ("Exif", "lens_name"),             # LensModel
    36867: ("Exif", "datetime_original"),    # DateTimeOriginal
    36868: ("Exif", "datetime_digitized"),   # DateTimeDigitized
    271: ("0th", "camera_make"),             # Make
    272: ("0th", "camera_model"),            # Model
}

# DateTime tag in 0th IFD
EXIF_TAGS[306] = ("0th", "datetime_modified")  # DateTime


# Pre-grouped by parent_key for faster lookups. Built once at import.
# Maps parent_key -> list of (tag_id, field_name)
_TAGS_BY_PARENT: dict[str, list[tuple[int, str]]] = {}
for _tag_id, (_parent, _field) in EXIF_TAGS.items():
    _TAGS_BY_PARENT.setdefault(_parent, []).append((_tag_id, _field))


def _parse_rational(value: tuple) -> float:
    """Parse a rational number tuple (numerator, denominator)."""
    if value is None:
        return None
    return value[0] / value[1]


def _parse_datetime(value: bytes) -> Optional[datetime]:
    """Parse EXIF datetime string to datetime object.

    EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
    """
    if value is None:
        return None
    try:
        dt_str = value.decode("utf-8")
        return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _parse_string(value: bytes) -> Optional[str]:
    """Parse bytes as UTF-8 string."""
    if value is None:
        return None
    try:
        return value.decode("utf-8").rstrip("\x00")
    except (ValueError, TypeError):
        return None


def extract_metadata(
    image_path: Path,
    crop_factor: float | None = None,
) -> PhotoMetadata:
    """Extract EXIF metadata from a single image.

    Focal-length resolution priority:
    1. If EXIF FocalLengthIn35mmFilm (0xA405) is present, use it directly
       (manufacturer-reported, most accurate).
    2. Else if camera_model is in the known-camera database, use that
       camera's crop factor.
    3. Else use the crop_factor argument (default 1.0).

    Args:
        image_path: Path to the image file.
        crop_factor: User-provided crop factor override. If set to a value
            other than 1.0, it overrides the EXIF 35mm tag and camera DB.
            If None or 1.0, auto-detection kicks in: 35mm tag > camera DB > raw.

    Returns:
        PhotoMetadata object with extracted values.
    """
    if crop_factor is None:
        crop_factor = 1.0

    result = PhotoMetadata(file_path=image_path)

    try:
        exif_data = piexif.load(str(image_path))
    except Exception as e:
        result.error = str(e)
        return result

    raw_focal: float | None = None

    for parent_key, tags in _TAGS_BY_PARENT.items():
        parent = exif_data.get(parent_key)
        if parent is None:
            continue
        for tag_id, field_name in tags:
            try:
                value = parent.get(tag_id)
                if value is None:
                    continue

                if field_name in ("focal_length", "focal_length_35mm", "f_stop", "shutter_speed"):
                    parsed = _parse_rational(value)
                    if field_name == "focal_length":
                        raw_focal = parsed
                    else:
                        setattr(result, field_name, parsed)
                elif field_name.startswith("datetime"):
                    parsed = _parse_datetime(value)
                    setattr(result, field_name, parsed)
                else:
                    parsed = _parse_string(value) if isinstance(value, bytes) else value
                    setattr(result, field_name, parsed)

            except Exception:
                continue

    # Resolve final focal_length.
    # Priority: user-explicit > EXIF 35mm tag > camera DB > raw
    # (user "explicit" means crop_factor != 1.0, i.e. they specifically
    # said "this is APS-C" or similar)
    if crop_factor != 1.0 and raw_focal is not None:
        result.focal_length = raw_focal * crop_factor
    elif result.focal_length_35mm is not None:
        result.focal_length = result.focal_length_35mm
    elif result.camera_model in _CAMERA_CROP_FACTOR and raw_focal is not None:
        cf = _CAMERA_CROP_FACTOR[result.camera_model]
        result.focal_length = raw_focal * cf
    else:
        result.focal_length = raw_focal

    return result
