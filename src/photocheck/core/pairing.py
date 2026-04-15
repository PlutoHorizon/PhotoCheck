"""ARW/JPG file pairing logic for PhotoCheck."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .extractor import extract_metadata


# Only ARW extensions (case-insensitive)
ARW_EXTENSIONS = {".arw"}


def resolve_file_pair(jpg_path: Path, arw_path: Path) -> Path:
    """Resolve ARW/JPG pair, preferring ARW if it exists.

    Args:
        jpg_path: Path to potential JPG file
        arw_path: Path to potential ARW file

    Returns:
        Path to the preferred file (ARW if exists, else JPG)
    """
    if arw_path.exists():
        return arw_path
    return jpg_path


def find_files_by_extensions(
    folder_path: Path,
    extensions_list: List[str],
) -> List[Path]:
    """Find all files with given extensions in a directory tree.

    Args:
        folder_path: Root directory to search
        extensions_list: List of extensions like ['.arw', '.jpg']

    Returns:
        List of Path objects
    """
    # Normalize extensions to lowercase with dot prefix
    normalized = set()
    for ext in extensions_list:
        if not ext.startswith("."):
            ext = "." + ext
        normalized.add(ext.lower())

    # Iterate all files and filter by extension (case-insensitive)
    result = []
    for file_path in folder_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in normalized:
            result.append(file_path)

    return sorted(result)


def get_metadata_signature(
    file_path: Path,
    crop_factor: float = 1.0,
) -> Optional[Tuple]:
    """Extract metadata signature for deduplication.

    Returns tuple of (datetime_original, f_stop, shutter_speed, focal_length, iso)
    or None if extraction fails.
    """
    meta = extract_metadata(file_path, crop_factor)
    if meta.error is not None:
        return None
    return (
        meta.datetime_original,
        meta.f_stop,
        meta.shutter_speed,
        meta.focal_length,
        meta.iso,
    )


def deduplicate_by_metadata(
    file_paths: List[Path],
    crop_factor: float = 1.0,
) -> List[Path]:
    """Deduplicate ARW files based on EXIF metadata.

    Files with the same basename are considered duplicates if their
    datetime_original, f_stop, shutter_speed, focal_length, and ISO match.

    Args:
        file_paths: List of ARW file paths
        crop_factor: Crop factor for focal length

    Returns:
        List of deduplicated file paths
    """
    # Group by basename
    by_basename: Dict[str, List[Path]] = {}
    for fp in file_paths:
        base = fp.stem
        if base not in by_basename:
            by_basename[base] = []
        by_basename[base].append(fp)

    # For each group, deduplicate by metadata
    result = []
    for base, paths in by_basename.items():
        if len(paths) == 1:
            result.append(paths[0])
            continue

        # Multiple files with same basename - check metadata
        seen_signatures: Dict[Tuple, Path] = {}
        for fp in paths:
            sig = get_metadata_signature(fp, crop_factor)
            if sig is None:
                # Can't extract metadata, keep the file
                result.append(fp)
                continue
            if sig not in seen_signatures:
                seen_signatures[sig] = fp

        # Add one representative per unique signature
        result.extend(seen_signatures.values())

    return result
