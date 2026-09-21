"""Histogram visualizations for PhotoCheck."""

from collections import Counter
from typing import List, Callable, Optional

import matplotlib.pyplot as plt

from ..core.models import PhotoMetadata


plt.rcParams["axes.unicode_minus"] = False


def classify_focal(focal_length: float) -> int:
    """Classify focal length into standard lens categories."""
    if focal_length < 19:
        return round(focal_length)
    elif 19 <= focal_length <= 21:
        return 20
    elif 21 < focal_length < 23:
        return 22
    elif 23 <= focal_length < 26:
        return 24
    elif 26 <= focal_length < 29:
        return 28
    elif 29 <= focal_length < 38:
        return 35
    elif 38 <= focal_length < 42.5:
        return 40
    elif 42.5 <= focal_length < 77.5:
        return round(focal_length / 5) * 5
    elif 77.5 <= focal_length <= 94.5:
        return 85
    elif 94.5 < focal_length <= 110:
        return 105
    elif 110 < focal_length <= 148.5:
        return 135
    elif 148.5 < focal_length <= 181.5:
        return 165
    elif 181.5 < focal_length <= 200:
        return 200
    else:
        return round(focal_length / 50) * 50


def _get_field_values(
    metadata_list: List[PhotoMetadata],
    getter: Callable[[PhotoMetadata], any],
    filter_fn: Callable[[any], bool] = lambda x: True,
) -> List:
    """Extract field values from metadata list using Counter."""
    values = []
    for m in metadata_list:
        if m.error is not None:
            continue
        val = getter(m)
        if val is not None and filter_fn(val):
            values.append(val)
    return values


def plot_lens_detail(
    metadata_list: List[PhotoMetadata],
    output_dir: str,
) -> List[str]:
    """Plot focal and aperture distribution for each lens.

    Args:
        metadata_list: List of PhotoMetadata objects
        output_dir: Directory to save charts

    Returns:
        List of saved file paths
    """
    from collections import defaultdict
    import os

    saved_paths = []

    # Group by lens
    by_lens: dict[str, list[PhotoMetadata]] = defaultdict(list)
    for m in metadata_list:
        if m.error is not None or m.lens_name is None:
            continue
        by_lens[m.lens_name].append(m)

    print(f"Found {len(by_lens)} lenses")

    for lens_name, photos in sorted(by_lens.items(), key=lambda x: len(x[1]), reverse=True):
        # Short name for filename (strip characters illegal on Windows)
        short_name = lens_name[:30]
        for ch in '\\/:*?"<>|':
            short_name = short_name.replace(ch, "-")

        # Focal length distribution
        focal_values = [m.focal_length for m in photos if m.focal_length is not None and m.focal_length >= 7]
        if focal_values:
            classified = [classify_focal(f) for f in focal_values]
            counts = Counter(classified)
            sorted_items = sorted(counts.items())
            focals = [item[0] for item in sorted_items]
            focal_counts = [item[1] for item in sorted_items]

            filepath = os.path.join(output_dir, f"lens_{short_name}_focal.png")
            _plot_bar_chart(
                focals,
                focal_counts,
                title=f"Focal: {lens_name}",
                xlabel="Focal Length (mm)",
                ylabel="Photo Count",
                filename=filepath,
            )
            saved_paths.append(filepath)

        # Aperture distribution
        fstop_values = [m.f_stop for m in photos if m.f_stop is not None and m.f_stop > 0]
        if fstop_values:
            counts = Counter(fstop_values)
            sorted_items = sorted(counts.items())
            fstops = [item[0] for item in sorted_items]
            fstop_counts = [item[1] for item in sorted_items]

            filepath = os.path.join(output_dir, f"lens_{short_name}_fstop.png")
            _plot_bar_chart(
                fstops,
                fstop_counts,
                title=f"Aperture: {lens_name}",
                xlabel="F-Stop",
                ylabel="Photo Count",
                filename=filepath,
            )
            saved_paths.append(filepath)

    print(f"Saved {len(saved_paths)} lens detail charts")
    return saved_paths


def plot_focal_histogram(
    metadata_list: List[PhotoMetadata],
    title: str = "Focal Length Distribution",
    xlabel: str = "Focal Length (mm)",
    ylabel: str = "Photo Count",
    filename: Optional[str] = None,
) -> Optional[str]:
    """Plot focal length distribution histogram."""
    raw_values = _get_field_values(
        metadata_list,
        lambda m: m.focal_length,
        filter_fn=lambda x: x >= 7,
    )

    if not raw_values:
        print("No valid focal length data to plot")
        return None

    # Classify and count using Counter (O(n))
    classified = [classify_focal(f) for f in raw_values]
    counts = Counter(classified)
    sorted_items = sorted(counts.items())

    focal_lengths = [item[0] for item in sorted_items]
    photo_counts = [item[1] for item in sorted_items]

    return _plot_bar_chart(
        focal_lengths,
        photo_counts,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
        filename=filename,
    )


def plot_fstop_histogram(
    metadata_list: List[PhotoMetadata],
    title: str = "Aperture Distribution",
    xlabel: str = "F-Stop",
    ylabel: str = "Photo Count",
    filename: Optional[str] = None,
) -> Optional[str]:
    """Plot F-stop distribution histogram."""
    values = _get_field_values(
        metadata_list,
        lambda m: m.f_stop,
        filter_fn=lambda x: x > 0,
    )

    if not values:
        print("No valid F-stop data to plot")
        return None

    counts = Counter(values)
    sorted_items = sorted(counts.items())

    f_stops = [item[0] for item in sorted_items]
    photo_counts = [item[1] for item in sorted_items]

    return _plot_bar_chart(
        f_stops,
        photo_counts,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
        filename=filename,
    )


def plot_lens_histogram(
    metadata_list: List[PhotoMetadata],
    title: str = "Lens Distribution",
    xlabel: str = "Lens Name",
    ylabel: str = "Photo Count",
    filename: Optional[str] = None,
) -> Optional[str]:
    """Plot lens name distribution histogram."""
    values = _get_field_values(
        metadata_list,
        lambda m: m.lens_name,
    )

    if not values:
        print("No valid lens name data to plot")
        return None

    counts = Counter(values)
    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    lens_names = [item[0][:30] for item in sorted_items]  # Truncate long names
    photo_counts = [item[1] for item in sorted_items]

    return _plot_bar_chart(
        range(len(lens_names)),
        photo_counts,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
        tick_labels=lens_names,
        filename=filename,
    )


def _plot_bar_chart(
    x_values: list,
    counts: list,
    title: str,
    xlabel: str,
    ylabel: str,
    tick_labels: Optional[list] = None,
    filename: Optional[str] = None,
) -> Optional[str]:
    """Helper to create a bar chart in Minimal Swiss style (black/gray, no color)."""
    # Match report CSS tokens
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [
        "-apple-system", "BlinkMacSystemFont", "Segoe UI",
        "PingFang SC", "Hiragino Sans GB", "sans-serif",
    ]

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("#fff")
    ax.set_facecolor("#fff")

    # Hide top/right spines, light gray remaining
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#1a1a1a")
        ax.spines[side].set_linewidth(0.8)

    bars = ax.bar(
        range(len(x_values)), counts,
        color="#1a1a1a", edgecolor="#1a1a1a", linewidth=0, width=0.7,
    )

    if tick_labels is not None:
        ax.set_xticks(range(len(tick_labels)))
        ax.set_xticklabels(tick_labels, rotation=45, ha="right", color="#1a1a1a", fontsize=10)
    else:
        ax.set_xticks(range(len(x_values)))
        ax.set_xticklabels(x_values, rotation=45, ha="right", color="#1a1a1a", fontsize=10)

    # Tick params
    ax.tick_params(axis="y", colors="#1a1a1a", labelsize=10, length=0)
    ax.tick_params(axis="x", colors="#1a1a1a", length=0)

    # Count labels above bars
    max_count = max(counts) if counts else 1
    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_count * 0.015,
            str(count),
            ha="center", va="bottom",
            color="#888", fontsize=9,
            family="monospace",
        )

    ax.set_title(title, fontsize=13, fontweight=500, color="#1a1a1a", loc="left", pad=15)
    ax.set_xlabel(xlabel, fontsize=10, color="#888", labelpad=10)
    ax.set_ylabel(ylabel, fontsize=10, color="#888", labelpad=10)

    # Subtle horizontal grid only
    ax.yaxis.grid(True, color="#e5e5e5", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    # Strip top/right padding
    ax.margins(y=0.15)

    plt.tight_layout()

    saved_path = None
    if filename:
        plt.savefig(filename, dpi=150, bbox_inches="tight", facecolor="#fff")
        saved_path = filename
        print(f"Saved: {filename}")

    plt.close()
    return saved_path
