---
name: darkeye-ui
description: >-
  Guides changes to the darkeye_ui PySide6 design system and reusable widget
  library (tokens, ThemeManager, QSS, layouts, demos). Use when editing or
  adding components under darkeye_ui/, theme/design code, public exports, or
  darkeye_ui.demo; or when the user mentions darkeye_ui, Token* widgets, or
  DarkEye UI components.
---

# darkeye_ui 组件库

`darkeye_ui` 是 DarkEye 的 **PySide6 可复用 UI 包**：设计令牌与主题、封装控件、布局与懒加载基类。业务页面多在仓库根目录的 `ui/`，与 `darkeye_ui` 分层：**组件库放通用外观与行为，业务逻辑留在 `ui/`**。

## 包结构与入口

| 路径 | 职责 |
|------|------|
| `darkeye_ui/design/` | `ThemeTokens`、`ThemeManager`、`load_stylesheet`、内置 SVG 图标、`theme_context.resolve_theme_manager` |
| `darkeye_ui/components/` | 对外组件实现；`components/__init__.py` 的 `__all__` 为**完整公共清单** |
| `darkeye_ui/layouts/` | `FlowLayout`、`WaterfallLayout`、`VFlowLayout`、`VerticalTextLayout` |
| `darkeye_ui/base/` | `LazyWidget` |
| `darkeye_ui/styles/mymain.qss` | 与主题配套的 QSS（与全局 `styles/main.qss` 等协同，按任务阅读） |
| `darkeye_ui/demo.py` | 组件演示入口 |
| `darkeye_ui/doc.md` | **完整规范与组件分类清单**（增删改 API 前应对照） |

## 两套导出（必读）

1. **`darkeye_ui` 顶层**（`darkeye_ui/__init__.py`）：只导出**稳定窄入口**（设计系统核心 + 少量基础控件 + 布局 + `LazyWidget`）。新组件**默认不自动进顶层**，除非刻意提升为稳定 API。
2. **`darkeye_ui.components`**（`darkeye_ui/components/__init__.py`）：**全量公共组件**（当前 `__all__` 为准，与 `tests/test_darkeye_ui_components_public_api.py` 自检一致）。

业务与 demo 中需要完整控件时：`from darkeye_ui.components import ...`。修改 `__all__` 时同步更新测试与（如有）demo。

## 新增或修改组件时的硬性约定

1. **公共 API**：新公共类必须加入 `darkeye_ui/components/__init__.py` 的 `__all__`；若需进入顶层 `darkeye_ui.__all__`，须单独评审。
2. **导入**：`darkeye_ui/components` 内**统一相对导入**（`from ..design...`、`from .foo import ...`），**禁止** `from darkeye_ui...` 绝对导入。
3. **主题**：构造函数保留 `theme_manager: Optional[ThemeManager] = None`；未注入时用 `resolve_theme_manager(theme_manager, "组件名")`（见 `darkeye_ui/design/theme_context.py`），**不要**在组件内各自 try-import `app_context`。
4. **异常**：禁止裸 `except Exception: pass`；预期异常可捕获；降级须可观测（`darkeye_ui/_logging.py` 的 `warn_once` / `logger`）。无 `ThemeManager` 时回退到 `LIGHT_TOKENS` 等策略见 `doc.md`。
5. **样式边界**：基础控件优先 **全局 QSS + objectName**；强自绘用 **paint + tokens**。避免在业务里堆局部 `setStyleSheet` 破坏主题一致性。
6. **演示**：新公共组件应在 `darkeye_ui/demo.py` 增加演示，覆盖默认态、主题切换、核心交互（见 `doc.md` 第 3.6 节）。

## 常用命令

从**项目根目录**运行演示：

```bash
python -m darkeye_ui.demo
```

组件相关测试（示例）：

```bash
pytest tests/test_darkeye_ui_components_public_api.py
```

## 详细参考

- 完整组件分类、Sidebar 说明、`__all__` 与 CI 自检约定：阅读仓库根目录下的 `darkeye_ui/doc.md`（不要用本 Skill 目录的相对路径去解析该文件）。
