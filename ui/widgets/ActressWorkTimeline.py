# 女优作品时间轴：按发行日横向排布，可缩放、可滚动。
# 滚轮以指针处为锚缩放（ppd 可至极小），刻度密度自适应；Ctrl+滚轮上下为横向平移；Shift+滚轮纵向滚动；中键拖拽平移。
# 轴在作品与默认窗合并后向过去/未来各延伸若干年，可沿轴持续平移；视口过窄时再对称加天数以撑满宽度。
# 首次进入将默认窗 2016–2026 按视口宽度缩放到大致可见，并左对齐从 2016 年起；仅未知日期时用合成区间。
# 标尺下为日期轴线（横线），作品以菱形锚在轴线上，悬停弹出封面卡片。

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtCore import QPoint, QPointF, QTimer, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QResizeEvent,
    QShowEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from darkeye_ui.components import Label
from darkeye_ui.design.theme_context import resolve_theme_manager
from darkeye_ui.design.tokens import LIGHT_TOKENS, ThemeTokens
from ui.navigation.router import Router
from ui.widgets.image.CoverCard import CoverCard

if TYPE_CHECKING:
    from darkeye_ui.design.theme_manager import ThemeManager

RULER_HEIGHT = 28
# 初始像素/天（首次 set_work_rows 后会按默认窗适配视口重算）
ZOOM_SLIDER_SCALE = 1000
ZOOM_SLIDER_DEFAULT = 32000
PPD_MIN = 0.001
PPD_MAX = 300.0
UNKNOWN_MARGIN = 16
UNKNOWN_SECTION_MIN_WIDTH = 120
# 主刻度、标签目标最小间距（像素），随 ppd 换算为天步长
TICK_TARGET_MAJOR_PX = 52
TICK_TARGET_LABEL_PX = 76
# 不低于此像素/天时标尺标签用完整 YYYY-MM-DD（由 label_step 控制密度避免重叠）
PPD_LABEL_FULL_DATE = 5.0
# 时间轴内容宽度至少覆盖视口 + 余量，避免缩成一条
AXIS_FILL_VIEWPORT_MARGIN = 64

# 菱形命中区（正方形）、同日复数作品沿垂直方向错开（中心距）
MARKER_HIT = 20
DIAMOND_STRIDE = 16
AXIS_TICK_HALF = 5
# 标尺绘制视口外扩（像素），避免滚轮缩放时刻度突然消失
RULER_CLIP_PAD_PX = 200
POPUP_HIDE_MS = 280
# 首日刻度在 x=0 时菱形会裁切，与时间轴同步右移
TRACK_PAD_X = MARKER_HIT // 2 + 4
# 时间轴与作品日期取并集：至少覆盖 [start, end] 整日
TIMELINE_DEFAULT_START = date(2016, 1, 1)
TIMELINE_DEFAULT_END = date(2026, 12, 31)
# 默认窗包含的起止日（含首尾）
TIMELINE_DEFAULT_SPAN_DAYS = (TIMELINE_DEFAULT_END - TIMELINE_DEFAULT_START).days + 1
# 首次把默认窗塞进视口时的左右留白（像素）
INITIAL_DEFAULT_WINDOW_FIT_MARGIN_PX = 32
# 合并作品区间与 2016–2026 后，核心区两侧各留若干天
TIMELINE_MERGE_SIDE_PAD_DAYS = 120
# 核心区再向过去/未来各延伸约若干年，形成可大幅平移的时间轴（有限但足够宽）
TIMELINE_INFINITE_EXTRA_YEARS = 90


@dataclass(slots=True)
class _TimelineBuckets:
    by_day: dict[date, list[tuple[Any, ...]]]
    unknown_list: list[tuple[Any, ...]]


@dataclass(slots=True)
class _TimelineSpan:
    date_min: Optional[date]
    num_days: int
    has_unknown: bool
    unknown_section_w: int
    unknown_x0: float


@dataclass(slots=True)
class _LayoutGeometry:
    date_axis_y: int
    content_width: int
    content_height: int


def _pick_tick_step_days(ppd: float, target_px: float) -> int:
    """按像素间距目标换算刻度步长（天），并取易读档位。"""
    ppd = max(float(ppd), 1e-9)
    raw = max(1, int(math.ceil(target_px / ppd)))
    nice = (
        1,
        2,
        3,
        5,
        7,
        10,
        14,
        21,
        30,
        60,
        90,
        120,
        180,
        365,
        730,
        1095,
        1825,
    )
    for n in nice:
        if n >= raw:
            return n
    y = int(math.ceil(raw / 365) * 365)
    return max(y, raw)


def _parse_release(raw: Any) -> Optional[date]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _tag_color(tag_id: Any) -> str:
    match tag_id:
        case 1:
            return "#80B0F8"
        case 2:
            return "#F88441"
        case 3:
            return "#FDEB48"
        case _:
            return "#00000000"


def _draw_ruler_label_centered_on_tick(
    painter: QPainter, tick_x: int, text: str, baseline_y: int
) -> None:
    """以 tick_x 为水平中心绘制标尺日期文字（基线为 baseline_y）。"""
    fm = painter.fontMetrics()
    tw = fm.horizontalAdvance(text)
    tx = int(round(float(tick_x) - float(tw) / 2.0))
    painter.drawText(tx, baseline_y, text)


class _HoverCardPopup(QWidget):
    """顶层浮动窗口承载 CoverCard（半幅封面样式）；鼠标可移入以点击卡片。"""

    def __init__(self, timeline: "ActressWorkTimeline") -> None:
        # parent必须为 None：带父级的 ToolTip 在部分平台上 move() 会按父坐标解释，
        # 与 mapToGlobal 不一致导致严重偏移。由 ActressWorkTimeline 持有引用即可。
        super().__init__(
            None,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self._timeline = timeline
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._timeline._cancel_popup_hide()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._timeline._schedule_popup_hide()


class _TimelineWorkMarker(QWidget):
    """时间轴上的作品锚点（菱形，中心落在竖向刻度线与横向日期轴交点上）。"""

    def __init__(
        self,
        timeline: "ActressWorkTimeline",
        row: tuple[Any, ...],
        fill_color: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._timeline = timeline
        self._row = row
        self._fill = fill_color
        self._mid_pan = False
        # 中键平移用全局坐标；子控件本地坐标会随滚动突变，导致抖动。
        self._mid_last_global = QPointF()
        self.setFixedSize(MARKER_HIT, MARKER_HIT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        t = self._timeline._tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        c = QColor(self._fill)
        if not c.isValid() or c.alpha() == 0:
            c = QColor(t.color_primary)
        p.setBrush(c)
        p.setPen(QPen(QColor(t.color_border), 1))
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        r = min(self.width(), self.height()) / 2.0 - 2.0
        path = QPainterPath()
        path.moveTo(cx, cy - r)
        path.lineTo(cx + r, cy)
        path.lineTo(cx, cy + r)
        path.lineTo(cx - r, cy)
        path.closeSubpath()
        p.drawPath(path)
        p.end()

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._timeline._on_marker_enter(self, self._row)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._timeline._schedule_popup_hide()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._timeline.horizontal_scroll_from_wheel(event.angleDelta().y())
            event.accept()
            return
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._timeline.vertical_scroll_from_wheel(event.angleDelta().y())
            event.accept()
            return
        parent = self.parentWidget()
        ax = float(self.mapTo(parent, event.position()).x()) if parent else 0.0
        self._timeline.bump_zoom_from_wheel(event.angleDelta().y(), anchor_canvas_x=ax)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._timeline.middle_pan_began()
            self._mid_pan = True
            self._mid_last_global = QPointF(event.globalPosition())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.grabMouse()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if getattr(self, "_mid_pan", False):
            cur_g = QPointF(event.globalPosition())
            d = cur_g - self._mid_last_global
            self._mid_last_global = cur_g
            self._timeline.pan_scroll_by(-d.x(), -d.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._mid_pan = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.releaseMouse()
            self._timeline.middle_pan_ended()
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._timeline._open_work_detail_from_row(self._row)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class _TimelineScrollArea(QScrollArea):
    """横向/纵向滚动区；滚轮默认交给子控件（画布/标记）处理缩放。"""

    def __init__(self, timeline: "ActressWorkTimeline", parent: QWidget | None = None):
        super().__init__(parent)
        self._timeline = timeline


class TimelineCanvas(QWidget):
    """绘制标尺与日期轴线；作品以子控件菱形呈现。"""

    def __init__(
        self,
        theme_manager: Optional["ThemeManager"] = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._tm = resolve_theme_manager(theme_manager, "TimelineCanvas")
        if self._tm is not None:
            self._tm.themeChanged.connect(self.update)
        self._ppd: float = ZOOM_SLIDER_DEFAULT / ZOOM_SLIDER_SCALE
        self._date_min: Optional[date] = None
        self._num_days = 0
        self._has_unknown = False
        self._unknown_x0 = 0
        self._unknown_section_w = 0
        self._date_axis_y = RULER_HEIGHT + 24
        self._mid_pan = False
        self._mid_last_global = QPointF()
        self._scroll_area_ref: Optional[QScrollArea] = None
        self._timeline_ref: Optional["ActressWorkTimeline"] = None

    def _tokens(self) -> ThemeTokens:
        if self._tm is not None:
            return self._tm.tokens()
        return LIGHT_TOKENS

    def configure_ruler(
        self,
        *,
        ppd: float,
        date_min: Optional[date],
        num_days: int,
        has_unknown: bool,
        unknown_x0: int,
        unknown_section_w: int,
        date_axis_y: int,
        content_width: int,
        content_height: int,
    ) -> None:
        self._ppd = float(ppd)
        self._date_min = date_min
        self._num_days = num_days
        self._has_unknown = has_unknown
        self._unknown_x0 = unknown_x0
        self._unknown_section_w = unknown_section_w
        self._date_axis_y = date_axis_y
        self.setFixedSize(max(content_width, 1), max(content_height, 1))
        self.update()

    def _visible_content_x_span(self) -> tuple[float, float] | None:
        """视口在画布坐标下的水平范围（含外扩），无滚动条引用时返回 None 表示全宽绘制。"""
        sa = self._scroll_area_ref
        if sa is None:
            return None
        hbar = sa.horizontalScrollBar()
        x0 = float(hbar.value())
        x1 = x0 + float(max(1, sa.viewport().width()))
        pad = float(RULER_CLIP_PAD_PX)
        return (x0 - pad, x1 + pad)

    def _day_index_bounds_for_span(self, x_lo: float, x_hi: float) -> tuple[int, int]:
        ppd = max(self._ppd, 1e-9)
        i0 = int(math.floor((x_lo - TRACK_PAD_X) / ppd)) - 1
        i1 = int(math.ceil((x_hi - TRACK_PAD_X) / ppd)) + 1
        return max(0, i0), min(self._num_days, i1)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        t = self._tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        painter.fillRect(self.rect(), QColor(t.color_bg_page))

        pen_grid = QPen(QColor(t.color_border))
        pen_grid.setWidth(1)
        painter.setPen(pen_grid)
        painter.drawLine(0, RULER_HEIGHT - 1, self.width(), RULER_HEIGHT - 1)

        axis_y = self._date_axis_y
        pen_axis = QPen(QColor(t.color_border))
        pen_axis.setWidth(2)
        painter.setPen(pen_axis)
        painter.drawLine(0, axis_y, self.width(), axis_y)

        pen_tick = QPen(QColor(t.color_border))
        pen_tick.setWidth(1)
        painter.setPen(pen_tick)

        if self._num_days > 0 and self._date_min is not None:
            major_step = _pick_tick_step_days(self._ppd, TICK_TARGET_MAJOR_PX)
            label_step = max(
                major_step,
                _pick_tick_step_days(self._ppd, TICK_TARGET_LABEL_PX),
            )
            span_days = max(self._num_days, 1)
            if self._ppd >= PPD_LABEL_FULL_DATE:
                label_fmt = "%Y-%m-%d"
            elif span_days > 800:
                label_fmt = "%Y-%m"
            else:
                label_fmt = "%m-%d"

            span = self._visible_content_x_span()
            if span is None:
                i_lo, i_hi = 0, self._num_days
            else:
                i_lo, i_hi = self._day_index_bounds_for_span(span[0], span[1])

            first_major = ((i_lo + major_step - 1) // major_step) * major_step
            if first_major < 0:
                first_major = 0
            for i in range(first_major, i_hi + 1, major_step):
                if i > self._num_days:
                    break
                x = int(TRACK_PAD_X + i * self._ppd)
                painter.drawLine(
                    x,
                    axis_y - AXIS_TICK_HALF,
                    x,
                    axis_y + AXIS_TICK_HALF,
                )
            last = self._num_days
            if last > 0 and last % major_step != 0 and i_lo <= last <= i_hi:
                x = int(TRACK_PAD_X + last * self._ppd)
                painter.drawLine(
                    x,
                    axis_y - AXIS_TICK_HALF,
                    x,
                    axis_y + AXIS_TICK_HALF,
                )

            painter.setPen(QColor(t.color_text))
            font = QFont()
            font.setPixelSize(10)
            painter.setFont(font)
            first_label = ((i_lo + label_step - 1) // label_step) * label_step
            if first_label < 0:
                first_label = 0
            label_baseline = RULER_HEIGHT - 6
            for i in range(first_label, i_hi + 1, label_step):
                if i > self._num_days:
                    break
                x = int(TRACK_PAD_X + i * self._ppd)
                d = self._date_min + timedelta(days=i)
                _draw_ruler_label_centered_on_tick(
                    painter, x, d.strftime(label_fmt), label_baseline
                )
            if last > 0 and last % label_step != 0 and i_lo <= last <= i_hi:
                x = int(TRACK_PAD_X + last * self._ppd)
                d = self._date_min + timedelta(days=last)
                _draw_ruler_label_centered_on_tick(
                    painter, x, d.strftime(label_fmt), label_baseline
                )
        elif self._has_unknown:
            painter.setPen(QColor(t.color_text))
            font = QFont()
            font.setPixelSize(10)
            painter.setFont(font)
            painter.drawText(TRACK_PAD_X + 8, RULER_HEIGHT - 6, "未标注发行日")

        if self._has_unknown and self._num_days > 0:
            sep_x = int(self._unknown_x0)
            painter.setPen(pen_grid)
            painter.drawLine(sep_x, 0, sep_x, self.height())

        painter.end()

    def wheelEvent(self, event: QWheelEvent) -> None:
        tref = self._timeline_ref
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if tref is not None:
                tref.horizontal_scroll_from_wheel(event.angleDelta().y())
            event.accept()
            return
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if tref is not None:
                tref.vertical_scroll_from_wheel(event.angleDelta().y())
            event.accept()
            return
        if tref is not None:
            tref.bump_zoom_from_wheel(
                event.angleDelta().y(),
                anchor_canvas_x=float(event.position().x()),
            )
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            tref = self._timeline_ref
            if tref is not None:
                tref.middle_pan_began()
            self._mid_pan = True
            self._mid_last_global = QPointF(event.globalPosition())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.grabMouse()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._mid_pan:
            cur_g = QPointF(event.globalPosition())
            d = cur_g - self._mid_last_global
            self._mid_last_global = cur_g
            tref = self._timeline_ref
            if tref is not None:
                tref.pan_scroll_by(-d.x(), -d.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._mid_pan = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.releaseMouse()
            tref = self._timeline_ref
            if tref is not None:
                tref.middle_pan_ended()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ActressWorkTimeline(QWidget):
    """女优作品时间轴：滚动区 + 轴线与菱形标记；悬停弹出卡片（滚轮缩放）。"""

    def __init__(
        self,
        theme_manager: Optional["ThemeManager"] = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._tm = resolve_theme_manager(theme_manager, "ActressWorkTimeline")
        self._rows: list[tuple[Any, ...]] = []
        self._marker_widgets: list[_TimelineWorkMarker] = []
        self._ppd: float = ZOOM_SLIDER_DEFAULT / ZOOM_SLIDER_SCALE
        self._layout_num_days = 0
        self._layout_date_min: Optional[date] = None
        self._layout_content_width: int = 0
        self._last_fill_viewport_w = 0
        self._pending_timeline_scroll_to_default = False
        self._initial_scroll_apply_attempts = 0
        self._initial_scroll_viewport_attempts = 0
        self._initial_timeline_center_applied = False
        self._initial_default_window_ppd_fit_done = False
        self._pan_remainder_h = 0.0
        self._pan_remainder_v = 0.0
        self._middle_pan_active = False
        self._rebuild_deferred_during_pan = False
        self._scroll_hide_popup_connected = True
        if self._tm is not None:
            self._tm.themeChanged.connect(self._on_theme_changed)

        self._hover_popup = _HoverCardPopup(self)
        self._popup_layout = self._hover_popup.content_layout

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        self._empty_label = Label("暂无作品")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._empty_label)

        self._scroll = _TimelineScrollArea(self)
        self._scroll.setWidgetResizable(False)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._canvas = TimelineCanvas(theme_manager=self._tm)
        self._scroll.setWidget(self._canvas)
        self._canvas._timeline_ref = self
        self._canvas._scroll_area_ref = self._scroll
        root.addWidget(self._scroll, 1)

        self._scroll.horizontalScrollBar().rangeChanged.connect(
            self._on_horizontal_range_changed_maybe_initial_scroll
        )
        self._scroll.horizontalScrollBar().valueChanged.connect(
            self._schedule_hide_popup_from_scroll
        )
        self._scroll.verticalScrollBar().valueChanged.connect(
            self._schedule_hide_popup_from_scroll
        )

        self._hide_popup_timer = QTimer(self)
        self._hide_popup_timer.setSingleShot(True)
        self._hide_popup_timer.timeout.connect(self._hide_popup_immediate)

        self._scroll_popup_hide_timer = QTimer(self)
        self._scroll_popup_hide_timer.setSingleShot(True)
        self._scroll_popup_hide_timer.timeout.connect(self._hide_popup_immediate)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._apply_visibility()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._schedule_initial_timeline_scroll_if_needed()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if not self._rows or not self._scroll.isVisible():
            return
        w = self._scroll.viewport().width()
        if w < 100:
            self._schedule_initial_timeline_scroll_if_needed()
            return
        prev = self._last_fill_viewport_w
        should_rebuild = prev == 0 or abs(w - prev) > 30
        if self._middle_pan_active:
            if should_rebuild:
                self._rebuild_deferred_during_pan = True
            return
        if should_rebuild:
            self._last_fill_viewport_w = w
            QTimer.singleShot(0, self._rebuild_layout)
        self._schedule_initial_timeline_scroll_if_needed()

    def _viewport_target_fill_width(self) -> int:
        vp = self._scroll.viewport().width()
        if vp >= 100:
            return int(vp + AXIS_FILL_VIEWPORT_MARGIN)
        outer = self.width()
        if outer > 200:
            return int(outer - 24 + AXIS_FILL_VIEWPORT_MARGIN)
        return int(1280 + AXIS_FILL_VIEWPORT_MARGIN)

    def _ensure_axis_covers_viewport(
        self,
        date_min: date,
        num_days: int,
        ppd: float,
        has_unknown: bool,
        unknown_section_w: int,
    ) -> tuple[date, int]:
        """画宽窄于视口时向左右对称加天数以撑满；resize 后由调用方按 date_min 变化补偿滚动。"""
        target_w = self._viewport_target_fill_width()
        cur_min, cur_n = date_min, num_days
        for _ in range(8):
            if has_unknown:
                unk_x0 = TRACK_PAD_X + cur_n * ppd + UNKNOWN_MARGIN
                total_w = unk_x0 + unknown_section_w + UNKNOWN_MARGIN + MARKER_HIT // 2
            else:
                total_w = TRACK_PAD_X + cur_n * ppd + MARKER_HIT // 2 + UNKNOWN_MARGIN
                total_w = max(total_w, 200.0)
            if total_w >= target_w:
                return cur_min, cur_n
            shortfall = float(target_w - total_w)
            extra_days = max(1, int(math.ceil(shortfall / max(ppd, 1e-9))))
            left = extra_days // 2
            right = extra_days - left
            cur_min = cur_min - timedelta(days=left)
            cur_n = cur_n + left + right
        return cur_min, cur_n

    def _tokens(self) -> ThemeTokens:
        if self._tm is not None:
            return self._tm.tokens()
        return LIGHT_TOKENS

    def _on_theme_changed(self) -> None:
        for m in self._marker_widgets:
            m.update()
        self._canvas.update()

    def _apply_ppd_with_anchor(
        self,
        new_ppd: float,
        anchor_canvas_x: float,
    ) -> None:
        new_ppd = max(PPD_MIN, min(PPD_MAX, float(new_ppd)))
        old_ppd = self._ppd
        hbar = self._scroll.horizontalScrollBar()
        old_scroll = hbar.value()
        vpx = float(anchor_canvas_x) - float(old_scroll)
        old_canvas_w = float(max(1, self._canvas.width()))
        nd = self._layout_num_days

        self._ppd = new_ppd

        self._hide_popup_immediate()
        self._rebuild_layout()

        new_canvas_w = float(max(1, self._canvas.width()))
        dated_end_old = TRACK_PAD_X + nd * old_ppd
        if nd > 0 and anchor_canvas_x <= dated_end_old + 1.0:
            t = (anchor_canvas_x - TRACK_PAD_X) / max(old_ppd, 1e-9)
            new_anchor_x = TRACK_PAD_X + t * new_ppd
        else:
            new_anchor_x = (anchor_canvas_x / old_canvas_w) * new_canvas_w

        new_scroll = int(round(new_anchor_x - vpx))
        hbar.setValue(max(hbar.minimum(), min(hbar.maximum(), new_scroll)))

    def bump_zoom_from_wheel(
        self, delta_y: int, anchor_canvas_x: Optional[float] = None
    ) -> None:
        self._initial_timeline_center_applied = True
        self._pending_timeline_scroll_to_default = False
        if delta_y == 0:
            return
        steps = delta_y / 120.0
        factor = 1.1**steps
        new_ppd = max(PPD_MIN, min(PPD_MAX, self._ppd * factor))
        if anchor_canvas_x is None:
            hbar = self._scroll.horizontalScrollBar()
            vw = max(1, self._scroll.viewport().width())
            anchor_canvas_x = float(hbar.value() + vw / 2.0)
        self._apply_ppd_with_anchor(new_ppd, anchor_canvas_x)

    def pan_scroll_by(self, dx: float, dy: float) -> None:
        if dx != 0.0 or dy != 0.0:
            self._initial_timeline_center_applied = True
            self._pending_timeline_scroll_to_default = False
        self._pan_remainder_h += float(dx)
        self._pan_remainder_v += float(dy)
        step_h = int(self._pan_remainder_h)
        step_v = int(self._pan_remainder_v)
        if step_h:
            self._pan_remainder_h -= step_h
            hbar = self._scroll.horizontalScrollBar()
            hbar.setValue(hbar.value() + step_h)
        if step_v:
            self._pan_remainder_v -= step_v
            vbar = self._scroll.verticalScrollBar()
            vbar.setValue(vbar.value() + step_v)

    def vertical_scroll_from_wheel(self, delta_y: int) -> None:
        self._initial_timeline_center_applied = True
        self._pending_timeline_scroll_to_default = False
        step = int(delta_y / 120.0 * 40)
        vbar = self._scroll.verticalScrollBar()
        vbar.setValue(vbar.value() - step)

    def horizontal_scroll_from_wheel(self, delta_y: int) -> None:
        self._initial_timeline_center_applied = True
        self._pending_timeline_scroll_to_default = False
        step = int(delta_y / 120.0 * 40)
        hbar = self._scroll.horizontalScrollBar()
        hbar.setValue(hbar.value() - step)

    def set_work_rows(self, rows: list[tuple[Any, ...]] | None) -> None:
        self._rows = list(rows or [])
        self._pending_timeline_scroll_to_default = bool(self._rows)
        self._initial_timeline_center_applied = not bool(self._rows)
        self._initial_default_window_ppd_fit_done = not bool(self._rows)
        self._initial_scroll_apply_attempts = 0
        self._initial_scroll_viewport_attempts = 0
        self._hide_popup_immediate()
        self._apply_visibility()
        self._rebuild_layout()

    def _apply_visibility(self) -> None:
        has = bool(self._rows)
        self._empty_label.setVisible(not has)
        self._scroll.setVisible(has)

    def _clear_markers(self) -> None:
        for w in self._marker_widgets:
            w.deleteLater()
        self._marker_widgets.clear()

    def _cancel_popup_hide(self) -> None:
        self._hide_popup_timer.stop()

    def _clear_hover_popup_widgets(self) -> None:
        while self._popup_layout.count():
            item = self._popup_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _schedule_popup_hide(self) -> None:
        self._hide_popup_timer.start(POPUP_HIDE_MS)

    def _schedule_hide_popup_from_scroll(self) -> None:
        """滚动条连续拖动时防抖，避免中键平移每一帧都关弹窗导致闪烁。"""
        if self._middle_pan_active:
            return
        self._scroll_popup_hide_timer.stop()
        self._scroll_popup_hide_timer.start(140)

    def _disconnect_scroll_popup_hide(self) -> None:
        if not self._scroll_hide_popup_connected:
            return
        hbar = self._scroll.horizontalScrollBar()
        vbar = self._scroll.verticalScrollBar()
        hbar.valueChanged.disconnect(self._schedule_hide_popup_from_scroll)
        vbar.valueChanged.disconnect(self._schedule_hide_popup_from_scroll)
        self._scroll_hide_popup_connected = False

    def _connect_scroll_popup_hide(self) -> None:
        if self._scroll_hide_popup_connected:
            return
        hbar = self._scroll.horizontalScrollBar()
        vbar = self._scroll.verticalScrollBar()
        hbar.valueChanged.connect(self._schedule_hide_popup_from_scroll)
        vbar.valueChanged.connect(self._schedule_hide_popup_from_scroll)
        self._scroll_hide_popup_connected = True

    def middle_pan_began(self) -> None:
        self._middle_pan_active = True
        self._pan_remainder_h = 0.0
        self._pan_remainder_v = 0.0
        self._scroll_popup_hide_timer.stop()
        self._hide_popup_immediate()
        self._disconnect_scroll_popup_hide()

    def middle_pan_ended(self) -> None:
        self._middle_pan_active = False
        self._connect_scroll_popup_hide()
        if self._pending_timeline_scroll_to_default:
            QTimer.singleShot(0, self._try_apply_initial_timeline_scroll)
        if self._rebuild_deferred_during_pan and self._rows:
            self._rebuild_deferred_during_pan = False
            w = self._scroll.viewport().width()
            if w >= 100:
                self._last_fill_viewport_w = w
                QTimer.singleShot(0, self._rebuild_layout)

    def _hide_popup_immediate(self) -> None:
        self._hide_popup_timer.stop()
        self._scroll_popup_hide_timer.stop()
        self._hover_popup.hide()
        self._clear_hover_popup_widgets()

    def _open_work_detail_from_row(self, row: tuple[Any, ...]) -> None:
        """左键菱形：跳转书架作品详情（与封面卡片左键一致）。"""
        if len(row) < 5:
            return
        wid = row[4]
        if wid is None:
            return
        try:
            wid_int = int(wid)
        except (TypeError, ValueError):
            return
        QTimer.singleShot(
            0, lambda w=wid_int: Router.instance().push("shelf", work_id=w)
        )

    def _on_marker_enter(
        self, marker: _TimelineWorkMarker, row: tuple[Any, ...]
    ) -> None:
        if self._middle_pan_active:
            return
        self._cancel_popup_hide()
        self._show_popup_for_row(row, marker)

    def _show_popup_for_row(self, row: tuple[Any, ...], anchor: QWidget) -> None:
        self._clear_hover_popup_widgets()
        if len(row) < 6:
            return
        serial_number, title, cover_path, tag_id, work_id, standard = row[:6]
        card = CoverCard(
            title or "",
            cover_path,
            serial_number,
            work_id,
            bool(standard),
            color=_tag_color(tag_id),
            parent=self._hover_popup,
        )
        self._popup_layout.addWidget(card)
        self._popup_layout.activate()
        self._hover_popup.adjustSize()
        hint = self._hover_popup.sizeHint()
        if hint.isValid() and hint.width() > 0 and hint.height() > 0:
            self._hover_popup.resize(hint)
        self._position_hover_popup_from_marker(anchor)
        self._hover_popup.show()
        self._position_hover_popup_from_marker(anchor)
        QTimer.singleShot(0, lambda a=anchor: self._position_hover_popup_from_marker(a))

    def _position_hover_popup_from_marker(self, anchor: QWidget | None) -> None:
        """水平以菱形几何中心对齐卡片水平中心；竖直紧挨菱形底边下方。"""
        if anchor is None:
            return
        try:
            if not anchor.isVisible():
                return
        except RuntimeError:
            return
        self._popup_layout.activate()
        self._hover_popup.adjustSize()
        hint = self._hover_popup.sizeHint()
        if hint.isValid() and hint.width() > 0 and hint.height() > 0:
            self._hover_popup.resize(hint)

        r = anchor.rect()
        center_g = anchor.mapToGlobal(r.center())
        # PySide6 的 QRect 无 bottomCenter()，底边中点用手动构造。
        bottom_g = anchor.mapToGlobal(QPoint(r.center().x(), r.bottom()))
        pw = self._hover_popup.width()
        ph = self._hover_popup.height()
        margin_below = 8
        edge = 4
        x = int(round(float(center_g.x()) - float(pw) / 2.0))
        y = int(round(float(bottom_g.y()) + float(margin_below)))

        screen = QApplication.screenAt(center_g)
        if screen is None:
            screen = anchor.screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            x = max(avail.left() + edge, min(x, avail.right() - pw - edge))
            y = max(avail.top() + edge, min(y, avail.bottom() - ph - edge))

        self._hover_popup.move(x, y)

    def _rebuild_layout(self) -> None:
        prev_dm = self._layout_date_min
        prev_scroll = self._scroll.horizontalScrollBar().value()
        ppd_for_scroll_sync = self._ppd

        self._clear_markers()
        if not self._rows:
            self._layout_num_days = 0
            self._layout_date_min = None
            self._layout_content_width = 0
            self._pending_timeline_scroll_to_default = False
            self._initial_timeline_center_applied = True
            return

        buckets = self._bucket_rows(self._rows)
        span = self._build_timeline_span(buckets)
        if span.date_min is None:
            self._pending_timeline_scroll_to_default = False
            self._initial_timeline_center_applied = True
        date_axis_y = self._compute_axis_y(buckets)
        placements = self._build_marker_placements(
            buckets=buckets,
            span=span,
            date_axis_y=date_axis_y,
        )
        geometry = self._compute_geometry(
            placements=placements,
            span=span,
            date_axis_y=date_axis_y,
        )

        for row, x, y in placements:
            marker = _TimelineWorkMarker(
                self,
                row,
                _tag_color(row[3]),
                parent=self._canvas,
            )
            marker.move(x, y)
            marker.show()
            self._marker_widgets.append(marker)

        self._layout_num_days = span.num_days
        self._layout_date_min = span.date_min
        self._layout_content_width = int(max(1, geometry.content_width))

        self._canvas.configure_ruler(
            ppd=self._ppd,
            date_min=span.date_min,
            num_days=span.num_days,
            has_unknown=span.has_unknown,
            unknown_x0=int(round(span.unknown_x0)),
            unknown_section_w=span.unknown_section_w if span.has_unknown else 0,
            date_axis_y=date_axis_y,
            content_width=geometry.content_width,
            content_height=geometry.content_height,
        )

        hbar = self._scroll.horizontalScrollBar()
        if (
            not self._pending_timeline_scroll_to_default
            and prev_dm is not None
            and span.date_min is not None
            and prev_dm != span.date_min
        ):
            delta_days = (prev_dm - span.date_min).days
            if delta_days != 0:
                adj = int(round(delta_days * ppd_for_scroll_sync))
                hbar.setValue(
                    max(
                        hbar.minimum(),
                        min(hbar.maximum(), prev_scroll + adj),
                    )
                )

        if self._pending_timeline_scroll_to_default and span.date_min is not None:
            self._scroll.widget().updateGeometry()
            self._scroll.updateGeometry()
            QTimer.singleShot(0, self._try_apply_initial_timeline_scroll)

    def _on_horizontal_range_changed_maybe_initial_scroll(
        self, _min_v: int, _max_v: int
    ) -> None:
        if self._middle_pan_active:
            return
        if self._pending_timeline_scroll_to_default:
            QTimer.singleShot(0, self._try_apply_initial_timeline_scroll)

    def _schedule_initial_timeline_scroll_if_needed(self) -> None:
        if (
            not self._rows
            or self._initial_timeline_center_applied
            or self._layout_date_min is None
        ):
            return
        self._pending_timeline_scroll_to_default = True
        self._initial_scroll_apply_attempts = 0
        self._initial_scroll_viewport_attempts = 0
        QTimer.singleShot(0, self._try_apply_initial_timeline_scroll)

    def _bucket_rows(self, rows: list[tuple[Any, ...]]) -> _TimelineBuckets:
        by_day: dict[date, list[tuple[Any, ...]]] = defaultdict(list)
        unknown_list: list[tuple[Any, ...]] = []
        for row in rows:
            if len(row) < 7:
                continue
            d = _parse_release(row[6])
            if d is None:
                unknown_list.append(row)
            else:
                by_day[d].append(row)
        for d, works in by_day.items():
            works.sort(key=lambda r: (r[0] or "", r[4]))
        unknown_list.sort(key=lambda r: (r[0] or "", r[4]))
        return _TimelineBuckets(by_day=by_day, unknown_list=unknown_list)

    def _build_timeline_span(self, buckets: _TimelineBuckets) -> _TimelineSpan:
        date_min: Optional[date] = None
        num_days = 0
        ext = timedelta(days=int(round(365.25 * float(TIMELINE_INFINITE_EXTRA_YEARS))))
        has_known = bool(buckets.by_day)
        has_unknown = bool(buckets.unknown_list)
        if has_known:
            raw_min = min(buckets.by_day.keys())
            raw_max = max(buckets.by_day.keys())
            merged_min = min(raw_min, TIMELINE_DEFAULT_START)
            merged_max = max(raw_max, TIMELINE_DEFAULT_END)
            core_min = merged_min - timedelta(days=TIMELINE_MERGE_SIDE_PAD_DAYS)
            core_max = merged_max + timedelta(days=TIMELINE_MERGE_SIDE_PAD_DAYS)
            date_min = core_min - ext
            timeline_end = core_max + ext
            num_days = (timeline_end - date_min).days + 1
        elif has_unknown:
            core_min = TIMELINE_DEFAULT_START - timedelta(
                days=TIMELINE_MERGE_SIDE_PAD_DAYS
            )
            core_max = TIMELINE_DEFAULT_END + timedelta(
                days=TIMELINE_MERGE_SIDE_PAD_DAYS
            )
            date_min = core_min - ext
            timeline_end = core_max + ext
            num_days = (timeline_end - date_min).days + 1

        unknown_section_w = max(MARKER_HIT + 16, UNKNOWN_SECTION_MIN_WIDTH)
        if date_min is not None and num_days > 0:
            date_min, num_days = self._ensure_axis_covers_viewport(
                date_min,
                num_days,
                self._ppd,
                has_unknown,
                unknown_section_w,
            )

        if num_days == 0 and has_unknown:
            unknown_x0 = TRACK_PAD_X + UNKNOWN_MARGIN
        elif has_unknown:
            unknown_x0 = TRACK_PAD_X + num_days * self._ppd + UNKNOWN_MARGIN
        else:
            unknown_x0 = TRACK_PAD_X + num_days * self._ppd

        return _TimelineSpan(
            date_min=date_min,
            num_days=num_days,
            has_unknown=has_unknown,
            unknown_section_w=unknown_section_w,
            unknown_x0=float(unknown_x0),
        )

    def _compute_axis_y(self, buckets: _TimelineBuckets) -> int:
        max_lane = 0
        for works in buckets.by_day.values():
            max_lane = max(max_lane, len(works))
        max_lane = max(max_lane, len(buckets.unknown_list))
        max_lane = max(1, max_lane)
        return RULER_HEIGHT + 2 + (max_lane - 1) * DIAMOND_STRIDE + MARKER_HIT // 2

    def _build_marker_placements(
        self,
        *,
        buckets: _TimelineBuckets,
        span: _TimelineSpan,
        date_axis_y: int,
    ) -> list[tuple[tuple[Any, ...], int, int]]:
        placements: list[tuple[tuple[Any, ...], int, int]] = []

        if span.date_min is not None and buckets.by_day:
            for d, works in buckets.by_day.items():
                day_idx = (d - span.date_min).days
                if day_idx < 0 or day_idx >= span.num_days:
                    continue
                for lane, row in enumerate(works):
                    cx = float(TRACK_PAD_X + day_idx * self._ppd)
                    center_y = date_axis_y - lane * DIAMOND_STRIDE
                    x = int(cx - MARKER_HIT / 2.0)
                    y = int(center_y - MARKER_HIT / 2.0)
                    placements.append((row, x, y))

        if span.has_unknown:
            x_unk = int(float(span.unknown_x0) - MARKER_HIT / 2.0)
            for lane, row in enumerate(buckets.unknown_list):
                center_y = date_axis_y - lane * DIAMOND_STRIDE
                y = int(center_y - MARKER_HIT / 2.0)
                placements.append((row, x_unk, y))
        return placements

    def _compute_geometry(
        self,
        *,
        placements: list[tuple[tuple[Any, ...], int, int]],
        span: _TimelineSpan,
        date_axis_y: int,
    ) -> _LayoutGeometry:
        if span.has_unknown:
            total_width = (
                span.unknown_x0
                + span.unknown_section_w
                + UNKNOWN_MARGIN
                + MARKER_HIT // 2
            )
        else:
            total_width = (
                TRACK_PAD_X + span.num_days * self._ppd + MARKER_HIT // 2 + UNKNOWN_MARGIN
            )
            total_width = max(total_width, 200)

        max_bottom = date_axis_y + MARKER_HIT // 2 + 12
        for _, _, y in placements:
            max_bottom = max(max_bottom, y + MARKER_HIT)
        content_height = max_bottom + 8
        return _LayoutGeometry(
            date_axis_y=date_axis_y,
            content_width=int(max(1, round(total_width))),
            content_height=int(max(1, round(content_height))),
        )

    def _maybe_apply_initial_default_window_fit_ppd(self, vw: int) -> bool:
        """首次：按视口宽度计算 ppd，使 2016–2026 默认窗大致占满可视宽度。

        若修改了 ppd 会触发 _rebuild_layout（内部会再次排队本滚动流程），返回 True。
        """
        if self._initial_default_window_ppd_fit_done:
            return False
        self._initial_default_window_ppd_fit_done = True
        vw_fit = max(200, int(vw))
        usable = max(
            100.0,
            float(vw_fit) - 2.0 * float(INITIAL_DEFAULT_WINDOW_FIT_MARGIN_PX),
        )
        fit_ppd = usable / float(max(1, TIMELINE_DEFAULT_SPAN_DAYS))
        fit_ppd = max(PPD_MIN, min(PPD_MAX, fit_ppd))
        if abs(fit_ppd - self._ppd) < 1e-9:
            return False
        self._ppd = fit_ppd
        self._rebuild_layout()
        return True

    def _try_apply_initial_timeline_scroll(self) -> None:
        """首次载入：缩放使默认窗 2016–2026 大致适配视口，并左对齐从 2016 年起。"""
        if not self._pending_timeline_scroll_to_default:
            return
        if self._middle_pan_active:
            return
        if not self._rows:
            self._pending_timeline_scroll_to_default = False
            self._initial_timeline_center_applied = True
            return
        dm = self._layout_date_min
        if dm is None:
            return

        hbar = self._scroll.horizontalScrollBar()
        vw_raw = self._scroll.viewport().width()
        if vw_raw < 100:
            self._initial_scroll_viewport_attempts += 1
            if self._initial_scroll_viewport_attempts < 200:
                self._scroll.updateGeometry()
                self._canvas.updateGeometry()
                QTimer.singleShot(0, self._try_apply_initial_timeline_scroll)
                return
        vw = max(1, vw_raw)
        self._initial_scroll_viewport_attempts = 0

        if self._maybe_apply_initial_default_window_fit_ppd(vw):
            return

        # setFixedSize 后 QScrollArea 可能尚未更新 horizontalScrollBar 的 range；
        # 若此时 setValue，会被钳到 0，视口会停在时间轴最左（远早于 2016）。
        needed_max = max(0, self._layout_content_width - vw)
        if needed_max > 0 and hbar.maximum() + 1 < needed_max:
            self._scroll.updateGeometry()
            self._canvas.updateGeometry()
            self._initial_scroll_apply_attempts += 1
            if self._initial_scroll_apply_attempts < 64:
                QTimer.singleShot(0, self._try_apply_initial_timeline_scroll)
                return
        self._initial_scroll_apply_attempts = 0

        dm = self._layout_date_min
        if dm is None:
            return
        idx_0 = (TIMELINE_DEFAULT_START - dm).days
        idx_1 = (TIMELINE_DEFAULT_END - dm).days
        if idx_1 < idx_0:
            hbar.setValue(0)
            self._pending_timeline_scroll_to_default = False
            self._initial_timeline_center_applied = True
            return
        # 左对齐默认窗起点（约 2016-01-01），避免把中点放在中央时只看到 2021 年中附近
        x_at_default_start = TRACK_PAD_X + float(idx_0) * self._ppd
        target = int(
            round(x_at_default_start - float(INITIAL_DEFAULT_WINDOW_FIT_MARGIN_PX))
        )
        smax = hbar.maximum()
        if smax > 0:
            target = max(0, min(smax, target))
            hbar.setValue(target)
        else:
            mid_y = max(0, self._canvas.height() // 2)
            self._scroll.ensureVisible(
                int(round(x_at_default_start)),
                mid_y,
                max(8, vw // 2),
                0,
            )
        self._pending_timeline_scroll_to_default = False
        self._initial_timeline_center_applied = True
