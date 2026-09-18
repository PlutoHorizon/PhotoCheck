"""EXIF metadata extractor for PhotoCheck."""

import piexif
from pathlib import Path
from typing import Optional
from datetime import datetime

from .models import PhotoMetadata


# EXIF tag mappings: tag_id -> (parent_key, field_name)
EXIF_TAGS = {
    37386: ("Exif", "focal_length"),      # FocalLength
    33437: ("Exif", "f_stop"),             # FNumber
    34855: ("Exif", "iso"),                # ISOSpeedRatings
    33434: ("Exif", "shutter_speed"),      # ExposureTime
    42036: ("Exif", "lens_name"),           # LensModel
    36867: ("Exif", "datetime_original"),  # DateTimeOriginal
    36868: ("Exif", "datetime_digitized"), # DateTimeDigitized
    271: ("0th", "camera_make"),           # Make
    272: ("0th", "camera_model"),          # Model
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
    crop_factor: float = 1.0,
) -> PhotoMetadata:
    """Extract EXIF metadata from a single image.

    Args:
        image_path: Path to the image file
        crop_factor: Multiplier for focal length (1.0 for full-frame, 1.5 for APS-C)

    Returns:
        PhotoMetadata object with extracted values
    """
    result = PhotoMetadata(file_path=image_path)

    try:
        exif_data = piexif.load(str(image_path))
    except Exception as e:
        result.error = str(e)
        return result

    # Iterate by parent_key (3 keys) instead of per-tag (10 tags),
    # so exif_data.get() is called once per parent, not once per tag.
    for parent_key, tags in _TAGS_BY_PARENT.items():
        parent = exif_data.get(parent_key)
        if parent is None:
            continue
        for tag_id, field_name in tags:
            try:
                value = parent.get(tag_id)
                if value is None:
                    continue

                # Type-specific parsing
                if field_name in ("focal_length", "f_stop", "shutter_speed"):
                    parsed = _parse_rational(value)
                    if field_name == "focal_length" and parsed is not None:
                        parsed *= crop_factor
                elif field_name.startswith("datetime"):
                    parsed = _parse_datetime(value)
                else:
                    parsed = _parse_string(value) if isinstance(value, bytes) else value

                setattr(result, field_name, parsed)

            except Exception:
                continue

    return result
