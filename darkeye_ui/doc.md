# darkeye_ui 组件库开发规范与现状清单

更新时间：2026-03-07

## 1. 文档目标

本文件用于统一 `darkeye_ui` 组件库的开发边界与交付标准，确保：

1. 公共 API 稳定且可预期。
2. 主题切换行为一致，可注入、可降级、可观测。
3. 样式实现边界清晰（全局 QSS vs 组件内部样式 vs 自绘）。
4. demo 与文档同步，避免“有组件无示例”。

---

## 2. 当前代码现状（基线）

1. `darkeye_ui.components.__all__`：59 个导出名。
2. `darkeye_ui.__all__`：29 个导出名。
3. `__all__` 自检通过：
   - `all(name in dir(darkeye_ui) for name in darkeye_ui.__all__) == True`
   - `all(name in dir(darkeye_ui.components) for name in darkeye_ui.components.__all__) == True`
4. 主题兜底统一走 `design/theme_context.py` 的 `resolve_theme_manager(...)`。
5. 统一日志能力存在于 `darkeye_ui/_logging.py`（`get_logger` + `warn_once`）。

---

## 3. 开发规则（必须遵守）

### 3.1 公共 API 一致性

1. 顶层包 `darkeye_ui/__init__.py` 只导出稳定入口，避免泄漏内部实现细节。
2. 组件导出以 `darkeye_ui/components/__init__.py` 的 `__all__` 为唯一准入清单。
3. 输入类保持显式导出：`LineEdit` / `TextEdit` / `PlainTextEdit`。
4. 每次增删导出名都要执行 `__all__` 自检（建议纳入 CI）。

### 3.2 异常处理策略

1. 禁止无条件吞异常：`except Exception: pass`。
2. 仅捕获预期异常，例如：`ImportError`、`RuntimeError`、`AttributeError`。
3. UI 可以降级，但必须可观测：通过 `warn_once(...)` 或 `logger.warning(...)` 输出告警。
4. 降级策略要明确：无法获取 `ThemeManager` 时回退到 `LIGHT_TOKENS`，而不是静默失败。

### 3.3 主题管理与注入策略

1. 组件构造参数统一提供 `theme_manager: Optional[ThemeManager] = None`。
2. 优先显式注入；未注入时统一通过 `resolve_theme_manager(theme_manager, "组件名")` 兜底获取。
3. 不允许每个组件手写 try-import `controller.app_context`；必须复用统一 helper。
4. 主题变更后统一刷新入口：
   - QSS 型组件：`style().unpolish/polish + update()`
   - 自绘型组件：`update()` 或重建绘制缓存

### 3.4 样式边界（QSS vs 组件内样式）

1. 基础控件（Button/Input/SpinBox/List/Table/Tree）优先：全局 QSS + `objectName`。
2. 强自绘控件（如雷达图、竖排文字、骨架屏）优先：`paintEvent + tokens`。
3. 组件内 `setStyleSheet` 仅用于无法由全局 QSS 管理的局部场景（如弹层、临时危险态）。
4. 禁止在普通业务组件里堆叠局部 QSS 覆盖全局主题，避免主题切换不一致。

### 3.5 导入风格

1. `darkeye_ui/components` 包内统一使用相对导入（`from ..design...`、`from .button...`）。
2. 禁止在组件内部写 `from darkeye_ui...` 绝对导入，避免打包与路径环境差异。
3. 新增组件文件保持与现有风格一致。

### 3.6 Demo 同步规则

1. 新增公共组件必须在 `darkeye_ui/demo.py` 至少有一个演示入口。
2. 演示至少覆盖：默认态、主题切换后表现、核心交互（点击/输入/状态切换）。
3. 若组件存在兼容别名，demo 优先展示主名，别名只在文档说明映射关系。

---

## 4. 现有公共组件清单（59）

以下清单来自 `darkeye_ui.components.__all__`。

### 4.1 文本与数据输入

1. `Label`
2. `LineEdit`
3. `TextEdit`
4. `PlainTextEdit`
5. `ComboBox`
6. `CompleterLineEdit`
7. `TokenSpinBox`
8. `TokenDateTimeEdit`
9. `TokenKeySequenceEdit`
10. `TokenListView`
11. `TokenTableView`
12. `TokenTableWidget`
13. `TreeView`
14. `TokenTreeView`
15. `TokenRadioButton`
16. `TokenCheckBox`

### 4.2 按钮与交互

1. `Button`
2. `IconPushButton`
3. `ChamferButton`
4. `RotateButton`
5. `ShakeButton`
6. `StateToggleButton`
7. `ToggleSwitch`
8. `Chip`
9. `Tag`

### 4.3 容器与导航

1. `TokenTabWidget`
2. `TokenGroupBox`
3. `TokenCollapsibleSection`
4. `TokenVerticalTabBar`
5. `Sidebar2`
6. `ModernScrollMenu`
7. `LazyScrollArea`
8. `TransparentWidget`
9. `Breadcrumb`
10. `Pagination`
11. `SearchBar`

### 4.4 反馈与状态

1. `ProgressBar`
2. `IndeterminateProgressBar`
3. `TokenProgressBar`
4. `ModalDialog`
5. `Dialog`
6. `TokenModalDialog`
7. `Toast`
8. `Notification`
9. `Skeleton`
10. `EmptyState`

### 4.5 图形与视觉组件

1. `VerticalTextLabel`
2. `TokenVLabel`
3. `CalendarHeatmap`
4. `RadarChartWidget`
5. `CircularLoading`
6. `ColorPicker`
7. `ClickableSlider`
8. `HeartLabel`
9. `HeartRatingWidget`
10. `OctImage`
11. `CalloutTooltip`
12. `Avatar`
13. `AvatarGroup`

---

## 5. 兼容别名映射（保留）

1. `Dialog` -> `ModalDialog`
2. `TokenModalDialog` -> `ModalDialog`
3. `Notification` -> `Toast`
4. `Tag` -> `Chip`
5. `TokenProgressBar` -> `ProgressBar`
6. `TokenTreeView` -> `TreeView`

说明：别名用于向后兼容，新增代码应优先使用主名。

---

## 6. 非公共内部类（不导出）

以下类存在于组件目录，但不在公共导出清单中：

1. `AlphaSliderCustom`（`components/ColorSlider.py`）
2. `TestWindow`（`components/ColorSlider.py`）
3. `CompleterLoaderRunnable`（`components/completer_line_edit.py`）
4. `ImageLoaderRunnable`（`components/oct_image.py`）

---

## 7. Demo 覆盖现状（`darkeye_ui/demo.py`）

1. demo 已导入 49 个组件导出名。
2. 已有页面：
   - `buttons`（按钮/图标按钮/状态按钮）
   - `text`（输入与文本）
   - `toggles`（开关/单选/复选）
   - `inputs`（日期时间/数字/滑块/快捷键/进度条）
   - `containers`（Tab/GroupBox/Table/透明容器）
   - `data_nav`（P1：Breadcrumb/SearchBar/Pagination/TreeView）
   - `p2_experience`（P2：Skeleton/EmptyState/Tag/Avatar）
   - `more`（弹层、提示、评分、图像）
   - `color_icons`（颜色和内置图标）
   - `theme`（主题切换）
3. 当前尚未在 demo 导入的导出组件（10 个）：
   - `CalendarHeatmap`
   - `LazyScrollArea`
   - `ModernScrollMenu`
   - `RadarChartWidget`
   - `TokenCollapsibleSection`
   - `TokenModalDialog`
   - `TokenProgressBar`
   - `TokenTreeView`
   - `TokenVLabel`
   - `TokenVerticalTabBar`

---

## 8. P0/P1/P2 事项状态

### 8.1 P0（已落地）

1. API 一致性修复：`darkeye_ui/__init__.py` 已显式导出 `LineEdit/TextEdit/PlainTextEdit`，不再导出 `Input`。
2. 异常处理收敛：主题获取相关逻辑使用 `resolve_theme_manager(...)`，并通过 `warn_once` 提示降级。
3. 导入风格统一：组件包内导入采用相对路径（含 `radar_chart_widget.py`）。

### 8.2 P1（已落地并演示）

1. `Breadcrumb`
2. `SearchBar`
3. `Pagination`
4. `TreeView/TokenTreeView`（主演示使用 `TreeView`）

### 8.3 P2（已落地并演示）

1. `Skeleton`
2. `EmptyState`
3. `Chip/Tag`
4. `Avatar/AvatarGroup`

---

## 9. 建议补充组件（下一阶段）

建议按“高复用优先”补齐以下组件：

1. `FormField` / `FormSection`（统一标签、必填、错误提示、说明文本）
2. `SegmentedControl`（比 Tab 更轻量的单行切换）
3. `Drawer`（侧边抽屉，补齐 Modal 之外的大块交互容器）
4. `ContextMenu` / `DropdownMenu`（右键菜单与操作菜单）
5. `DateRangePicker`（与现有 `TokenDateTimeEdit` 形成组合能力）
6. `CodeEditor`（日志/配置编辑场景，带行号与高亮）

---

## 10. 新增组件准入检查清单（PR 勾选）

1. 是否加入 `components/__init__.py` 且 `__all__` 正确？
2. 是否支持 `theme_manager` 显式注入，并通过 `resolve_theme_manager` 兜底？
3. 是否避免了 `except Exception: pass`？
4. 是否满足样式边界规则（QSS / 自绘 / 局部 `setStyleSheet`）？
5. 是否采用组件内相对导入？
6. 是否在 demo 中新增可交互演示入口？
7. 是否验证了主题切换（至少 Light / Dark）？
8. 是否补充了最小用例测试（初始化、交互、主题刷新）？

