"""ARW/JPG file pairing logic for PhotoCheck."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import PhotoMetadata


# Only ARW extensions (case-insensitive)
ARW_EXTENSIONS = {".arw"}


def resolve_file_pair(jpg_path: Path, arw_path: Path) -> Path:
    """Resolve ARW/JPG pair, preferring ARW if it exists."""
    if arw_path.exists():
        return arw_path
    return jpg_path


def find_files_by_extensions(
    folder_path: Path,
    extensions_list: List[str],
) -> List[Path]:
    """Find all files with given extensions in a directory tree."""
    normalized = set()
    for ext in extensions_list:
        if not ext.startswith("."):
            ext = "." + ext
        normalized.add(ext.lower())

    result = []
    for file_path in folder_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in normalized:
            result.append(file_path)

    return sorted(result)


def _signature(meta: PhotoMetadata) -> Optional[Tuple]:
    """Build dedup signature from already-extracted metadata.

    Returns tuple of (datetime_original, f_stop, shutter_speed, focal_length, iso)
    or None if the record is unusable for dedup (extraction error or missing
    key fields). Returns None intentionally so callers can keep the file.
    """
    if meta.error is not None:
        return None
    return (
        meta.datetime_original,
        meta.f_stop,
        meta.shutter_speed,
        meta.focal_length,
        meta.iso,
    )


def deduplicate_metadata_list(
    metadata_list: List[PhotoMetadata],
) -> List[PhotoMetadata]:
    """Deduplicate a list of already-extracted PhotoMetadata.

    Files with the same basename are considered duplicates if their
    datetime_original, f_stop, shutter_speed, focal_length, and ISO match.

    Operates in-memory on already-extracted records, so EXIF is read
    exactly once per file (by the caller). The first record encountered
    with a given signature is kept; subsequent matches are dropped.

    Args:
        metadata_list: List of PhotoMetadata records (extracted by caller).

    Returns:
        New list of deduplicated PhotoMetadata, in input order (skipping dropped).
    """
    by_basename: Dict[str, List[PhotoMetadata]] = {}
    for meta in metadata_list:
        by_basename.setdefault(meta.file_path.stem, []).append(meta)

    result: list[PhotoMetadata] = []
    for base, group in by_basename.items():
        if len(group) == 1:
            result.append(group[0])
            continue
        seen: set = set()
        for meta in group:
            sig = _signature(meta)
            if sig is None:
                # Can't form a signature; keep the file to be safe
                result.append(meta)
                continue
            if sig not in seen:
                seen.add(sig)
                result.append(meta)
            # else: exact signature already represented by an earlier file

    return result
