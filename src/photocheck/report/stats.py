"""Pure stat functions for the HTML report.

All functions are pure: take List[PhotoMetadata], return dicts.
All functions re-filter m.error is not None defensively.
"""

from collections import Counter

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
    """Month with the most photos (tie-break: earliest wins)."""
    valid = _valid(metadata)
    months: Counter = Counter()
    for m in valid:
        if m.datetime_original is not None:
            key = m.datetime_original.strftime("%Y-%m")
            months[key] += 1
    if not months:
        return {**_EMPTY, "label": None, "count": 0}
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
