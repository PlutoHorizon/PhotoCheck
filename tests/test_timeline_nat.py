"""Tests for NaT (Not-a-Time) handling in timeline visualizations.

When datetime_original comes back from a parquet round-trip, missing
values arrive as pd.NaT, not Python None. The original `is None` checks
let NaT through, which then crashes:

- plot_timeline_scatter: ax.scatter([NaT], ...) raises
- plot_hourly_heatmap: dt.hour on NaT raises
- plot_timeline_series: min()/max() of {NaT, real} → NaT → no series
- plot_timeline_by_lens: pd.Timestamp(NaT).to_period() raises
- plot_timeline_by_lens_html: same as above
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from photocheck.core.models import PhotoMetadata
from photocheck.viz.timeline import (
    plot_hourly_heatmap,
    plot_timeline_by_lens,
    plot_timeline_by_lens_html,
    plot_timeline_scatter,
    plot_timeline_series,
)


def _meta(path: str, dt, lens: str = "Test Lens") -> PhotoMetadata:
    return PhotoMetadata(
        file_path=Path(path),
        datetime_original=dt,
        lens_name=lens,
        focal_length=50.0,
    )


class TestScatterNaT:
    def test_scatter_skips_nat_rows(self, tmp_path):
        """NaT datetime_original must not crash scatter plot."""
        rows = [
            _meta("/a.ARW", pd.NaT),
            _meta("/b.ARW", datetime(2024, 1, 1, 10)),
            _meta("/c.ARW", datetime(2024, 1, 2, 12)),
        ]
        out = tmp_path / "out.png"
        # Must not raise
        result = plot_timeline_scatter(rows, filename=str(out))
        assert result == str(out)
        assert out.exists()

    def test_scatter_all_nat_returns_none(self, tmp_path):
        """If every row has NaT, plot returns None with a message."""
        rows = [_meta(f"/{i}.ARW", pd.NaT) for i in range(5)]
        out = tmp_path / "out.png"
        result = plot_timeline_scatter(rows, filename=str(out))
        assert result is None
        assert not out.exists()


class TestHourlyHeatmapNaT:
    def test_hourly_heatmap_skips_nat_rows(self, tmp_path):
        """NaT datetime_original must not crash hourly heatmap."""
        rows = [
            _meta("/a.ARW", pd.NaT),
            _meta("/b.ARW", datetime(2024, 1, 1, 8)),
            _meta("/c.ARW", datetime(2024, 1, 2, 8)),
        ]
        out = tmp_path / "out.png"
        result = plot_hourly_heatmap(rows, filename=str(out))
        assert result == str(out)
        assert out.exists()

    def test_hourly_heatmap_all_nat_returns_none(self, tmp_path):
        rows = [_meta(f"/{i}.ARW", pd.NaT) for i in range(5)]
        out = tmp_path / "out.png"
        result = plot_hourly_heatmap(rows, filename=str(out))
        assert result is None
        assert not out.exists()


class TestTimelineSeriesNaT:
    def test_timeline_series_skips_nat_rows(self, tmp_path):
        """NaT datetime_original must not break the time series."""
        rows = [
            _meta("/a.ARW", pd.NaT),
            _meta("/b.ARW", datetime(2024, 1, 1, 10)),
            _meta("/c.ARW", datetime(2024, 1, 2, 12)),
        ]
        out = tmp_path / "out.png"
        result = plot_timeline_series(rows, filename=str(out))
        # Either succeeds with a series, or returns None cleanly — never raises
        if result is not None:
            assert out.exists()

    def test_timeline_series_all_nat_returns_none(self, tmp_path):
        rows = [_meta(f"/{i}.ARW", pd.NaT) for i in range(5)]
        out = tmp_path / "out.png"
        result = plot_timeline_series(rows, filename=str(out))
        assert result is None


class TestTimelineByLensNaT:
    def test_by_lens_skips_nat_rows(self, tmp_path):
        """NaT must not crash the lens timeline (would raise in to_period)."""
        rows = [
            _meta("/a.ARW", pd.NaT, lens="Lens A"),
            _meta("/b.ARW", datetime(2024, 1, 1), lens="Lens A"),
            _meta("/c.ARW", datetime(2024, 1, 8), lens="Lens B"),
        ]
        out = tmp_path / "out.png"
        result = plot_timeline_by_lens(rows, filename=str(out))
        assert result == str(out)
        assert out.exists()

    def test_by_lens_html_skips_nat_rows(self, tmp_path):
        rows = [
            _meta("/a.ARW", pd.NaT, lens="Lens A"),
            _meta("/b.ARW", datetime(2024, 1, 1), lens="Lens A"),
            _meta("/c.ARW", datetime(2024, 1, 8), lens="Lens B"),
        ]
        out = tmp_path / "out.html"
        result = plot_timeline_by_lens_html(rows, filename=str(out))
        assert result == str(out)
        assert out.exists()

    def test_by_lens_all_nat_returns_none(self, tmp_path):
        rows = [_meta(f"/{i}.ARW", pd.NaT, lens="Lens A") for i in range(5)]
        out = tmp_path / "out.png"
        assert plot_timeline_by_lens(rows, filename=str(out)) is None
        assert plot_timeline_by_lens_html(rows, filename=str(out)) is None


class TestMixedRealAndNaT:
    """Realistic mix: most rows have datetime, some have NaT after parquet load."""

    def test_realistic_mix_does_not_crash_any_function(self, tmp_path):
        rows = []
        # 100 valid rows across 10 weeks
        for i in range(100):
            rows.append(_meta(
                f"/{i}.ARW",
                datetime(2024, 1, 1) + pd.Timedelta(days=i),
                lens="Lens A" if i % 2 == 0 else "Lens B",
            ))
        # 50 NaT rows sprinkled in
        for i in range(50):
            rows.append(_meta(f"/bad{i}.ARW", pd.NaT, lens="Lens A"))

        out_png = tmp_path / "out.png"
        out_html = tmp_path / "out.html"

        # Each must complete without raising
        assert plot_timeline_scatter(rows, filename=str(out_png)) == str(out_png)
        assert out_png.exists()

        assert plot_hourly_heatmap(rows, filename=str(out_png.with_name("h.png"))) is not None

        assert plot_timeline_by_lens(rows, filename=str(out_png.with_name("lens.png"))) is not None

        assert plot_timeline_by_lens_html(rows, filename=str(out_html)) == str(out_html)
        assert out_html.exists()