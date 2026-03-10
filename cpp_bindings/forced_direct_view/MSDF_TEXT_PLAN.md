# ForceViewOpenGL 文本渲染改造计划（强制 MSDF 方案）

## 1. 目标（硬约束）
- 文本渲染必须从 `QPainter/QStaticText` 完全切换到 **MSDF + OpenGL 3.3 Core**。
- 节点和边继续沿用现有 `GraphRenderer` 管线，不做风格和行为回退。
- 缩放阈值、分组透明度、hover 高亮/放大效果保持与当前版本一致。

## 2. 现状对照（基于当前源码）
### 2.1 ForceViewOpenGL.cpp
- `initStaticTextCache()` 当前构建 `QStaticText` 缓存。
- `paintGL()` 当前在节点/边绘制后走 `QOpenGLPaintDevice + QPainter` 文本路径：
  - 常规标签：`drawStaticText`
  - hover 标签：`drawText` + 动态 `QFontMetrics`
- 现有文字行为依赖以下状态：
  - 阈值：`m_textThresholdOff`, `m_textThresholdShow`
  - 分组：`m_groupBase`, `m_groupDim`, `m_groupHover`
  - hover 动画：`m_hoverIndex`, `m_hoverGlobal`

### 2.2 GraphRenderer.cpp
- 仅包含 `drawLines()` / `drawNodes()`，没有字体、纹理图集、文本 shader、文本批渲染接口。
- 结论：文本改造不应塞进当前 `GraphRenderer`，应并行新增文本模块，由 `ForceViewOpenGL` 调度。

### 2.3 CMake 现状
- 已有 `3rdparty/freetype`、`3rdparty/msdfgen` 目录。
- `forceviewlib` 目前未链接 FreeType/msdfgen（主 CMakeLists.txt 中无 add_subdirectory）。
- `msdfgen-ext` 依赖 `Freetype::Freetype`；`add_subdirectory(freetype)` 只生成 `freetype` 目标，需在 add_subdirectory(msdfgen) 前补 `add_library(Freetype::Freetype ALIAS freetype)`。

### 2.4 已有 MSDF 模块
- **`MsdfFontAtlas`（已实现）**：字体加载（FreeType + msdfgen-ext）、em 归一化 glyph 生成、简单行排 atlas 打包、`measureText`/`kerning` 查询。
  - 使用 `FONT_SCALING_EM_NORMALIZED`，所有 glyph metrics（`advance`、`planeBounds`）均为 em 归一化值（0~1 区间）。
  - `buildForLabels(labels)` 收集所有标签的唯一 codepoint 后**全量重建** atlas。
  - atlas 像素格式：RGB 3 通道（`std::vector<unsigned char>`），每像素 3 字节。
  - 暴露 `ascender()`/`descender()`/`lineHeight()` 等字体度量接口（**当前为 private，需公开**）。
- **`MsdfTextRenderer`（不存在）**：源文件 `.h/.cpp` 不存在，仅有旧 build 残留的 `.obj`。**需要全新编写**。
- 顶点格式：8 浮点/顶点 = pos.xy(2) + uv.xy(2) + color.rgba(4)。
- **注意**：顶点构建逻辑（从 label + 位置 → quad 顶点）需在 ForceViewOpenGL 或辅助函数中实现，MsdfTextRenderer 仅负责绘制。

## 3. 架构决策（本次确定）
新增两个模块，不改 `GraphRenderer` 现有职责：

1. `MsdfFontAtlas`（已实现，需小幅修改）
- 职责：字体加载、glyph 生成、atlas 打包、glyph metrics/kerning 查询。
- 依赖：FreeType + msdfgen-ext。
- **待修改**：公开 `ascender()`/`descender()`/`lineHeight()` 接口；增加增量 glyph 添加能力（详见 §4.5）。

2. `MsdfTextRenderer`（需全新编写）
- 职责：MSDF shader 编译/管理、atlas 纹理上传/更新、批次提交。
- 依赖：OpenGL 3.3 Core。
- **完整 API 见 §4.6。**

`ForceViewOpenGL` 负责：
- 生命周期管理（初始化/销毁文本模块）。
- 按当前分组与 hover 状态构建文本顶点并提交 draw call。
- 在图数据变更时触发 atlas 更新（增量优先，必要时全量重建）。

## 4. 数据与渲染设计
### 4.1 图集与字体
- 首版固定单字体（默认沿用 `Microsoft YaHei`，后续配置化）。
- atlas 初值：`2048x2048`, `GL_RGB8`, `pxRange=6`。
  - **理由**：CJK 场景唯一字符量大。每 glyph 约 40x40 px，`1024x1024` 最多约 576 个唯一字形，中文标签极易超出。`2048x2048` 可容纳约 2400 个唯一字形，覆盖绝大多数场景。
- glyph 元数据至少包含：
  - `uvRect` (u0, v0, u1, v1)
  - `planeBounds` (left, bottom, right, top) — em 归一化
  - `advance` — em 归一化
  - `kerning` 查询接口（懒加载缓存）

### 4.2 em 到世界坐标的映射（关键新增）
- 定义 `m_msdfFontSize`（世界坐标单位），等价于"1 em 在世界坐标中的大小"。
- 当前 QPainter 字体 pointSize=5，在 painter 坐标中文字高度约 5~7 逻辑像素。由于 painter 在 `scale(m_zoom, m_zoom)` 后绘制，实际世界坐标中文字高度 ≈ `fontHeight / m_zoom`。
- **换算规则**：对于任意 glyph，其世界坐标宽 = `advance * m_msdfFontSize`，世界坐标高 = `(planeTop - planeBottom) * m_msdfFontSize`。
- 初始值建议 `m_msdfFontSize = 8.0f`（可调节），需通过实际对比确定与 QPainter pointSize=5 视觉一致的值。

### 4.3 标签布局缓存
- 新增 `LabelLayoutEntry`：
  ```cpp
  struct LabelLayoutEntry {
      float totalWidth;  // em 归一化总宽度（含 kerning）
      std::vector<GlyphQuad> quads; // 每字形的局部 quad（em 归一化，原点在文本左基线）
  };
  struct GlyphQuad {
      float x0, y0, x1, y1; // 局部位置（em 归一化）
      float u0, v0, u1, v1; // atlas UV
  };
  ```
- 缓存 key：label 文本的 `std::string`（因为相同文本的布局完全一致）。
- **仿真运行时**：glyph 局部布局不变，每帧仅需对每个可见 label 做"局部 quad + 世界变换 + 颜色 → 最终顶点"的组装，避免重复的 kerning/measureText 计算。
- **重建时机**：仅在 `m_labels` 变化或 atlas generation 变化时重建布局缓存。

### 4.4 Shader 与混合
- 顶点属性：`pos.xy + uv.xy + color.rgba`（8 floats/vertex）。
- **Vertex Shader**：
  ```glsl
  #version 330 core
  layout(location = 0) in vec2 aPos;
  layout(location = 1) in vec2 aUV;
  layout(location = 2) in vec4 aColor;
  uniform mat4 uMVP;
  out vec2 vUV;
  out vec4 vColor;
  void main() {
      gl_Position = uMVP * vec4(aPos, 0.0, 1.0);
      vUV = aUV;
      vColor = aColor;
  }
  ```
- **Fragment Shader**：
  ```glsl
  #version 330 core
  in vec2 vUV;
  in vec4 vColor;
  uniform sampler2D uAtlas;
  uniform float uScreenPxRange;
  out vec4 fragColor;
  float median(float r, float g, float b) {
      return max(min(r, g), min(max(r, g), b));
  }
  void main() {
      vec3 msdf = texture(uAtlas, vUV).rgb;
      float sd = median(msdf.r, msdf.g, msdf.b);
      float screenPxDist = uScreenPxRange * (sd - 0.5);
      float alpha = clamp(screenPxDist + 0.5, 0.0, 1.0);
      alpha *= vColor.a;
      // 预乘 alpha 输出（匹配现有 GL_ONE, GL_ONE_MINUS_SRC_ALPHA 混合）
      fragColor = vec4(vColor.rgb * alpha, alpha);
  }
  ```
- **`uScreenPxRange` 计算**（CPU 侧每帧更新）：
  - 含义：atlas 中 `pxRange` 个纹素在当前屏幕上映射到多少个屏幕像素。
  - 公式：`screenPxRange = pxRange * (screenGlyphSize / atlasGlyphSize)`。
  - 其中 `screenGlyphSize` ≈ `m_msdfFontSize * m_zoom * dpr`（em 归一化 1.0 在屏幕上的像素数），`atlasGlyphSize` ≈ 32（glyph 内区域目标像素数 `targetInnerPixels`）。
  - 简化为 uniform 传入，避免 per-vertex 计算。最低钳位到 1.0 防止超小文字锯齿。
- 混合保持现状：`GL_ONE, GL_ONE_MINUS_SRC_ALPHA`（预乘）。

### 4.5 atlas 增量更新（关键修正）
当前 `buildForLabels()` 每次**全量重建**所有 glyph 的 MSDF 位图——每次运行时增删节点都会触发。对 500+ 节点图的 CJK 标签（可能 1000+ 唯一字符），全量重建耗时数秒，**不可接受**。

改造为增量模式：
```cpp
// MsdfFontAtlas 新增接口
bool ensureGlyphs(const QStringList& labels, QString* errorMessage = nullptr);
// 行为：扫描 labels 中所有 codepoint，仅对 m_glyphs 中不存在的 codepoint 生成 MSDF 并追加到 atlas 尾部。
// 返回 true 表示 atlas 有变化（需要重新上传纹理），false 表示无新增。
```
- 打包算法改为"游标递增"：维护 `(cursorX, cursorY, rowH)` 状态，新 glyph 追加到当前行尾部或换行。
- atlas 满时扩展高度（翻倍到 `min(currentH * 2, maxH)`），老数据不动，仅在扩展区域追加。
- `buildForLabels()` 保留用于首次全量构建或强制重建。

### 4.6 MsdfTextRenderer 完整接口规格（新增）
```cpp
class MsdfTextRenderer {
public:
    MsdfTextRenderer() = default;
    ~MsdfTextRenderer() = default;

    bool initialize(QOpenGLFunctions_3_3_Core* gl);
    void cleanup();

    // atlas 纹理管理（generation 变化或首次时调用）
    void uploadAtlas(const unsigned char* pixels, int width, int height, int generation);

    // 批量绘制文本
    // vertices: [x, y, u, v, r, g, b, a] * N（6 vertices per glyph, 2 triangles）
    // mvp: 4x4 正交投影矩阵
    // screenPxRange: pxRange 在当前缩放/DPI 下的屏幕像素值
    void draw(const std::vector<float>& vertices, const float* mvp, float screenPxRange);

private:
    QOpenGLFunctions_3_3_Core* m_gl = nullptr;
    unsigned int m_program = 0;
    unsigned int m_vao = 0;
    unsigned int m_vbo = 0;
    unsigned int m_texture = 0;
    int m_atlasGeneration = -1;
    int m_uniformMvp = -1;
    int m_uniformScreenPxRange = -1;
    int m_uniformAtlas = -1;
};
```

### 4.7 像素稳定性与 DPI
- 保留当前"像素对齐"目标，避免缩放时文字抖动。
- **DPI 处理**：MSDF 渲染走纯 GL 路径，`glViewport` 已使用 device pixel 尺寸，MVP 矩阵基于逻辑像素视口。`uScreenPxRange` 计算中需乘 `devicePixelRatio`（见 §4.4）。
- 像素对齐：在 CPU 侧对每个 label 的世界坐标 `(x, y)` 做 device-space snap：
  ```
  deviceX = worldX * zoom * dpr
  snappedX = round(deviceX) / (zoom * dpr)
  ```
  与当前 `alignToDevice` 逻辑一致。

## 5. 与现有行为一一对齐

### 5.1 标签世界坐标定位（修正）
- 标签中心 X 对齐节点中心，Y 在节点下方：
  ```
  labelWorldX = nodeX - (totalWidth * m_msdfFontSize) / 2
  labelWorldY = nodeY + nodeRadius
  ```
  其中 `totalWidth` 来自 `LabelLayoutEntry`（em 归一化），`m_msdfFontSize` 做 em→世界坐标换算。
- 不再使用 QPainter 的 screen→painter 坐标混合。MVP 直接将世界坐标映射到 NDC。

### 5.2 显示阈值
- 继续使用 `m_textThresholdOff / m_textThresholdShow` 控制文本显隐和淡入。
- `scale < m_textThresholdOff`：不绘制任何文本。
- `m_textThresholdOff ≤ scale < m_textThresholdShow`：`baseAlpha = (scale - off) / (show - off)`。
- `scale ≥ m_textThresholdShow`：`baseAlpha = 1.0`。

### 5.3 分组透明度
- `groupBase`: `color.a = baseAlpha`
- `groupDim`: `color.a = baseAlpha * (1 - 0.7 * m_hoverGlobal)`
- `groupHover`: `color.a = baseAlpha`（hover 标签保持全 alpha）

### 5.4 hover 放大
- 由"字体点大小放大"改为"MSDF 几何 scale 放大"。
- hover label 的 `m_msdfFontSize` 乘以 `(1 + m_hoverGlobal * 2.0)` → 最大 3x。
- 重新居中：放大后 `totalWidth * scaledFontSize / 2`。
- 垂直偏移增加 `m_fontHeight * (0.2 * m_hoverGlobal + 1.0)` 的等效世界坐标偏移。

### 5.5 渲染顺序
- 保持不变：边 → 节点 → 文本（文本最后绘制，覆盖在节点/边之上）。
- 绘制文本前不需要清除深度（2D 场景不开深度测试）。

## 6. CMake 接入计划（按实际仓库修正）
在 `cpp_bindings/forced_direct_view/CMakeLists.txt` 执行，**必须在 `add_library(forceviewlib)` 之前**插入：

1. 引入第三方子工程（顺序固定，插入到 `find_package(OpenMP)` 之后、`# Project 1: Shared library` 之前）
```cmake
# ----- MSDF text rendering dependencies -----
set(MSDFGEN_USE_VCPKG OFF CACHE BOOL "" FORCE)
set(MSDFGEN_BUILD_STANDALONE OFF CACHE BOOL "" FORCE)
set(MSDFGEN_USE_SKIA OFF CACHE BOOL "" FORCE)
set(MSDFGEN_DISABLE_SVG ON CACHE BOOL "" FORCE)
set(MSDFGEN_DISABLE_PNG ON CACHE BOOL "" FORCE)

add_subdirectory(3rdparty/freetype)
if(NOT TARGET Freetype::Freetype)
  add_library(Freetype::Freetype ALIAS freetype)
endif()
add_subdirectory(3rdparty/msdfgen)
```

2. `forceviewlib` 源文件新增（在 `set(${forceview_library}_sources` 中追加）
```
src/MsdfFontAtlas.cpp
src/MsdfTextRenderer.cpp
include/MsdfFontAtlas.h
include/MsdfTextRenderer.h
```

3. `forceviewlib` 链接新增
```cmake
target_link_libraries(${forceview_library}
  PUBLIC Qt6::Widgets Qt6::OpenGLWidgets Qt6::OpenGL
  PRIVATE OpenMP::OpenMP_CXX
          msdfgen::msdfgen-core
          msdfgen::msdfgen-ext
          Freetype::Freetype
)
```

## 7. 分阶段实施（强制落地）

### Phase 1: 基础打通（必须完成）
| 步骤 | 操作 | 验证 |
|------|------|------|
| 1.1 | 在 CMakeLists.txt 中按 §6 插入 3rdparty、源文件、链接 | `cmake -B build && cmake --build build` 成功 |
| 1.2 | **创建** `MsdfTextRenderer.h/cpp`（按 §4.6 接口规格），包含 shader 编译（§4.4 的 VS/FS）、VAO/VBO 创建、纹理管理、draw 方法 | 编译通过 |
| 1.3 | 修改 `MsdfFontAtlas.h`：将 `ascender()`/`descender()`/`lineHeight()` 改为 public | 编译通过 |
| 1.4 | 在 `ForceViewOpenGL.h` 添加成员：`std::unique_ptr<MsdfFontAtlas> m_fontAtlas; std::unique_ptr<MsdfTextRenderer> m_textRenderer; float m_msdfFontSize = 8.0f;` | - |
| 1.5 | 在 `initializeGL()` 中：创建 `MsdfFontAtlas`（Config：fontPath=`C:/Windows/Fonts/msyh.ttc`、atlasWidth=2048、atlasHeight=2048、pxRange=6）；创建 `MsdfTextRenderer` 并 `initialize(this)` | 运行无崩溃 |
| 1.6 | 在析构或 `cleanup` 中释放 `m_textRenderer`、`m_fontAtlas` | 无泄漏 |

### Phase 2: 文本最小可用（必须完成）
| 步骤 | 操作 | 验证 |
|------|------|------|
| 2.1 | 在 `setGraph()` 和 `m_labels` 变化路径中调用 `m_fontAtlas->buildForLabels(m_labels)`，并 `m_textRenderer->uploadAtlas(...)` | atlas 生成、纹理上传 |
| 2.2 | 实现 `LabelLayoutEntry` 缓存（§4.3）：对每个唯一 label 文本，用 `findGlyph`/`kerning` 计算 glyph 局部 quad（em 归一化坐标），缓存到 `std::unordered_map<std::string, LabelLayoutEntry>` | 布局数据正确 |
| 2.3 | 实现顶点构建函数：对每个可见 label，从缓存取局部 quad，用 `m_msdfFontSize` 缩放到世界坐标，加上节点偏移（§5.1），设置颜色/alpha（§5.2, §5.3），输出 6 顶点/字形（2 三角形），格式 `[x,y,u,v,r,g,b,a]` | 顶点数据正确 |
| 2.4 | 在 `paintGL()` 中，当 `scale > m_textThresholdOff` 时：计算 `uScreenPxRange`（§4.4），构建顶点，调用 `m_textRenderer->draw(vertices, m_cachedMvp, screenPxRange)`，**移除** `QOpenGLPaintDevice`/`QPainter` 常规标签绘制 | 文本显示 |
| 2.5 | 实现缩放阈值淡入（§5.2）和分组 alpha（§5.3） | 淡入/分组透明度一致 |
| 2.6 | 像素对齐：在构建顶点时对 label 世界坐标做 device-space snap（§4.7） | 缩放时无抖动 |
| 2.7 | 调节 `m_msdfFontSize` 初始值，使文本大小与 QPainter pointSize=5 视觉一致 | 视觉对比验证 |

### Phase 3: 交互对齐（必须完成）
| 步骤 | 操作 | 验证 |
|------|------|------|
| 3.1 | hover 标签：`m_hoverIndex != -1` 时，对该 label 单独构建顶点，几何 scale 放大 `(1 + m_hoverGlobal * 2.0)`，颜色高亮，重新居中 | 视觉与当前一致 |
| 3.2 | 在 `addNodes`、`removeNodes`、`applyDiffRuntime` 等修改 `m_labels` 的路径中，触发 atlas/布局重建 | 图数据变更后文本正确 |
| 3.3 | 移除所有 QPainter 文本残留：删除 `m_staticTextCache`、`m_labelCacheByIndex`、`m_cachedHoverLabel*` 相关成员和 `initStaticTextCache()` | 代码清理完成 |

### Phase 4: 增量 atlas 与性能（必须完成，CJK 场景硬需求）
| 步骤 | 操作 | 验证 |
|------|------|------|
| 4.1 | 实现 `MsdfFontAtlas::ensureGlyphs()`（§4.5）：增量扫描 + 追加生成 + atlas 扩展 | 新增节点时不全量重建 |
| 4.2 | 在 `add_node_runtime` / `apply_diff_runtime` 路径中改用 `ensureGlyphs()` 替代 `buildForLabels()` | runtime 增删节点无卡顿 |
| 4.3 | atlas 扩展时 `MsdfTextRenderer::uploadAtlas()` 支持纹理 resize（销毁旧纹理、创建新纹理） | 扩展后文本正确 |

### Phase 5: 鲁棒与可观测（建议完成）
| 步骤 | 操作 | 验证 |
|------|------|------|
| 5.1 | atlas 分页（单页 2048x2048 不足时创建第二页纹理），MsdfTextRenderer 支持多纹理 draw call | 超大字符集不溢出 |
| 5.2 | LRU 淘汰（当 atlas 满且无法扩展时淘汰最久未使用字形） | 极端场景不崩溃 |
| 5.3 | 渲染统计：字形命中率、atlas 重建次数、文本 draw call 耗时 | 可观测 |
| 5.4 | 可配置字体路径（通过 config.py 或 setFont 接口） | 跨平台支持 |

## 8. 验收标准
- 代码中不再使用 `QOpenGLPaintDevice/QPainter/QStaticText` 绘制文本。
- 与当前版本相比：
  - 阈值显隐行为一致
  - 分组透明度一致
  - hover 放大视觉一致
- 缩放过程中文本边缘清晰、无明显闪烁。
- 大图场景下帧率不低于当前实现（至少持平）。
- CJK 标签（500+ 唯一字符）正常显示，不溢出。

## 9. 风险与规避
- **OpenGL 3.3 Core**：MSDF shader 与 GraphRenderer 均使用 `#version 330 core`，需确保 QOpenGLWidget 的 context 支持 3.3（当前构造函数已设置 `QSurfaceFormat` 请求 3.3 Core，已满足）。
- **预乘 alpha**：fragment shader 必须输出 `vec4(color.rgb * alpha, alpha)`，配合 `GL_ONE, GL_ONE_MINUS_SRC_ALPHA`。若输出非预乘会导致文字颜色偏亮。
- 复杂脚本（阿拉伯等）需 HarfBuzz shaping，首版暂不覆盖。
- CJK 字符集大，**Phase 4 的增量 atlas 为必须项**，不可推迟到"建议完成"。
- 多平台字体路径差异大，Phase 1 可先固定字体（Windows: `C:/Windows/Fonts/msyh.ttc`），Phase 5 前完成可配置字体查找。
- **GL 状态管理**：文本绘制前需绑定自身 shader/VAO/纹理，绘制后不需要恢复（因为是最后一个绘制步骤）。若后续渲染顺序变化，需确保 `GraphRenderer` 在下次 `drawLines`/`drawNodes` 前重新绑定自己的状态。

## 10. 本次计划更新结论
- 已按 `ForceViewOpenGL.cpp` 与 `GraphRenderer.cpp` 现状完成计划重排。
- 文本渲染路线已明确为 **MSDF 唯一方案**，不保留 QPainter 文本回退路径。

## 11. 方案修正记录

### 第一次审查
| 修正项 | 原描述 | 修正后 |
|--------|--------|--------|
| CMake 插入位置 | 未明确 | 必须在 `add_library(forceviewlib)` 之前，建议在 `find_package(OpenMP)` 之后 |
| 源文件与链接 | 分条列出 | 明确需在 `forceviewlib` 的 sources 中追加 4 个文件 |
| Phase 1 描述 | "空实现" | 改为具体步骤表，含 CMake、成员、初始化、字体路径 |
| Phase 2 顶点构建 | 未细化 | 明确由 ForceViewOpenGL 实现，格式 8 浮点/顶点，6 顶点/字形 |
| Phase 2–3 落地 | 笼统 | 拆分为可执行步骤表，每步带验证方法 |
| 2.4 已有模块 | 无 | 新增 §2.4，说明 MsdfFontAtlas/MsdfTextRenderer 接口与顶点构建职责 |

### 第二次审查（本次）
| 修正项 | 原描述 | 修正后 |
|--------|--------|--------|
| MsdfTextRenderer 状态 | §2.4 写"若存在"，Plan 假设已有 | 明确标注"不存在，需全新编写"，增加 §4.6 完整接口规格 |
| em→世界坐标映射 | 完全缺失 | 新增 §4.2，定义 `m_msdfFontSize` 及换算规则 |
| atlas 尺寸 | `1024x1024` | 改为 `2048x2048`，附 CJK 容量分析 |
| 预乘 alpha | 仅提"混合保持现状" | §4.4 明确 FS 必须输出预乘颜色 `vec4(rgb*a, a)` |
| 标签定位坐标系 | 使用 QPainter 的 screen/scale 混合坐标 | §5.1 改为纯世界坐标定位，通过 MVP 直接映射 |
| screenPxRange | 仅提 "fwidth + pxRange" | §4.4 补充完整公式、uniform 传入方式 |
| ascender/descender | MsdfFontAtlas 中为 private | §1.3 要求公开，§5.1 说明用途 |
| 增量 atlas | Phase 4 "建议完成" | 改为 Phase 4 **必须完成**，新增 §4.5 增量设计 |
| atlas 全量重建 | 未识别为问题 | §4.5 分析性能问题，增加 `ensureGlyphs()` 增量接口 |
| DPI 处理 | 仅提像素对齐 | §4.7 补充 DPI 对 screenPxRange 和像素对齐的影响 |
| Shader 代码 | 无 | §4.4 提供完整 VS/FS 源码 |
| GL 状态管理 | 无 | §9 风险中补充 |
| LabelLayoutCache 设计 | 笼统 | §4.3 明确数据结构、缓存 key、重建时机 |
| Phase 阶段调整 | 4 阶段 | 拆分为 5 阶段，Phase 4 增量 atlas 升级为必须 |
