from PySide6.QtWidgets import QLabel, QSizePolicy, QFileDialog, QMenu, QWidget
from PySide6.QtGui import (
    QPixmap,
    QImage,
    QDragEnterEvent,
    QDropEvent,
    QMouseEvent,
    QAction,
)
from PySide6.QtCore import Qt, Signal, Slot
import shutil, logging, os, subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from config import ACTRESSIMAGES_PATH, TEMP_PATH, ACTORIMAGES_PATH
from controller.message_service import MessageBoxService
from ui.widgets.image.CoverDropWidget import _container_qss_from_tokens

if TYPE_CHECKING:
    from darkeye_ui.design.theme_manager import ThemeManager


class _ActressAvatarDropLabel(QLabel):
    """内部拖放头像 QLabel（与 Cover 内层一致，不用 DesignLabel，避免透明背景导致 QSS 边框不画）。"""

    coverChanged = Signal()

    _DIRTY_BORDER_QSS = "2px solid #FFA500"

    def __init__(self, type="actress", theme_manager: Optional["ThemeManager"] = None):
        super().__init__()
        if type == "actress":
            self.show_text = "把女优头像拖进来"
            self.base_path = ACTRESSIMAGES_PATH  # 要保存与读取的地址
        elif type == "actor":
            self.show_text = "把男优头像拖进来"
            self.base_path = ACTORIMAGES_PATH

        self.setScaledContents(False)  # 关闭默认拉伸
        self.setAcceptDrops(True)  # 允许拖放
        self.setText(self.show_text)
        self.setAlignment(Qt.AlignCenter)
        # 与 CoverDropWidget 内层一致：用 #container + 令牌虚线边框
        self.setObjectName("container")
        if theme_manager is None:
            try:
                from controller.app_context import get_theme_manager

                theme_manager = get_theme_manager()
            except Exception as e:
                logging.debug(
                    "_ActressAvatarDropLabel: 获取主题管理器失败: %s",
                    e,
                    exc_info=True,
                )
                theme_manager = None
        self._theme_manager = theme_manager
        # 未保存提示等场景覆盖边框（完整 border 值，与 Cover 一致）
        self._border_override: Optional[str] = None
        self._apply_token_styles()
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_token_styles)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._original_pixmap = None  # 保存原始图像,这个是个QPixmap对象
        self._path = None  # 这个是核心
        self.msg = MessageBoxService(self)

    def _apply_token_styles(self) -> None:
        """与 _CoverDropLabel 相同：令牌虚线边，可选 _border_override。"""
        if self._border_override:
            self.setStyleSheet(
                f"QLabel#container{{border: {self._border_override}; "
                f"font-size: 16px; padding: 0px; margin: 0px;}}"
            )
            return
        if self._theme_manager is not None:
            t = self._theme_manager.tokens()
            # 使用 QLabel#container 提高优先级，避免被上级 QSS 冲掉边框
            qss = _container_qss_from_tokens(t).replace(
                "#container {", "QLabel#container {", 1
            )
            self.setStyleSheet(qss)
        else:
            self.setStyleSheet(
                "QLabel#container{border: 2px dashed gray; font-size: 16px; "
                "padding: 0px; margin: 0px;}"
            )

    def set_dirty_highlight(self, on: bool) -> None:
        """为「相对基准已修改」等场景高亮边框；False 恢复令牌/默认虚线框。"""
        want = bool(on)
        new_override = self._DIRTY_BORDER_QSS if want else None
        if self._border_override == new_override:
            return
        self._border_override = new_override
        self._apply_token_styles()

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        open_folder_action = QAction("打开图片所在位置", self)
        open_folder_action.triggered.connect(self.open_image_folder)

        clear_action = QAction("清除封面", self)
        clear_action.triggered.connect(lambda: self.set_image(None))

        menu.addAction(open_folder_action)
        menu.addAction(clear_action)

        menu.exec(event.globalPos())

    def open_image_folder(self):
        if not self._path or not os.path.exists(self._path):
            self.msg.show_info("错误", "当前没有可打开的图片。")
            return

        try:
            if os.name == "nt":  # Windows
                subprocess.run(["explorer", "/select,", self._path])
            elif os.name == "posix":  # macOS / Linux
                subprocess.run(["xdg-open", os.path.dirname(self._path)])
        except Exception as e:
            logging.error("无法打开文件夹: %s", e)
            self.msg.show_info("错误", f"无法打开文件夹: {e}")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择封面图片",
                "",
                "图片文件 (*.jpg *.jpeg *.png *.bmp *.gif *.webp)",
            )
            if file_path:
                if self.is_image(file_path):
                    self._path = self.temp_save_image(file_path)
                    self._show_image()
                    self.coverChanged.emit()
                else:
                    self.msg.show_info("文件类型错误", f"不是图片文件：{file_path}")
        else:
            super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        for url in urls:
            file_path = url.toLocalFile()
            if self.is_image(file_path):
                self._path = self.temp_save_image(file_path)
                self._show_image()
                self.coverChanged.emit()
            else:
                self.msg.show_info("文件类型错误", f"不是图片文件：{file_path}")

    def temp_save_image(self, src_path: str) -> str:
        """使用pathlib保存图片到临时目录"""
        src = Path(src_path)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst_name = f"image_{timestamp}{src.suffix.lower()}"

        TEMP_PATH.mkdir(parents=True, exist_ok=True)
        dst_path = Path(TEMP_PATH) / dst_name

        shutil.copy(src, dst_path)
        logging.info("图片已临时保存到%s", dst_path)

        return str(dst_path)

    def is_image(self, path: str | Path) -> bool:
        file_path = Path(path) if isinstance(path, str) else path
        return file_path.suffix.lower() in {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
        }

    def _show_image(self):
        if self._path is None:
            self.setText("无封面")
            return

        original_image = QImage(str(self._path))
        if original_image.isNull():
            logging.warning("图片加载失败,可能是不存在图片")
            self.setText("无封面")
            return

        self._original_pixmap = QPixmap.fromImage(original_image)
        scaled_pixmap = self._original_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        if self._original_pixmap:
            scaled = self._original_pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            super().setPixmap(scaled)
        super().resizeEvent(event)

    @Slot(str)
    def set_image(self, relative_image_path: str | None):
        cover_changed = False
        if relative_image_path is None or relative_image_path == "":
            if self._path is not None:
                cover_changed = True
            self._path = None
            self._original_pixmap = None
            self.setPixmap(QPixmap())
            self.setText(self.show_text)
            if cover_changed:
                self.coverChanged.emit()
            return

        p = Path(relative_image_path)
        if p.is_absolute():
            self._path = str(p)
        else:
            self._path = str(self.base_path / relative_image_path)
        self._show_image()
        self.coverChanged.emit()

    def get_image(self) -> str:
        return self._path


class ActressAvatarDropWidget(QWidget):
    """可拖动式添加头像；在父容器内按宽高比占满并居中（与 CoverDropWidget 相同的外框适配方式）。"""

    coverChanged = Signal()

    def __init__(
        self,
        type="actress",
        aspect_ratio: float = 1.0,
        theme_manager: Optional["ThemeManager"] = None,
    ):
        super().__init__()
        self._aspect_ratio = aspect_ratio
        self._inner = _ActressAvatarDropLabel(type, theme_manager=theme_manager)
        self._inner.setParent(self)
        self._inner.coverChanged.connect(self.coverChanged.emit)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        if h <= 0 or w <= 0:
            return
        if w / h >= self._aspect_ratio:
            tw, th = int(h * self._aspect_ratio), h
        else:
            tw, th = w, int(w / self._aspect_ratio)
        self._inner.setFixedSize(tw, th)
        self._inner.move((w - tw) // 2, (h - th) // 2)

    def set_image(self, relative_image_path: str | None):
        self._inner.set_image(relative_image_path)

    def get_image(self) -> str:
        return self._inner.get_image()

    def set_dirty_highlight(self, on: bool) -> None:
        """高亮头像区域边框，表示相对加载基准已变更。"""
        self._inner.set_dirty_highlight(on)
