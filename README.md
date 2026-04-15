# PhotoCheck

Photo EXIF metadata analysis tool — extract and visualize shooting patterns from your photo library.

## Features

- **EXIF Extraction**: Focal length, aperture, ISO, shutter speed, lens name, capture time
- **Deduplication**: Automatic ARW/JPG pairing based on metadata
- **Caching**: Parquet-based cache with mtime change detection
- **Visualizations**:
  - Focal length / aperture / lens distribution histograms
  - Timeline scatter plots (datetime vs any field)
  - Hourly shooting heatmap
  - Lens usage over time (stacked area + interactive HTML)
  - Per-lens detail charts
- **Flexible**: CLI, interactive menu, or Python API

## Quick Start

```bash
# Edit run.py with your photo folder path
# SCAN_FOLDER = "/path/to/photos"

# Run
uv run python run.py
```

## Usage Modes

### 1. Run Script (Recommended)

Edit `run.py` configuration section, then:

```bash
uv run python run.py
```

### 2. CLI

```bash
# Scan photos
uv run python -m photocheck scan /path/to/photos --crop-factor 1.5

# Generate visualizations
uv run python -m photocheck analyze --type all
```

### 3. Interactive Menu

```bash
uv run python -m photocheck interactive
```

## Configuration

Edit `photocheck.toml` or `run.py`:

| Setting | Description | Default |
|---------|-------------|---------|
| `SCAN_FOLDER` | Path to photos | - |
| `CROP_FACTOR` | Sensor crop factor (1.0=FF, 1.5=APS-C) | 1.0 |
| `WORKERS` | Thread count | 8 |

## Output

All generated charts saved to `output/`:

- `focal_histogram.png` — Focal length distribution
- `fstop_histogram.png` — Aperture distribution
- `lens_histogram.png` — Lens usage frequency
- `timeline_*.png` — Timeline scatter plots
- `hourly_heatmap.png` — Shooting frequency by hour
- `timeline_by_lens.png` — Lens usage stacked area chart
- `timeline_by_lens.html` — **Interactive** lens timeline (Plotly)
- `lens_*.png` — Per-lens detail charts

## Requirements

- Python 3.12+
- uv (package manager)

Install dependencies:

```bash
uv sync
```
