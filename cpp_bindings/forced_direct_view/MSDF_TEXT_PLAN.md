# ForceViewOpenGL MSDF 文字渲染接入计划（FreeType + msdfgen）

## 1. 目标与范围
- 目标：将 `ForceViewOpenGL` 的文字渲染从 `QPainter + QStaticText` 迁移为纯 OpenGL 的 MSDF 文本渲染。
- 范围：仅替换文字层；节点与边的现有 OpenGL 渲染逻辑保持不变。
- 约束：保持现有缩放阈值、hover 分组、透明度渐变等交互视觉行为。

## 2. 现状确认
当前文字路径：
- 文本缓存：`src/ForceViewOpenGL.cpp::initStaticTextCache()`
- 文本绘制：`src/ForceViewOpenGL.cpp::paintGL()` 中 `QOpenGLPaintDevice + QPainter`
- 普通文字：`drawStaticText`
- hover 文字：`drawText`

当前工程状态：
- 工程已有 `3rdparty/freetype` 与 `3rdparty/msdfgen` 目录。
- 主 `CMakeLists.txt` 尚未将 FreeType/msdfgen 接入到 `forceviewlib` 的构建与链接。

## 3. 总体架构
新增两个模块：

1. `MsdfFontAtlas`
- 职责：字体加载、glyph 生成、atlas 管理、metrics/kerning 查询。
- 依赖：FreeType + msdfgen(ext)。

2. `MsdfTextRenderer`
- 职责：文本布局、顶点缓冲构建、MSDF shader 绘制。
- 依赖：OpenGL 3.3 Core。

`ForceViewOpenGL` 只做调度：
- 在初始化时创建字体图集与文本渲染器。
- 在每帧根据分组/缩放/hover 状态提交文本绘制命令。

**设计决策（补充）**：
- `MsdfTextRenderer` 由 `ForceViewOpenGL` 独立持有，与 `GraphRenderer`（m_renderer）并列，不并入 GraphRenderer。GraphRenderer 继续专注节点/边渲染。

## 4. 技术方案细节
### 4.1 Font Atlas 生成（FreeType + msdfgen）
- 使用 FreeType 加载字体文件（默认可先沿用 `Microsoft YaHei` 对应 ttf 路径，后续可配置化）。
- 字体路径建议：优先通过 `QFontDatabase::font()` 或 `QStandardPaths` 获取系统字体，避免硬编码；Phase 1 可先硬编码，Phase 4 或更早改为配置化。
- 通过 msdfgen `loadGlyph` 获取轮廓，`edgeColoring` 后调用 `generateMSDF` 生成 3 通道 MSDF。
- 将多个 glyph 打包进单张 atlas（初始可单页，后续支持分页）。
- 保存 glyph 数据：
  - UV 矩形
  - plane bounds（渲染平面边界）
  - advance
  - bearing
  - 可选 kerning pair

建议参数（首版）：
- atlas 尺寸：`1024x1024`（可配置）
- 每 glyph box：按字体 em 缩放自动估算
- `pxRange`：`4~8`（先用 `6`）
- 纹理格式：`GL_RGB8`

### 4.2 文本布局
- 首版按 Unicode codepoint 顺序布局（不做复杂 shaping）。
- 支持：中英文、数字、常见符号。
- 行高/基线使用字体 metrics。
- 对每个 label 生成 quad 顶点并缓存到 `LabelLayoutCache`。
- label 内容未变化时复用布局缓存，仅在缩放/hover scale 变化时更新最终变换参数。

### 4.3 渲染管线
- 顶点属性：`pos.xy + uv.xy + color.rgba`。
- 顶点着色器：世界坐标乘 `uMvp`。
- 片元着色器：
  - 读取 `msdfTex.rgb`
  - `sd = median(r,g,b)`
  - 基于 `fwidth` 与 `pxRange` 求平滑宽度
  - `alpha = smoothstep(...)`
- 混合：保持当前 premultiplied alpha 流程（`GL_ONE, GL_ONE_MINUS_SRC_ALPHA`）。
- MSDF 片元着色器中的 `fwidth` 导数需注意高 DPI 下的表现，保持与 GraphRenderer 的坐标系一致。

## 5. 与现有逻辑对齐
保留并复用现有行为：
- `m_textThresholdOff` / `m_textThresholdShow`：控制文字显示和淡入。
- `m_groupBase / m_groupDim / m_groupHover`：按分组绘制并设置不同 alpha。
- hover 放大：将当前 `QFont` 动态放大逻辑改为 MSDF 几何缩放。
- 像素对齐：保留当前对齐策略，避免抖动。

替换点：
- 删除（或停用）`QOpenGLPaintDevice/QPainter/QStaticText` 路径。
- `initStaticTextCache()` 改为“文本字符集预热 + glyph 准备”。

## 6. CMake 接入计划
- 在根 `CMakeLists.txt` 添加：
  - `add_subdirectory(3rdparty/freetype)`（必须先于 msdfgen，使 `Freetype::Freetype` 存在）
  - `add_subdirectory(3rdparty/msdfgen)`
- `forceviewlib` 追加链接：
  - `freetype`
  - `msdfgen-core`
  - `msdfgen-ext`
- 视 include 结构补充 `target_include_directories`。
- 若 Windows 下字体路径硬编码，后续改为可配置（避免环境耦合）。

**msdfgen 子工程配置（补充）**：
- msdfgen 默认 `MSDFGEN_USE_VCPKG=ON`，会依赖 vcpkg 及 tinyxml2、PNG、Skia 等。作为子工程引入时建议显式关闭并精简：
  ```cmake
  set(MSDFGEN_USE_VCPKG OFF CACHE BOOL "" FORCE)
  set(MSDFGEN_CORE_ONLY OFF)
  set(MSDFGEN_BUILD_STANDALONE OFF)
  set(MSDFGEN_USE_SKIA OFF)
  # 若仅需 FreeType 扩展，可设置 MSDFGEN_DISABLE_SVG、MSDFGEN_DISABLE_PNG
  add_subdirectory(3rdparty/freetype)
  add_subdirectory(3rdparty/msdfgen)
  ```

## 7. 分阶段实施
### Phase 1（最小可用）
- 接入 FreeType/msdfgen。
- 构建单字体、有限字符集 atlas。
- 在 `paintGL` 中替换普通标签绘制（无 hover 放大）。
- 引入基础 `LabelLayoutCache` 框架（按 label 内容 hash 缓存），便于 Phase 3 扩展增量更新与 LRU，避免 Phase 2 每帧重建全部顶点。

### Phase 2（行为对齐）
- 接入 `groupBase/groupDim/groupHover`。
- 完成阈值淡入淡出。
- 对齐现有文本位置与偏移规则。

### Phase 3（hover 体验）
- 加入 hover label 放大动画。
- 做缓存策略，避免每帧重建全部顶点。

### Phase 4（性能与鲁棒）
- 增量 glyph 加载（按需）与 LRU。
- atlas 分页支持。
- 大图场景下批次优化与统计监控。

## 8. 风险与规避
- 复杂脚本文本（阿拉伯等）需要 HarfBuzz shaping；首版不覆盖。
- CJK 大字符集可能导致 atlas 膨胀；采用按需增量加载。CJK 的 glyph 预热策略应尽早明确（例如按 label 出现频率或可见性）。
- msdfgen-ext 可选依赖：`MSDFGEN_DISABLE_SVG`、`MSDFGEN_DISABLE_PNG` 可减少依赖；若仅需 FreeType，应精简配置。
- 渲染一致性需验证：
  - 小字号边缘
  - 高缩放下清晰度
  - hover 动画期间的稳定性

## 9. 验收标准
- 缩放过程中标签边缘清晰、无明显锯齿或闪烁。
- 与当前版本视觉行为一致：显示阈值、分组透明度、hover 放大。
- 大图场景下帧率不低于当前实现，或有可量化改善。
- 不再依赖 `QPainter` 进行文本绘制。
- （补充）目标平台（Win/Linux/macOS）上构建通过，MSDF 路径可正常运行并成功替换 QPainter 文本。

## 10. 本次任务边界说明
- 本文档仅为实施计划落地，不包含代码改动。
- 下一步如开始实现，将按 Phase 1 → Phase 2 顺序提交最小可验证变更。
- 建议：实现 Phase 1 前先落实 CMake 与依赖配置（见第 6 节），明确 `MsdfTextRenderer` 归属（见第 3 节），再按阶段推进。
