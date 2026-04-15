"""Cache management for PhotoCheck using Parquet."""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .models import PhotoMetadata


def metadata_to_dataframe(metadata_list: List[PhotoMetadata]) -> pd.DataFrame:
    """Convert a list of PhotoMetadata objects to a DataFrame.

    Args:
        metadata_list: List of PhotoMetadata objects

    Returns:
        DataFrame with columns for each metadata field
    """
    records = []
    for meta in metadata_list:
        records.append({
            "file_path": str(meta.file_path),
            "shutter_speed": meta.shutter_speed,
            "iso": meta.iso,
            "focal_length": meta.focal_length,
            "f_stop": meta.f_stop,
            "lens_name": meta.lens_name,
            "datetime_original": meta.datetime_original,
            "datetime_digitized": meta.datetime_digitized,
            "datetime_modified": meta.datetime_modified,
            "camera_make": meta.camera_make,
            "camera_model": meta.camera_model,
            "error": meta.error,
            "mtime": os.path.getmtime(meta.file_path) if meta.file_path.exists() else None,
        })

    return pd.DataFrame(records)


def _nan_to_none(value):
    """Convert NaN to None, pass through other values."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (ValueError, TypeError):
        pass
    return value


def dataframe_to_metadata(df: pd.DataFrame) -> List[PhotoMetadata]:
    """Convert a DataFrame back to a list of PhotoMetadata objects.

    Args:
        df: DataFrame with metadata columns

    Returns:
        List of PhotoMetadata objects
    """
    metadata_list = []
    for _, row in df.iterrows():
        meta = PhotoMetadata(
            file_path=Path(row["file_path"]),
            shutter_speed=_nan_to_none(row.get("shutter_speed")),
            iso=_nan_to_none(row.get("iso")),
            focal_length=_nan_to_none(row.get("focal_length")),
            f_stop=_nan_to_none(row.get("f_stop")),
            lens_name=_nan_to_none(row.get("lens_name")),
            datetime_original=_nan_to_none(row.get("datetime_original")),
            datetime_digitized=_nan_to_none(row.get("datetime_digitized")),
            datetime_modified=_nan_to_none(row.get("datetime_modified")),
            camera_make=_nan_to_none(row.get("camera_make")),
            camera_model=_nan_to_none(row.get("camera_model")),
            error=_nan_to_none(row.get("error")),
        )
        metadata_list.append(meta)
    return metadata_list


def save_cache(metadata_list: List[PhotoMetadata], cache_path: Path) -> None:
    """Save metadata list to a Parquet cache file.

    Args:
        metadata_list: List of PhotoMetadata objects
        cache_path: Path to save the cache file
    """
    df = metadata_to_dataframe(metadata_list)
    df.to_parquet(cache_path, index=False)


def load_cache(cache_path: Path) -> List[PhotoMetadata]:
    """Load metadata list from a Parquet cache file.

    Args:
        cache_path: Path to the cache file

    Returns:
        List of PhotoMetadata objects, or empty list if cache doesn't exist
    """
    if not cache_path.exists():
        return []

    df = pd.read_parquet(cache_path)
    return dataframe_to_metadata(df)


def get_stale_files(
    cached_df: pd.DataFrame,
    current_files: List[Path],
) -> List[Path]:
    """Find files that have changed since cache was created.

    Args:
        cached_df: DataFrame from cache file
        current_files: List of current file paths

    Returns:
        List of file paths that are stale (mtime changed or new)
    """
    cached_paths = set(cached_df["file_path"].values)
    current_paths = {str(p) for p in current_files}

    stale = []

    # Check for new or modified files
    for file_path in current_files:
        str_path = str(file_path)
        if str_path not in cached_paths:
            stale.append(file_path)
            continue

        # Check mtime
        cached_mtime = cached_df[cached_df["file_path"] == str_path]["mtime"].values
        if len(cached_mtime) > 0:
            current_mtime = os.path.getmtime(file_path)
            if cached_mtime[0] != current_mtime:
                stale.append(file_path)

    return stale
