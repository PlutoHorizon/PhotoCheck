"""Tests for photocheck.report.stats."""

from datetime import datetime
from pathlib import Path

import pytest

from photocheck.core.models import PhotoMetadata
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

    def test_partial_skips_lens_none(self, partial_metadata):
        result = main_lens(partial_metadata)
        # partial has 2 photos with lens_name, 1 with error
        assert result["value"] is not None
        assert "count" in result


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
        # sample: 3 at f/1.4 (DSC00001, 6, 10), 3 at f/1.8 (3, 7, 9), 2 at f/2.0, 1 f/2.8, 1 f/4.0
        # Tie between 1.4 and 1.8; first-seen wins → 1.4
        assert result["fstop"] == 1.4
        assert result["count"] == 3

    def test_empty_returns_none(self, empty_metadata):
        result = main_aperture(empty_metadata)
        assert result["value"] is None
        assert result["note"] == "无数据"


class TestPeakMonth:
    def test_returns_month_with_most_photos(self, sample_metadata):
        result = peak_month(sample_metadata)
        # sample dates: 2024-01 (3), 2024-02 (2), 2024-03 (2), 2024-04 (1), 2024-05 (1), 2024-06 (1)
        assert result["label"] == "2024-01"
        assert result["count"] == 3

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
        single = [
            PhotoMetadata(
                file_path=Path("/x.ARW"),
                datetime_original=datetime(2024, 1, 1),
            )
        ]
        result = span(single)
        assert result["value"] is None
        assert result["note"] == "无数据"


class TestActiveDays:
    def test_counts_unique_dates(self, sample_metadata):
        result = active_days(sample_metadata)
        # sample has 8 unique dates (2 photos share 2024-01-15, 2 share 2024-02-10)
        assert result["days"] == 8
        assert result["total_span_days"] > 0
        assert 0 < result["ratio"] <= 100

    def test_empty_returns_none(self, empty_metadata):
        result = active_days(empty_metadata)
        assert result["value"] is None
        assert result["note"] == "无数据"


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
        # 4 distinct lenses in sample
        assert len(result) == 4

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
        assert len(result) == 4
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
