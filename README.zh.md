# PhotoCheck

照片 EXIF 元数据分析工具——从你的照片库中提取拍摄规律并可视化。

## 功能特性

- **EXIF 提取**：焦距、光圈、ISO、快门速度、镜头型号、拍摄时间
- **去重**：基于元数据的 ARW/JPG 配对（跨格式）
- **缓存**：基于 Parquet 的本地缓存（路径匹配，不依赖 mtime）
- **可视化**：
  - 焦距 / 光圈 / 镜头使用频率分布直方图
  - 时间轴散点图（时间 vs 任意字段）
  - 每小时拍摄频率热力图
  - 镜头使用时间线（堆叠面积图 + 交互式 HTML）
  - 每个镜头的详细图表
- **HTML 报告**：自包含的 `report/` 目录，包含 hero 统计、所有图表和交互式时间线
- **灵活调用**：CLI、交互菜单或 Python API

## 快速开始

```bash
# 编辑 run.py 配置你的照片目录
# SCAN_FOLDER = "/path/to/photos"

# 运行
uv run python run.py
```

## 使用方式

### 1. 运行脚本（推荐）

编辑 `run.py` 配置区，然后：

```bash
uv run python run.py
```

### 2. CLI

```bash
# 扫描照片
uv run python -m photocheck scan /path/to/photos

# 生成可视化
uv run python -m photocheck analyze --type all

# 生成 HTML 报告
uv run python -m photocheck report

# 预览扫描（不写 cache）
uv run python -m photocheck scan /path/to/photos --dry-run
```

### 3. 交互菜单

```bash
uv run python -m photocheck interactive
```

## 配置

编辑 `photocheck.toml` 或 `run.py`：

| 设置 | 说明 | 默认值 |
|------|------|--------|
| `SCAN_FOLDER` | 照片目录 | - |
| `CROP_FACTOR` | 裁切系数（1.0=全画幅）| 1.0 |
| `WORKERS` | 工作线程数 | 8 |
| `DO_REPORT` | 是否生成 HTML 报告 | True |
| `REPORT_DIR` | 报告输出目录 | `./report` |
| `TOP_LENSES` | 主页内嵌 Top N 镜头 | 5 |

> **注意**：现在焦段自动按以下优先级解析：
> 1. **EXIF FocalLengthIn35mmFilm (0xA405)** — 厂商报告的 35mm 等效值（如有就用）
> 2. **机身 crop factor 表** — 没有 35mm tag 时，按相机型号查表（a6400=1.5, Canon 80D=1.6, MFT=2.0 等），把原始焦段乘上去
> 3. **原始焦段** — 找不到机身表时不做换算（保守默认）
>
> 这样全画幅和半画幅混拍的照片都能在同一个图上正确比较了。
>
> #### 自定义 crop factor
>
> 内置的 `CAMERA_CROP_FACTORS` 表覆盖了约 50 个常见机身。对于特殊机型（Fuji GFX、OM System OM-1、Sony RX1 等），可以在 `photocheck.toml` 里添加条目：
>
> ```toml
> [[crop_factors]]
> match = "GFX100S"
> factor = 0.79            # 中画幅（<1.0 表示比 35mm 更广）
>
> [[crop_factors]]
> match = "OM-1"
> factor = 2.0             # OM System OM-1（MFT）
>
> [[crop_factors]]
> match = "ILCE-6400"
> factor = 1.0             # 强制把特定机身当全画幅
> ```
>
> `match` 是相对 EXIF `Camera Model` 值的**前缀匹配**。最长前缀优先，所以 `"ILCE-6400"` 会覆盖内置的 `"ILCE-6"`（否则所有 Sony APS-C 都会被匹配到）。

## HTML 报告

完成 `scan` + `analyze` 后，生成统一的 HTML 报告：

```bash
uv run python -m photocheck report
# 指定输出目录
uv run python -m photocheck report --output ./my_report
# 调整主页内嵌的 Top N 镜头（默认 5）
uv run python -m photocheck report --top-lenses 8
```

`report/` 目录包含：
- `index.html` — 主报告（hero 统计卡片 + 左侧导航 + 所有图表）
- `lenses.html` — 全部镜头子页（按使用量排序）
- `charts/` — PNG 图表 + 嵌入的 Plotly 交互图

设计风格：Minimal / Swiss（白底、无衬线、强数字对比）。除嵌入的 Plotly iframe 外无 JavaScript 依赖。

## 输出

所有生成的图表保存在 `output/`：

- `focal_histogram.png` — 焦距分布
- `fstop_histogram.png` — 光圈分布
- `lens_histogram.png` — 镜头使用频率
- `timeline_*.png` — 时间轴散点图
- `hourly_heatmap.png` — 每小时拍摄频率
- `timeline_by_lens.png` — 镜头使用堆叠面积图
- `timeline_by_lens.html` — **交互式**镜头时间线（Plotly）
- `lens_*.png` — 每个镜头的详细图表

## 照片筛选逻辑

`scan` 在提取 EXIF 前应用三层过滤，避免在垃圾文件上浪费 I/O：

### 1. 格式支持（扩展名 + 文件头魔数）

默认 `DEFAULT_EXTENSIONS` 覆盖常见 RAW + 标准格式：

| 厂商 | RAW | 标准 |
|------|-----|------|
| Sony | `.arw` | |
| Nikon | `.nef` | |
| Canon | `.cr2`, `.cr3` | |
| Adobe / 通用 | `.dng` | |
| Fuji | `.raf` | |
| Olympus | `.orf` | |
| JPEG / WebP / TIFF | | `.jpg`, `.jpeg`, `.webp`, `.tif`, `.tiff` |

每个文件还会用 **魔数校验**（前 8 字节）：
- `FF D8 FF` → JPEG
- `II *\0` / `MM\0 *` → TIFF（覆盖 ARW、NEF、CR2、DNG、ORF、通用 TIFF）
- `FUJIFOTO` → Fuji RAF
- `RIFF...WEBP` → WebP

扩展名有效但魔数无效的文件会被静默跳过。**HEIC/HEIF 不支持**（需要 `exifread`）。

### 2. 系统文件夹跳过

以下目录在扫描时直接跳过（不 stat、不查魔数）：

```
$RECYCLE.BIN                （Windows 回收站）
System Volume Information   （Windows）
.Spotlight-V100             （macOS Spotlight 缓存）
.Trashes                     （macOS 回收站）
.fseventsd, .TemporaryItems, .DocumentRevisions-V100
Thumbs.db
```

### 3. macOS AppleDouble 跳过

以 `._` 开头的文件会被跳过。这些是 macOS 资源派生文件（例如 `._DSC0001.ARW` 与真实的 `DSC0001.ARW` 并列），不是真图。

### 4. 去重策略（内容哈希）

照片用 6 元签名去重：

```
(datetime_original, f_stop, shutter_speed, focal_length, iso, file_number)
```

`file_number` 是从文件 stem 提取的尾部数字：
- `DSC05833.ARW` → `5833`
- `IMG_1234` → `1234`
- `vacation_sunset` → `None`

**为什么加 file_number**：相机给连拍照片分配连续编号（DSC05833、DSC05834、DSC05835），EXIF 完全相同。加入 file_number 后，6 张连拍保留 6 条记录而不是合并成 1 条。

跨格式去重也能工作：ARW 和 JPG 副本共享相同 stem：

```
/raw/DSC05833.ARW   → file_number=5833
/jpg/DSC05833.JPG   → file_number=5833   ← 相同签名，自动合并
```

### 5. 故意禁用 mtime 检查

相机 RAW 的 EXIF 在拍摄时就固定了，事后不会变。基于 mtime 的重新提取会因任何无关修改（比如 Lightroom 重新导出触碰了 mtime）误触发。缓存查找纯粹基于路径。

**强制重新提取某文件**：重命名它或手动从 cache 删除该条目。

## 部分读取 EXIF

`extract_metadata` 每张照片只读取前 **256 KB**，而不是整个 RAW 文件。EXIF IFD（包括 Sony/Nikon/Canon MakerNote）都在文件头——典型 40MB Sony ARW 的 EXIF 段约 135KB，所以部分读取只读 **文件大小的约 0.3%**。

实测在内置 SSD 上：**3.64 ms/张 → 0.07 ms/张（约 50 倍加速）**。在更慢的外置硬盘（USB / NAS）上 I/O 占比更高，加速比会更大。

安全机制：
- 小于 256KB 的文件走完整读全文件路径，无额外开销。
- 如果任何 IFD 偏移指向 256KB buffer 之外，piexif 会抛 `struct.error`，代码自动回退到读整文件。基于真实 Sony ARW 文件头（`tests/fixtures/arw_header_256k.bin`）测试过。

优化是无感知的——相同输出、相同 cache 格式、无需迁移。

## 安全保证

- **只读取**用户照片（piexif 读取 EXIF 段，不修改照片）
- **只写入**项目本地目录：`data/photocheck_cache.parquet`、`output/`、`report/`
- **永不删除**用户照片或缓存条目（即便文件被删，cache 记录保留作为历史）

`analyze` / `report` 等命令可能覆盖 `output/` 和 `report/` 里的旧文件，默认目录是安全的；自定义 `--output` 需要 `--force` 标志。

## 环境要求

- Python 3.12+
- uv（包管理器）

安装依赖：

```bash
uv sync
```

## 运行测试

```bash
uv run pytest tests/
```
