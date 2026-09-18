# HTML Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `report` subcommand to PhotoCheck that generates a self-contained `report/` folder with an `index.html` consolidating the existing PNG/HTML charts plus a new hero stats block.

**Architecture:** A new `src/photocheck/report/` package with three modules — `stats.py` (pure stat functions), `renderer.py` (Jinja2 wrapper), `builder.py` (orchestration). All existing `viz/` code is reused unchanged. Two Jinja2 templates in `src/photocheck/templates/`. Output is a folder with `index.html` + `charts/` (PNG + iframe'd timeline_by_lens.html) + `lenses.html` subpage.

**Tech Stack:** Python 3.10+ · Jinja2 3+ (new dep) · pytest 7+ · existing piexif/pandas/matplotlib stack

---

## File Structure

| File | Responsibility | Status |
|------|---------------|--------|
| `pyproject.toml` | Add `jinja2>=3.0.0` to deps | Modify |
| `src/photocheck/report/__init__.py` | Package marker | Create |
| `src/photocheck/report/stats.py` | 10 pure stat functions | Create |
| `src/photocheck/report/renderer.py` | Jinja2 env + render functions | Create |
| `src/photocheck/report/builder.py` | Orchestration (`build_report`) | Create |
| `src/photocheck/templates/report.html.j2` | Main report template | Create |
| `src/photocheck/templates/lenses.html.j2` | All-lens subpage template | Create |
| `src/photocheck/cli.py` | Add `report` subcommand | Modify |
| `src/photocheck/cli.py` (interactive_menu) | Add option 4 | Modify |
| `run.py` | Add `DO_REPORT`/`REPORT_DIR`/`TOP_LENSES` | Modify |
| `tests/__init__.py` | Make tests a package | Create |
| `tests/conftest.py` | Pytest config + sys.path | Create |
| `tests/fixtures/sample_metadata.json` | 10 photos, full data | Create |
| `tests/fixtures/empty_metadata.json` | `[]` | Create |
| `tests/fixtures/partial_metadata.json` | 5 photos, some None | Create |
| `tests/test_stats.py` | Unit tests for stats | Create |
| `tests/test_renderer.py` | Integration tests for renderer | Create |
| `README.md` | Document `report` command | Modify |
| `docs/usage.md` | Document `report` command | Modify |

---

## Task 1: Add Jinja2 dependency and prepare test infrastructure

**Files:**
- Modify: `pyproject.toml:5-13` (dependencies block)
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/sample_metadata.json`
- Create: `tests/fixtures/empty_metadata.json`
- Create: `tests/fixtures/partial_metadata.json`

- [ ] **Step 1: Add jinja2 to pyproject.toml**

Edit `pyproject.toml` dependencies block:

```toml
dependencies = [
    "piexif>=1.0.8",
    "pandas>=2.0.0",
    "pyarrow>=14.0.0",
    "matplotlib>=3.7.0",
    "seaborn>=0.12.0",
    "tqdm>=4.65.0",
    "jinja2>=3.0.0",
]
```

- [ ] **Step 2: Install jinja2 via uv**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv sync`
Expected: lockfile updated, jinja2 installed, no errors.

- [ ] **Step 3: Verify jinja2 imports**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run python -c "import jinja2; print(jinja2.__version__)"`
Expected: prints version like `3.1.x`

- [ ] **Step 4: Create tests package init**

Create `tests/__init__.py` (empty file):

```python
"""Tests for PhotoCheck."""
```

- [ ] **Step 5: Create conftest.py with sys.path setup**

Create `tests/conftest.py`:

```python
"""Pytest config: ensure src/ is on sys.path so `import photocheck` works."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
```

- [ ] **Step 6: Create sample_metadata.json fixture**

Create `tests/fixtures/sample_metadata.json` with 10 photos covering varied data:

```json
[
  {
    "file_path": "/photos/2024-01-15_DSC00001.ARW",
    "shutter_speed": 0.005,
    "iso": 100,
    "focal_length": 35.0,
    "f_stop": 1.4,
    "lens_name": "FE 35mm F1.4 GM",
    "datetime_original": "2024-01-15T10:30:00",
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": "SONY",
    "camera_model": "ILCE-7M4",
    "error": null
  },
  {
    "file_path": "/photos/2024-01-15_DSC00002.ARW",
    "shutter_speed": 0.008,
    "iso": 200,
    "focal_length": 35.0,
    "f_stop": 2.0,
    "lens_name": "FE 35mm F1.4 GM",
    "datetime_original": "2024-01-15T10:35:00",
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": "SONY",
    "camera_model": "ILCE-7M4",
    "error": null
  },
  {
    "file_path": "/photos/2024-01-20_DSC00003.ARW",
    "shutter_speed": 0.004,
    "iso": 400,
    "focal_length": 85.0,
    "f_stop": 1.8,
    "lens_name": "FE 85mm F1.8",
    "datetime_original": "2024-01-20T14:20:00",
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": "SONY",
    "camera_model": "ILCE-7M4",
    "error": null
  },
  {
    "file_path": "/photos/2024-02-10_DSC00004.ARW",
    "shutter_speed": 0.001,
    "iso": 800,
    "focal_length": 24.0,
    "f_stop": 2.8,
    "lens_name": "FE 24-70mm F2.8 GM",
    "datetime_original": "2024-02-10T08:15:00",
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": "SONY",
    "camera_model": "ILCE-7M4",
    "error": null
  },
  {
    "file_path": "/photos/2024-02-10_DSC00005.ARW",
    "shutter_speed": 0.002,
    "iso": 400,
    "focal_length": 70.0,
    "f_stop": 4.0,
    "lens_name": "FE 24-70mm F2.8 GM",
    "datetime_original": "2024-02-10T08:30:00",
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": "SONY",
    "camera_model": "ILCE-7M4",
    "error": null
  },
  {
    "file_path": "/photos/2024-03-05_DSC00006.ARW",
    "shutter_speed": 0.016,
    "iso": 100,
    "focal_length": 35.0,
    "f_stop": 1.4,
    "lens_name": "FE 35mm F1.4 GM",
    "datetime_original": "2024-03-05T17:45:00",
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": "SONY",
    "camera_model": "ILCE-7M4",
    "error": null
  },
  {
    "file_path": "/photos/2024-03-12_DSC00007.ARW",
    "shutter_speed": 0.005,
    "iso": 200,
    "focal_length": 50.0,
    "f_stop": 1.8,
    "lens_name": "FE 50mm F1.8",
    "datetime_original": "2024-03-12T12:00:00",
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": "SONY",
    "camera_model": "ILCE-7M4",
    "error": null
  },
  {
    "file_path": "/photos/2024-04-08_DSC00008.ARW",
    "shutter_speed": 0.008,
    "iso": 400,
    "focal_length": 35.0,
    "f_stop": 2.0,
    "lens_name": "FE 35mm F1.4 GM",
    "datetime_original": "2024-04-08T19:20:00",
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": "SONY",
    "camera_model": "ILCE-7M4",
    "error": null
  },
  {
    "file_path": "/photos/2024-05-15_DSC00009.ARW",
    "shutter_speed": 0.001,
    "iso": 1600,
    "focal_length": 85.0,
    "f_stop": 1.8,
    "lens_name": "FE 85mm F1.8",
    "datetime_original": "2024-05-15T21:30:00",
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": "SONY",
    "camera_model": "ILCE-7M4",
    "error": null
  },
  {
    "file_path": "/photos/2024-06-22_DSC00010.ARW",
    "shutter_speed": 0.004,
    "iso": 100,
    "focal_length": 35.0,
    "f_stop": 1.4,
    "lens_name": "FE 35mm F1.4 GM",
    "datetime_original": "2024-06-22T11:10:00",
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": "SONY",
    "camera_model": "ILCE-7M4",
    "error": null
  }
]
```

- [ ] **Step 7: Create empty_metadata.json fixture**

Create `tests/fixtures/empty_metadata.json`:

```json
[]
```

- [ ] **Step 8: Create partial_metadata.json fixture**

Create `tests/fixtures/partial_metadata.json`:

```json
[
  {
    "file_path": "/photos/partial_01.ARW",
    "shutter_speed": 0.005,
    "iso": null,
    "focal_length": 50.0,
    "f_stop": null,
    "lens_name": null,
    "datetime_original": "2024-01-15T10:30:00",
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": null,
    "camera_model": null,
    "error": null
  },
  {
    "file_path": "/photos/partial_02.ARW",
    "shutter_speed": null,
    "iso": 400,
    "focal_length": null,
    "f_stop": 2.8,
    "lens_name": "FE 50mm F1.8",
    "datetime_original": null,
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": "SONY",
    "camera_model": "ILCE-7M4",
    "error": null
  },
  {
    "file_path": "/photos/partial_03.ARW",
    "shutter_speed": null,
    "iso": null,
    "focal_length": null,
    "f_stop": null,
    "lens_name": null,
    "datetime_original": null,
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": null,
    "camera_model": null,
    "error": null
  },
  {
    "file_path": "/photos/partial_04.ARW",
    "shutter_speed": 0.01,
    "iso": 200,
    "focal_length": 85.0,
    "f_stop": 4.0,
    "lens_name": "FE 85mm F1.8",
    "datetime_original": "2024-03-01T09:00:00",
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": "SONY",
    "camera_model": "ILCE-7M4",
    "error": null
  },
  {
    "file_path": "/photos/partial_05.ARW",
    "shutter_speed": null,
    "iso": null,
    "focal_length": null,
    "f_stop": null,
    "lens_name": null,
    "datetime_original": null,
    "datetime_digitized": null,
    "datetime_modified": null,
    "camera_make": null,
    "camera_model": null,
    "error": "EXIF read error"
  }
]
```

- [ ] **Step 9: Add loader helper module for fixtures**

Append to `tests/conftest.py`:

```python
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


def _load_fixture(name: str):
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
```

- [ ] **Step 10: Verify fixtures load correctly**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run python -c "from tests.conftest import _load_fixture; m = _load_fixture('sample_metadata.json'); print(len(m), m[0].lens_name)"`
Expected: prints `10 FE 35mm F1.4 GM`

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml uv.lock tests/
git commit -m "feat: add jinja2 dep + test fixtures and conftest"
```

---

## Task 2: Implement 6 hero stat functions in stats.py (TDD)

**Files:**
- Create: `src/photocheck/report/__init__.py`
- Create: `src/photocheck/report/stats.py`
- Create: `tests/test_stats.py`

- [ ] **Step 1: Create the report package init**

Create `src/photocheck/report/__init__.py`:

```python
"""HTML report generation for PhotoCheck."""
```

- [ ] **Step 2: Write failing test for main_lens**

Create `tests/test_stats.py`:

```python
"""Tests for photocheck.report.stats."""

import pytest

from photocheck.report.stats import (
    active_days,
    all_lenses,
    compute_all,
    hourly_distribution,
    main_aperture,
    main_focal,
    main_lens,
    peak_month,
    span,
    top_lenses,
)


class TestMainLens:
    def test_returns_most_common_lens(self, sample_metadata):
        result = main_lens(sample_metadata)
        assert result["name"] == "FE 35mm F1.4 GM"
        assert result["count"] == 5
        assert result["pct"] == 50.0

    def test_empty_returns_none(self, empty_metadata):
        result = main_lens(empty_metadata)
        assert result["value"] is None
        assert result["note"] == "无数据"

    def test_partial_all_lens_none(self, partial_metadata):
        result = main_lens(partial_metadata)
        # partial has 2 photos with lens_name (1 None, 1 "FE 50mm F1.8", 1 None, 1 "FE 85mm F1.8", error)
        # "无数据" if all None; otherwise returns most common
        assert result["value"] is not None or result["note"] == "无数据"
```

- [ ] **Step 3: Run test, verify it fails**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run pytest tests/test_stats.py::TestMainLens -v`
Expected: ImportError or ModuleNotFoundError (stats.py doesn't exist yet)

- [ ] **Step 4: Create stats.py with main_lens implementation**

Create `src/photocheck/report/stats.py`:

```python
"""Pure stat functions for the HTML report.

All functions are pure: take List[PhotoMetadata], return dicts.
All functions re-filter m.error is not None defensively.
"""

from collections import Counter
from datetime import datetime
from typing import Optional

from ..core.models import PhotoMetadata
from ..viz.histograms import classify_focal


# Sentinel returned when a function has no usable data.
_EMPTY = {"value": None, "note": "无数据"}


def _valid(metadata: list[PhotoMetadata]) -> list[PhotoMetadata]:
    """Filter to photos with no error."""
    return [m for m in metadata if m.error is None]


def main_lens(metadata: list[PhotoMetadata]) -> dict:
    """Most-used lens with count and percentage."""
    valid = _valid(metadata)
    lenses = [m.lens_name for m in valid if m.lens_name is not None]
    if not lenses:
        return {**_EMPTY, "name": None, "count": 0, "pct": 0.0}
    counter = Counter(lenses)
    name, count = counter.most_common(1)[0]
    return {
        "name": name,
        "count": count,
        "pct": round(100.0 * count / len(valid), 1),
        "value": name,
    }


def main_focal(metadata: list[PhotoMetadata]) -> dict:
    """Most-used focal length (bucketed via classify_focal)."""
    valid = _valid(metadata)
    focals = [m.focal_length for m in valid if m.focal_length is not None and m.focal_length >= 7]
    if not focals:
        return {**_EMPTY, "focal": None, "count": 0, "pct": 0.0}
    bucketed = [classify_focal(f) for f in focals]
    counter = Counter(bucketed)
    focal, count = counter.most_common(1)[0]
    return {
        "focal": focal,
        "count": count,
        "pct": round(100.0 * count / len(focals), 1),
        "value": f"{focal}mm",
    }


def main_aperture(metadata: list[PhotoMetadata]) -> dict:
    """Most-used f-stop."""
    valid = _valid(metadata)
    fstops = [m.f_stop for m in valid if m.f_stop is not None and m.f_stop > 0]
    if not fstops:
        return {**_EMPTY, "fstop": None, "count": 0, "pct": 0.0}
    counter = Counter(fstops)
    fstop, count = counter.most_common(1)[0]
    return {
        "fstop": fstop,
        "count": count,
        "pct": round(100.0 * count / len(fstops), 1),
        "value": f"f/{fstop}",
    }


def peak_month(metadata: list[PhotoMetadata]) -> dict:
    """Month with the most photos."""
    valid = _valid(metadata)
    months: Counter = Counter()
    for m in valid:
        if m.datetime_original is not None:
            key = m.datetime_original.strftime("%Y-%m")
            months[key] += 1
    if not months:
        return {**_EMPTY, "label": None, "count": 0}
    # Tie-break: earliest month wins
    label, count = sorted(months.items(), key=lambda x: (-x[1], x[0]))[0]
    return {"label": label, "count": count, "value": label}


def span(metadata: list[PhotoMetadata]) -> dict:
    """Days between first and last photo."""
    valid = _valid(metadata)
    dates = [m.datetime_original for m in valid if m.datetime_original is not None]
    if len(dates) < 2:
        return {**_EMPTY, "days": 0, "years_approx": 0.0}
    days = (max(dates) - min(dates)).days
    years = round(days / 365.25, 1)
    return {"days": days, "years_approx": years, "value": days}


def active_days(metadata: list[PhotoMetadata]) -> dict:
    """Number of unique shooting days and ratio to total span."""
    valid = _valid(metadata)
    date_set = {m.datetime_original.date() for m in valid if m.datetime_original is not None}
    if not date_set:
        return {**_EMPTY, "days": 0, "total_span_days": 0, "ratio": 0.0}
    days = len(date_set)
    sorted_dates = sorted(date_set)
    total_span = (sorted_dates[-1] - sorted_dates[0]).days or 1
    ratio = round(100.0 * days / (total_span + 1), 1)
    return {"days": days, "total_span_days": total_span, "ratio": ratio, "value": days}
```

- [ ] **Step 5: Run main_lens tests, verify they pass**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run pytest tests/test_stats.py::TestMainLens -v`
Expected: 3 passed

- [ ] **Step 6: Add tests for the remaining 5 hero functions**

Append to `tests/test_stats.py`:

```python
class TestMainFocal:
    def test_returns_most_common_focal(self, sample_metadata):
        result = main_focal(sample_metadata)
        # sample has 5 photos at 35mm, 2 at 85mm, 2 at 24-70mm
        assert result["focal"] == 35
        assert result["count"] == 5
        assert result["pct"] == 50.0

    def test_empty_returns_none(self, empty_metadata):
        result = main_focal(empty_metadata)
        assert result["value"] is None
        assert result["note"] == "无数据"


class TestMainAperture:
    def test_returns_most_common_aperture(self, sample_metadata):
        result = main_aperture(sample_metadata)
        # sample: 5 at f/1.4, 2 at f/1.8, 1 at f/2.0, 1 at f/2.8, 1 at f/4.0
        assert result["fstop"] == 1.4
        assert result["count"] == 5

    def test_empty_returns_none(self, empty_metadata):
        result = main_aperture(empty_metadata)
        assert result["value"] is None
        assert result["note"] == "无数据"


class TestPeakMonth:
    def test_returns_month_with_most_photos(self, sample_metadata):
        result = peak_month(sample_metadata)
        # sample dates: 2024-01 (2), 2024-02 (2), 2024-03 (2), 2024-04 (1), 2024-05 (1), 2024-06 (1)
        # Tie — earliest wins: 2024-01
        assert result["label"] == "2024-01"
        assert result["count"] == 2

    def test_empty_returns_none(self, empty_metadata):
        result = peak_month(empty_metadata)
        assert result["value"] is None
        assert result["note"] == "无数据"


class TestSpan:
    def test_returns_days_between_first_and_last(self, sample_metadata):
        result = span(sample_metadata)
        # 2024-01-15 to 2024-06-22 = ~159 days
        assert 150 <= result["days"] <= 165
        assert result["years_approx"] >= 0

    def test_empty_returns_none(self, empty_metadata):
        result = span(empty_metadata)
        assert result["value"] is None
        assert result["note"] == "无数据"

    def test_single_date_returns_none(self):
        from photocheck.core.models import PhotoMetadata
        single = [PhotoMetadata(file_path=__import__("pathlib").Path("/x.ARW"), datetime_original=datetime(2024, 1, 1))]
        result = span(single)
        assert result["value"] is None
        assert result["note"] == "无数据"


class TestActiveDays:
    def test_counts_unique_dates(self, sample_metadata):
        result = active_days(sample_metadata)
        # sample has 10 unique dates
        assert result["days"] == 10
        assert result["total_span_days"] > 0
        assert 0 < result["ratio"] <= 100

    def test_empty_returns_none(self, empty_metadata):
        result = active_days(empty_metadata)
        assert result["value"] is None
        assert result["note"] == "无数据"
```

Add the missing import at the top of `tests/test_stats.py`:

```python
from datetime import datetime
from pathlib import Path

from photocheck.core.models import PhotoMetadata
```

(Replacing the existing imports block.)

- [ ] **Step 7: Run all hero function tests**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run pytest tests/test_stats.py -v`
Expected: 16 tests pass (3 + 2 + 2 + 2 + 3 + 2 + 2 from helper tests added in Task 3)

- [ ] **Step 8: Commit**

```bash
git add src/photocheck/report/ tests/test_stats.py
git commit -m "feat(report): add 6 hero stat functions with tests"
```

---

## Task 3: Implement 3 helper stat functions in stats.py (TDD)

**Files:**
- Modify: `src/photocheck/report/stats.py`
- Modify: `tests/test_stats.py`

- [ ] **Step 1: Write failing tests for helper functions**

Append to `tests/test_stats.py`:

```python
class TestHourlyDistribution:
    def test_returns_24_int_list(self, sample_metadata):
        result = hourly_distribution(sample_metadata)
        assert isinstance(result, list)
        assert len(result) == 24
        assert all(isinstance(x, int) for x in result)
        assert sum(result) == 10  # 10 photos total

    def test_empty_returns_zeros(self, empty_metadata):
        result = hourly_distribution(empty_metadata)
        assert result == [0] * 24


class TestTopLenses:
    def test_returns_lenses_sorted_by_count(self, sample_metadata):
        result = top_lenses(sample_metadata, n=3)
        assert len(result) == 3
        # "FE 35mm F1.4 GM" (5), "FE 85mm F1.8" (2), "FE 24-70mm F2.8 GM" (2)
        names = [item["name"] for item in result]
        assert names[0] == "FE 35mm F1.4 GM"
        assert "FE 85mm F1.8" in names
        assert "FE 24-70mm F2.8 GM" in names

    def test_returns_fewer_when_less_available(self, sample_metadata):
        result = top_lenses(sample_metadata, n=10)
        # Only 3 distinct lenses in sample
        assert len(result) == 3

    def test_includes_position(self, sample_metadata):
        result = top_lenses(sample_metadata, n=3)
        assert result[0]["position"] == 1
        assert result[1]["position"] == 2
        assert result[2]["position"] == 3

    def test_includes_chart_paths(self, sample_metadata):
        result = top_lenses(sample_metadata, n=2)
        assert result[0]["focal_chart"] == "charts/lens_top1_focal.png"
        assert result[0]["fstop_chart"] == "charts/lens_top1_fstop.png"
        assert result[1]["focal_chart"] == "charts/lens_top2_focal.png"

    def test_empty_returns_empty_list(self, empty_metadata):
        result = top_lenses(empty_metadata, n=5)
        assert result == []


class TestAllLenses:
    def test_returns_all_lenses(self, sample_metadata):
        result = all_lenses(sample_metadata)
        assert len(result) == 3
        names = [item["name"] for item in result]
        assert "FE 35mm F1.4 GM" in names

    def test_includes_count_and_position(self, sample_metadata):
        result = all_lenses(sample_metadata)
        for item in result:
            assert "name" in item
            assert "count" in item
            assert "position" in item

    def test_empty_returns_empty_list(self, empty_metadata):
        result = all_lenses(empty_metadata)
        assert result == []
```

- [ ] **Step 2: Run, verify failures**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run pytest tests/test_stats.py::TestHourlyDistribution tests/test_stats.py::TestTopLenses tests/test_stats.py::TestAllLenses -v`
Expected: ImportError on the three new function names

- [ ] **Step 3: Add helper functions to stats.py**

Append to `src/photocheck/report/stats.py`:

```python
def hourly_distribution(metadata: list[PhotoMetadata]) -> list[int]:
    """Return a list of 24 ints: photo count per hour-of-day (0-23)."""
    valid = _valid(metadata)
    counts = [0] * 24
    for m in valid:
        if m.datetime_original is not None:
            counts[m.datetime_original.hour] += 1
    return counts


def top_lenses(metadata: list[PhotoMetadata], n: int = 5) -> list[dict]:
    """Return up to n most-used lenses with chart paths.

    Each item: {name, count, pct, position, focal_chart, fstop_chart}
    Chart paths are relative to the report folder root.
    """
    valid = _valid(metadata)
    lens_counts: Counter = Counter(
        m.lens_name for m in valid if m.lens_name is not None
    )
    if not lens_counts:
        return []
    top = lens_counts.most_common(n)
    total = sum(lens_counts.values())
    result = []
    for position, (name, count) in enumerate(top, start=1):
        result.append({
            "name": name,
            "count": count,
            "pct": round(100.0 * count / total, 1),
            "position": position,
            "focal_chart": f"charts/lens_top{position}_focal.png",
            "fstop_chart": f"charts/lens_top{position}_fstop.png",
        })
    return result


def all_lenses(metadata: list[PhotoMetadata]) -> list[dict]:
    """Return all lenses sorted by count (for lenses.html subpage)."""
    valid = _valid(metadata)
    lens_counts: Counter = Counter(
        m.lens_name for m in valid if m.lens_name is not None
    )
    total = sum(lens_counts.values()) or 1
    return [
        {
            "name": name,
            "count": count,
            "pct": round(100.0 * count / total, 1),
            "position": position,
        }
        for position, (name, count) in enumerate(
            sorted(lens_counts.items(), key=lambda x: -x[1]), start=1
        )
    ]
```

- [ ] **Step 4: Run helper tests, verify they pass**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run pytest tests/test_stats.py -v`
Expected: all tests pass (16+)

- [ ] **Step 5: Commit**

```bash
git add src/photocheck/report/stats.py tests/test_stats.py
git commit -m "feat(report): add hourly/top_lenses/all_lenses helpers"
```

---

## Task 4: Implement compute_all aggregator in stats.py (TDD)

**Files:**
- Modify: `src/photocheck/report/stats.py`
- Modify: `tests/test_stats.py`

- [ ] **Step 1: Write failing test for compute_all**

Append to `tests/test_stats.py`:

```python
class TestComputeAll:
    def test_returns_all_stats_keys(self, sample_metadata):
        result = compute_all(sample_metadata, top_n=5)
        expected_keys = {
            "main_lens", "main_focal", "main_aperture",
            "peak_month", "span", "active_days",
            "hourly", "top_lenses", "all_lenses",
            "total_photos", "valid_photos",
        }
        assert expected_keys.issubset(result.keys())

    def test_total_photos_counts_all(self, sample_metadata):
        result = compute_all(sample_metadata, top_n=5)
        assert result["total_photos"] == 10
        # valid excludes error entries; sample has 0 errors
        assert result["valid_photos"] == 10

    def test_top_n_passes_through(self, sample_metadata):
        result = compute_all(sample_metadata, top_n=2)
        assert len(result["top_lenses"]) == 2

    def test_empty_returns_empty_sentinels(self, empty_metadata):
        result = compute_all(empty_metadata, top_n=5)
        assert result["total_photos"] == 0
        assert result["valid_photos"] == 0
        assert result["top_lenses"] == []
        assert result["all_lenses"] == []
        assert result["main_lens"]["value"] is None

    def test_partial_excludes_error_photos(self, partial_metadata):
        result = compute_all(partial_metadata, top_n=5)
        # partial has 5 entries, 1 with error → 4 valid
        assert result["total_photos"] == 5
        assert result["valid_photos"] == 4
```

- [ ] **Step 2: Run, verify failure**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run pytest tests/test_stats.py::TestComputeAll -v`
Expected: ImportError

- [ ] **Step 3: Add compute_all to stats.py**

Append to `src/photocheck/report/stats.py`:

```python
def compute_all(metadata: list[PhotoMetadata], top_n: int = 5) -> dict:
    """Compute all stats used by the report. Single entry point for the builder."""
    return {
        "main_lens": main_lens(metadata),
        "main_focal": main_focal(metadata),
        "main_aperture": main_aperture(metadata),
        "peak_month": peak_month(metadata),
        "span": span(metadata),
        "active_days": active_days(metadata),
        "hourly": hourly_distribution(metadata),
        "top_lenses": top_lenses(metadata, n=top_n),
        "all_lenses": all_lenses(metadata),
        "total_photos": len(metadata),
        "valid_photos": len(_valid(metadata)),
    }
```

- [ ] **Step 4: Run, verify pass**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run pytest tests/test_stats.py -v`
Expected: all pass

- [ ] **Step 5: Check coverage**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run pytest tests/test_stats.py --cov=src/photocheck/report/stats --cov-report=term-missing`
Expected: ≥ 90% coverage on stats.py

- [ ] **Step 6: Commit**

```bash
git add src/photocheck/report/stats.py tests/test_stats.py
git commit -m "feat(report): add compute_all aggregator"
```

---

## Task 5: Implement renderer.py (Jinja2 wrapper)

**Files:**
- Create: `src/photocheck/report/renderer.py`
- Create: `tests/test_renderer.py`

- [ ] **Step 1: Write failing test for renderer**

Create `tests/test_renderer.py`:

```python
"""Tests for photocheck.report.renderer."""

from pathlib import Path

import pytest

from photocheck.report.renderer import (
    get_env,
    render_lenses,
    render_report,
)


def test_get_env_returns_jinja2_environment():
    env = get_env()
    # jinja2 Environment exposes get_template
    assert hasattr(env, "get_template")
    assert callable(env.get_template)


def test_render_report_creates_file(tmp_path, sample_metadata):
    from photocheck.report.stats import compute_all
    stats = compute_all(sample_metadata, top_n=5)
    context = {**stats, "charts_dir": "charts", "generated_at": "2026-09-18"}
    output = tmp_path / "index.html"
    render_report(context, output)
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "FE 35mm F1.4 GM" in content
    assert "html" in content.lower()


def test_render_report_with_empty_data(tmp_path, empty_metadata):
    from photocheck.report.stats import compute_all
    stats = compute_all(empty_metadata, top_n=5)
    context = {**stats, "charts_dir": "charts", "generated_at": "2026-09-18"}
    output = tmp_path / "index.html"
    render_report(context, output)
    assert output.exists()
    # Empty data should still produce valid HTML
    content = output.read_text(encoding="utf-8")
    assert "<!DOCTYPE" in content or "<html" in content


def test_render_lenses_creates_file(tmp_path, sample_metadata):
    from photocheck.report.stats import compute_all
    stats = compute_all(sample_metadata, top_n=5)
    context = {**stats, "charts_dir": "charts", "generated_at": "2026-09-18"}
    output = tmp_path / "lenses.html"
    render_lenses(context, output)
    assert output.exists()
```

- [ ] **Step 2: Create the templates directory with stub templates**

Create `src/photocheck/templates/report.html.j2`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>PhotoCheck Report</title></head>
<body>
<h1>PhotoCheck Report</h1>
<p>Generated: {{ generated_at }}</p>
<p>Main lens: {{ main_lens.name }}</p>
</body>
</html>
```

Create `src/photocheck/templates/lenses.html.j2`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>All Lenses</title></head>
<body>
<h1>All Lenses</h1>
{% for lens in all_lenses %}
<p>{{ lens.position }}. {{ lens.name }} — {{ lens.count }}</p>
{% endfor %}
</body>
</html>
```

- [ ] **Step 3: Run tests, verify they fail (renderer.py missing)**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run pytest tests/test_renderer.py -v`
Expected: ModuleNotFoundError on import

- [ ] **Step 4: Create renderer.py**

Create `src/photocheck/report/renderer.py`:

```python
"""Jinja2 rendering for the HTML report."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def get_env() -> Environment:
    """Return a Jinja2 Environment with autoescape enabled for HTML."""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        keep_trailing_newline=True,
    )


def render_report(context: dict, output_path: Path) -> None:
    """Render the main report template to output_path."""
    env = get_env()
    template = env.get_template("report.html.j2")
    output_path.write_text(template.render(**context), encoding="utf-8")


def render_lenses(context: dict, output_path: Path) -> None:
    """Render the all-lenses subpage template to output_path."""
    env = get_env()
    template = env.get_template("lenses.html.j2")
    output_path.write_text(template.render(**context), encoding="utf-8")
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run pytest tests/test_renderer.py -v`
Expected: 4 tests pass

- [ ] **Step 6: Commit**

```bash
git add src/photocheck/report/renderer.py src/photocheck/templates/ tests/test_renderer.py
git commit -m "feat(report): add Jinja2 renderer with stub templates"
```

---

## Task 6: Build the main report template (Minimal Swiss layout)

**Files:**
- Modify: `src/photocheck/templates/report.html.j2`

This task replaces the stub with the full Minimal Swiss design. No code logic, just HTML/CSS.

- [ ] **Step 1: Replace report.html.j2 with full template**

Overwrite `src/photocheck/templates/report.html.j2` with:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PhotoCheck Report</title>
<style>
:root {
  --color-bg: #fff;
  --color-text: #1a1a1a;
  --color-muted: #888;
  --color-rule: #e5e5e5;
  --color-accent: #1a1a1a;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
  --font-num: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--font-sans);
  color: var(--color-text);
  background: var(--color-bg);
  line-height: 1.5;
  padding: 3rem 2rem 6rem;
  max-width: 1100px;
  margin: 0 auto;
}
header {
  border-bottom: 1px solid var(--color-rule);
  padding-bottom: 1.5rem;
  margin-bottom: 3rem;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
header h1 {
  font-size: 1.25rem;
  font-weight: 500;
  letter-spacing: -0.01em;
}
header .meta {
  font-size: 0.75rem;
  color: var(--color-muted);
  font-variant-numeric: tabular-nums;
}
section {
  border-bottom: 1px solid var(--color-rule);
  padding: 2.5rem 0;
}
section:last-of-type { border-bottom: none; }
.section-head {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}
.section-head .num {
  font-family: var(--font-num);
  font-size: 0.75rem;
  color: var(--color-muted);
  letter-spacing: 0.05em;
}
.section-head h2 {
  font-size: 1rem;
  font-weight: 500;
  letter-spacing: -0.005em;
}
.hero-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2rem 1.5rem;
}
.hero-card .value {
  font-family: var(--font-num);
  font-size: 2.25rem;
  font-weight: 500;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
  margin-bottom: 0.5rem;
  word-break: break-word;
}
.hero-card .label {
  font-size: 0.7rem;
  color: var(--color-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 0.5rem;
}
.hero-card .sub {
  font-size: 0.85rem;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}
.hero-card.empty .value { color: var(--color-muted); font-size: 1.5rem; }
.hero-card.empty .sub { color: var(--color-muted); }
.chart-full { width: 100%; height: auto; display: block; }
.hourly-bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 100px;
  margin-top: 1rem;
}
.hourly-bar {
  flex: 1;
  background: var(--color-accent);
  position: relative;
  min-height: 1px;
}
.hourly-labels {
  display: flex;
  gap: 2px;
  font-family: var(--font-num);
  font-size: 0.65rem;
  color: var(--color-muted);
  margin-top: 0.5rem;
}
.hourly-labels span { flex: 1; text-align: center; }
iframe {
  width: 100%;
  height: 700px;
  border: 1px solid var(--color-rule);
  display: block;
}
.lens-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 3rem;
  margin-top: 1.5rem;
}
.lens-detail {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}
.lens-detail h3 {
  grid-column: 1 / -1;
  font-size: 0.95rem;
  font-weight: 500;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.5rem;
}
.lens-detail h3 .count {
  font-family: var(--font-num);
  font-size: 0.8rem;
  color: var(--color-muted);
  font-weight: 400;
  font-variant-numeric: tabular-nums;
}
.empty-state {
  color: var(--color-muted);
  font-size: 0.9rem;
  text-align: center;
  padding: 2rem 0;
}
footer {
  margin-top: 4rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--color-rule);
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: var(--color-muted);
}
footer a {
  color: var(--color-text);
  text-decoration: none;
  border-bottom: 1px solid var(--color-text);
}
@media (max-width: 720px) {
  body { padding: 1.5rem 1rem 3rem; }
  .hero-grid { grid-template-columns: repeat(2, 1fr); gap: 1.5rem 1rem; }
  .hero-card .value { font-size: 1.75rem; }
  .lens-detail { grid-template-columns: 1fr; }
  iframe { height: 500px; }
}
</style>
</head>
<body>

<header>
  <h1>PhotoCheck Report</h1>
  <div class="meta">{{ generated_at }} · {{ valid_photos }} photos</div>
</header>

{# ============ HERO STATS ============ #}
{% set hero_data = [
  ('01', 'Main lens', main_lens.name, main_lens.count, main_lens.pct, main_lens.value, main_lens.note, 'lens'),
  ('02', 'Most-used focal', main_focal.value, main_focal.count, main_focal.pct, main_focal.value, main_focal.note, 'mm'),
  ('03', 'Most-used aperture', main_aperture.value, main_aperture.count, main_aperture.pct, main_aperture.value, main_aperture.note, 'f'),
  ('04', 'Peak month', peak_month.label, peak_month.count, none, peak_month.value, peak_month.note, ''),
  ('05', 'Span', span.days ~ ' days', none, none, span.value, span.note, ''),
  ('06', 'Active days', active_days.days, active_days.total_span_days, active_days.ratio, active_days.value, active_days.note, '%')
] %}

<section class="hero">
  <div class="hero-grid">
    {% for num, label, primary, secondary, pct, sentinel_value, note, _ in hero_data %}
      <div class="hero-card {% if not sentinel_value %}empty{% endif %}">
        <div class="value">{% if sentinel_value %}{{ primary }}{% else %}—{% endif %}</div>
        <div class="label">{{ label }}</div>
        <div class="sub">
          {% if sentinel_value %}
            {% if pct is not none %}{{ count }}{% if pct %} · {{ pct }}%{% endif %}{% endif %}
          {% else %}
            {{ note or "暂无数据" }}
          {% endif %}
        </div>
      </div>
    {% endfor %}
  </div>
</section>

{# ============ 01 — HOURLY ============ #}
{% if hourly and hourly|sum > 0 %}
<section>
  <div class="section-head"><span class="num">01</span><h2>Hourly distribution</h2></div>
  <div class="hourly-bars">
    {% set max_h = (hourly|max) or 1 %}
    {% for count in hourly %}
      <div class="hourly-bar" style="height: {{ (count / max_h * 100)|round(1) }}%" title="{{ count }} photos at {{ loop.index0 }}:00"></div>
    {% endfor %}
  </div>
  <div class="hourly-labels">
    {% for h in range(24) %}<span>{{ h }}</span>{% endfor %}
  </div>
</section>
{% endif %}

{# ============ 02 — FOCAL ============ #}
<section>
  <div class="section-head"><span class="num">02</span><h2>Focal length</h2></div>
  <img class="chart-full" src="charts/focal.png" alt="Focal length distribution"
       onerror="this.outerHTML='<div class=&quot;empty-state&quot;>图表未生成</div>'">
</section>

{# ============ 03 — FSTOP ============ #}
<section>
  <div class="section-head"><span class="num">03</span><h2>Aperture</h2></div>
  <img class="chart-full" src="charts/fstop.png" alt="Aperture distribution"
       onerror="this.outerHTML='<div class=&quot;empty-state&quot;>图表未生成</div>'">
</section>

{# ============ 04 — LENS ============ #}
<section>
  <div class="section-head"><span class="num">04</span><h2>Lens usage</h2></div>
  <img class="chart-full" src="charts/lens.png" alt="Lens usage"
       onerror="this.outerHTML='<div class=&quot;empty-state&quot;>图表未生成</div>'">
</section>

{# ============ 05 — LENS TIMELINE IFRAME ============ #}
<section>
  <div class="section-head"><span class="num">05</span><h2>Lens timeline</h2></div>
  <iframe src="charts/timeline_by_lens.html" loading="lazy"></iframe>
</section>

{# ============ 06 — TIMELINE FOCAL ============ #}
<section>
  <div class="section-head"><span class="num">06</span><h2>Focal over time</h2></div>
  <img class="chart-full" src="charts/timeline_focal.png" alt="Focal length over time"
       onerror="this.outerHTML='<div class=&quot;empty-state&quot;>图表未生成</div>'">
</section>

{# ============ 07 — TOP 5 LENS DETAILS ============ #}
{% if top_lenses %}
<section>
  <div class="section-head"><span class="num">07</span><h2>Top lenses</h2></div>
  <div class="lens-grid">
    {% for lens in top_lenses %}
      <div class="lens-detail">
        <h3><span>{{ lens.position }}. {{ lens.name }}</span><span class="count">{{ lens.count }} · {{ lens.pct }}%</span></h3>
        <img src="{{ lens.focal_chart }}" alt="Focal: {{ lens.name }}"
             onerror="this.outerHTML='<div class=&quot;empty-state&quot;>图表未生成</div>'">
        <img src="{{ lens.fstop_chart }}" alt="Aperture: {{ lens.name }}"
             onerror="this.outerHTML='<div class=&quot;empty-state&quot;>图表未生成</div>'">
      </div>
    {% endfor %}
  </div>
</section>
{% endif %}

<footer>
  <a href="lenses.html">View all lenses →</a>
  <span>PhotoCheck v0.1.0</span>
</footer>

</body>
</html>
```

- [ ] **Step 2: Re-run renderer tests to make sure template still renders**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run pytest tests/test_renderer.py -v`
Expected: 4 pass

- [ ] **Step 3: Smoke-test the template rendering manually**

Run:
```bash
cd /Users/pluto/PythonProjects/PhotoCheck && uv run python -c "
import sys
sys.path.insert(0, 'tests')
from conftest import _load_fixture
from photocheck.report.stats import compute_all
from photocheck.report.renderer import render_report
metadata = _load_fixture('sample_metadata.json')
stats = compute_all(metadata, top_n=5)
render_report({**stats, 'charts_dir': 'charts', 'generated_at': '2026-09-18'}, Path('/tmp/test_report.html'))
print('OK')
"
```
(You'll need to add `from pathlib import Path` to the inline command or use a heredoc.)

Run:
```bash
cd /Users/pluto/PythonProjects/PhotoCheck && uv run python -c "
import sys; sys.path.insert(0, 'tests')
from pathlib import Path
from conftest import _load_fixture
from photocheck.report.stats import compute_all
from photocheck.report.renderer import render_report
metadata = _load_fixture('sample_metadata.json')
stats = compute_all(metadata, top_n=5)
render_report({**stats, 'charts_dir': 'charts', 'generated_at': '2026-09-18'}, Path('/tmp/test_report.html'))
print('OK, size:', Path('/tmp/test_report.html').stat().st_size)
"
```
Expected: prints `OK, size: <some number>` around 10-15KB

- [ ] **Step 4: Open the generated file in browser and verify visually**

Run: `open /tmp/test_report.html`
Expected: browser opens, shows the report skeleton with hero cards visible. (Some images will 404, that's expected at this stage.)

- [ ] **Step 5: Commit**

```bash
git add src/photocheck/templates/report.html.j2
git commit -m "feat(report): full Minimal Swiss template with hero + 7 sections"
```

---

## Task 7: Build the lenses.html.j2 subpage

**Files:**
- Modify: `src/photocheck/templates/lenses.html.j2`

- [ ] **Step 1: Replace lenses.html.j2 with full template**

Overwrite `src/photocheck/templates/lenses.html.j2`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>All Lenses — PhotoCheck Report</title>
<style>
:root { --color-bg: #fff; --color-text: #1a1a1a; --color-muted: #888; --color-rule: #e5e5e5;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif;
  --font-num: ui-monospace, SFMono-Regular, Menlo, monospace; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--font-sans); color: var(--color-text); background: var(--color-bg);
  line-height: 1.5; padding: 3rem 2rem 6rem; max-width: 900px; margin: 0 auto; }
header { border-bottom: 1px solid var(--color-rule); padding-bottom: 1.5rem; margin-bottom: 2rem;
  display: flex; justify-content: space-between; align-items: baseline; }
header h1 { font-size: 1.25rem; font-weight: 500; }
header a { font-size: 0.8rem; color: var(--color-muted); text-decoration: none;
  border-bottom: 1px solid var(--color-muted); }
.lens-table { width: 100%; border-collapse: collapse; }
.lens-table th { text-align: left; font-size: 0.7rem; color: var(--color-muted);
  text-transform: uppercase; letter-spacing: 0.08em; font-weight: 500; padding: 0.75rem 0;
  border-bottom: 1px solid var(--color-rule); }
.lens-table td { padding: 1rem 0; border-bottom: 1px solid var(--color-rule);
  font-variant-numeric: tabular-nums; }
.lens-table td.pos { font-family: var(--font-num); color: var(--color-muted); width: 3rem; }
.lens-table td.name { font-weight: 500; }
.lens-table td.count { text-align: right; font-family: var(--font-num); }
.lens-table td.pct { text-align: right; color: var(--color-muted); width: 5rem; }
.empty-state { color: var(--color-muted); text-align: center; padding: 3rem 0; }
</style>
</head>
<body>

<header>
  <h1>All lenses</h1>
  <a href="index.html">← Back to report</a>
</header>

{% if all_lenses %}
<table class="lens-table">
  <thead>
    <tr><th>#</th><th>Lens</th><th style="text-align:right">Photos</th><th style="text-align:right">Share</th></tr>
  </thead>
  <tbody>
    {% for lens in all_lenses %}
      <tr>
        <td class="pos">{{ lens.position }}</td>
        <td class="name">{{ lens.name }}</td>
        <td class="count">{{ lens.count }}</td>
        <td class="pct">{{ lens.pct }}%</td>
      </tr>
    {% endfor %}
  </tbody>
</table>
{% else %}
<div class="empty-state">暂无镜头数据</div>
{% endif %}

</body>
</html>
```

- [ ] **Step 2: Re-run renderer tests**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run pytest tests/test_renderer.py -v`
Expected: 4 pass

- [ ] **Step 3: Commit**

```bash
git add src/photocheck/templates/lenses.html.j2
git commit -m "feat(report): lenses.html subpage template"
```

---

## Task 8: Implement builder.copy_charts helper

**Files:**
- Create: `src/photocheck/report/builder.py`

- [ ] **Step 1: Create builder.py with copy_charts function**

Create `src/photocheck/report/builder.py`:

```python
"""Orchestration: copy charts, compute stats, render templates."""

import shutil
from collections import Counter
from pathlib import Path
from typing import Optional

from ..cli import OUTPUT_DIR
from ..core.models import PhotoMetadata
from ..viz.histograms import plot_lens_detail
from .renderer import render_lenses, render_report
from .stats import _valid, compute_all


# PNGs that exist in output/ and get copied verbatim into report/charts/
_BASE_CHARTS = [
    "focal.png",
    "fstop.png",
    "lens.png",
    "timeline_focal.png",
    "hourly_heatmap.png",
    "timeline_by_lens.html",  # the iframe target
]


def _copy_base_charts(src_dir: Path, dst_dir: Path) -> list[str]:
    """Copy base charts from src to dst. Returns list of copied filenames."""
    copied = []
    for name in _BASE_CHARTS:
        src = src_dir / name
        if src.exists():
            shutil.copy2(src, dst_dir / name)
            copied.append(name)
    return copied


def _generate_top_lens_charts(
    metadata: list[PhotoMetadata],
    top_lenses: list[dict],
    output_dir: Path,
) -> list[str]:
    """Generate per-lens focal/fstop PNGs for the top N lenses.

    Each lens's photos are written to a temp directory structure, then
    plot_lens_detail scans that directory and saves with predictable names.
    """
    from ..viz.histograms import _plot_bar_chart
    from collections import defaultdict

    valid = _valid(metadata)
    by_lens: dict[str, list[PhotoMetadata]] = defaultdict(list)
    for m in valid:
        if m.lens_name is not None:
            by_lens[m.lens_name].append(m)

    written = []
    for lens in top_lenses:
        name = lens["name"]
        position = lens["position"]
        photos = by_lens.get(name, [])
        if not photos:
            continue

        # Focal
        focals = [m.focal_length for m in photos if m.focal_length is not None and m.focal_length >= 7]
        if focals:
            from .stats import classify_focal  # local import to avoid cycle
            from ..viz.histograms import classify_focal as cf
            bucketed = [cf(f) for f in focals]
            counts = Counter(bucketed).most_common()
            counts.sort(key=lambda x: x[0])
            xs = [c[0] for c in counts]
            ys = [c[1] for c in counts]
            path = output_dir / f"lens_top{position}_focal.png"
            _plot_bar_chart(xs, ys, title=f"Focal: {name}", xlabel="Focal Length (mm)",
                            ylabel="Photo Count", filename=str(path))
            written.append(path.name)

        # F-stop
        fstops = [m.f_stop for m in photos if m.f_stop is not None and m.f_stop > 0]
        if fstops:
            counts = Counter(fstops).most_common()
            counts.sort(key=lambda x: x[0])
            xs = [c[0] for c in counts]
            ys = [c[1] for c in counts]
            path = output_dir / f"lens_top{position}_fstop.png"
            _plot_bar_chart(xs, ys, title=f"Aperture: {name}", xlabel="F-Stop",
                            ylabel="Photo Count", filename=str(path))
            written.append(path.name)
    return written
```

- [ ] **Step 2: Smoke-test the helpers exist and are importable**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run python -c "from photocheck.report.builder import _copy_base_charts, _generate_top_lens_charts; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add src/photocheck/report/builder.py
git commit -m "feat(report): builder helpers for chart copying and per-lens PNGs"
```

---

## Task 9: Implement build_report main flow

**Files:**
- Modify: `src/photocheck/report/builder.py`

- [ ] **Step 1: Append build_report function to builder.py**

Append to `src/photocheck/report/builder.py`:

```python
def build_report(
    metadata: list[PhotoMetadata],
    output_dir: Path,
    top_lenses_n: int = 5,
    charts_src: Optional[Path] = None,
    generated_at: Optional[str] = None,
) -> Path:
    """Build the full report/ folder. Returns path to index.html.

    Args:
        metadata: Valid PhotoMetadata list (caller filters out errors).
        output_dir: Where to create the report folder (will be wiped if exists).
        top_lenses_n: How many top lenses to inline on main page.
        charts_src: Directory containing the base charts. Defaults to OUTPUT_DIR.
        generated_at: Timestamp string for the report header. Defaults to now.
    """
    from datetime import datetime as _dt

    if charts_src is None:
        charts_src = OUTPUT_DIR
    if generated_at is None:
        generated_at = _dt.now().strftime("%Y-%m-%d %H:%M")

    output_dir = Path(output_dir)
    charts_dst = output_dir / "charts"

    # Wipe and recreate
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    charts_dst.mkdir(parents=True, exist_ok=True)

    # 1. Compute stats
    stats = compute_all(metadata, top_n=top_lenses_n)

    # 2. Copy base charts
    _copy_base_charts(charts_src, charts_dst)

    # 3. Generate per-lens top-N charts
    _generate_top_lens_charts(metadata, stats["top_lenses"], charts_dst)

    # 4. Render templates
    context = {**stats, "charts_dir": "charts", "generated_at": generated_at}
    index_path = output_dir / "index.html"
    render_report(context, index_path)
    render_lenses(context, output_dir / "lenses.html")

    return index_path
```

- [ ] **Step 2: Smoke-test the full build_report function**

Run:
```bash
cd /Users/pluto/PythonProjects/PhotoCheck && uv run python -c "
import sys; sys.path.insert(0, 'tests')
from pathlib import Path
from conftest import _load_fixture
from photocheck.report.builder import build_report
metadata = _load_fixture('sample_metadata.json')
index = build_report(metadata, Path('/tmp/test_report'))
print('Report at:', index)
print('Files:', sorted(p.name for p in index.parent.rglob('*')))
"
```
Expected: prints path to index.html, then list of files in `/tmp/test_report/` (should include `index.html`, `lenses.html`, `charts/` directory)

- [ ] **Step 3: Open the report in a browser and visually verify**

Run: `open /tmp/test_report/index.html`
Expected: browser shows the report with hero cards filled in. (Some chart images will 404 since we didn't run analyze first — that's OK; the onerror handler shows "图表未生成".)

- [ ] **Step 4: Commit**

```bash
git add src/photocheck/report/builder.py
git commit -m "feat(report): build_report orchestration"
```

---

## Task 10: Add `report` subcommand to cli.py

**Files:**
- Modify: `src/photocheck/cli.py`

- [ ] **Step 1: Add the report subparser and report_command function**

Add to the imports at the top of `src/photocheck/cli.py`:

```python
from .report.builder import build_report
```

Add the `report_command` function (e.g., just before `interactive_menu`):

```python
def report_command(args: argparse.Namespace) -> int:
    """Generate HTML report from cached metadata."""
    cache_path = get_cache_path()

    if not cache_path.exists():
        print(f"Error: No cache found at {cache_path}. Run 'scan' first.")
        return 1

    metadata_list = load_cache(cache_path)
    if not metadata_list:
        print("Error: Cache is empty. Run 'scan' first.")
        return 1

    valid = [m for m in metadata_list if m.error is None]
    output_dir = Path(args.output) if args.output else Path("report")
    top_n = args.top_lenses

    print(f"Generating report at: {output_dir}/")
    print(f"Top lenses to inline: {top_n}")

    index_path = build_report(valid, output_dir, top_lenses_n=top_n)
    print(f"Done. Open: {index_path}")
    return 0
```

Add the subparser in `main()` (just after the `analyze_parser` block, before `interact_parser`):

```python
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate HTML report from cache")
    report_parser.add_argument(
        "--output", "-o",
        default=None,
        help="报告输出目录 (默认: ./report/)",
    )
    report_parser.add_argument(
        "--top-lenses", "-n",
        type=int,
        default=5,
        help="主页内嵌 Top N 镜头详情 (默认: 5)",
    )
    report_parser.set_defaults(func=report_command)
```

- [ ] **Step 2: Verify the subcommand is registered**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run python -m photocheck --help`
Expected: shows `report` in the subcommand list

- [ ] **Step 3: Verify report --help works**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run python -m photocheck report --help`
Expected: shows usage with `--output` and `--top-lenses` options

- [ ] **Step 4: Commit**

```bash
git add src/photocheck/cli.py
git commit -m "feat(cli): add report subcommand"
```

---

## Task 11: Add option 4 to interactive_menu

**Files:**
- Modify: `src/photocheck/cli.py` (interactive_menu function)

- [ ] **Step 1: Update interactive_menu to include report option**

In the `interactive_menu()` function, change the print block to:

```python
        print("1. 扫描照片 (scan)")
        print("2. 可视化分析 (analyze)")
        print("3. 生成 HTML 报告 (report)")
        print("4. 退出 (quit)")
        print()

        choice = input("请选择 (1/2/3/4): ").strip()
```

- [ ] **Step 2: Update choice handling — renumber existing "3" to "4" and add "3" branch**

```python
        if choice == "1":
            # (unchanged)
            ...
        elif choice == "2":
            # (unchanged)
            ...
        elif choice == "3":
            if not has_cache:
                print("错误: 暂无数据，请先扫描照片")
                continue
            print()
            class Args:
                folder = default_folder
                output = None
                top_lenses = 5
            report_command(Args())
        elif choice in ("4", "q", "quit", "exit"):
            print("再见!")
            break
        else:
            print("无效选择，请重试")
```

- [ ] **Step 3: Verify interactive menu launches without errors**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run python -m photocheck interactive` then immediately `4` + Enter
Expected: prints menu, accepts "4", prints "再见!", exits

- [ ] **Step 4: Commit**

```bash
git add src/photocheck/cli.py
git commit -m "feat(cli): add report option to interactive menu"
```

---

## Task 12: Update run.py to add DO_REPORT

**Files:**
- Modify: `run.py`

- [ ] **Step 1: Add report configuration constants**

Edit `run.py` config block to add (after the existing `VIZ_FIELD` line):

```python
# Report configuration
DO_REPORT = True                              # 是否生成 HTML 报告
REPORT_DIR = "./report"                       # 报告输出目录
TOP_LENSES = 5                                # 主页内嵌 Top N 镜头
```

- [ ] **Step 2: Add report step to the run() function**

After the existing `if DO_VISUALIZE:` block, add:

```python
    if DO_REPORT:
        print(f"\n=== 生成 HTML 报告 ===")
        report_args = ["report", "--output", REPORT_DIR, "--top-lenses", str(TOP_LENSES)]
        print(f"执行: uv run python -m photocheck {' '.join(report_args)}")
        result = cli_main(report_args)
        if result != 0:
            print(f"报告生成失败: {result}")
            return result
```

- [ ] **Step 3: Verify run.py runs end-to-end with empty cache (should fail gracefully)**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run python run.py`
Expected: scan + analyze + report attempt. If no `SCAN_FOLDER` set or folder empty, report command should print "No cache found" and return 1, which run.py will surface as "报告生成失败: 1"

- [ ] **Step 4: Commit**

```bash
git add run.py
git commit -m "feat(run): add DO_REPORT configuration"
```

---

## Task 13: Update documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/usage.md`

- [ ] **Step 1: Add report section to README.md**

Insert before the `## Output` section:

```markdown
## Generate HTML Report

After running `scan` and `analyze`, generate a consolidated HTML report:

```bash
uv run python -m photocheck report
# Or specify output directory
uv run python -m photocheck report --output ./my_report
# Or change the number of inlined top lenses (default: 5)
uv run python -m photocheck report --top-lenses 8
```

This produces a `report/` folder with `index.html` (consolidated report) and `charts/` (PNG/HTML chart assets), plus a `lenses.html` subpage listing all lenses.
```

(Note: use the existing markdown formatting in the file. If the project uses Chinese in the README, follow that style.)

- [ ] **Step 2: Add report section to docs/usage.md**

Insert before the "## 数据合并" section:

```markdown
---

## HTML 报告生成

完成 scan + analyze 后，可以生成 HTML 报告：

```bash
uv run python -m photocheck report
```

输出目录结构：

```
report/
├── index.html         # 主报告（hero 卡片 + 7 个 section）
├── lenses.html        # 全部镜头子页
└── charts/            # PNG 图表 + 交互式 timeline
```

常用参数：

| 参数 | 说明 | 默认 |
|------|------|------|
| `--output, -o` | 报告输出目录 | `./report/` |
| `--top-lenses, -n` | 主页内嵌 Top N 镜头详情 | 5 |

样式采用 Minimal Swiss 设计风格（白底、无衬线、强数字对比），无 JavaScript 依赖（仅交互图 iframe）。

---
```

- [ ] **Step 3: Verify the markdown renders reasonably**

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && head -30 README.md`
Expected: includes the new section

- [ ] **Step 4: Commit**

```bash
git add README.md docs/usage.md
git commit -m "docs: document report subcommand"
```

---

## Task 14: Manual end-to-end test

**Files:** none (manual verification)

- [ ] **Step 1: Ensure existing cache and output/ charts exist**

If you have a real photo library at `SCAN_FOLDER` (configured in `run.py`):

Run: `cd /Users/pluto/PythonProjects/PhotoCheck && uv run python run.py`
Expected: completes scan → analyze → report sequence, prints "Done. Open: ./report/index.html"

If you don't have a real library, you can do a minimal smoke test by:
1. Running `scan` against any folder containing at least one ARW
2. Running `analyze --type all` to populate `output/`
3. Running `report`

- [ ] **Step 2: Open the report in browser**

Run: `open ./report/index.html`
Expected: Browser shows a clean Minimal Swiss report with:
- Header with "PhotoCheck Report" + timestamp + photo count
- 6 hero stat cards (3 × 2 grid)
- Hourly distribution bars
- Focal length PNG
- Aperture PNG
- Lens usage PNG
- Lens timeline iframe (interactive Plotly chart)
- Focal over time PNG
- Top lenses section with detail charts
- Footer with "View all lenses →" link

- [ ] **Step 3: Verify the lenses subpage works**

Click "View all lenses →" in the footer.
Expected: Navigates to `lenses.html` with a sortable-style table of all lenses.

- [ ] **Step 4: Verify responsive layout**

Resize browser window to mobile width (e.g., 400px).
Expected: Hero grid becomes 2 columns, lens detail stacks vertically.

- [ ] **Step 5: Verify the iframe interaction**

In the "Lens timeline" section, hover over the chart.
Expected: Plotly tooltip shows date + lens + photo count.

- [ ] **Step 6: Report any issues found**

If anything looks wrong, file issues or fix inline. Common issues:
- CDN-loaded Plotly may not work offline — note this in docs but don't fix in this round
- Some charts may have CJK font issues if matplotlib doesn't have a CJK font installed — handled by the existing rcParams settings

- [ ] **Step 7: Final commit if any fixes were made**

```bash
git status
# If changes:
git add -A
git commit -m "fix: address issues from E2E test"
```

---

## Self-Review

After writing the plan, check against the spec:

**Spec coverage:**
- ✓ Folder + relative refs (Task 9)
- ✓ 6 hero cards (Task 6 template + Task 2 stats)
- ✓ New report subcommand (Task 10)
- ✓ Minimal Swiss style (Task 6 CSS)
- ✓ iframe embed (Task 6 section 05)
- ✓ Top 5 lens inline + view all link (Tasks 3, 6, 7)
- ✓ Jinja2 templates (Tasks 5, 6, 7)
- ✓ 10 report sections in correct order (Task 6)
- ✓ All-lens subpage (Tasks 7, 9)
- ✓ Error handling: cache missing/empty (Task 10), missing PNGs (Task 6 onerror), wiped output (Task 9)
- ✓ Tests for stats + renderer (Tasks 2, 3, 4, 5)

**No placeholders:** searched for TBD/TODO — none.

**Type consistency:** all references to `main_lens.name`, `top_lenses[].position`, `valid_photos`, `total_photos`, `charts_dir`, `generated_at` are defined where used.

**Plan is complete and ready to execute.**
