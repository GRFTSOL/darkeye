from __future__ import annotations

import copy
import logging
import os
from collections.abc import Callable, Sequence
from functools import lru_cache
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from PySide6.QtCore import (
    QByteArray,
    QBuffer,
    QObject,
    QIODevice,
    Qt,
    QThreadPool,
    QTimer,
    QSize,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QCloseEvent,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from darkeye_ui.components.button import Button
from darkeye_ui.components.input import LineEdit
from darkeye_ui.design.icon import (
    SVG_ARROW_DOWN_TO_LINE,
    SVG_ARROW_LEFT,
    SVG_ARROW_RIGHT,
)
from core.crawler.Worker import Worker
from core.crawler.download import download_image_with_retry
from core.database.insert import rename_save_image

LOCAL_ABS_KEY = "_local_abs"

# 缩略图：外框为正方形；内区为正方形，图片按比例缩放至尽量占满（不裁切、不变形）
_THUMB_SIDE = 100
_THUMB_MARGIN = 4
_THUMB_CELL = _THUMB_SIDE + 2 * _THUMB_MARGIN


class _FanartStripInner(QWidget):
    """横条内容底：缩略图未铺满时，空白处长按也可进入编辑模式。"""

    longPressed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._long_press_fired = False
        self._lp_start = None
        self._lp_timer = QTimer(self)
        self._lp_timer.setSingleShot(True)
        self._lp_timer.setInterval(450)
        self._lp_timer.timeout.connect(self._on_long_press_timeout)

    def _on_long_press_timeout(self) -> None:
        self._long_press_fired = True
        self.longPressed.emit()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._long_press_fired = False
            self._lp_start = event.position()
            self._lp_timer.start()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._lp_start is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and self._lp_timer.isActive()
        ):
            if (
                event.position() - self._lp_start
            ).manhattanLength() > QApplication.startDragDistance():
                self._lp_timer.stop()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._lp_timer.stop()
        self._lp_start = None
        self._long_press_fired = False
        super().mouseReleaseEvent(event)


class _FanartHScrollArea(QScrollArea):
    """缩略图条：滚轮只做横向平移，不驱动竖向滚动。"""

    def wheelEvent(self, event: QWheelEvent) -> None:
        hbar = self.horizontalScrollBar()
        pd = event.pixelDelta()
        if not pd.isNull():
            if pd.x():
                hbar.setValue(hbar.value() - pd.x())
                event.accept()
                return
            if pd.y():
                hbar.setValue(hbar.value() - pd.y())
                event.accept()
                return
        ad = event.angleDelta()
        if ad.y():
            hbar.setValue(hbar.value() - ad.y())
            event.accept()
            return
        if ad.x():
            hbar.setValue(hbar.value() - ad.x())
            event.accept()
            return
        super().wheelEvent(event)


def _thumb_path_for_entry(
    entry: dict,
    fanart_root: Path,
    legacy_cover_root: Path | None = None,
) -> str | None:
    local = entry.get(LOCAL_ABS_KEY) or ""
    if local and Path(local).is_file():
        return str(local)
    rel = (entry.get("file") or "").strip()
    if rel:
        for base in (fanart_root, legacy_cover_root):
            if base is None:
                continue
            p = Path(base) / rel
            if p.is_file():
                return str(p)
    return None


def _entry_has_url(entry: dict) -> bool:
    return bool((entry.get("url") or "").strip())


def _thumb_cache_token(path: str) -> tuple[str, int, int] | None:
    try:
        stat = Path(path).stat()
    except OSError:
        return None
    return (path, stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=256)
def _load_cached_thumb_pixmap(path: str, mtime_ns: int, size: int) -> QPixmap | None:
    del mtime_ns, size
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return None
    return pixmap.scaled(
        QSize(_THUMB_SIDE, _THUMB_SIDE),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _thumb_pixmap_for_path(path: str | None) -> QPixmap | None:
    if not path:
        return None
    token = _thumb_cache_token(path)
    if token is None:
        return None
    return _load_cached_thumb_pixmap(*token)


_DIALOG_PREVIEW = 600
# 对话框预览：工作线程里先把长边压到此值以下，避免主线程解码/缩放超大图卡顿
_PREVIEW_DECODE_MAX_SIDE = 1400


def _load_fanart_dialog_preview_task(path: str) -> tuple[str, object] | None:
    """在工作线程执行：解码、缩小，再编码为 PNG 字节供主线程加载。

    不通过信号传递 QImage（PySide 跨线程易崩溃/无效），只传 bytes。
    """
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return ("fail", path)
    img = QImage()
    if not img.loadFromData(QByteArray(raw)):
        img = QImage(path)
        if img.isNull():
            return ("fail", path)
    w, h = img.width(), img.height()
    m = max(w, h)
    if m > _PREVIEW_DECODE_MAX_SIDE:
        img = img.scaled(
            _PREVIEW_DECODE_MAX_SIDE,
            _PREVIEW_DECODE_MAX_SIDE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    if not img.save(buf, "PNG"):
        return ("fail", path)
    return ("ok", bytes(ba))


_WIN_FILENAME_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_fanart_stem(stem: str) -> str:
    stem = _WIN_FILENAME_FORBIDDEN.sub("_", stem).strip(" .")
    return stem or "fanart"


def _fanart_jpg_name_from_url(url: str) -> str | None:
    """取 URL 路径最后一段，统一为「原名 stem + .jpg」（与 fanart 库内 jpg 惯例一致）。"""
    path = unquote(urlparse((url or "").strip()).path)
    base = Path(path).name
    if not base or base in (".", ".."):
        return None
    stem = _safe_fanart_stem(Path(base).stem)
    if not stem:
        return None
    return f"{stem}.jpg"


def _fanart_download_task(url: str) -> tuple[str, str, str | None, str]:
    """在工作线程中执行：下载并写入 Fanart 目录。
    返回 (\"ok\", \"\", dest_name, url) 或 (\"err\", message, None, \"\" )。
    """
    url = (url or "").strip()
    if not url:
        return ("err", "请先填写图片网址。", None, "")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return ("err", "网址需要以 http(s) 开头。", None, "")
    dest_name = _fanart_jpg_name_from_url(url)
    if not dest_name:
        return ("err", "无法从网址中解析出文件名。", None, "")
    path_part = Path(unquote(parsed.path))
    ext = path_part.suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    try:
        ok, msg = download_image_with_retry(url, tmp_path, timeout_s=30, retries=2)
        if not ok:
            try:
                os.remove(tmp_path)
            except OSError as e:
                logging.debug(
                    "Fanart 下载失败：清理临时文件失败 %s: %s",
                    tmp_path,
                    e,
                    exc_info=True,
                )
            return ("err", msg or "下载失败", None, "")
        rename_save_image(tmp_path, dest_name, "fanart")
        return ("ok", "", dest_name, url)
    except Exception as e:
        logging.exception("Fanart 后台下载保存失败")
        try:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)
        except OSError as rm_err:
            logging.debug(
                "Fanart 异常后清理临时文件失败 %s: %s",
                tmp_path,
                rm_err,
                exc_info=True,
            )
        return ("err", str(e), None, "")


class _FanartPreviewLoadBridge(QObject):
    """预览解码在线程池完成；用挂到对话框上的 QObject 槽接收 finished，与下载桥接同理。

    若用 functools.partial 绑到 FanartEditDialog 的方法作为槽，QueuedConnection 可能无法
    正确识别接收者线程，模态 exec 时界面会一直停在「加载中…」。
    """

    def __init__(
        self,
        dialog: QWidget,
        gen: int,
        slot_index: int,
        has_url: bool,
    ) -> None:
        super().__init__(dialog)
        self._dialog = dialog
        self._gen = gen
        self._slot_index = slot_index
        self._has_url = has_url

    @Slot(object)
    def on_preview_finished(self, result: object) -> None:
        dlg = self._dialog
        try:
            if dlg is not None:
                dlg._on_preview_image_loaded(
                    self._gen, self._slot_index, self._has_url, result
                )
        finally:
            self._dialog = None
            self.deleteLater()


class FanartEditDialog(QDialog):
    """大图预览与网址编辑；支持上一张/下一张（按钮或左右键，焦点不在网址框时）。"""

    def __init__(
        self,
        entries: list[dict],
        start_index: int,
        fanart_root: Path,
        legacy_cover_root: Path | None = None,
        parent: QWidget | None = None,
        *,
        auto_download_if_missing: bool = False,
        url_read_only: bool = False,
    ) -> None:
        super().__init__(parent)
        self._entries = entries
        self._fanart_root = Path(fanart_root)
        self._legacy_cover_root = (
            Path(legacy_cover_root) if legacy_cover_root is not None else None
        )
        self._n = len(self._entries)
        if self._n == 0:
            self._index = 0
        else:
            self._index = max(0, min(int(start_index), self._n - 1))

        self._download_busy = False
        self._btn_download_default_text = "下载"
        self._auto_download_if_missing = auto_download_if_missing
        self._url_read_only = url_read_only
        self._preview_load_gen = 0

        self.setWindowTitle("Fanart")
        self.resize(440, 560)
        self._source_pixmap: QPixmap | None = None
        layout = QVBoxLayout(self)
        self._img = QLabel()
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setMinimumSize(_DIALOG_PREVIEW, _DIALOG_PREVIEW)
        self._img.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._img.setStyleSheet(
            "QLabel { background-color: transparent; border: none; }"
        )
        layout.addWidget(self._img, 1)

        nav = QHBoxLayout()
        self._btn_prev = Button(icon=SVG_ARROW_LEFT, icon_size=18, parent=self)
        self._btn_next = Button(icon=SVG_ARROW_RIGHT, icon_size=18, parent=self)
        self._btn_prev.clicked.connect(self._go_prev)
        self._btn_next.clicked.connect(self._go_next)
        self._lbl_pos = QLabel("0 / 0")
        self._lbl_pos.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self._btn_prev)
        nav.addWidget(self._lbl_pos, 1)
        nav.addWidget(self._btn_next)
        layout.addLayout(nav)

        layout.addWidget(QLabel("图片网址："))
        self._url = LineEdit()
        self._url.setReadOnly(url_read_only)
        if url_read_only:
            self._url.setToolTip("预览模式：网址由资料库提供，仅可下载到本地")
        url_row = QHBoxLayout()
        url_row.addWidget(self._url, 1)
        self._btn_download = Button(
            self._btn_download_default_text,
            icon=SVG_ARROW_DOWN_TO_LINE,
            icon_size=18,
            parent=self,
        )
        self._btn_download.setToolTip(
            "从网址下载图片到 Fanart 目录，文件名为链接路径末尾的 .jpg 名"
        )
        self._btn_download.clicked.connect(self._on_download_url)
        url_row.addWidget(self._btn_download, 0)
        layout.addLayout(url_row)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self._btn_ok = Button("确定", variant="primary", parent=self)
        self._btn_cancel = Button("取消", parent=self)
        self._btn_ok.setDefault(True)
        self._btn_ok.setAutoDefault(True)
        self._btn_ok.clicked.connect(self.accept)
        self._btn_cancel.clicked.connect(self.reject)
        actions.addWidget(self._btn_ok)
        actions.addWidget(self._btn_cancel)
        layout.addLayout(actions)

        self._refresh_view()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._invalidate_preview_loads()
        super().closeEvent(event)

    def _invalidate_preview_loads(self) -> None:
        self._preview_load_gen += 1

    def _maybe_auto_download_current(self) -> None:
        """当前项有 URL 且本地尚无文件时自动下载（打开对话框或上一张/下一张切换后）。"""
        if not self._auto_download_if_missing:
            return
        if not self._entries or not (0 <= self._index < self._n):
            return
        e = self._entries[self._index]
        url = (e.get("url") or "").strip()
        if not url:
            return
        path = _thumb_path_for_entry(e, self._fanart_root, self._legacy_cover_root)
        if path:
            return
        self._start_fanart_download_async(self._index, url)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_scaled_preview()

    def _apply_scaled_preview(self) -> None:
        if self._source_pixmap is None or self._source_pixmap.isNull():
            return
        w = max(1, self._img.width())
        h = max(1, self._img.height())
        self._img.setPixmap(
            self._source_pixmap.scaled(
                QSize(w, h),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _on_download_url(self) -> None:
        self._sync_url_to_entry()
        url = self._url.text().strip()
        if not url:
            QMessageBox.warning(self, "Fanart", "请先填写图片网址。")
            return
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            QMessageBox.warning(self, "Fanart", "网址需要以 http(s) 开头。")
            return
        if _fanart_jpg_name_from_url(url) is None:
            QMessageBox.warning(self, "Fanart", "无法从网址中解析出文件名。")
            return
        self._start_fanart_download_async(self._index, url)

    def _start_fanart_download_async(self, slot_index: int, url: str) -> None:
        if self._download_busy:
            return
        if not (0 <= slot_index < self._n):
            return
        self._download_busy = True
        self._btn_download.setEnabled(False)
        self._btn_download.setText("下载中…")

        strip = self.parent()
        if not isinstance(strip, FanartStripWidget):
            self._download_busy = False
            self._btn_download.setEnabled(True)
            self._btn_download.setText(self._btn_download_default_text)
            QMessageBox.warning(
                self,
                "Fanart",
                "内部错误：无法挂接下载回调，请从作品编辑页的 Fanart 条打开。",
            )
            return
        strip.run_fanart_download(self, slot_index, url)

    def _sync_url_to_entry(self) -> None:
        if not self._entries or not (0 <= self._index < self._n):
            return
        self._entries[self._index]["url"] = self._url.text().strip()

    def _pull_file_from_strip_for_index(self, index: int) -> None:
        """后台下载只更新条带数据时，对话框内列表可能未写入 file；从父级条带补全。"""

        if not self._entries or not (0 <= index < self._n):
            return
        strip = self.parent()
        if not isinstance(strip, FanartStripWidget):
            return
        if not (0 <= index < len(strip._entries)):
            return
        s_ent = strip._entries[index]
        d_ent = self._entries[index]
        s_file = (s_ent.get("file") or "").strip()
        d_file = (d_ent.get("file") or "").strip()
        if s_file and not d_file:
            d_ent["file"] = s_ent["file"]
            if LOCAL_ABS_KEY in d_ent:
                del d_ent[LOCAL_ABS_KEY]

    def _refresh_view(self) -> None:
        if not self._entries:
            self._source_pixmap = None
            self._img.clear()
            self._img.setText("无图片")
            self._url.clear()
            self._lbl_pos.setText("0 / 0")
            self._btn_prev.setEnabled(False)
            self._btn_next.setEnabled(False)
            return

        self._pull_file_from_strip_for_index(self._index)
        single = self._n <= 1
        self._btn_prev.setEnabled(not single)
        self._btn_next.setEnabled(not single)
        self._lbl_pos.setText(f"{self._index + 1} / {self._n}")

        e = self._entries[self._index]
        self._url.setText(e.get("url") or "")
        path = _thumb_path_for_entry(e, self._fanart_root, self._legacy_cover_root)
        has_url = _entry_has_url(e)
        if path:
            self._preview_load_gen += 1
            gen = self._preview_load_gen
            slot_index = self._index
            self._source_pixmap = None
            self._img.clear()
            self._img.setText("加载中…")
            worker = Worker(_load_fanart_dialog_preview_task, str(path))
            bridge = _FanartPreviewLoadBridge(self, gen, slot_index, has_url)
            worker.signals.finished.connect(
                bridge.on_preview_finished,
                Qt.ConnectionType.QueuedConnection,
            )
            QThreadPool.globalInstance().start(worker)
        elif path:
            self._source_pixmap = None
            self._img.clear()
            self._img.setText("图片未下载" if has_url else "无预览")
        else:
            self._source_pixmap = None
            self._img.clear()
            self._img.setText("图片未下载" if has_url else "无预览")

        self._maybe_auto_download_current()

    def _on_preview_image_loaded(
        self,
        gen: int,
        slot_index: int,
        has_url: bool,
        result: object,
    ) -> None:
        try:
            if gen != self._preview_load_gen:
                return
            if not self._entries or not (0 <= self._index < self._n):
                return
            if self._index != slot_index:
                return
            if result is None or not isinstance(result, tuple) or len(result) != 2:
                self._source_pixmap = None
                self._img.clear()
                self._img.setText("无预览")
                return
            tag, payload = result
            if tag == "ok" and payload is not None:
                data: bytes | None = None
                if isinstance(payload, (bytes, bytearray, memoryview)):
                    data = bytes(payload)
                elif isinstance(payload, QByteArray):
                    data = bytes(payload)
                if data:
                    img = QImage()
                    if img.loadFromData(QByteArray(data), "PNG"):
                        self._source_pixmap = QPixmap.fromImage(img)
                        self._img.setText("")
                        self._apply_scaled_preview()
                        return
            self._source_pixmap = None
            self._img.clear()
            self._img.setText("图片未下载" if has_url else "无预览")
        except RuntimeError:
            # 对话框已销毁时仍可能收到队列中的回调
            logging.debug(
                "Fanart 预览: 对话框已销毁仍收到加载回调，已忽略",
                exc_info=True,
            )

    def _go_prev(self) -> None:
        if self._n <= 1:
            return
        self._sync_url_to_entry()
        self._index = (self._index - 1) % self._n
        self._refresh_view()

    def _go_next(self) -> None:
        if self._n <= 1:
            return
        self._sync_url_to_entry()
        self._index = (self._index + 1) % self._n
        self._refresh_view()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._n > 1 and event.key() in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
        ):
            fw = self.focusWidget()
            if fw is not self._url:
                if event.key() == Qt.Key.Key_Left:
                    self._go_prev()
                else:
                    self._go_next()
                event.accept()
                return
        super().keyPressEvent(event)

    def accept(self) -> None:
        self._sync_url_to_entry()
        super().accept()

    def result_entries(self) -> list[dict]:
        self._sync_url_to_entry()
        return self._entries

    def current_index(self) -> int:
        return self._index


class _FanartThumbCell(QFrame):
    clicked = Signal()
    doubleClicked = Signal()
    longPressed = Signal()
    closeRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedSize(_THUMB_CELL, _THUMB_CELL)
        self._is_add_placeholder = False
        self._long_press_fired = False
        self._lp_start = None
        self._lp_timer = QTimer(self)
        self._lp_timer.setSingleShot(True)
        self._lp_timer.setInterval(450)
        self._lp_timer.timeout.connect(self._on_long_press_timeout)

        self._btn_close = QToolButton(self)
        self._btn_close.setText("×")
        self._btn_close.setFixedSize(20, 20)
        self._btn_close.setToolTip("删除")
        self._btn_close.setVisible(False)
        self._btn_close.setAutoRaise(True)
        self._btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_close.setStyleSheet(
            "QToolButton { background: rgba(0,0,0,0.55); color: #fff; "
            "border: none; border-radius: 10px; font-weight: bold; font-size: 14px; }"
            "QToolButton:hover { background: rgba(200,60,60,0.9); }"
        )
        self._btn_close.clicked.connect(lambda: self.closeRequested.emit())

        lay = QVBoxLayout(self)
        lay.setContentsMargins(
            _THUMB_MARGIN, _THUMB_MARGIN, _THUMB_MARGIN, _THUMB_MARGIN
        )
        lay.setSpacing(0)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setFixedSize(_THUMB_SIDE, _THUMB_SIDE)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            "QLabel { background-color: transparent; border: none; }"
        )
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addStretch(1)
        lay.addWidget(self._label, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(1)
        self._selected = False
        self._apply_style()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        m = 2
        self._btn_close.move(
            max(0, self.width() - self._btn_close.width() - m),
            m,
        )
        self._btn_close.raise_()

    def set_edit_overlay_visible(self, on: bool) -> None:
        if self._is_add_placeholder:
            self._btn_close.setVisible(False)
            return
        self._btn_close.setVisible(on)
        if on:
            self._btn_close.raise_()

    def set_as_add_placeholder(self, on: bool) -> None:
        self._is_add_placeholder = on
        if on:
            self._btn_close.setVisible(False)
            self._label.clear()
            self._label.setText("+")
            self._label.setWordWrap(False)
            self._label.setFixedSize(36, 36)
            self._label.setStyleSheet(
                "QLabel { background-color: transparent; border: none; "
                "color: #8b909a; font-size: 28px; font-weight: 300; }"
            )
        else:
            self._label.setFixedSize(_THUMB_SIDE, _THUMB_SIDE)
            self._label.setStyleSheet(
                "QLabel { background-color: transparent; border: none; }"
            )
        self._apply_style()

    def _on_long_press_timeout(self) -> None:
        self._long_press_fired = True
        self.longPressed.emit()

    def set_selected(self, on: bool) -> None:
        if self._is_add_placeholder:
            return
        self._selected = on
        self._apply_style()

    def _apply_style(self) -> None:
        if self._is_add_placeholder:
            self.setStyleSheet(
                "QFrame { background: transparent; border: 2px dashed #9aa0a6; "
                "border-radius: 4px; }"
            )
            return
        if self._selected:
            self.setStyleSheet(
                "QFrame { border: 2px solid #4a9eff; background: transparent; }"
            )
        else:
            self.setStyleSheet("QFrame { background: transparent; border: none; }")

    def set_thumb(self, pix: QPixmap | None, *, url_but_no_image: bool) -> None:
        if self._is_add_placeholder:
            return
        self._label.clear()
        if pix is not None and not pix.isNull():
            if pix.width() > _THUMB_SIDE or pix.height() > _THUMB_SIDE:
                pix = pix.scaled(
                    QSize(_THUMB_SIDE, _THUMB_SIDE),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            self._label.setPixmap(pix)
            self._label.setStyleSheet(
                "QLabel { background-color: transparent; border: none; }"
            )
            return
        if url_but_no_image:
            self._label.setText("图片未下载")
            self._label.setStyleSheet(
                "QLabel { background-color: transparent; border: none; font-size: 8pt; }"
            )
        else:
            self._label.setText("-")
            self._label.setStyleSheet(
                "QLabel { background-color: transparent; border: none; }"
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._long_press_fired = False
            self._lp_start = event.position()
            self._lp_timer.start()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._lp_start is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and self._lp_timer.isActive()
        ):
            delta = event.position() - self._lp_start
            if delta.manhattanLength() > QApplication.startDragDistance():
                self._lp_timer.stop()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._lp_timer.stop()
        self._lp_start = None
        if event.button() == Qt.MouseButton.LeftButton and not self._long_press_fired:
            self.clicked.emit()
        self._long_press_fired = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self._lp_timer.stop()
        self.doubleClicked.emit()
        event.accept()


class FanartStripWidget(QWidget):
    """横向 Fanart 缩略图条。

    默认仅显示缩略图；在缩略图或横条空白处长按约 0.45s 进入编辑模式：末尾出现虚线「+」格，
    每项右上角显示 × 可删。焦点离开本控件（及无模态框遮挡）后退出编辑模式并发出
    ``fanart_changed`` 以同步模型。非编辑模式下单击缩略图打开大图/网址编辑；编辑模式下单击仅选中，不打开大图。

    **预览模式**（`set_preview_mode(True)`）：禁止长按进入编辑；单击仍打开大图对话框，
    网址为只读，可从网址下载；下载成功后除 ``fanart_changed`` 外，若已设置
    ``set_preview_download_persist``，会再调用该回调（用于浏览场景下写回数据库）。
    """

    fanart_changed = Signal(list)

    def __init__(
        self,
        fanart_path: Path,
        *,
        legacy_cover_path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fanart_path = Path(fanart_path)
        self._legacy_cover_path = (
            Path(legacy_cover_path) if legacy_cover_path is not None else None
        )
        self._entries: list[dict] = []
        self._thumb_cells: list[_FanartThumbCell] = []
        self._selected_index: int | None = None
        self._can_add = True
        self._preview_mode = False
        self._preview_download_persist: Callable[[list[dict]], None] | None = None
        self._edit_mode = False
        self._suspend_leave_edit_for_modal = False
        self._pending_open_index: int | None = None
        self._click_open_timer = QTimer(self)
        self._click_open_timer.setSingleShot(True)
        self._click_open_timer.timeout.connect(self._on_delayed_thumb_open)
        self._edit_focus_check_timer = QTimer(self)
        self._edit_focus_check_timer.setSingleShot(True)
        self._edit_focus_check_timer.timeout.connect(
            self._deferred_leave_edit_if_focus_outside
        )

        self._scroll = _FanartHScrollArea()
        self._scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setMinimumHeight(_THUMB_CELL + 8)
        self._scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._inner = _FanartStripInner()
        self._inner.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._inner.longPressed.connect(self._enter_edit_mode)
        self._hbox = QHBoxLayout(self._inner)
        self._hbox.setContentsMargins(4, 4, 4, 4)
        self._hbox.setSpacing(8)
        self._hbox.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._scroll.setWidget(self._inner)

        self._tail_cell: _FanartThumbCell | None = None

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll, 1)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        QApplication.instance().focusObjectChanged.connect(
            self._on_app_focus_object_changed
        )
        self._rebuild_strip()

    def _cancel_pending_thumb_open(self) -> None:
        self._click_open_timer.stop()
        self._pending_open_index = None

    def _thumb_open_delay_ms(self) -> int:
        return max(40, QApplication.styleHints().mouseDoubleClickInterval() - 30)

    def _enter_edit_mode(self) -> None:
        if self._preview_mode:
            return
        if self._edit_mode:
            return
        self._cancel_pending_thumb_open()
        self._edit_mode = True
        self._apply_edit_mode_ui()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _leave_edit_mode(self, *, commit: bool) -> None:
        if not self._edit_mode:
            return
        self._cancel_pending_thumb_open()
        self._edit_mode = False
        self._apply_edit_mode_ui()
        if commit:
            self._emit()

    def _apply_edit_mode_ui(self) -> None:
        if self._tail_cell is not None:
            self._tail_cell.setVisible(self._edit_mode)
        for c in self._thumb_cells:
            c.set_edit_overlay_visible(self._edit_mode)
        self._sync_tail_cell_enabled()

    def _on_app_focus_object_changed(self, _obj: QObject | None) -> None:
        """焦点链在一次用户操作里可能连发多帧；延后到下一事件循环再判断是否已离开本控件树。"""
        if not self._edit_mode:
            return
        if QApplication.activeModalWidget() is not None:
            return
        if self._suspend_leave_edit_for_modal:
            return
        self._edit_focus_check_timer.start(0)

    def _deferred_leave_edit_if_focus_outside(self) -> None:
        if not self._edit_mode:
            return
        if QApplication.activeModalWidget() is not None:
            return
        if self._suspend_leave_edit_for_modal:
            return
        fw = QApplication.focusWidget()
        if fw is not None and (fw is self or self.isAncestorOf(fw)):
            return
        self._leave_edit_mode(commit=True)

    def _resume_edit_after_modal(self) -> None:
        """模态框（如选文件）关闭后焦点常落回应用内其它控件，下一 tick 拉回以继续编辑。"""
        if QApplication.activeModalWidget() is not None:
            return
        self._edit_focus_check_timer.stop()
        self._suspend_leave_edit_for_modal = False
        self._edit_mode = True
        self._apply_edit_mode_ui()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_overlay_delete(self, index: int) -> None:
        if not self._edit_mode:
            return
        if 0 <= index < len(self._entries):
            self._entries.pop(index)
            self._selected_index = None
            self._rebuild_strip()
            self._emit()

    def set_can_add(self, enabled: bool) -> None:
        self._can_add = enabled
        self._sync_tail_cell_enabled()

    def set_preview_mode(self, enabled: bool) -> None:
        """预览模式：不可长按进入编辑；详見类文档。"""
        self._preview_mode = bool(enabled)
        if self._preview_mode:
            self._leave_edit_mode(commit=False)

    def set_preview_download_persist(
        self, fn: Callable[[list[dict]], None] | None
    ) -> None:
        """浏览场景下，剧照下载成功后额外调用此回调传入当前条目列表（已含 ``file`` 等），用于写库。"""
        self._preview_download_persist = fn

    def _sync_tail_cell_enabled(self) -> None:
        if self._tail_cell is None:
            return
        self._tail_cell.setEnabled(self._can_add)

    def _thumb_payload_for_entry(self, entry: dict) -> tuple[QPixmap | None, bool]:
        path = _thumb_path_for_entry(entry, self._fanart_path, self._legacy_cover_path)
        return _thumb_pixmap_for_path(path), _entry_has_url(entry)

    def _populate_thumb_cell(
        self, cell: _FanartThumbCell, entry: dict, *, selected: bool
    ) -> None:
        pixmap, has_url = self._thumb_payload_for_entry(entry)
        cell.set_thumb(pixmap, url_but_no_image=has_url)
        cell.set_selected(selected)

    def _refresh_thumb_cell(self, index: int) -> bool:
        if not (0 <= index < len(self._entries)):
            return False
        if not (
            index < len(self._thumb_cells)
            and len(self._thumb_cells) == len(self._entries)
        ):
            return False
        self._populate_thumb_cell(
            self._thumb_cells[index],
            self._entries[index],
            selected=self._selected_index == index,
        )
        return True

    def set_entries(self, entries: list[dict]) -> None:
        self._cancel_pending_thumb_open()
        self._leave_edit_mode(commit=False)
        self._entries = copy.deepcopy(entries)
        for e in self._entries:
            if LOCAL_ABS_KEY in e and not e[LOCAL_ABS_KEY]:
                del e[LOCAL_ABS_KEY]
        if self._selected_index is not None and self._selected_index >= len(
            self._entries
        ):
            self._selected_index = None
        self._rebuild_strip()

    def set_url_list(self, url_list: Sequence[str] | None) -> None:
        """用一组 HTTP(S) 图片地址覆盖当前 Fanart 列表（每项为 url + 空 file，不经由 JSON 解析）。

        若与当前 ``_entries`` 中按顺序的 ``url``（去空白后）完全一致，则保留原有条目（含 ``file`` 等），不重建、不发出 ``fanart_changed``；否则按新列表取代并 ``fanart_changed``。（与 ``set_entries`` 不同：后者用于从模型同步到 UI，不触发信号。）
        """
        self._cancel_pending_thumb_open()
        self._leave_edit_mode(commit=False)
        new_urls: list[str] = []
        if url_list:
            for u in url_list:
                s = (u or "").strip() if isinstance(u, str) else str(u).strip()
                if s:
                    new_urls.append(s)
        old_urls = [(e.get("url") or "").strip() for e in self._entries]
        if new_urls == old_urls:
            return
        if not new_urls:
            self._entries = []
            self._selected_index = None
            self._rebuild_strip()
            self._emit()
            return
        out: list[dict] = []
        for s in new_urls:
            out.append({"url": s, "file": ""})
        self._entries = out
        if self._selected_index is not None and self._selected_index >= len(
            self._entries
        ):
            self._selected_index = None
        self._rebuild_strip()
        self._emit()

    def entries(self) -> list[dict]:
        return copy.deepcopy(self._entries)

    def _rebuild_strip(self) -> None:
        while self._hbox.count():
            item = self._hbox.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._thumb_cells.clear()
        for i, entry in enumerate(self._entries):
            cell = _FanartThumbCell()
            self._populate_thumb_cell(cell, entry, selected=self._selected_index == i)
            cell.clicked.connect(lambda idx=i: self._on_thumb_cell_clicked(idx))
            cell.doubleClicked.connect(lambda idx=i: self._on_thumb_cell_double(idx))
            cell.longPressed.connect(self._enter_edit_mode)
            cell.closeRequested.connect(lambda idx=i: self._on_overlay_delete(idx))
            self._hbox.addWidget(cell)
            self._thumb_cells.append(cell)
        tail = _FanartThumbCell()
        tail.set_as_add_placeholder(True)
        tail.setToolTip("点击添加本地图片")
        tail.clicked.connect(self._on_tail_placeholder_clicked)
        tail.longPressed.connect(self._enter_edit_mode)
        self._hbox.addWidget(tail)
        self._tail_cell = tail
        self._apply_edit_mode_ui()

    def _on_tail_placeholder_clicked(self) -> None:
        if not self._edit_mode:
            return
        self._selected_index = None
        for c in self._thumb_cells:
            c.set_selected(False)
        self._on_add()

    def _emit(self) -> None:
        self.fanart_changed.emit(copy.deepcopy(self._entries))

    def run_fanart_download(
        self,
        dialog: FanartEditDialog | None,
        slot_index: int,
        url: str,
    ) -> None:
        bridge = _FanartDownloadBridge(self, slot_index, dialog)
        worker = Worker(lambda u=url: _fanart_download_task(u))
        worker.signals.finished.connect(
            bridge.on_fanart_download_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        QThreadPool.globalInstance().start(worker)

    def _persist_fanart_slot_after_download(self, index: int, fields: dict) -> None:
        """下载完成后立即写回条带数据并通知模型，避免仅关对话框导致 file 丢失。"""
        if not (0 <= index < len(self._entries)):
            return
        self._entries[index].update(fields)
        if LOCAL_ABS_KEY in self._entries[index]:
            del self._entries[index][LOCAL_ABS_KEY]
        if not self._refresh_thumb_cell(index):
            self._rebuild_strip()
        self._emit()
        if self._preview_mode and self._preview_download_persist is not None:
            self._preview_download_persist(copy.deepcopy(self._entries))

    def _on_cell_select_only(self, index: int) -> None:
        self._selected_index = index
        for i, c in enumerate(self._thumb_cells):
            c.set_selected(i == index)

    def _on_thumb_cell_clicked(self, index: int) -> None:
        if self._edit_mode:
            self._on_cell_select_only(index)
            return
        self._pending_open_index = index
        self._click_open_timer.start(self._thumb_open_delay_ms())

    def _on_thumb_cell_double(self, index: int) -> None:
        if self._edit_mode:
            return
        self._cancel_pending_thumb_open()
        self._open_fanart_edit_dialog(index)

    def _on_delayed_thumb_open(self) -> None:
        idx = self._pending_open_index
        self._pending_open_index = None
        if idx is None or self._edit_mode:
            return
        if not (0 <= idx < len(self._entries)):
            return
        self._open_fanart_edit_dialog(idx)

    def _open_fanart_edit_dialog(self, index: int) -> None:
        if self._edit_mode or not (0 <= index < len(self._entries)):
            return
        self._on_cell_select_only(index)
        editing = copy.deepcopy(self._entries)
        dlg = FanartEditDialog(
            editing,
            index,
            self._fanart_path,
            legacy_cover_root=self._legacy_cover_path,
            parent=self,
            auto_download_if_missing=True,
            url_read_only=self._preview_mode,
        )
        rc = dlg.exec()
        if rc == QDialog.DialogCode.Accepted:
            self._entries = dlg.result_entries()
            ci = dlg.current_index()
            if self._entries:
                self._selected_index = max(0, min(ci, len(self._entries) - 1))
            else:
                self._selected_index = None
            self._rebuild_strip()
            self._emit()

    def _on_add(self) -> None:
        if not self._can_add:
            QMessageBox.information(self, "Fanart", "请先填写番号后再添加。")
            return
        keep_edit = self._edit_mode
        if keep_edit:
            self._suspend_leave_edit_for_modal = True
            self._edit_focus_check_timer.stop()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片 (*.jpg *.jpeg *.png *.webp);;所有文件 (*.*)",
        )
        if path:
            self._entries.append({"url": "", "file": "", LOCAL_ABS_KEY: path})
            self._selected_index = len(self._entries) - 1
            self._rebuild_strip()
            self._emit()
        if keep_edit:
            QTimer.singleShot(0, self._resume_edit_after_modal)


class _FanartDownloadBridge(QObject):
    """下载完成后在主线程回调；挂到 FanartStripWidget 上，避免模态对话框内嵌闭包导致投递/卡死。"""

    def __init__(
        self,
        strip: FanartStripWidget,
        slot_index: int,
        dialog: FanartEditDialog | None,
    ) -> None:
        super().__init__(strip)
        self._strip = strip
        self._slot_index = slot_index
        self._dialog = dialog

    @Slot(object)
    def on_fanart_download_finished(self, result: object) -> None:
        dlg = self._dialog
        try:
            if dlg is not None:
                dlg._download_busy = False
                dlg._btn_download.setEnabled(True)
                dlg._btn_download.setText(dlg._btn_download_default_text)
            if result is None:
                parent = (
                    dlg
                    if dlg is not None
                    else (QApplication.activeModalWidget() or self._strip)
                )
                QMessageBox.warning(parent, "Fanart", "下载异常")
            else:
                status, msg, dest_name, final_url = result
                if status == "err":
                    parent = (
                        dlg
                        if dlg is not None
                        else (QApplication.activeModalWidget() or self._strip)
                    )
                    QMessageBox.warning(parent, "Fanart", f"下载失败：{msg}")
                elif dest_name is not None and final_url:
                    patch = {"file": dest_name, "url": final_url}
                    self._strip._persist_fanart_slot_after_download(
                        self._slot_index, patch
                    )
                    if dlg is not None and 0 <= self._slot_index < len(dlg._entries):
                        e = dlg._entries[self._slot_index]
                        e["file"] = dest_name
                        e["url"] = final_url
                        if LOCAL_ABS_KEY in e:
                            del e[LOCAL_ABS_KEY]
                        dlg._refresh_view()
        finally:
            self._dialog = None
            self.deleteLater()
