"""Timeline visualizations for PhotoCheck."""

import re
from collections import Counter
from datetime import datetime
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd

from ..core.extractor import is_valid_dt
from ..core.models import PhotoMetadata


plt.rcParams["axes.unicode_minus"] = False


# Compact lens labels for legends: "<system/brand prefix> <focal range>",
# e.g. "FE 200-600mm F5.6-6.3 G OSS" -> "FE 200-600". Full names make
# stacked-chart legends overflow the plot area.
_ZOOM_RE = re.compile(r"(\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?)\s*mm", re.I)
_PRIME_RE = re.compile(r"(\d{2,3}(?:\.\d)?)\s*(?:mm\b|/)")  # "35/1.7", "50mm"


def _shorten_lens_name(name: str) -> str:
    """Compact lens label: leading brand/system words + focal range."""
    m = _ZOOM_RE.search(name)
    if m:
        focal = re.sub(r"\s+", "", m.group(1))
        prefix = name[: m.start()].strip()
    else:
        m = _PRIME_RE.search(name)
        if not m:
            return name[:24]
        focal = m.group(1)
        prefix = name[: m.start()].strip()
    words = prefix.split()
    if len(words) > 3:
        words = words[-3:]
    return " ".join(words + [focal])


def _short_lens_mapping(lens_names: list[str]) -> dict[str, str]:
    """Map full lens names to unique short labels.

    On collision (two lenses shortening to the same label) the longer
    original names are kept truncated, so distinct lenses never merge
    in the chart.
    """
    mapping: dict[str, str] = {}
    counts = Counter(_shorten_lens_name(n) for n in lens_names)
    for name in lens_names:
        short = _shorten_lens_name(name)
        mapping[name] = short if counts[short] == 1 else name[:24]
    return mapping


def plot_timeline_scatter(
    metadata_list: list[PhotoMetadata],
    field: str = "focal_length",
    title: str = None,
    filename: Optional[str] = None,
) -> Optional[str]:
    """Plot datetime vs specified field as scatter plot (Minimal Swiss style)."""
    field_names = {
        "focal_length": "Focal Length",
        "iso": "ISO",
        "f_stop": "Aperture",
        "shutter_speed": "Shutter Speed",
    }

    if title is None:
        title = f"{field_names.get(field, field)} Timeline"

    dates = []
    values = []
    for m in metadata_list:
        if m.error is not None or not is_valid_dt(m.datetime_original):
            continue
        val = getattr(m, field, None)
        if val is not None and val > 0:
            dates.append(m.datetime_original)
            values.append(val)

    if not dates:
        print(f"No valid data for timeline plot (field={field})")
        return None

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [
        "-apple-system", "BlinkMacSystemFont", "Segoe UI",
        "PingFang SC", "Hiragino Sans GB", "sans-serif",
    ]

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor("#fff")
    ax.set_facecolor("#fff")

    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#1a1a1a")
        ax.spines[side].set_linewidth(0.8)

    ax.scatter(dates, values, s=14, c="#1a1a1a", alpha=0.4, edgecolors="none")

    ax.set_title(title, fontsize=13, fontweight=500, color="#1a1a1a", loc="left", pad=15)
    ax.set_xlabel("Capture Time", fontsize=10, color="#888", labelpad=10)
    ax.set_ylabel(field_names.get(field, field), fontsize=10, color="#888", labelpad=10)
    ax.tick_params(axis="both", colors="#1a1a1a", labelsize=10, length=0)
    ax.yaxis.grid(True, color="#e5e5e5", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.margins(y=0.1)

    fig.autofmt_xdate()
    plt.tight_layout()

    saved_path = None
    if filename:
        plt.savefig(filename, dpi=150, bbox_inches="tight", facecolor="#fff")
        saved_path = filename
        print(f"Saved: {filename}")

    plt.close()
    return saved_path


def plot_hourly_heatmap(
    metadata_list: list[PhotoMetadata],
    title: str = "Hourly Shooting Distribution",
    field: str = "focal_length",
    filename: Optional[str] = None,
) -> Optional[str]:
    """Plot hourly shooting frequency as a black/gray bar chart (Minimal Swiss style)."""
    hour_data = []
    for m in metadata_list:
        if m.error is not None or not is_valid_dt(m.datetime_original):
            continue
        hour = m.datetime_original.hour
        if field is None:
            hour_data.append(hour)
        else:
            val = getattr(m, field, None)
            if val is not None and val > 0:
                hour_data.append(hour)

    if not hour_data:
        print("No valid data for hourly heatmap")
        return None

    hour_counts = Counter(hour_data)
    hours = list(range(24))
    counts = [hour_counts.get(h, 0) for h in hours]

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [
        "-apple-system", "BlinkMacSystemFont", "Segoe UI",
        "PingFang SC", "Hiragino Sans GB", "sans-serif",
    ]

    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor("#fff")
    ax.set_facecolor("#fff")

    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#1a1a1a")
        ax.spines[side].set_linewidth(0.8)

    bars = ax.bar(hours, counts, color="#1a1a1a", edgecolor="none", width=0.8)

    for bar, count in zip(bars, counts):
        if count > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(counts) * 0.015,
                str(count),
                ha="center", va="bottom",
                color="#888", fontsize=9,
                family="monospace",
            )

    ax.set_title(title, fontsize=13, fontweight=500, color="#1a1a1a", loc="left", pad=15)
    ax.set_xlabel("Hour (0-23)", fontsize=10, color="#888", labelpad=10)
    ax.set_ylabel("Photo Count", fontsize=10, color="#888", labelpad=10)
    ax.set_xticks(hours)
    ax.tick_params(axis="both", colors="#1a1a1a", labelsize=10, length=0)
    ax.yaxis.grid(True, color="#e5e5e5", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.margins(y=0.15)

    plt.tight_layout()

    saved_path = None
    if filename:
        plt.savefig(filename, dpi=150, bbox_inches="tight", facecolor="#fff")
        saved_path = filename
        print(f"Saved: {filename}")

    plt.close()
    return saved_path


def plot_timeline_series(
    metadata_list: list[PhotoMetadata],
    freq: str = "D",
    title: str = "Daily Photo Count",
    filename: Optional[str] = None,
) -> Optional[str]:
    """Plot photo count over time as a time series.

    Args:
        metadata_list: List of PhotoMetadata objects
        freq: Frequency for aggregation ('D'=day, 'W'=week, 'M'=month)
        title: Chart title
        filename: If provided, save chart to this path instead of displaying
    """
    # Extract dates
    dates = []
    for m in metadata_list:
        if m.error is not None or not is_valid_dt(m.datetime_original):
            continue
        dates.append(m.datetime_original.date())

    if not dates:
        print("No valid dates for time series plot")
        return None

    date_counts = Counter(dates)

    # Create series
    if date_counts:
        start_date = min(date_counts.keys())
        end_date = max(date_counts.keys())

        all_dates = pd.date_range(start=start_date, end=end_date, freq=freq)
        counts = [date_counts.get(d.date(), 0) for d in all_dates]

        plt.figure(figsize=(14, 6))
        plt.plot(all_dates, counts, marker="o", markersize=3, linewidth=1, color="steelblue")
        plt.fill_between(all_dates, counts, alpha=0.3)

        plt.title(title, fontsize=14, fontweight="bold")
        plt.xlabel("Date", fontsize=12)
        plt.ylabel("Photo Count", fontsize=12)
        plt.grid(alpha=0.3)
        plt.gcf().autofmt_xdate()

        plt.tight_layout()

        saved_path = None
        if filename:
            plt.savefig(filename, dpi=150, bbox_inches="tight")
            saved_path = filename
            print(f"Saved: {filename}")

        plt.close()
        return saved_path


def plot_timeline_by_lens(
    metadata_list: list[PhotoMetadata],
    freq: str = "W",
    title: str = "Photo Count by Lens Over Time",
    filename: Optional[str] = None,
    top_n: int = 8,
) -> Optional[str]:
    """Plot stacked area chart showing photo count by lens over time.

    Args:
        metadata_list: List of PhotoMetadata objects
        freq: Frequency for aggregation ('D'=day, 'W'=week, 'M'=month)
        title: Chart title
        filename: If provided, save chart to this path instead of displaying
        top_n: Number of top lenses to show (others grouped as 'Other')
    """
    from collections import defaultdict

    # Collect valid data
    records = []
    short_map = _short_lens_mapping(
        [m.lens_name for m in metadata_list if m.lens_name is not None]
    )
    for m in metadata_list:
        if m.error is not None or not is_valid_dt(m.datetime_original) or m.lens_name is None:
            continue
        records.append({
            "date": pd.Timestamp(m.datetime_original),
            "lens": short_map[m.lens_name],
        })

    if not records:
        print("No valid data for lens timeline plot")
        return None

    df = pd.DataFrame(records)

    # Group by date and lens
    df["period"] = df["date"].dt.to_period(freq)
    pivot = df.groupby(["period", "lens"]).size().unstack(fill_value=0)

    # Keep top N lenses by total count, group rest as "Other"
    lens_totals = pivot.sum().sort_values(ascending=False)
    top_lenses = lens_totals.head(top_n).index.tolist()

    if len(pivot.columns) > top_n:
        other_lenses = [c for c in pivot.columns if c not in top_lenses]
        pivot["Other"] = pivot[other_lenses].sum(axis=1)
        pivot = pivot[top_lenses + ["Other"]]

    if pivot.empty or pivot.sum().sum() == 0:
        print("No valid data for lens timeline plot")
        return None

    # Convert period to timestamp for plotting
    x = pivot.index.to_timestamp()

    # Plot stacked area
    plt.figure(figsize=(14, 8))

    # Use a colorful colormap
    n_colors = len(pivot.columns)
    colors = plt.cm.tab20(range(n_colors))

    plt.stackplot(x, *[pivot[col].values for col in pivot.columns],
                 labels=pivot.columns, colors=colors, alpha=0.8)

    plt.title(title, fontsize=14, fontweight="bold")
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Photo Count", fontsize=12)
    # Legend below the axes in multiple columns: with 9-11 long lens
    # names, an in-axes legend squeezes the plot area to half its size.
    plt.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.14),
        ncol=3, fontsize=8, frameon=False,
        columnspacing=1.4, handlelength=1.6,
    )
    plt.grid(alpha=0.3)
    plt.gcf().autofmt_xdate()

    plt.tight_layout()

    saved_path = None
    if filename:
        plt.savefig(filename, dpi=150, bbox_inches="tight")
        saved_path = filename
        print(f"Saved: {filename}")

    plt.close()
    return saved_path


def plot_timeline_by_lens_html(
    metadata_list: list[PhotoMetadata],
    freq: str = "W",
    filename: Optional[str] = None,
    top_n: int = 10,
) -> Optional[str]:
    """Generate interactive HTML chart showing photo count by lens over time.

    Uses Plotly.js for interactivity - can hover to see details.

    Args:
        metadata_list: List of PhotoMetadata objects
        freq: Frequency for aggregation ('D'=day, 'W'=week, 'M'=month)
        filename: Path to save HTML file
        top_n: Number of top lenses to show (others grouped as 'Other')

    Returns:
        Path to saved HTML file
    """
    import json

    # Collect valid data
    records = []
    short_map = _short_lens_mapping(
        [m.lens_name for m in metadata_list if m.lens_name is not None]
    )
    for m in metadata_list:
        if m.error is not None or not is_valid_dt(m.datetime_original) or m.lens_name is None:
            continue
        records.append({
            "date": pd.Timestamp(m.datetime_original),
            "lens": short_map[m.lens_name],
        })

    if not records:
        print("No valid data for lens timeline plot")
        return None

    df = pd.DataFrame(records)

    # Group by date and lens
    df["period"] = df["date"].dt.to_period(freq)
    pivot = df.groupby(["period", "lens"]).size().unstack(fill_value=0)

    # Keep top N lenses by total count, group rest as "Other"
    lens_totals = pivot.sum().sort_values(ascending=False)
    top_lenses = lens_totals.head(top_n).index.tolist()

    if len(pivot.columns) > top_n:
        other_lenses = [c for c in pivot.columns if c not in top_lenses]
        pivot["Other"] = pivot[other_lenses].sum(axis=1)
        pivot = pivot[top_lenses + ["Other"]]

    if pivot.empty or pivot.sum().sum() == 0:
        print("No valid data for lens timeline plot")
        return None

    # Convert period to timestamp for JSON; weekly PeriodIndex str() is
    # "2025-05-12/2025-05-18" (far too wide for tick labels), so use the
    # period start date and let Plotly's tickformat compress it.
    x_labels = [ts.strftime("%Y-%m-%d") for ts in pivot.index.to_timestamp()]

    # Build traces data
    traces = []
    colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
    ]

    # Per-trace translucent fill to zero: every curve is independent, so
    # toggling a lens via the legend removes exactly that trace. Stacked
    # modes (fill:"tonexty", stackgroup) re-bind/re-stack the remaining
    # traces on toggle, which reads as other lenses changing color/shape.
    def _rgba(hex_color: str, alpha: float) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    for i, col in enumerate(pivot.columns):
        c = colors[i % len(colors)]
        traces.append({
            "name": col,
            "x": x_labels,
            "y": pivot[col].tolist(),
            "type": "scatter",
            "mode": "lines+markers",
            "fill": "tozeroy",
            "fillcolor": _rgba(c, 0.18),
            "line": {"color": c, "width": 1.5},
            "marker": {"size": 4},
        })

    layout = {
        "title": {"text": "Photo Count by Lens Over Time", "font": {"size": 16}},
        "xaxis": {
            "title": "Date",
            "showgrid": True,
            "tickangle": -45,
            "tickformat": "%y-%m",
            "nticks": 14,
        },
        "yaxis": {"title": "Photo Count", "showgrid": True},
        "hovermode": "x unified",
        # Legend below the x-axis title (title sits just under the tick
        # labels); yanchor top pins the first row at y so the rows extend
        # downward into the reserved bottom margin.
        "legend": {
            "orientation": "h", "y": -0.28, "yanchor": "top",
            "x": 0.5, "xanchor": "center", "font": {"size": 11},
        },
        "height": 630,
        "margin": {"l": 60, "r": 30, "t": 60, "b": 150},
    }

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Photo Count by Lens Over Time</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 8px 12px; }}
        #chart {{ width: 100%; height: 630px; }}
        .legend-note {{ color: #666; font-size: 12px; margin: 2px 0 0; text-align: center; }}
    </style>
</head>
<body>
    <div id="chart"></div>
    <p class="legend-note">Top {top_n} lenses + Other | Hover for details | Click legend to toggle</p>
    <script>
        var traces = {json.dumps(traces)};
        Plotly.newPlot('chart', traces, {json.dumps(layout)}, {{responsive: true}});
    </script>
</body>
</html>"""

    if filename:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Saved interactive chart: {filename}")

    return filename
