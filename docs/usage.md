# PhotoCheck 使用说明

PhotoCheck 是一款照片 EXIF 元数据分析工具，支持从 ARW/JPG 照片中提取焦距、光圈、ISO、快门、镜头名称、拍摄时间等信息，并生成可视化图表。

---

## 目录

- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [使用方式](#使用方式)
- [功能详解](#功能详解)
- [输出文件](#输出文件)

---

## 快速开始

### 1. 修改运行配置

编辑项目根目录下的 `run.py`：

```python
# 扫描配置
SCAN_FOLDER = "/Volumes/Extreme SSD"  # 照片文件夹路径
CROP_FACTOR = 1.0                    # 裁切系数 (1.0=全画幅, 1.5=APS-C)
WORKERS = 8                          # 工作线程数

# 操作控制
DO_SCAN = True                       # 是否执行扫描
DO_VISUALIZE = True                  # 是否执行可视化
```

### 2. 运行

```bash
cd /Users/pluto/PythonProjects/PhotoCheck
uv run python run.py
```

---

## 配置说明

### 裁切系数 (Crop Factor)

| 传感器尺寸 | 裁切系数 |
|-----------|---------|
| 全画幅 (Full Frame) | 1.0 |
| APS-C (Canon) | 1.6 |
| APS-C (Nikon/Sony/Fuji) | 1.5 |
| M4/3 | 2.0 |

焦距会自动换算为等效 35mm 焦距：

```
等效焦距 = 原始焦距 × 裁切系数
```

### photocheck.toml 配置文件

项目根目录的 `photocheck.toml` 用于 CLI 模式配置：

```toml
default_folder = "/Volumes/Extreme SSD"
crop_factor = 1.0
workers = 8
```

---

## 使用方式

### 方式一：运行脚本（推荐）

直接修改 `run.py` 后运行：

```bash
uv run python run.py
```

### 方式二：CLI 命令

#### 扫描照片

```bash
# 基本扫描
uv run python -m photocheck scan /path/to/photos

# 指定裁切系数
uv run python -m photocheck scan /path/to/photos --crop-factor 1.5

# 指定工作线程数
uv run python -m photocheck scan /path/to/photos --workers 16

# 强制重新扫描（不使用缓存）
uv run python -m photocheck scan /path/to/photos --no-cache
```

#### 生成可视化

```bash
# 全部图表
uv run python -m photocheck analyze

# 只生成直方图
uv run python -m photocheck analyze --type histogram

# 只生成时间轴
uv run python -m photocheck analyze --type timeline

# 指定时间轴字段
uv run python -m photocheck analyze --type timeline --field iso

# 指定输出目录
uv run python -m photocheck analyze --output ./my_charts
```

#### 交互模式

```bash
uv run python -m photocheck interactive
```

### 方式三：Python 脚本

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from photocheck.cli import main as cli_main

# 扫描
cli_main(["scan", "/path/to/photos", "--crop-factor", "1.5"])

# 可视化
cli_main(["analyze", "--type", "all"])
```

---

## 功能详解

### 1. 元数据提取

支持提取以下字段：

| 字段 | 说明 | EXIF 标签 |
|------|------|-----------|
| focal_length | 焦距 (mm) | FocalLength |
| f_stop | 光圈 (f/) | FNumber |
| iso | ISO | ISOSpeedRatings |
| shutter_speed | 快门速度 (秒) | ExposureTime |
| lens_name | 镜头型号 | LensModel |
| datetime_original | 拍摄时间 | DateTimeOriginal |
| camera_make | 相机品牌 | Make |
| camera_model | 相机型号 | Model |

### 2. 文件去重

相同照片的 ARW 和 JPG 版本会基于元数据自动去重，优先保留 ARW 文件。

### 3. 可视化类型

#### 直方图 (histogram)

| 图表 | 说明 |
|------|------|
| focal_histogram.png | 焦距分布 |
| fstop_histogram.png | 光圈分布 |
| lens_histogram.png | 镜头使用频率 |

#### 时间轴 (timeline)

| 图表 | 说明 |
|------|------|
| timeline_focal_length.png | 焦距随时间变化散点图 |
| hourly_heatmap.png | 每小时拍摄频率热力图 |
| timeline_by_lens.png | 各镜头使用频率堆叠面积图 |
| timeline_by_lens.html | **交互式**各镜头使用频率（可悬停查看详情） |

#### 镜头详情 (lens_detail)

为每个镜头生成单独的焦距和光圈分布图。

### 4. 缓存机制

- 缓存文件：`data/photocheck_cache.parquet`
- 基于文件修改时间 (mtime) 检测变更
- 新照片自动增量添加
- 如需备份，直接复制 `.parquet` 文件即可

---

## HTML 报告生成

完成 `scan` + `analyze` 后，可以一键生成 HTML 报告：

```bash
uv run python -m photocheck report
```

输出目录结构：

```
report/
├── index.html              # 主报告（6 个 hero 卡片 + 7 个 section）
├── lenses.html             # 全部镜头子页（带表格）
└── charts/                 # PNG 图表 + 交互式 timeline
    ├── focal_histogram.png
    ├── fstop_histogram.png
    ├── lens_histogram.png
    ├── timeline_focal_length.png
    ├── hourly_heatmap.png
    ├── timeline_by_lens.html     (iframe 嵌入)
    ├── lens_top1_focal.png       (Top 5 镜头焦距分布)
    ├── lens_top1_fstop.png
    └── ...
```

常用参数：

| 参数 | 说明 | 默认 |
|------|------|------|
| `--output, -o` | 报告输出目录 | `./report/` |
| `--top-lenses, -n` | 主页内嵌 Top N 镜头详情 | 5 |

设计风格：Minimal Swiss（白底、无衬线、强数字对比、章节编号 01-07），无 JavaScript 依赖（仅交互图通过 iframe 加载）。

在 `run.py` 中通过以下开关控制：

```python
DO_REPORT = True      # 是否生成 HTML 报告
REPORT_DIR = "./report"  # 报告输出目录
TOP_LENSES = 5        # 主页内嵌 Top N 镜头
```

---

## 输出文件

所有输出保存在 `output/` 目录下：

```
output/
├── focal_histogram.png         # 焦距分布直方图
├── fstop_histogram.png         # 光圈分布直方图
├── lens_histogram.png          # 镜头使用频率
├── timeline_focal_length.png   # 焦距时间轴
├── hourly_heatmap.png          # 每小时拍摄频率
├── timeline_by_lens.png        # 镜头使用堆叠面积图
├── timeline_by_lens.html       # 交互式镜头时间轴
└── lens_*.png                 # 各镜头详情图
```

---

## 数据合并

如需合并多个照片库的数据：

1. 将旧缓存文件放入 `data/` 目录
2. 修改 `run.py` 中的 `SCAN_FOLDER` 为新照片路径
3. 运行扫描，新数据会自动合并到现有缓存

---

## 常见问题

**Q: 扫描很慢怎么办？**
A: 增加 `WORKERS` 数值（建议 8-16），利用多线程加速。

**Q: 某些照片没有数据？**
A: 检查是否为 RAW 格式（.arw/.ARW），非 RAW 格式支持有限。

**Q: 如何重新生成所有图表？**
A: 删除 `output/` 目录内容，重新运行可视化即可。
