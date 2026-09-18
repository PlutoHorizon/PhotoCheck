"""File discovery and deduplication for PhotoCheck.

Supports many RAW and standard image formats. Files are validated by
both extension AND magic bytes to avoid feeding piexif invalid input.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .models import PhotoMetadata


# Match a trailing sequence of digits in a file stem. Used as a
# disambiguator for burst-mode photos that share all other EXIF fields.
# Examples: "DSC05833" -> 5833, "IMG_1234" -> 1234, "vacation" -> None.
_FILE_NUMBER_RE = re.compile(r"(\d+)$")


# ---- Format support ----
#
# Magic byte prefixes for each supported image format. We check 8 bytes
# from the start of the file to determine if it can be EXIF-parsed.
#
# Most RAW formats (ARW, NEF, CR2, DNG, ORF) are TIFF-based and share
# the same II*\0 or MM\0* magic. CR3 (Canon) and HEIC use a different
# container; we don't support them yet (would need exifread).

_JPEG_MAGIC: Tuple[bytes, ...] = (b"\xff\xd8\xff",)
_TIFF_MAGIC: Tuple[bytes, ...] = (b"II*\x00", b"MM\x00*")
_RAF_MAGIC: Tuple[bytes, ...] = (b"FUJIFOTO",)
_RIFF_MAGIC: Tuple[bytes, ...] = (b"RIFF",)  # WebP: RIFF + size + WEBP

# All known magic prefixes (for single-pass check)
_ALL_MAGICS: Tuple[bytes, ...] = _JPEG_MAGIC + _TIFF_MAGIC + _RAF_MAGIC + _RIFF_MAGIC

# System/hidden folder names to skip during scans. These are
# Windows/macOS artifacts that may contain files with valid image
# extensions but garbage content (recycle bin, Spotlight cache, etc.)
_SKIP_DIR_NAMES: Set[str] = {
    "$RECYCLE.BIN",
    "$Recycle.Bin",
    "System Volume Information",
    ".Spotlight-V100",
    ".Trashes",
    ".fseventsd",
    ".TemporaryItems",
    ".DocumentRevisions-V100",
    ".DocumentRevisions-V100 (Being Edited)",
    ".Temporary Items",
    "Thumbs.db",
}

# Default extensions scanned when the user doesn't specify --extensions.
# Includes common RAW formats plus JPEG. User can override with
# --extensions if they want a narrower set.
DEFAULT_EXTENSIONS: Set[str] = {
    ".arw", ".ARW",  # Sony
    ".nef", ".NEF",  # Nikon
    ".cr2", ".CR2",  # Canon (legacy)
    ".cr3", ".CR3",  # Canon (newer; not all are EXIF-readable)
    ".dng", ".DNG",  # Adobe / universal
    ".raf", ".RAF",  # Fuji
    ".orf", ".ORF",  # Olympus
    ".jpg", ".JPG", ".jpeg", ".JPEG",  # JPEG
    ".tif", ".TIF", ".tiff", ".TIFF",  # TIFF
    ".webp", ".WEBP",  # WebP
}

# Backwards-compat alias
ARW_EXTENSIONS = {".arw"}


def _is_supported_image(path: Path, buf_size: int = 12) -> bool:
    """Quick check: does this file have a magic byte signature we can parse?

    Validates that the file is one of the supported image formats
    (JPEG, TIFF, ARW, NEF, CR2, DNG, ORF, RAF, WebP). Does NOT verify
    the file is uncorrupted; piexif will still fail gracefully on bad
    data and we record the error.
    """
    try:
        with open(path, "rb") as f:
            head = f.read(buf_size)
    except OSError:
        return False

    if not head:
        return False

    # JPEG: starts with FF D8 FF
    if head[:3] == b"\xff\xd8\xff":
        return True
    # TIFF-based RAW (ARW, NEF, CR2, DNG, ORF, WebP-via-Riff, generic TIFF)
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return True
    # Fuji RAF
    if head[:8] == b"FUJIFOTO":
        return True
    # WebP: RIFF....WEBP
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return True
    return False


def resolve_file_pair(jpg_path: Path, arw_path: Path) -> Path:
    """Resolve ARW/JPG pair, preferring ARW if it exists."""
    if arw_path.exists():
        return arw_path
    return jpg_path


def find_files_by_extensions(
    folder_path: Path,
    extensions_list: Optional[List[str]] = None,
) -> List[Path]:
    """Find image files in a directory tree.

    Files are filtered by:
    1. Extension (case-insensitive)
    2. Magic byte signature (must be a supported image format)

    If extensions_list is None, uses DEFAULT_EXTENSIONS (RAW + JPEG + TIFF).
    """
    if extensions_list is None:
        normalized = {ext.lower() for ext in DEFAULT_EXTENSIONS}
    else:
        normalized = set()
        for ext in extensions_list:
            if not ext.startswith("."):
                ext = "." + ext
            normalized.add(ext.lower())

    result: list[Path] = []
    for file_path in folder_path.rglob("*"):
        if not file_path.is_file():
            continue
        # Skip system / hidden folders
        if any(part in _SKIP_DIR_NAMES for part in file_path.parts):
            continue
        if file_path.suffix.lower() not in normalized:
            continue
        if not _is_supported_image(file_path):
            continue
        result.append(file_path)

    return sorted(result)


def _file_number(stem: str) -> Optional[int]:
    """Extract the trailing numeric sequence from a file stem.

    Camera-assigned file numbers (e.g., DSC05833 -> 5833) are unique per
    photo from the same camera session, even for burst-mode shots. Used
    as a dedup disambiguator when EXIF (5-tuple) is identical between
    two distinct photos.

    Returns None if the stem has no trailing digits.
    """
    m = _FILE_NUMBER_RE.search(stem)
    return int(m.group(1)) if m else None


def _signature(meta: PhotoMetadata) -> Optional[Tuple]:
    """Build dedup signature from already-extracted metadata.

    Returns tuple of
        (datetime_original, f_stop, shutter_speed, focal_length, iso, file_number)
    or None if the record is unusable for dedup.

    The file_number (parsed from the file stem's trailing digits) breaks
    ties between burst-mode photos that share all other EXIF fields.
    """
    if meta.error is not None:
        return None
    return (
        meta.datetime_original,
        meta.f_stop,
        meta.shutter_speed,
        meta.focal_length,
        meta.iso,
        _file_number(meta.file_path.stem),
    )


def deduplicate_metadata_list(
    metadata_list: List[PhotoMetadata],
) -> List[PhotoMetadata]:
    """Deduplicate a list of already-extracted PhotoMetadata.

    Two photos are considered duplicates when their datetime_original,
    f_stop, shutter_speed, focal_length, ISO, and the trailing numeric
    part of the file stem all match. This catches:

    - Cross-format duplicates (ARW + JPG of the same shot have the
      same file number and same EXIF).
    - Cross-folder duplicates (same content saved to multiple paths).

    It does NOT merge burst-mode photos that share all other EXIF but
    have different file numbers (DSC05898, DSC05899, etc. stay distinct).

    Operates in O(n) by using a dict of signature -> first record. EXIF is
    read exactly once per file (by the caller). The first record with a
    given signature is kept; subsequent matches are dropped.

    Args:
        metadata_list: List of PhotoMetadata records (extracted by caller).

    Returns:
        New list of deduplicated PhotoMetadata, in input order (skipping dropped).
    """
    result: list[PhotoMetadata] = []
    seen: Dict[Tuple, PhotoMetadata] = {}

    for meta in metadata_list:
        sig = _signature(meta)
        if sig is None:
            # Can't form a signature; keep the file to be safe
            result.append(meta)
            continue
        if sig in seen:
            # Exact signature already represented by an earlier file
            continue
        seen[sig] = meta
        result.append(meta)

    return result
