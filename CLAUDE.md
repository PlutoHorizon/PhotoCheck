# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**PhotoCheck** — Python tool that extracts EXIF metadata from a photo library (primarily Sony `.arw` RAW files) and produces visualizations of shooting patterns. Single-user, runs locally against a local photo folder.

**Stack**: Python 3.10+ · piexif · pandas · pyarrow · matplotlib · seaborn · tqdm · uv

## Common Commands

```bash
# Install deps
uv sync

# Recommended: edit run.py SCAN_FOLDER, then:
uv run python run.py

# CLI equivalents
uv run python -m photocheck scan /path/to/photos --crop-factor 1.5
uv run python -m photocheck analyze --type all --field focal_length
uv run python -m photocheck interactive

# No test suite exists yet (pytest is declared in dev deps only)
```

## Architecture — Data Pipeline

The codebase is one linear pipeline split across three layers:

```
cli.py (orchestration)
   │
   ├─► core/extractor.py   — piexif → PhotoMetadata
   ├─► core/pairing.py     — basename-grouped dedup by EXIF signature
   ├─► core/cache.py       — Parquet ↔ PhotoMetadata list
   └─► viz/{histograms,timeline}.py — PhotoMetadata → PNG/HTML
```

**Key abstraction**: `PhotoMetadata` (a `@dataclass` in `core/models.py`) is the only data type that flows through the entire system. Every module takes `List[PhotoMetadata]` and returns `List[PhotoMetadata]` or None. There is no ORM, no DB session — just dataclass + Parquet serialization.

## Critical Architectural Decisions

### 1. ARW-only by design
`DEFAULT_EXTENSIONS = [".arw", ".ARW"]` in `cli.py:22`. ARW is Sony's RAW format. JPG is intentionally ignored. If a user wants to include JPG, they pass `--extensions .arw,.jpg`, but `pairing.py` is the only module that knows about the ARW/JPG relationship (via `resolve_file_pair` — though it's never called in the current flow).

### 2. Crop factor applied at extraction, not visualization
In `extractor.py:91`, focal length is multiplied by `crop_factor` **once** during extraction, then stored in the cache as the "35mm equivalent". All downstream viz code assumes focal length is already normalized. This means changing crop factor requires a re-scan (cache is invalidated only by mtime).

### 3. Dedup signature
`pairing.py:78 deduplicate_by_metadata()` groups files by `Path.stem` (basename without extension), then within each group compares a 5-tuple signature: `(datetime_original, f_stop, shutter_speed, focal_length, iso)`. **This is more expensive than it looks** — every duplicate candidate triggers a full EXIF parse. No fuzzy matching, no date tolerance.

### 4. Cache invalidation
`cli.py:88-95` does **not use `get_stale_files()`** despite the helper existing in `cache.py:111`. Instead, the cache is loaded, the cached entries that still exist on disk are kept, and the remaining new file paths are processed. **mtime is stored in the cache but never read back** for invalidation. Files that were modified after caching will be re-processed only if their path was deleted and recreated.

### 5. Visualization functions are pure
Every function in `viz/histograms.py` and `viz/timeline.py` takes `List[PhotoMetadata]` + `filename`, builds a figure, saves, and closes — no global state, no plt subplot sharing. Safe to call concurrently *per figure* but each figure is single-threaded internally.

### 6. `plot_timeline_by_lens_html()` does not use plotly Python
`viz/timeline.py:298` writes a hand-built HTML file that pulls plotly.js from CDN (`https://cdn.plot.ly/plotly-2.27.0.min.js`). The Python `plotly` package is **not** a dependency. This means the generated HTML works offline only if the user has the plotly.js cached.

## Configuration

Two config files, both read independently — `run.py` wins for `run.py` mode, `photocheck.toml` wins for CLI mode:

| File | Read by | Used for |
|------|---------|----------|
| `run.py` (top constants) | `run.py` directly | `uv run python run.py` |
| `photocheck.toml` | `cli.py:43 load_config()` | `python -m photocheck` |

`run.py` constructs an `argparse` argument list by hand and calls `cli_main(args_list)` — see `run.py:38-67`. This bypasses `sys.argv` parsing entirely.

## Output Convention

- All charts go to `output/` (project-relative, computed in `cli.py:27-29` from `__file__`).
- `output/` and `data/` are gitignored — they are local artifacts.
- `timeline_by_lens.html` is the only interactive output. Everything else is static PNG at 150 DPI.

## Known Gaps

- **No `tests/` directory**. `pytest` is in `[project.optional-dependencies].dev` but unused. Adding tests requires creating the directory.
- **`models.py:27 focal_length_35mm` property is a no-op** — returns `self.focal_length`. The crop factor is already baked in during extraction, so this property is misleading. Either remove it or compute it from a separate "raw focal length" field.
- **`cache.py:111 get_stale_files()` is dead code** — never imported by `cli.py`.
- **`pairing.py:13 resolve_file_pair()` is dead code** — never called.
- **No CI/CD** (no `.github/`, no `.gitlab-ci.yml`).
- **Plotly is loaded from CDN** — offline HTML viewing will fail without network on first load.
