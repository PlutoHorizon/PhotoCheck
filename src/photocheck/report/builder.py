"""Orchestration: copy charts, compute stats, render templates."""

import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from ..core.models import PhotoMetadata
from ..viz.histograms import _plot_bar_chart, classify_focal
from .renderer import render_lenses, render_report
from .stats import _valid, compute_all


# PNGs/HTML that exist in output/ and get copied verbatim into report/charts/
# Filenames match what cli.analyze_command writes (see cli.py:166-197)
_BASE_CHARTS = [
    "focal_histogram.png",
    "fstop_histogram.png",
    "lens_histogram.png",
    "timeline_focal_length.png",
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
    """Generate per-lens focal/fstop PNGs for the top N lenses."""
    valid = _valid(metadata)
    by_lens: dict[str, list[PhotoMetadata]] = defaultdict(list)
    for m in valid:
        if m.lens_name is not None:
            by_lens[m.lens_name].append(m)

    written: list[str] = []
    for lens in top_lenses:
        name = lens["name"]
        position = lens["position"]
        photos = by_lens.get(name, [])
        if not photos:
            continue

        # Focal length
        focals = [
            m.focal_length
            for m in photos
            if m.focal_length is not None and m.focal_length >= 7
        ]
        if focals:
            bucketed = [classify_focal(f) for f in focals]
            counts = sorted(Counter(bucketed).items(), key=lambda x: x[0])
            xs = [c[0] for c in counts]
            ys = [c[1] for c in counts]
            path = output_dir / f"lens_top{position}_focal.png"
            _plot_bar_chart(
                xs, ys,
                title=f"Focal: {name}",
                xlabel="Focal Length (mm)",
                ylabel="Photo Count",
                filename=str(path),
            )
            written.append(path.name)

        # Aperture
        fstops = [
            m.f_stop for m in photos if m.f_stop is not None and m.f_stop > 0
        ]
        if fstops:
            counts = sorted(Counter(fstops).items(), key=lambda x: x[0])
            xs = [c[0] for c in counts]
            ys = [c[1] for c in counts]
            path = output_dir / f"lens_top{position}_fstop.png"
            _plot_bar_chart(
                xs, ys,
                title=f"Aperture: {name}",
                xlabel="F-Stop",
                ylabel="Photo Count",
                filename=str(path),
            )
            written.append(path.name)
    return written


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
    from ..cli import OUTPUT_DIR  # lazy import: avoids circular dependency

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

    # 2. Copy base charts (may be empty if analyze hasn't run)
    _copy_base_charts(charts_src, charts_dst)

    # 3. Generate per-lens top-N charts
    _generate_top_lens_charts(metadata, stats["top_lenses"], charts_dst)

    # 4. Render templates
    context = {**stats, "charts_dir": "charts", "generated_at": generated_at}
    index_path = output_dir / "index.html"
    render_report(context, index_path)
    render_lenses(context, output_dir / "lenses.html")

    return index_path
