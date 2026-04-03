import logging
import re
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtWidgets import (
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QTextBrowser,
    QButtonGroup,
    QStackedWidget,
    QSizePolicy,
)
from PySide6.QtCore import QFileSystemWatcher
from PySide6.QtGui import QFont

from config import AVWIKI_PATH
from darkeye_ui import LazyWidget
from darkeye_ui.components.button import Button
from darkeye_ui.components.input import PlainTextEdit
from darkeye_ui.design.theme_context import resolve_theme_manager


def _preprocess_wiki_links(text: str) -> str:
    """将 [[Page]] 转为 HTML 链接，供 QTextBrowser 点击跳转。"""
    return re.sub(r"\[\[(.+?)\]\]", r'<a href="internal:\1">\1</a>', text)


class AvPage(LazyWidget):
    def __init__(self):
        super().__init__()
        self._stem_to_path: dict[str, Path] = {}
        self._path_to_item: dict[Path, QTreeWidgetItem] = {}
        self._current_path: Path | None = None
        self._edit_dirty = False
        self._save_timer: QTimer | None = None
        self._watcher: QFileSystemWatcher | None = None

    def _lazy_load(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 4)
        self._splitter.setChildrenCollapsible(False)

        self._theme_manager = resolve_theme_manager(None, "AvPage")
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_splitter_style)
        self._apply_splitter_style()

        self._tree = QTreeWidget()
        self._tree.setObjectName("DesignTreeView")
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # 右侧：工具栏 + 预览/编辑堆叠
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        btn_preview = Button("预览")
        btn_preview.setCheckable(True)
        btn_preview.setChecked(True)
        btn_edit = Button("编辑")
        btn_edit.setEnabled(False)
        btn_edit.setCheckable(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(btn_preview)
        self._mode_group.addButton(btn_edit)
        toolbar = QHBoxLayout()
        toolbar.addWidget(btn_preview)
        toolbar.addWidget(btn_edit)
        toolbar.addStretch()
        right_layout.addLayout(toolbar)

        content_font = QFont()
        content_font.setPointSize(13)

        self._browser = QTextBrowser()
        self._browser.setObjectName("DesignTextEdit")
        self._browser.setFont(content_font)
        self._browser.setOpenExternalLinks(False)
        self._browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._browser.anchorClicked.connect(self._handle_link)

        self._editor = PlainTextEdit()
        self._editor.setFont(content_font)
        self._editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._editor.setPlaceholderText("请在左侧选择一篇文档")
        self._editor.textChanged.connect(self._on_editor_text_changed)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._browser)
        self._stack.addWidget(self._editor)
        self._stack.setCurrentIndex(0)
        right_layout.addWidget(self._stack)

        self._splitter.addWidget(self._tree)
        self._splitter.addWidget(right_widget)
        self._splitter.setSizes([220, 2000])

        layout.addWidget(self._splitter)

        btn_preview.clicked.connect(self._switch_to_preview)
        btn_edit.clicked.connect(self._switch_to_edit)

        self._tree.itemClicked.connect(self._on_tree_item_clicked)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_auto_save)

        root_path = Path(AVWIKI_PATH)
        if root_path.is_dir():
            self._watcher = QFileSystemWatcher(self)
            self._watcher.addPath(str(root_path.resolve()))
            self._watcher.directoryChanged.connect(self._on_avwiki_changed)

        self._build_tree()
        self._select_first_and_load()

    def _apply_splitter_style(self) -> None:
        """用当前主题 token 设置 splitter 把手样式，随主题变色。"""
        if self._theme_manager is not None:
            t = self._theme_manager.tokens()
            handle = t.color_border
            handle_hover = t.color_primary
        else:
            handle = "#cccccc"
            handle_hover = "#888888"
        self._splitter.setStyleSheet(
            f"""
            QSplitter::handle {{
                background: {handle};
                width: 1px;
                height: 1px;
                border: none;
                margin: 0;
            }}
            QSplitter::handle:hover {{
                background: {handle_hover};
            }}
        """
        )

    def showEvent(self, event):
        super().showEvent(event)
        if self._initialized:
            self._build_tree()
            self._restore_selection()

    def _on_avwiki_changed(self) -> None:
        self._build_tree()
        self._restore_selection()

    def _restore_selection(self) -> None:
        """根据 _current_path 恢复树选中项。"""
        if not self._current_path:
            return
        resolved = self._current_path.resolve()
        item = self._path_to_item.get(resolved)
        if item is not None:
            self._tree.setCurrentItem(item)
            self._tree.scrollToItem(item)
        else:
            self._current_path = None

    def _build_tree(self) -> None:
        """递归扫描 AVWIKI_PATH 下所有 .md，构建树并缓存 stem -> path。"""
        self._tree.clear()
        self._stem_to_path.clear()
        self._path_to_item.clear()
        root_path = Path(AVWIKI_PATH)
        if not root_path.is_dir():
            return
        md_files = sorted(root_path.rglob("*.md"))
        dir_nodes: dict[Path, QTreeWidgetItem] = {}
        for p in md_files:
            try:
                rel = p.relative_to(root_path)
            except ValueError:
                continue
            stem = p.stem
            if stem not in self._stem_to_path:
                self._stem_to_path[stem] = p
            parts = rel.parts
            if len(parts) == 1:
                item = QTreeWidgetItem(self._tree, [stem])
            else:
                parent_path = root_path
                for i, segment in enumerate(parts[:-1]):
                    parent_path = parent_path / segment
                    if parent_path not in dir_nodes:
                        dir_item = QTreeWidgetItem(
                            self._tree if i == 0 else dir_nodes[parent_path.parent],
                            [segment],
                        )
                        dir_nodes[parent_path] = dir_item
                parent_item = (
                    dir_nodes[root_path / parts[0]] if len(parts) > 1 else self._tree
                )
                for i in range(1, len(parts) - 1):
                    parent_path = root_path
                    for j in range(i + 1):
                        parent_path = parent_path / parts[j]
                    parent_item = dir_nodes[parent_path]
                item = QTreeWidgetItem(parent_item, [stem])
            item.setData(0, Qt.ItemDataRole.UserRole, str(p.resolve()))
            self._path_to_item[p.resolve()] = item

    def _select_first_and_load(self) -> None:
        """若有节点则选中第一项并加载其内容。"""
        root = self._tree.invisibleRootItem()
        if root.childCount() == 0:
            return
        first = self._first_leaf(root)
        if first is not None:
            self._tree.setCurrentItem(first)
            path_str = first.data(0, Qt.ItemDataRole.UserRole)
            if path_str:
                self._current_path = Path(path_str)
                self._load_md_to_browser(self._current_path)
                if self._stack.currentIndex() == 1:
                    self._load_md_to_editor(self._current_path)

    def _first_leaf(self, item: QTreeWidgetItem) -> QTreeWidgetItem | None:
        """取树中第一个叶子（有 UserRole 路径的节点）。"""
        path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if path_str:
            return item
        for i in range(item.childCount()):
            child = self._first_leaf(item.child(i))
            if child is not None:
                return child
        return None

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not path_str:
            return
        path = Path(path_str)
        if self._stack.currentIndex() == 1 and self._current_path and self._edit_dirty:
            self._do_auto_save()
        self._current_path = path
        if self._stack.currentIndex() == 0:
            self._load_md_to_browser(path)
        else:
            self._load_md_to_editor(path)
        self._tree.setCurrentItem(item)
        self._tree.scrollToItem(item)

    def _load_md_to_browser(self, path: Path) -> None:
        """读取 md 并渲染到 browser。"""
        if not path.is_file():
            self._browser.setPlainText("文件不存在。")
            return
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            self._browser.setPlainText(f"读取失败: {e}")
            return
        self._browser.setMarkdown(_preprocess_wiki_links(text))

    def _load_md_to_editor(self, path: Path) -> None:
        """读取 md 原始文本到 editor，并清除 dirty。"""
        self._editor.blockSignals(True)
        if not path.is_file():
            self._editor.setPlainText("")
        else:
            try:
                text = path.read_text(encoding="utf-8")
                self._editor.setPlainText(text)
            except Exception:
                logging.exception("AvPage: 读取 Markdown 到编辑器失败 path=%s", path)
                self._editor.setPlainText("")
        self._editor.blockSignals(False)
        self._edit_dirty = False

    def _on_editor_text_changed(self) -> None:
        self._edit_dirty = True
        self._save_timer.stop()
        self._save_timer.start(1500)

    def _do_auto_save(self) -> None:
        """将 editor 内容写入 _current_path（仅编辑模式且路径存在时）。"""
        if self._stack.currentIndex() != 1 or not self._current_path:
            return
        path = self._current_path
        if not path.is_file():
            return
        try:
            path.write_text(self._editor.toPlainText(), encoding="utf-8")
            self._edit_dirty = False
        except Exception:
            logging.exception("AvPage: 自动保存 Markdown 失败 path=%s", path)

    def _switch_to_preview(self) -> None:
        if self._stack.currentIndex() == 1 and self._edit_dirty and self._current_path:
            self._do_auto_save()
        if self._current_path:
            self._load_md_to_browser(self._current_path)
        self._stack.setCurrentIndex(0)

    def _switch_to_edit(self) -> None:
        if self._current_path:
            self._load_md_to_editor(self._current_path)
        self._stack.setCurrentIndex(1)

    def _handle_link(self, url: QUrl) -> None:
        """处理 [[页面名]] 点击：internal 按 stem 匹配并跳转。"""
        if url.scheme() == "internal":
            raw = url.path()
            page = raw[1:] if raw.startswith("/") else raw
            path = self._stem_to_path.get(page)
            if path is not None:
                self._current_path = path
                self._load_md_to_browser(path)
                item = self._path_to_item.get(path.resolve())
                if item is not None:
                    self._tree.setCurrentItem(item)
                    self._tree.scrollToItem(item)
            else:
                self._browser.setPlainText(f"未找到页面：{page}")
        else:
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(url)
