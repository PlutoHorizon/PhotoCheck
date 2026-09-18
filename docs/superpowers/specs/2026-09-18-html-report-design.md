# PhotoCheck HTML Report — Design Spec

**Date:** 2026-09-18
**Status:** Approved (awaiting plan)
**Author:** Brainstorming session

## Goal

Extend PhotoCheck with a new `report` subcommand that produces a self-contained HTML report folder (`report/index.html` + relative `charts/` assets) consolidating the existing static PNG charts, the interactive Plotly chart, and a new hero stats block. The new flow sits on top of — and does not modify — the existing `scan` and `analyze` flows.

## Design Decisions (from brainstorming)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Output form | **B. Folder + relative refs** | HTML lightweight, OS can preview PNGs, browser caches images |
| Hero cards | 6 cards (no 最长连续拍摄) | User selected 6, second click on longest-streak was a deselect |
| Invocation | **A. New `report` subcommand** | Clean separation; future extensions (email, upload) independent |
| Visual style | **B. Minimal / Swiss** | Clean, data-forward, photographer's personal tool aesthetic |
| Interactive chart | **A. iframe embed** | Zero changes to existing `plot_timeline_by_lens_html`; natural in folder mode |
| Lens details | **A. Top 5 inline + "view all" link** | Top 5 lenses cover ~80% of data; report stays scannable |
| Template engine | **A. Jinja2** | Clean logic/presentational split; ~200KB dep is acceptable; designer can edit HTML independently |

## Hero Stat Cards (6)

1. **主力镜头** (Main lens) — most-used lens + photo count + percentage
2. **最常用焦距** (Most-used focal length) — bucketed via `classify_focal()` + percentage
3. **最常用光圈** (Most-used aperture) — `Counter(f_stop).most_common(1)` + percentage
4. **最忙月份** (Peak month) — `YYYY-MM` with highest photo count
5. **拍摄跨度** (Shooting span) — `(max_date - min_date).days` + years approximation
6. **拍摄天数** (Active days) — unique date count + ratio of total span

## Architecture

```
report subcommand triggered
    ↓
[1] Read cache → List[PhotoMetadata]    (reuses core.cache.load_cache)
    ↓
[2] Compute stats → dict                (NEW: report/stats.py — pure functions)
    ↓
[3] Generate all PNG/HTML charts        (reuses viz/ — unchanged)
    ↓
[4] Copy/symlink charts into report/charts/
    ↓
[5] Render templates via Jinja2 → report/{index,lenses}.html
    ↓
report/
├── index.html                    (~30KB, Jinja2-rendered)
├── lenses.html                   (all-lens detail subpage)
└── charts/
    ├── focal.png
    ├── fstop.png
    ├── lens.png
    ├── timeline_focal.png
    ├── hourly_heatmap.png
    ├── lens_top1_focal.png ... lens_top5_fstop.png
    └── timeline_by_lens.html    (iframe target)
```

### Key principles

1. **Zero changes to existing code** — all `viz/` functions remain untouched. The report flow *calls* them.
2. **`output/` keeps its current contents** — `report/` is a *separate* output directory containing its own copies of the charts (not symlinks, to keep the folder portable when zipped/shared).
3. **Jinja2 owns the HTML structure** — Python computes data, Jinja2 renders.
4. **`timeline_by_lens.html` is embedded via iframe** in `index.html`, pointing at the copy under `report/charts/`.

## New Files

```
src/photocheck/
├── report/
│   ├── __init__.py
│   ├── builder.py        # build_report() orchestration; called by cli.report_command
│   ├── stats.py          # pure stat functions
│   └── renderer.py       # Jinja2 rendering wrapper
└── templates/
    ├── report.html.j2     # main report template
    └── lenses.html.j2     # all-lens detail subpage

tests/
├── test_stats.py
├── test_renderer.py
└── fixtures/
    ├── sample_metadata.json     (10 photos, full data)
    ├── empty_metadata.json      (empty list)
    └── partial_metadata.json    (some None fields)
```

## Module Specifications

### `report/stats.py` — Pure Functions

All functions are **pure** (no side effects, no I/O) and **defensive** (re-filter `m.error is not None` even if upstream already did).

| Function | Signature | Returns |
|----------|-----------|---------|
| `main_lens(metadata)` | `List[PhotoMetadata] → dict` | `{name, count, pct}` or `{value: None, note: "无数据"}` |
| `main_focal(metadata)` | same | `{focal, count, pct}` (uses `viz.histograms.classify_focal`) |
| `main_aperture(metadata)` | same | `{fstop, count, pct}` |
| `peak_month(metadata)` | same | `{label: "YYYY-MM", count}` |
| `span(metadata)` | same | `{days, years_approx}` |
| `active_days(metadata)` | same | `{days, total_span_days, ratio}` |
| `top_lenses(metadata, n=5)` | same | `[(name, count, focal_png, fstop_png, pct), ...]` |
| `all_lenses(metadata)` | same | `[(name, count), ...]` for `lenses.html` |
| `hourly_distribution(metadata)` | same | `list[int]` of length 24 |
| `compute_all(metadata, top_n=5)` | same | `dict` aggregating all of the above (the single entry called by builder); passes `top_n` through to `top_lenses()` |

**Empty data policy:** if all photos have `error is not None`, every function returns the "无数据" sentinel. The renderer checks for this and shows a "暂无数据" message instead of empty cards.

**Missing section policy:** if a stat function's data is all None, the section is omitted entirely (not rendered as an empty block).

### `report/renderer.py` — Jinja2 Wrapper

```python
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

def get_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )

def render_report(context: dict, output_path: Path) -> None:
    env = get_env()
    template = env.get_template("report.html.j2")
    output_path.write_text(template.render(**context), encoding="utf-8")

def render_lenses(context: dict, output_path: Path) -> None:
    env = get_env()
    template = env.get_template("lenses.html.j2")
    output_path.write_text(template.render(**context), encoding="utf-8")
```

### `report/builder.py` — Orchestration

```python
def build_report(
    metadata: List[PhotoMetadata],
    output_dir: Path,
    top_lenses_n: int = 5,
) -> Path:
    """Build the full report/ folder. Returns path to index.html."""
    charts_src = OUTPUT_DIR                # existing output/
    charts_dst = output_dir / "charts"

    # 1. Compute stats
    stats = compute_all(metadata, top_n=top_lenses_n)
    # (compute_all internally calls all hero functions + top_lenses + all_lenses + hourly_distribution)

    # 2. Prepare charts folder (copy PNGs, copy timeline_by_lens.html)
    output_dir.mkdir(parents=True, exist_ok=True)
    charts_dst.mkdir(parents=True, exist_ok=True)
    _copy_charts(charts_src, charts_dst, top_lenses_n, metadata)

    # 3. Render templates
    context = {**stats, "charts_dir": "charts"}
    index_path = output_dir / "index.html"
    render_report(context, index_path)

    lenses_path = output_dir / "lenses.html"
    render_lenses({**stats, "charts_dir": "charts"}, lenses_path)

    return index_path
```

The `_copy_charts` helper:
- Copies: `focal.png`, `fstop.png`, `lens.png`, `timeline_focal.png`, `hourly_heatmap.png`, `timeline_by_lens.html` from `output/` to `report/charts/`
- Generates Top 5 lens detail PNGs into `report/charts/lens_top{N}_focal.png` and `lens_top{N}_fstop.png` by calling `plot_lens_detail` filtered to top 5 lenses

## CLI Integration

```python
# cli.py — new subparser
report_parser = subparsers.add_parser("report", help="Generate HTML report")
report_parser.add_argument(
    "--output", "-o",
    default=None,
    help="报告输出目录 (默认: ./report/)",
)
report_parser.add_argument(
    "--top-lenses", "-n",
    type=int,
    default=5,
    help="主页内嵌 Top N 镜头详情 (默认: 5)",
)
report_parser.set_defaults(func=report_command)
```

```python
def report_command(args):
    cache_path = get_cache_path()
    if not cache_path.exists():
        print(f"Error: No cache at {cache_path}. Run 'scan' first.")
        return 1

    metadata_list = load_cache(cache_path)
    if not metadata_list:
        print("Error: Cache is empty. Run 'scan' first.")
        return 1

    valid = [m for m in metadata_list if m.error is None]
    output_dir = Path(args.output) if args.output else Path("report")

    print(f"Generating report at: {output_dir}/")
    index_path = build_report(valid, output_dir, top_lenses_n=args.top_lenses)
    print(f"Done. Open: {index_path}")
    return 0
```

`run.py` gains:
```python
DO_REPORT = True
REPORT_DIR = "./report"
TOP_LENSES = 5
# ... in run():
if DO_REPORT:
    cli_main(["report", "--output", REPORT_DIR, "--top-lenses", str(TOP_LENSES)])
```

`interactive_menu()` gains a 4th option "4. 生成 HTML 报告".

## Report Section Order

The HTML body of `report/index.html` renders sections in this exact order. Each section can be **omitted** if its underlying data is empty (no header, no placeholder).

1. **Header** — report title + generation timestamp
2. **Hero stats** — 6 cards in a 3×2 grid (the 6 hero functions above)
3. **拍摄时间规律** (`01`) — `hourly_distribution` data as a small inline SVG bar chart (24-hour distribution)
4. **焦距分布** (`02`) — `charts/focal.png` full-width
5. **光圈分布** (`03`) — `charts/fstop.png` full-width
6. **镜头使用** (`04`) — `charts/lens.png` full-width
7. **镜头使用时间线** (`05`) — `<iframe src="charts/timeline_by_lens.html">` 700px tall
8. **焦距时间线** (`06`) — `charts/timeline_focal.png` full-width
9. **Top 5 镜头详情** (`07`) — for each of top 5 lenses, side-by-side focal + fstop mini charts
10. **Footer** — link to `lenses.html` (all lenses subpage) + total photo count

The numeric section markers (`01`–`07`) provide the editorial Swiss aesthetic and create a sense of progression through the report.

## Top N Lens PNG Naming Convention

`builder.py` generates these files in `report/charts/`:

```
lens_top1_focal.png   lens_top1_fstop.png
lens_top2_focal.png   lens_top2_fstop.png
...
lens_topN_focal.png   lens_topN_fstop.png
```

Where `N` is the position (1-indexed) in the sorted-by-count top list. Lens name is **not** in the filename (to keep paths short and OS-safe for non-ASCII lens names). The template looks up the human-readable name via the same index from `top_lenses()`.

## Visual Design (Minimal / Swiss)

- **Background:** white (#fff)
- **Text:** near-black (#1a1a1a)
- **Secondary text:** gray (#888)
- **Font stack:** system sans-serif (`-apple-system, BlinkMacSystemFont, "Segoe UI", ...`)
- **Numerics:** `font-variant-numeric: tabular-nums`
- **Sections:** separated by 1px hairlines (#e5e5e5)
- **Hero cards:** 3 columns × 2 rows, value at 32–40px, label in 10px uppercase tracked
- **Section headers:** 14px, with a small numeric marker ("01", "02", ...) for the editorial feel
- **Charts:** full-width within their section
- **No animations, no shadows, no decorative elements**

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Cache missing | Error message, exit 1 |
| Cache empty (0 photos) | Error message, exit 1 |
| All photos have errors | Report still generates, hero shows "暂无数据" |
| Some hero data missing | Card renders with "—" + "暂无数据" sublabel |
| Some sections have no data | Section is omitted from HTML (no empty title) |
| PNG missing for a section | Section title shown, body shows "图表未生成" placeholder |
| Output dir exists | **Wiped and rebuilt** (no prompt) |
| Jinja2 template missing | Error at import time (template ships in package, can't disappear) |

## Testing Strategy

**Coverage target: 80%**

### `tests/test_stats.py` (unit, ~12 tests)

For each of the 6 hero functions:
- Normal data → expected output
- Empty list → "无数据" sentinel
- All-None fields for that stat → "无数据" sentinel

Plus:
- `classify_focal` boundary values (already tested in viz; add 1 sanity test)
- `top_lenses` with < 5 lenses available → returns what's there
- `peak_month` tie-breaking (use earliest month)

### `tests/test_renderer.py` (integration, ~4 tests)

- Full fixture → rendered HTML contains all 6 hero labels
- Empty fixture → rendered HTML contains "暂无数据"
- Missing chart file → renderer doesn't crash, body shows placeholder
- Template syntax check (smoke test that `get_template()` succeeds)

### `tests/fixtures/`

- `sample_metadata.json` — 10 PhotoMetadata, full data, varied
- `empty_metadata.json` — `[]`
- `partial_metadata.json` — 5 entries, some fields None

### Manual E2E (no automation)

After implementation, on a real photo library:
1. `uv run python -m photocheck scan /path`
2. `uv run python -m photocheck analyze --type all`
3. `uv run python -m photocheck report`
4. Open `report/index.html` in browser
5. Verify: 6 hero cards, all PNGs load, iframe interaction works, mobile responsive

## Out of Scope (deferred)

- Plotly offline mode (inline plotly.js instead of CDN)
- Multiple report templates (quarterly, monthly variants)
- Auto-upload to cloud / email
- i18n
- Dark mode toggle
- Print-optimized stylesheet

## Dependencies

**Add:** `jinja2>=3.0.0` to `pyproject.toml` `[project].dependencies`

**Add dev:** `pytest>=7.0.0` (already in dev deps, but no test dir exists yet)
