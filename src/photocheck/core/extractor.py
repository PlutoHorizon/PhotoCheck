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


# Camera-body crop factor table. Used when EXIF FocalLengthIn35mmFilm
# is missing (most Sony APS-C, all Canon EF-S, all MFT bodies).
#
# Entries are (model_prefix, factor) pairs. Lookup tries each prefix
# against the EXIF Camera Model name. The first matching prefix wins;
# longest prefixes are listed first to win over shorter ones.
#
# Sources: manufacturer spec sheets; defaults are:
#   full-frame (incl. Sony ILCE-7/9/1, Canon R5/R6, Nikon Zx)        1.0
#   Canon APS-C DSLR (EF-S bodies, EOS M, Rebel xxxD/xxxxD)         1.6
#   Sony / Nikon / Fuji APS-C                                        1.5
#   Micro Four Thirds (Olympus OM, Panasonic Lumix G)                2.0
CAMERA_CROP_FACTORS: list[tuple[str, float]] = [
    # Sony APS-C (ILCE-6xxx)
    ("ILCE-6", 1.5),
    ("NEX-", 1.5),
    # Sony full-frame (FF bodies usually write 35mm tag, but include for fallback)
    ("ILCE-7", 1.0),
    ("ILCE-9", 1.0),
    ("ILCE-1", 1.0),
    # Canon APS-C — DSLR and mirrorless
    ("Canon EOS 7D", 1.6),
    ("Canon EOS 60D", 1.6),
    ("Canon EOS 80D", 1.6),
    ("Canon EOS 90D", 1.6),
    ("Canon EOS R7", 1.6),
    ("Canon EOS R10", 1.6),
    ("Canon EOS R50", 1.6),
    ("Canon EOS R100", 1.6),
    ("Canon EOS M50", 1.6),
    ("Canon EOS M6", 1.6),
    ("Canon EOS M5", 1.6),
    ("Canon EOS 100D", 1.6),
    ("Canon EOS 200D", 1.6),
    ("Canon EOS 250D", 1.6),
    ("Canon EOS 500D", 1.6),
    ("Canon EOS 550D", 1.6),
    ("Canon EOS 600D", 1.6),
    ("Canon EOS 650D", 1.6),
    ("Canon EOS 700D", 1.6),
    ("Canon EOS 750D", 1.6),
    ("Canon EOS 760D", 1.6),
    ("Canon EOS 800D", 1.6),
    ("Canon EOS 850D", 1.6),
    ("Canon EOS 1000D", 1.6),
    ("Canon EOS 1100D", 1.6),
    ("Canon EOS 1200D", 1.6),
    ("Canon EOS 1300D", 1.6),
    ("Canon EOS 2000D", 1.6),
    ("Canon EOS 4000D", 1.6),
    # Nikon APS-C. Real EXIF Model strings carry the "NIKON " prefix
    # ("NIKON Z 30", "NIKON D7200"), so startswith("Z30")-style entries
    # never match; list the prefixed forms too. Longest-prefix-wins
    # keeps these ahead of any future short/full-frame conflicts.
    ("NIKON Z 30", 1.5),
    ("NIKON Z 50", 1.5),
    ("NIKON Z fc", 1.5),
    ("NIKON D300", 1.5),
    ("NIKON D500", 1.5),
    ("NIKON D7000", 1.5),
    ("NIKON D7100", 1.5),
    ("NIKON D7200", 1.5),
    ("NIKON D7500", 1.5),
    ("D300", 1.5),
    ("D500", 1.5),
    ("D7000", 1.5),
    ("D7100", 1.5),
    ("D7200", 1.5),
    ("D7500", 1.5),
    ("Z50", 1.5),
    ("Z fc", 1.5),
    ("Z30", 1.5),
    # Fuji APS-C
    ("X-T", 1.5),
    ("X-H", 1.5),
    ("X-Pro", 1.5),
    ("X-E", 1.5),
    ("X-S10", 1.5),
    ("X-S20", 1.5),
    ("X-A", 1.5),
    ("X-M", 1.5),
    # Olympus / OM System MFT
    ("E-M", 2.0),
    ("E-P", 2.0),
    # Panasonic MFT
    ("DC-GH", 2.0),
    ("DC-G9", 2.0),
    ("DMC-G", 2.0),
]


# Backwards-compatible alias (some tests/docs reference this name)
DEFAULT_CROP_FACTORS = CAMERA_CROP_FACTORS


# Module-level active table. Defaults to the built-in list; can be
# overridden per-process via set_crop_factor_overrides() (called by
# CLI after loading photocheck.toml). User entries are prepended so
# they win the longest-prefix lookup over the built-in defaults.
_active_crop_factors: list[tuple[str, float]] = list(CAMERA_CROP_FACTORS)


def set_crop_factor_overrides(overrides: list[tuple[str, float]] | None) -> None:
    """Replace the active crop-factor table with overrides + built-ins.

    Call once at scan start (e.g. from CLI after loading photocheck.toml).
    Pass None to reset to built-ins only.

    Longest-prefix-wins ordering means a user entry like ("ILCE-6400", 1.5)
    will beat the built-in ("ILCE-6", 1.5) only if the user prefix is
    longer, but since both yield the same factor it doesn't matter.
    To override a built-in factor (e.g. force 1.0 for an APS-C body),
    the user entry must be longer than the built-in prefix.
    """
    global _active_crop_factors
    if overrides:
        _active_crop_factors = list(overrides) + list(CAMERA_CROP_FACTORS)
    else:
        _active_crop_factors = list(CAMERA_CROP_FACTORS)


def get_crop_factor(camera_model: Optional[str]) -> float:
    """Look up sensor crop factor from camera model name.

    Returns 1.0 (full-frame) for unknown or missing models — this is
    a safe default: it leaves FocalLength as-is rather than guessing.

    Uses the active table set by set_crop_factor_overrides(), or the
    built-in defaults if no overrides were registered.
    """
    if not camera_model:
        return 1.0
    # Sort by length descending so longer prefixes win ("Canon EOS R7" before "Canon EOS")
    for prefix, factor in sorted(_active_crop_factors, key=lambda p: -len(p[0])):
        if camera_model.startswith(prefix):
            return factor
    return 1.0


# Lens-name markers that mark a lens as APS-C, independent of body.
# Deliberately NOT matching Sony's "E " prefix: Tamron full-frame lenses
# (e.g. "E 28-200mm F2.8-5.6 A071", Di III) show up with an E prefix in
# EXIF LensModel on Sony bodies, so the prefix is not trustworthy.
APS_C_LENS_MARKERS: tuple[str, ...] = (
    "DC DN",          # Sigma APS-C mirrorless (vs "DG DN" full-frame)
    "Di III-A",       # Tamron APS-C mirrorless (vs "Di III" full-frame)
    "DX ",            # Nikon DX (NIKKOR Z DX ...)
    "EF-S",           # Canon APS-C DSLR
    "E 17-70mm",      # Tamron 17-70 B070 for Sony E (Di III-A, EXIF name lacks it)
    "E 70-350mm",     # Sony native APS-C E 70-350 G OSS
)


def lens_crop_factor(lens_name: Optional[str]) -> float:
    """Crop factor implied by the lens (1.5 for APS-C lenses, else 1.0).

    A full-frame body with an APS-C lens mounted captures an APS-C image
    (Nikon Z forces the DX crop; Sony/Canon default to it), so the lens
    can raise the effective factor above the body's own.
    """
    if not lens_name:
        return 1.0
    if any(marker in lens_name for marker in APS_C_LENS_MARKERS):
        return 1.5
    return 1.0


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


def _parse_rational(value) -> Optional[float]:
    """Parse an EXIF rational.

    piexif returns a (num, den) tuple for RATIONAL tags but a plain int
    for SHORT/LONG tags (e.g. FocalLengthIn35mmFilm) — handle both.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, tuple) and len(value) == 2:
        return value[0] / value[1]
    return None


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

    Focal-length resolution (priority order):
    1. EXIF FocalLengthIn35mmFilm (0xA405) — manufacturer-reported
       35mm-equivalent, used as-is.
    2. raw FocalLength × camera crop factor (from CAMERA_CROP_FACTORS)
       — for bodies that don't write the 35mm tag (Sony APS-C, Canon
       EF-S bodies, all MFT, etc.).
    3. raw FocalLength as-is — when the body is unknown (assumes FF,
       no conversion).

    The crop_factor argument is preserved for API compatibility but
    is no longer applied (the per-body table handles conversion).

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

    # Resolve focal_length in this priority:
    #   1. EXIF FocalLengthIn35mmFilm (0xA405) when non-zero — the body
    #      computed it from its real crop state (incl. in-body crop
    #      modes). Sony writes 0 at long focal lengths, so 0 means
    #      "absent", not "0mm".
    #   2. raw FocalLength × max(body, lens) crop factor — for bodies
    #      that don't write the 35mm tag, and for APS-C lenses mounted
    #      on full-frame bodies (which capture an APS-C image).
    #   3. raw FocalLength — when nothing is known (assume FF, no
    #      conversion) so the value is at least recorded.
    if result.focal_length_35mm:
        result.focal_length = result.focal_length_35mm
    elif raw_focal is not None:
        crop = max(
            get_crop_factor(result.camera_model),
            lens_crop_factor(result.lens_name),
        )
        result.focal_length = raw_focal * crop
    # else: focal_length stays None

    return result
