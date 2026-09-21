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
- **HTML Report** (new): Consolidated self-contained `report/` folder with hero stats, all charts, and interactive timeline
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
| `CROP_FACTOR` | Deprecated — see "Focal length resolution" below | 1.0 |
| `WORKERS` | Thread count | 8 |
| `DO_REPORT` | Generate HTML report | True |
| `REPORT_DIR` | Report output directory | `./report` |
| `TOP_LENSES` | Top N lenses inlined on main page | 5 |

### Focal length resolution

The focal length stored in the cache is **always** the 35mm-equivalent value, regardless of sensor size. Resolution priority:

1. **EXIF `FocalLengthIn35mmFilm` (0xA405)** — the manufacturer-reported 35mm equivalent. Used as-is when present (Sony FF bodies, Nikon Z8, etc.).
2. **Raw `FocalLength` × camera crop factor** — for bodies that don't write the 35mm tag (Sony APS-C like a6400, Canon EF-S bodies, all MFT). Crop factors are looked up in `CAMERA_CROP_FACTORS` in `core/extractor.py`, plus any `[[crop_factors]]` overrides from `photocheck.toml`.
3. **Raw `FocalLength` as-is** — when the body is unknown. Conservative default (no conversion), still better than nothing.

This means a Sony a6400 + E 18-135mm records as 27-202mm (physical × 1.5), while a Sony a7C II + FE 200-600mm records as 200-600mm (from the 35mm tag). They can be plotted together on the same axis.

#### Custom crop factors

The built-in `CAMERA_CROP_FACTORS` table covers ~50 common bodies. For unusual cameras (Fuji GFX, OM System OM-1, Sony RX1, etc.), add entries to `photocheck.toml`:

```toml
[[crop_factors]]
match = "GFX100S"
factor = 0.79            # medium format (<1.0 means wider than 35mm)

[[crop_factors]]
match = "OM-1"
factor = 2.0             # OM System OM-1 (MFT)

[[crop_factors]]
match = "ILCE-6400"
factor = 1.0             # force a specific body to be treated as FF
```

The `match` field is a **prefix** against the EXIF `Camera Model` value. Lookup is longest-prefix-wins, so an entry `"ILCE-6400"` overrides the built-in `"ILCE-6"` (which would otherwise match every Sony APS-C body).

## HTML Report

After running `scan` and `analyze`, generate a consolidated HTML report:

```bash
uv run python -m photocheck report
# Or specify output directory
uv run python -m photocheck report --output ./my_report
# Or change the number of inlined top lenses (default: 5)
uv run python -m photocheck report --top-lenses 8
```

The `report/` folder contains `index.html` (consolidated report with hero stats, all charts, and interactive timeline via iframe) and `lenses.html` (subpage listing every lens with counts and share). Design follows a Minimal / Swiss aesthetic — white background, sans-serif, no JavaScript dependencies except the embedded Plotly iframe.

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

## Photo Filtering Logic

`scan` applies three filters before EXIF extraction to avoid wasting I/O on garbage:

### 1. Format support (by extension + magic bytes)

Default `DEFAULT_EXTENSIONS` covers all common RAW + standard formats:

| Manufacturer | RAW | Standard |
|---|---|---|
| Sony | `.arw` | |
| Nikon | `.nef` | |
| Canon | `.cr2`, `.cr3` | |
| Adobe / Universal | `.dng` | |
| Fuji | `.raf` | |
| Olympus | `.orf` | |
| JPEG / WebP / TIFF | | `.jpg`, `.jpeg`, `.webp`, `.tif`, `.tiff` |

Each file is also validated by **magic bytes** (first 8 bytes):
- `FF D8 FF` → JPEG
- `II *\0` / `MM\0 *` → TIFF (covers ARW, NEF, CR2, DNG, ORF, generic TIFF)
- `FUJIFOTO` → Fuji RAF
- `RIFF...WEBP` → WebP

Files with valid extension but invalid magic bytes are silently skipped. HEIC/HEIF is not supported (would need `exifread`).

### 2. System folder skip

The following paths are skipped during discovery (no stat, no magic check):

```
$RECYCLE.BIN                (Windows recycle bin)
System Volume Information   (Windows)
.Spotlight-V100             (macOS Spotlight cache)
.Trashes                     (macOS trash)
.fseventsd, .TemporaryItems, .DocumentRevisions-V100
Thumbs.db
```

### 3. macOS AppleDouble skip

Files starting with `._` are skipped. These are macOS resource-fork metadata companions (e.g., `._DSC0001.ARW` next to the real `DSC0001.ARW`) — not real images.

### 4. Duplicate detection (content-hash dedup)

Photos are deduplicated using a 6-tuple signature:

```
(datetime_original, f_stop, shutter_speed, focal_length, iso, file_number)
```

The `file_number` is the trailing numeric sequence parsed from the file stem:
- `DSC05833.ARW` → `5833`
- `IMG_1234` → `1234`
- `vacation_sunset` → `None`

This breaks ties between burst-mode photos (Sony assigns sequential numbers like 5833, 5834, 5835) so a 6-shot burst stays as 6 records instead of collapsing into 1.

Same-photo detection across formats works because ARW and JPG exports share the same stem:

```
/raw/DSC05833.ARW   → file_number=5833
/jpg/DSC05833.JPG   → file_number=5833   ← same signature, deduped
```

### 5. mtime check intentionally disabled

Camera RAW EXIF is set at capture and doesn't change after. mtime-based re-extraction triggers false positives for any unrelated file modification (e.g., a re-export touching the mtime without changing EXIF). Cache lookup is purely path-based.

To force re-extraction of a known file: rename it or delete the cache entry manually.

## Partial EXIF Read

For each photo, `extract_metadata` reads only the first **256 KB** of the file instead of the entire RAW payload. EXIF IFDs (including Sony/Nikon/Canon MakerNotes) live in the file header — on a typical 40 MB Sony ARW, the EXIF region is ~135 KB, so the partial read is **~0.3% of the file size**.

Measured on internal SSD: **3.64 ms/file → 0.07 ms/file (~50× faster)**. The speedup is even larger on slower external drives (USB / NAS) where I/O dominates.

Safety:
- Files smaller than 256 KB use the standard full-file read path (no overhead).
- If any IFD offset points past the 256 KB buffer, piexif raises `struct.error` and the code falls back to reading the whole file. Verified against a real Sony ARW header fixture (`tests/fixtures/arw_header_256k.bin`).

The optimization is transparent — same output, same cache schema, no migration needed.

## Requirements

- Python 3.12+
- uv (package manager)

Install dependencies:

```bash
uv sync
```
