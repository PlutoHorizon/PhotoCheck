"""CLI interface for PhotoCheck."""

import argparse
import sys
import os
from pathlib import Path
from typing import List, Optional
import tomllib

import concurrent.futures
from tqdm import tqdm

from .core.extractor import extract_metadata
from .core.pairing import find_files_by_extensions, deduplicate_by_metadata
from .core.cache import save_cache, load_cache, get_stale_files
from .core.models import PhotoMetadata
from .viz.histograms import plot_focal_histogram, plot_fstop_histogram, plot_lens_histogram, plot_lens_detail
from .viz.timeline import plot_timeline_scatter, plot_hourly_heatmap, plot_timeline_by_lens, plot_timeline_by_lens_html
from .report.builder import build_report


# Only ARW files by default
DEFAULT_EXTENSIONS = [".arw", ".ARW"]
CACHE_FILENAME = "photocheck_cache.parquet"
CONFIG_FILE = "photocheck.toml"

# Database and output directory (project-relative)
_PHOTOCHECK_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = _PHOTOCHECK_ROOT / "data"
OUTPUT_DIR = _PHOTOCHECK_ROOT / "output"


def ensure_data_dir() -> Path:
    """Ensure the data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def get_cache_path() -> Path:
    """Get the unified cache file path."""
    return ensure_data_dir() / CACHE_FILENAME


def load_config() -> dict:
    """Load configuration from photocheck.toml."""
    config_path = Path(CONFIG_FILE)
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def scan_command(args: argparse.Namespace) -> int:
    """Execute the scan command: find and extract metadata from photos."""
    folder = Path(args.folder).expanduser().resolve()
    if not folder.exists():
        print(f"Error: Folder not found: {folder}")
        return 1

    cache_path = get_cache_path()
    extensions = args.extensions.split(",") if args.extensions else DEFAULT_EXTENSIONS
    crop_factor = args.crop_factor

    print(f"Scanning: {folder}")
    print(f"Extensions: {extensions}")
    print(f"Crop factor: {crop_factor}")

    # Find ARW files
    file_paths = find_files_by_extensions(folder, extensions)
    print(f"Found {len(file_paths)} files")

    if not file_paths:
        return 0

    # Deduplicate by metadata (same basename + same EXIF = same photo)
    if len(file_paths) > 1:
        unique_paths = deduplicate_by_metadata(file_paths, crop_factor)
        removed = len(file_paths) - len(unique_paths)
        if removed > 0:
            print(f"Deduplicated {removed} duplicate(s) based on metadata")
        file_paths = unique_paths

    print(f"Processing {len(file_paths)} unique photos with {args.workers} workers...")

    # Load existing unified cache if requested
    cached_metadata: List[PhotoMetadata] = []
    if args.use_cache and cache_path.exists():
        cached_df = load_cache(cache_path)
        # Filter cached entries that still exist on disk
        cached_metadata = [m for m in cached_df if m.file_path.exists()]
        existing_paths = {m.file_path for m in cached_metadata}
        file_paths = [f for f in file_paths if f not in existing_paths]
        print(f"Loaded {len(cached_metadata)} entries from cache, {len(file_paths)} new files to process")

    # Process new files
    if file_paths:
        new_metadata = _process_files(file_paths, crop_factor, args.workers)
        metadata_list = cached_metadata + new_metadata
    else:
        metadata_list = cached_metadata

    # Save unified cache
    save_cache(metadata_list, cache_path)
    print(f"Cache saved to {cache_path}")
    print(f"Total entries: {len(metadata_list)}")

    # Print summary
    valid_count = sum(1 for m in metadata_list if m.error is None)
    print(f"Successfully processed: {valid_count}/{len(metadata_list)}")

    return 0


def _process_files(
    file_paths: List[Path],
    crop_factor: float,
    max_workers: int,
) -> List[PhotoMetadata]:
    """Process files with multithreading and progress bar."""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(extract_metadata, fp, crop_factor): fp
            for fp in file_paths
        }

        with tqdm(total=len(futures), desc="Processing", unit="photo") as pbar:
            for future in concurrent.futures.as_completed(futures):
                fp = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(PhotoMetadata(file_path=fp, error=str(e)))
                pbar.update(1)

    # Sort by original file path order
    path_to_result = {r.file_path: r for r in results}
    sorted_results = [path_to_result[fp] for fp in file_paths if fp in path_to_result]

    return sorted_results


def analyze_command(args: argparse.Namespace) -> int:
    """Execute the analyze command: generate visualizations from cached data."""
    cache_path = get_cache_path()

    if not cache_path.exists():
        print(f"No cache found at {cache_path}. Run 'scan' first.")
        return 1

    metadata_list = load_cache(cache_path)
    print(f"Loaded {len(metadata_list)} entries from cache")

    valid_metadata = [m for m in metadata_list if m.error is None]

    # Create output directory
    output_dir = Path(args.output) if args.output else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Generate requested visualizations
    if args.type in ("all", "histogram"):
        plot_focal_histogram(
            valid_metadata,
            filename=str(output_dir / "focal_histogram.png"),
        )
        plot_fstop_histogram(
            valid_metadata,
            filename=str(output_dir / "fstop_histogram.png"),
        )
        plot_lens_histogram(
            valid_metadata,
            filename=str(output_dir / "lens_histogram.png"),
        )

    if args.type in ("all", "timeline"):
        field = args.field or "focal_length"
        plot_timeline_scatter(
            valid_metadata,
            field=field,
            filename=str(output_dir / f"timeline_{field}.png"),
        )
        plot_hourly_heatmap(
            valid_metadata,
            filename=str(output_dir / "hourly_heatmap.png"),
        )
        plot_timeline_by_lens(
            valid_metadata,
            filename=str(output_dir / "timeline_by_lens.png"),
        )
        plot_timeline_by_lens_html(
            valid_metadata,
            filename=str(output_dir / "timeline_by_lens.html"),
        )

    if args.type in ("all", "lens_detail"):
        plot_lens_detail(valid_metadata, str(output_dir))

    return 0


def report_command(args: argparse.Namespace) -> int:
    """Generate HTML report from cached metadata."""
    cache_path = get_cache_path()

    if not cache_path.exists():
        print(f"Error: No cache found at {cache_path}. Run 'scan' first.")
        return 1

    metadata_list = load_cache(cache_path)
    if not metadata_list:
        print("Error: Cache is empty. Run 'scan' first.")
        return 1

    valid = [m for m in metadata_list if m.error is None]
    output_dir = Path(args.output) if args.output else Path("report")
    top_n = args.top_lenses

    print(f"Generating report at: {output_dir}/")
    print(f"Top lenses to inline: {top_n}")

    index_path = build_report(valid, output_dir, top_lenses_n=top_n)
    print(f"Done. Open: {index_path}")
    return 0


def interactive_menu() -> int:
    """Show interactive menu and handle user choices."""
    config = load_config()
    default_folder = config.get("default_folder", "")
    default_crop_factor = config.get("crop_factor", 1.0)
    default_workers = config.get("workers", 8)

    cache_path = get_cache_path()
    has_cache = cache_path.exists()

    while True:
        print("\n" + "=" * 50)
        print("PhotoCheck - 照片元数据分析工具")
        print("=" * 50)
        print(f"数据库位置: {cache_path}")
        if has_cache:
            cached = load_cache(cache_path)
            valid = sum(1 for m in cached if m.error is None)
            print(f"已有数据: {valid} 张照片")
        print()
        print("1. 扫描照片 (scan)")
        print("2. 可视化分析 (analyze)")
        print("3. 退出 (quit)")
        print()

        choice = input("请选择 (1/2/3): ").strip()

        if choice == "1":
            folder = input(f"照片文件夹 [{default_folder}]: ").strip() or default_folder
            if not folder:
                print("错误: 请设置 default_folder 或手动输入")
                continue
            crop_str = input(f"裁切系数(1.0=全画幅,1.5=APS-C) [{default_crop_factor}]: ").strip()
            crop_factor = float(crop_str) if crop_str else default_crop_factor
            workers_str = input(f"工作线程数 [{default_workers}]: ").strip()
            workers = int(workers_str) if workers_str else default_workers

            print()
            # Simulate scan command args
            class Args:
                folder = folder
                extensions = None
                crop_factor = crop_factor
                workers = workers
                use_cache = True

            scan_command(Args())
            has_cache = cache_path.exists()

        elif choice == "2":
            if not has_cache:
                print("错误: 暂无数据，请先扫描照片")
                continue

            print("\n可视化类型:")
            print("1. 全部 (all)")
            print("2. 直方图 (histogram)")
            print("3. 时间轴 (timeline)")

            viz_choice = input("请选择 (1/2/3): ").strip()
            viz_type = {"1": "all", "2": "histogram", "3": "timeline"}.get(viz_choice, "all")

            print("\n选择字段 (用于时间轴):")
            print("1. 焦距 (focal_length)")
            print("2. ISO")
            print("3. 光圈 (f_stop)")
            print("4. 快门 (shutter_speed)")

            field_choice = input("请选择 (1/2/3/4): ").strip()
            field = {"1": "focal_length", "2": "iso", "3": "f_stop", "4": "shutter_speed"}.get(field_choice, "focal_length")

            print()
            class Args:
                folder = default_folder
                type = viz_type
                field = field
                output = None

            analyze_command(Args())

        elif choice in ("3", "q", "quit", "exit"):
            print("再见!")
            break

        else:
            print("无效选择，请重试")


def main(argv: List[str] | None = None) -> int:
    """Main entry point for the CLI."""
    config = load_config()
    default_folder = config.get("default_folder", "")
    default_crop_factor = config.get("crop_factor", 1.0)
    default_workers = config.get("workers", 8)

    parser = argparse.ArgumentParser(
        description="PhotoCheck - Photo EXIF metadata analysis tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan photos and extract metadata")
    scan_parser.add_argument(
        "folder",
        nargs="?",
        default=default_folder,
        help="Folder containing photos (default: from config)",
    )
    scan_parser.add_argument(
        "--extensions", "-e",
        default=None,
        help="Comma-separated extensions (default: .arw,.ARW only)",
    )
    scan_parser.add_argument(
        "--crop-factor", "-c",
        type=float,
        default=default_crop_factor,
        help=f"Crop factor (default: {default_crop_factor})",
    )
    scan_parser.add_argument(
        "--use-cache",
        action="store_true",
        default=True,
        help="Use existing cache if available (default: True)",
    )
    scan_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force reprocessing ignoring cache",
    )
    scan_parser.add_argument(
        "--workers", "-w",
        type=int,
        default=default_workers,
        help=f"Number of worker threads (default: {default_workers})",
    )
    scan_parser.set_defaults(func=scan_command)

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze cached metadata")
    analyze_parser.add_argument(
        "folder",
        nargs="?",
        default=default_folder,
        help="Folder (for config loading, not used for cache location)",
    )
    analyze_parser.add_argument(
        "--type", "-t",
        choices=["all", "histogram", "timeline", "lens_detail"],
        default="all",
        help="Type of visualization (default: all)",
    )
    analyze_parser.add_argument(
        "--field", "-f",
        choices=["focal_length", "iso", "f_stop", "shutter_speed"],
        default="focal_length",
        help="Field for timeline scatter plot (default: focal_length)",
    )
    analyze_parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory for saved charts (default: ~/.photocheck/output/)",
    )
    analyze_parser.set_defaults(func=analyze_command)

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate HTML report from cache")
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

    # Interactive mode
    interact_parser = subparsers.add_parser("interactive", help="Start interactive menu")
    interact_parser.set_defaults(func=lambda _: interactive_menu())

    args = parser.parse_args(argv)

    if args.command is None:
        # Default to interactive mode
        return interactive_menu()

    # For scan/analyze, validate folder
    if args.command in ("scan", "analyze") and not args.folder:
        print(f"Error: folder not specified. Set default_folder in {CONFIG_FILE} or pass as argument.")
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
