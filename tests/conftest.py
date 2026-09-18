"""Pytest config: ensure src/ is on sys.path so `import photocheck` works."""

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from photocheck.core.models import PhotoMetadata  # noqa: E402


def _parse_dt(s):
    return datetime.fromisoformat(s) if s else None


def _load_fixture(name: str) -> list[PhotoMetadata]:
    path = _ROOT / "tests" / "fixtures" / name
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [
        PhotoMetadata(
            file_path=Path(item["file_path"]),
            shutter_speed=item.get("shutter_speed"),
            iso=item.get("iso"),
            focal_length=item.get("focal_length"),
            f_stop=item.get("f_stop"),
            lens_name=item.get("lens_name"),
            datetime_original=_parse_dt(item.get("datetime_original")),
            datetime_digitized=_parse_dt(item.get("datetime_digitized")),
            datetime_modified=_parse_dt(item.get("datetime_modified")),
            camera_make=item.get("camera_make"),
            camera_model=item.get("camera_model"),
            error=item.get("error"),
        )
        for item in raw
    ]


@pytest.fixture
def sample_metadata() -> list[PhotoMetadata]:
    return _load_fixture("sample_metadata.json")


@pytest.fixture
def empty_metadata() -> list[PhotoMetadata]:
    return _load_fixture("empty_metadata.json")


@pytest.fixture
def partial_metadata() -> list[PhotoMetadata]:
    return _load_fixture("partial_metadata.json")
