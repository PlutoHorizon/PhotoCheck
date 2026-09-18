#!/usr/bin/env python3
"""
PhotoCheck - 运行脚本

直接在下方修改配置，然后运行: python run.py
"""

import sys
from pathlib import Path

# ============================================
# 配置区域 - 修改这里来控制程序行为
# ============================================

# 扫描配置
SCAN_FOLDER = "/Volumes/Extreme SSD"  # 扫描路径，留空则不扫描
CROP_FACTOR = 1.0                          # 裁切系数 (1.0=全画幅, 1.5=APS-C)
WORKERS = 8                                # 工作线程数

# 操作控制
DO_SCAN = True                             # 是否执行扫描
DO_VISUALIZE = True                        # 是否执行可视化

# 可视化配置
VIZ_TYPE = "all"                           # all, histogram, timeline, lens_detail
VIZ_FIELD = "focal_length"                 # focal_length, iso, f_stop, shutter_speed

# 报告配置
DO_REPORT = True                           # 是否生成 HTML 报告
REPORT_DIR = "./report"                    # 报告输出目录
TOP_LENSES = 5                             # 主页内嵌 Top N 镜头

# ============================================
# 以下代码一般不需要修改
# ============================================

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from photocheck.cli import main as cli_main


def run():
    args_list = []

    if DO_SCAN and SCAN_FOLDER:
        print(f"=== 扫描照片 ===")
        print(f"路径: {SCAN_FOLDER}")
        args_list.extend([
            "scan",
            SCAN_FOLDER,
            "--crop-factor", str(CROP_FACTOR),
            "--workers", str(WORKERS),
        ])
        print(f"执行: uv run python -m photocheck {' '.join(args_list)}")
        result = cli_main(args_list)
        if result != 0:
            print(f"扫描失败: {result}")
            return result

    if DO_VISUALIZE:
        print(f"\n=== 可视化分析 ===")
        viz_args = ["analyze", "--type", VIZ_TYPE, "--field", VIZ_FIELD]
        print(f"执行: uv run python -m photocheck {' '.join(viz_args)}")
        result = cli_main(viz_args)
        if result != 0:
            print(f"可视化失败: {result}")
            return result

    if DO_REPORT:
        print(f"\n=== 生成 HTML 报告 ===")
        report_args = ["report", "--output", REPORT_DIR, "--top-lenses", str(TOP_LENSES)]
        print(f"执行: uv run python -m photocheck {' '.join(report_args)}")
        result = cli_main(report_args)
        if result != 0:
            print(f"报告生成失败: {result}")
            return result

    print("\n完成!")
    return 0


if __name__ == "__main__":
    sys.exit(run())
