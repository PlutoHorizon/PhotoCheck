"""Data models for PhotoCheck."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class PhotoMetadata:
    """Metadata extracted from a single photo."""

    file_path: Path
    shutter_speed: Optional[float] = None  # seconds
    iso: Optional[int] = None
    focal_length: Optional[float] = None  # mm (after crop factor)
    f_stop: Optional[float] = None
    lens_name: Optional[str] = None
    datetime_original: Optional[datetime] = None
    datetime_digitized: Optional[datetime] = None
    datetime_modified: Optional[datetime] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    error: Optional[str] = None

    @property
    def focal_length_35mm(self) -> Optional[float]:
        """Return focal length assuming full-frame equivalent."""
        return self.focal_length
