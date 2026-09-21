"""EXIF metadata extractor for PhotoCheck."""

import os
import piexif
from pathlib import Path
from typing import Optional
from datetime import datetime

import pandas as pd

from .models import PhotoMetadata


# Only the EXIF region at the head of the file is needed — typically < 64 KB.
# Reading the whole 30-50 MB RAW file wastes ~99.7% of I/O.
# 256 KB safely includes Sony/Nikon/Canon MakerNotes; any offset pointing
# beyond the buffer raises struct.error from piexif and we fall back to the
# full read.
EXIF_HEADER_BYTES = 256 * 1024


def is_valid_dt(dt) -> bool:
    """True if dt is a real datetime (not None and not pd.NaT).

    After a parquet round-trip, missing datetimes come back as pd.NaT
    (not None). NaT propagates silently through arithmetic and indexing,
    so callers must filter it explicitly before using dt as a real
    timestamp. Use this helper instead of `dt is not None`.
    """
    if dt is None:
        return False
    try:
        return not pd.isna(dt)
    except (ValueError, TypeError):
        return False


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


def _read_exif_bytes(path: Path) -> Optional[bytes]:
    """Read the EXIF source bytes, preferring a 256 KB header read.

    Returns the first EXIF_HEADER_BYTES of the file on success, or None if
    the file is small enough that the partial-read path offers no benefit
    (caller should pass the path to piexif, which reads it whole).

    piexif.load(bytes) supports TIFF/WEBP/JPEG sources; passing bytes
    avoids the f.read() of the entire 30-50 MB RAW file. If any IFD
    offset points beyond the buffer, piexif raises struct.error and
    the caller falls back to the full-file read.
    """
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size <= EXIF_HEADER_BYTES:
        # No truncation risk; let piexif read the whole small file.
        return None
    try:
        with open(path, "rb") as f:
            return f.read(EXIF_HEADER_BYTES)
    except OSError:
        return None


def extract_metadata(
    image_path: Path,
    crop_factor: float = 1.0,
) -> PhotoMetadata:
    """Extract EXIF metadata from a single image.

    Focal-length resolution:
    - If EXIF FocalLengthIn35mmFilm (0xA405) is present, use it directly
      (manufacturer-reported 35mm-equivalent, most accurate).
    - Otherwise use raw FocalLength as-is.

    The crop_factor argument is preserved for API compatibility but
    is no longer applied. Use FocalLengthIn35mmFilm in the EXIF instead
    of guessing sensor format.

    Args:
        image_path: Path to the image file.
        crop_factor: Deprecated, ignored. Kept for API compat only.

    Returns:
        PhotoMetadata object with extracted values.
    """
    result = PhotoMetadata(file_path=image_path)

    # Fast path: read just the first 256 KB (EXIF lives in the file head).
    # On ARW this is ~50x less I/O than reading the whole 40 MB file.
    # piexif raises struct.error if any IFD offset points past our buffer;
    # in that case we fall back to the full-file read.
    head = _read_exif_bytes(image_path)
    if head is not None:
        try:
            exif_data = piexif.load(head)
        except Exception:
            exif_data = None
        if exif_data is not None and not _looks_empty(exif_data):
            return _populate_result(result, exif_data)
        # Partial read yielded nothing useful — fall through to full read.

    try:
        exif_data = piexif.load(str(image_path))
    except Exception as e:
        result.error = str(e)
        return result

    return _populate_result(result, exif_data)


def _looks_empty(exif_data: dict) -> bool:
    """True if piexif returned no tags — partial read likely missed them.

    For JPEG partial-read, piexif silently returns an empty dict when
    the APP1 marker is beyond our buffer; for TIFF partial-read, it
    either works fully or raises. Either way, an empty result with a
    large file means the partial path failed and the caller should
    fall back.
    """
    for section in ("0th", "Exif", "GPS", "Interop", "1st"):
        if exif_data.get(section):
            return False
    return True


def _populate_result(
    result: PhotoMetadata, exif_data: dict
) -> PhotoMetadata:
    """Pull our known tags out of a piexif dict into the result."""
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

    # Use 35mm tag if present, else raw. No DB or crop_factor math.
    if result.focal_length_35mm is not None:
        result.focal_length = result.focal_length_35mm
    else:
        result.focal_length = raw_focal

    return result
