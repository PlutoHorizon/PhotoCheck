"""Timeline visualizations for PhotoCheck."""

from collections import Counter
from datetime import datetime
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd

from ..core.models import PhotoMetadata


plt.rcParams["axes.unicode_minus"] = False


def plot_timeline_scatter(
    metadata_list: list[PhotoMetadata],
    field: str = "focal_length",
    title: str = None,
    filename: Optional[str] = None,
) -> Optional[str]:
    """Plot datetime vs specified field as scatter plot.

    Args:
        metadata_list: List of PhotoMetadata objects
        field: Field to plot on Y-axis ('focal_length', 'iso', 'f_stop', 'shutter_speed')
        title: Chart title (auto-generated if None)
        filename: If provided, save chart to this path instead of displaying
    """
    field_names = {
        "focal_length": "Focal Length",
        "iso": "ISO",
        "f_stop": "Aperture",
        "shutter_speed": "Shutter Speed",
    }

    if title is None:
        title = f"{field_names.get(field, field)} Timeline"

    # Extract data with datetime_original
    dates = []
    values = []

    for m in metadata_list:
        if m.error is not None or m.datetime_original is None:
            continue

        val = getattr(m, field, None)
        if val is not None and val > 0:
            dates.append(m.datetime_original)
            values.append(val)

    if not dates:
        print(f"No valid data for timeline plot (field={field})")
        return None

    plt.figure(figsize=(14, 6))
    plt.scatter(dates, values, alpha=0.5, s=20, c="steelblue")

    plt.title(title, fontsize=14, fontweight="bold")
    plt.xlabel("Capture Time", fontsize=12)
    plt.ylabel(field_names.get(field, field), fontsize=12)
    plt.grid(alpha=0.3)

    # Format x-axis dates
    plt.gcf().autofmt_xdate()

    plt.tight_layout()

    saved_path = None
    if filename:
        plt.savefig(filename, dpi=150, bbox_inches="tight")
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
    """Plot hourly shooting frequency heatmap.

    Shows which hours of the day have most photo activity.

    Args:
        metadata_list: List of PhotoMetadata objects
        title: Chart title
        field: Field to aggregate ('focal_length', 'iso', or None for count)
        filename: If provided, save chart to this path instead of displaying
    """
    # Extract hour and field value
    hour_data = []

    for m in metadata_list:
        if m.error is not None or m.datetime_original is None:
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

    # Count photos per hour (0-23)
    hour_counts = Counter(hour_data)
    hours = list(range(24))
    counts = [hour_counts.get(h, 0) for h in hours]

    # Create heatmap-style bar chart
    plt.figure(figsize=(14, 6))

    # Use a colormap to show intensity
    colors = plt.cm.YlOrRd([c / max(counts) if max(counts) > 0 else 0 for c in counts])

    bars = plt.bar(hours, counts, color=colors, edgecolor="darkred", alpha=0.8)

    # Add count labels
    for bar, count in zip(bars, counts):
        if count > 0:
            plt.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(counts) * 0.01,
                str(count),
                ha="center",
                va="bottom",
                fontsize=9,
            )

    plt.title(title, fontsize=14, fontweight="bold")
    plt.xlabel("Hour (0-23)", fontsize=12)
    plt.ylabel("Photo Count", fontsize=12)
    plt.xticks(hours)
    plt.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    saved_path = None
    if filename:
        plt.savefig(filename, dpi=150, bbox_inches="tight")
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
        if m.error is not None or m.datetime_original is None:
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
    for m in metadata_list:
        if m.error is not None or m.datetime_original is None or m.lens_name is None:
            continue
        records.append({
            "date": pd.Timestamp(m.datetime_original),
            "lens": m.lens_name[:30],  # Truncate long names
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
    plt.legend(loc="upper left", fontsize=8, ncol=2)
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
    for m in metadata_list:
        if m.error is not None or m.datetime_original is None or m.lens_name is None:
            continue
        records.append({
            "date": pd.Timestamp(m.datetime_original),
            "lens": m.lens_name,
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

    # Convert period to string for JSON
    x_labels = [str(p) for p in pivot.index]

    # Build traces data
    traces = []
    colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
    ]

    for i, col in enumerate(pivot.columns):
        traces.append({
            "name": col,
            "x": x_labels,
            "y": pivot[col].tolist(),
            "type": "scatter",
            "mode": "lines+markers",
            "fill": "tonexty" if i > 0 else "none",
            "line": {"color": colors[i % len(colors)]},
            "marker": {"size": 4},
        })

    layout = {
        "title": {"text": "Photo Count by Lens Over Time", "font": {"size": 16}},
        "xaxis": {
            "title": "Date",
            "showgrid": True,
            "tickangle": -45,
            "tickmode": "auto",
            "nticks": 20,
        },
        "yaxis": {"title": "Photo Count", "showgrid": True},
        "hovermode": "x unified",
        "legend": {"orientation": "h", "y": -0.3, "x": 0.5, "xanchor": "center"},
        "height": 700,
        "margin": {"l": 60, "r": 30, "t": 60, "b": 180},
    }

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Photo Count by Lens Over Time</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        #chart {{ width: 100%; height: 700px; }}
        .legend-note {{ color: #666; font-size: 12px; margin-top: 10px; }}
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
