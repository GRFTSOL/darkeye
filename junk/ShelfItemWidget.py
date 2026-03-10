from dataclasses import dataclass
from pathlib import Path
from PySide6.QtCore import Qt, QPointF, QRect, QTimer, Signal, Slot, QThreadPool, QRunnable, QObject
from PySide6.QtGui import QColor,QImage,QPainter,QPainterPath,QPen,QPixmap,QPolygonF,QTransform,QCursor
from PySide6.QtWidgets import QWidget

from config import WORKCOVER_PATH
from ui.navigation.router import Router


TRAP_WIDTH = 8
TRAP_INSET_RATIO = 0.12
SPINE_PLACEHOLDER_W = 40
# 展开/收拢动画：每帧向目标插值的比例
EXPAND_LERP_STEP = 0.14
EXPAND_TOLERANCE = 0.01


def _perspective_transform(
    src: list[tuple[float, float]], dst: list[tuple[float, float]]
) -> QTransform:
    """根据 4 组对应点求透视变换矩阵（src[i] -> dst[i]），返回 QTransform。"""
    if len(src) != 4 or len(dst) != 4:
        return QTransform()

    # 设 (x',y') = ((a*x+b*y+c)/(g*x+h*y+1), (d*x+e*y+f)/(g*x+h*y+1))
    # 展开得: a*x+b*y+c - x'*(g*x+h*y) = x',  d*x+e*y+f - y'*(g*x+h*y) = y'
    # 未知数 [a,b,c,d,e,f,g,h]，共 8 个方程
    A = []
    b = []
    for i in range(4):
        x, y = src[i]
        X, Y = dst[i]
        A.append([x, y, 1, 0, 0, 0, -X * x, -X * y])
        b.append(X)
        A.append([0, 0, 0, x, y, 1, -Y * x, -Y * y])
        b.append(Y)

    # 高斯消元解 8x8
    n = 8
    for col in range(n):
        pivot = -1
        for row in range(col, n):
            if abs(A[row][col]) > 1e-12:
                pivot = row
                break
        if pivot < 0:
            return QTransform()
        A[col], A[pivot] = A[pivot], A[col]
        b[col], b[pivot] = b[pivot], b[col]
        t = A[col][col]
        for j in range(n):
            A[col][j] /= t
        b[col] /= t
        for row in range(n):
            if row != col and abs(A[row][col]) > 1e-12:
                f = A[row][col]
                for j in range(n):
                    A[row][j] -= f * A[col][j]
                b[row] -= f * b[col]

    a, b0, c, d, e, f, g, h = b
    # QTransform 行优先: (x',y') = ((m11*x+m21*y+m31)/(m13*x+m23*y+m33), (m12*x+m22*y+m32)/(...))
    # 对应 a*x+b*y+c -> m11=a, m21=b, m31=c;  d*x+e*y+f -> m12=d, m22=e, m32=f;  g*x+h*y+1 -> m13=g, m23=h, m33=1
    return QTransform(a, d, g, b0, e, h, c, f, 1.0)


@dataclass
class ShelfImageResult:
    spine_img: QImage | None
    left_img: QImage | None
    right_img: QImage | None
    spine_w: int
    left_strip_full_w: int
    right_strip_full_w: int


class ShelfImageLoaderSignals(QObject):
    image_ready = Signal(object)


class ShelfImageLoaderRunnable(QRunnable):
    """后台加载、裁剪、缩放封面为 spine/left/right，用 QImage 处理，emit ShelfImageResult。"""

    def __init__(
        self,
        path: str,
        target_h: int,
    ) -> None:
        super().__init__()
        self.path = path
        self.target_h = target_h
        self.signals = ShelfImageLoaderSignals()

    def run(self) -> None:
        img = QImage(str(self.path))
        if img.isNull():
            self.signals.image_ready.emit(
                ShelfImageResult(
                    spine_img=None,
                    left_img=None,
                    right_img=None,
                    spine_w=0,
                    left_strip_full_w=TRAP_WIDTH,
                    right_strip_full_w=TRAP_WIDTH,
                )
            )
            return

        h = img.height()
        w = img.width()
        if h <= 0 or w <= 0:
            self.signals.image_ready.emit(
                ShelfImageResult(
                    spine_img=None,
                    left_img=None,
                    right_img=None,
                    spine_w=0,
                    left_strip_full_w=TRAP_WIDTH,
                    right_strip_full_w=TRAP_WIDTH,
                )
            )
            return

        aspect = 0.71
        side_w = int(h * aspect)
        center_x = side_w
        center_w = w - 2 * side_w

        if center_w <= 0:
            center_w = max(1, int(w * 0.2))
            center_x = max(0, (w - center_w) // 2)

        spine_img: QImage | None = None
        left_img: QImage | None = None
        right_img: QImage | None = None
        spine_w = 0
        left_strip_full_w = TRAP_WIDTH
        right_strip_full_w = TRAP_WIDTH

        # 中缝
        rect = QRect(center_x, 0, center_w, h)
        rect = rect.intersected(QRect(0, 0, w, h))
        spine_img = img.copy(rect)
        spine_img = spine_img.scaledToHeight(
            self.target_h,
            Qt.TransformationMode.SmoothTransformation,
        )
        spine_w = max(25, spine_img.width())

        # 左侧条
        left_w = center_x
        if left_w > 0:
            left_strip_full_w = max(TRAP_WIDTH, int(left_w * self.target_h / h))
            left_strip = img.copy(QRect(0, 0, left_w, h))
            left_img = left_strip.scaled(
                left_strip_full_w,
                self.target_h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        # 右侧条
        right_x = center_x + center_w
        right_w = w - right_x
        if right_w > 0:
            right_strip_full_w = max(TRAP_WIDTH, int(right_w * self.target_h / h))
            right_strip = img.copy(QRect(right_x, 0, right_w, h))
            right_img = right_strip.scaled(
                right_strip_full_w,
                self.target_h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        self.signals.image_ready.emit(#这个加载过快的时候有概率出问题
            ShelfImageResult(
                spine_img=spine_img,
                left_img=left_img,
                right_img=right_img,
                spine_w=spine_w,
                left_strip_full_w=left_strip_full_w,
                right_strip_full_w=right_strip_full_w,
            )
        )


class ShelfItemWidget(QWidget):
    """
    单个拟物化「光盘盒」控件：
    - 中间为书脊图，左右为原图两侧裁剪条经透视贴到梯形上
    - 悬停向上「抽出」，双击进入作品详情
    """

    image_ready = Signal(object)  # 发射 ShelfImageResult

    def __init__(self, card_info: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._work_id: int = card_info["work_id"]
        self._serial_number: str = card_info["serial_number"]
        self._title: str = card_info.get("cn_title") or ""
        self._image_url: str | None = card_info.get("image_url")

        self._h = 500#封面高度，这个是个固定的值
        self._spine_pix: QPixmap | None = None
        self._spine_w = 0
        self._left_strip_pix: QPixmap | None = None
        self._right_strip_pix: QPixmap | None = None
        self._left_strip_full_w = TRAP_WIDTH
        self._right_strip_full_w = TRAP_WIDTH
        self._image_loader: ShelfImageLoaderRunnable | None = None
        # 展开状态：用动画插值，不随鼠标连续变化
        self._left_expand = 0.0
        self._right_expand = 0.0
        self._left_expand_target = 0.0
        self._right_expand_target = 0.0
        self._expand_anim_timer = QTimer(self)
        self._expand_anim_timer.setInterval(16)
        self._expand_anim_timer.timeout.connect(self._tick_expand_anim)
        self._mouse_inside = False
        self._last_zone = "middle"

        self.setMinimumWidth(40)
        self.setFixedHeight(self._h)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.setStyleSheet("ShelfItemWidget { background: transparent; }")

        self.image_ready.connect(self._on_image_loaded)
        self._setup_image()

    def _setup_image(self) -> None:
        self._spine_pix = None
        self._spine_w = 0
        self._left_strip_pix = None
        self._right_strip_pix = None
        self._left_strip_full_w = TRAP_WIDTH
        self._right_strip_full_w = TRAP_WIDTH

        if not self._image_url:
            self._spine_w = SPINE_PLACEHOLDER_W
            self._update_width()
            self.update()
            return

        path = Path(WORKCOVER_PATH / self._image_url)
        runnable = ShelfImageLoaderRunnable(
            str(path), self._h
        )
        runnable.signals.image_ready.connect(self._on_image_loaded)
        self._image_loader = runnable
        QThreadPool.globalInstance().start(runnable)

    @Slot(object)
    def _on_image_loaded(self, result: ShelfImageResult) -> None:
        """主线程：将 QImage 转为 QPixmap 并上屏。"""
        if result.spine_img is None:
            self._spine_pix = None
            self._left_strip_pix = None
            self._right_strip_pix = None
            self._left_strip_full_w = TRAP_WIDTH
            self._right_strip_full_w = TRAP_WIDTH
            self._spine_w = SPINE_PLACEHOLDER_W
            self._left_expand = 0.0
            self._right_expand = 0.0
            self._left_expand_target = 0.0
            self._right_expand_target = 0.0
            self._update_width()
            self.update()
            return
        self._spine_w = result.spine_w
        self._left_strip_full_w = result.left_strip_full_w
        self._right_strip_full_w = result.right_strip_full_w
        self._spine_pix = QPixmap.fromImage(result.spine_img)
        self._left_strip_pix = (
            QPixmap.fromImage(result.left_img) if result.left_img else None
        )
        self._right_strip_pix = (
            QPixmap.fromImage(result.right_img) if result.right_img else None
        )
        self._update_width()
        self.update()

    def _get_expand_factors(self) -> tuple[float, float]:
        """当前展开系数（动画插值后的值），用于绘制与宽度计算。"""
        return (self._left_expand, self._right_expand)

    def _current_left_right_widths(self) -> tuple[float, float]:
        """当前左右侧宽度（随展开插值）：(left_width, right_width)。"""
        left_expand, right_expand = self._get_expand_factors()
        left_w = TRAP_WIDTH + (self._left_strip_full_w - TRAP_WIDTH) * left_expand
        right_w = TRAP_WIDTH + (self._right_strip_full_w - TRAP_WIDTH) * right_expand
        return (left_w, right_w)

    def _update_width(self) -> None:
        """根据当前展开状态更新控件总宽度。"""
        left_w, right_w = self._current_left_right_widths()
        total = int(left_w) + self._spine_w + int(right_w)
        #new_w = max(self.minimumWidth(), total)
        new_w = total

        # 调试日志：打印宽度变化
        old_w = self.width()
        left_expand, right_expand = self._get_expand_factors()
        #print(f"[ShelfItemWidget] work_id={self._work_id}: 左展开={left_expand:.3f}, 右展开={right_expand:.3f}")
        #print(f"[ShelfItemWidget] work_id={self._work_id}: 左宽={left_w:.1f}, 书脊宽={self._spine_w}, 右宽={right_w:.1f}")
        #print(f"[ShelfItemWidget] work_id={self._work_id}: 旧宽度={old_w}, 新宽度={new_w}, total={total}")

        self.setFixedWidth(new_w)
        self.updateGeometry()  # 通知父布局重新计算，收拢时宽度才能缩小
        # 向上传播几何变化，确保父容器和 ScrollArea 内容区域随之更新
        parent = self.parentWidget()
        if parent and parent.layout():
            parent.layout().invalidate()
            parent.updateGeometry()

    def _zone_from_mouse_x(self, mouse_x: float) -> str:
        """以书脊边缘为判断线：左缘左侧=展开左，书脊中间=收拢，右缘右侧=展开右。"""
        left_width, _ = self._current_left_right_widths()
        spine_left = left_width
        spine_right = left_width + self._spine_w
        if mouse_x < spine_left:
            return "left"
        if mouse_x < spine_right:
            return "middle"
        return "right"

    def _set_expand_targets_from_zone(self, zone: str) -> None:
        """根据区域设置展开目标并启动动画。"""
        self._last_zone = zone
        if zone == "left":
            self._left_expand_target = 1.0
            self._right_expand_target = 0.0
        elif zone == "right":
            self._left_expand_target = 0.0
            self._right_expand_target = 1.0
        else:
            self._left_expand_target = 0.0
            self._right_expand_target = 0.0
        if not self._expand_anim_timer.isActive():
            self._expand_anim_timer.start()

    def _tick_expand_anim(self) -> None:
        """每帧向目标插值，更新宽度与重绘。展开/收拢仅由点击与离开区域驱动，不随悬停变化。"""
        done = True
        if abs(self._left_expand - self._left_expand_target) > EXPAND_TOLERANCE:
            self._left_expand += (self._left_expand_target - self._left_expand) * EXPAND_LERP_STEP
            self._left_expand = max(0.0, min(1.0, self._left_expand))
            done = False
        else:
            self._left_expand = self._left_expand_target
        if abs(self._right_expand - self._right_expand_target) > EXPAND_TOLERANCE:
            self._right_expand += (self._right_expand_target - self._right_expand) * EXPAND_LERP_STEP
            self._right_expand = max(0.0, min(1.0, self._right_expand))
            done = False
        else:
            self._right_expand = self._right_expand_target
        self._update_width()
        self.update()
        if done:
            self._expand_anim_timer.stop()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        H = self._h
        inset = int(H * TRAP_INSET_RATIO)
        left_expand, right_expand = self._get_expand_factors()
        left_width, right_width = self._current_left_right_widths()
        img_right = left_width + self._spine_w  # 书脊右缘 = 左侧宽 + 书脊宽

        # 左侧：与右侧同理——右缘两点始终紧贴中间图片左缘 left_width；展开时左缘从 0 到 0、右缘从 TRAP_WIDTH 到 left_width
        left_trap_pts = [
            (0, inset),
            (TRAP_WIDTH, 0),
            (TRAP_WIDTH, H),
            (0, H - inset),
        ]
        left_rect_pts = [
            (0, 0), (left_width, 0), (left_width, H), (0, H),
        ]
        left_quad = []
        left_edge_x = left_width * right_expand  # 右侧展开时左梯形左缘向右收，贴到右缘时宽度为 0
        for i in range(4):
            tx = (1 - left_expand) * left_trap_pts[i][0] + left_expand * left_rect_pts[i][0]
            ty = (1 - left_expand) * left_trap_pts[i][1] + left_expand * left_rect_pts[i][1]
            if i in (0, 3):
                tx = left_edge_x  # 左缘两点随 right_expand 向右
            elif i in (1, 2):
                tx = left_width  # 右缘两点始终紧贴中间图片左缘（与右侧梯形左缘贴书脊同理）
            left_quad.append((tx, ty))
        left_poly = QPolygonF([QPointF(x, y) for x, y in left_quad])

        if self._left_strip_pix and not self._left_strip_pix.isNull():
            path_left = QPainterPath()
            path_left.addPolygon(left_poly)
            painter.save()
            painter.setClipPath(path_left)
            src_quad = [
                (0, 0), (self._left_strip_full_w, 0),
                (self._left_strip_full_w, H), (0, H),
            ]
            dst_quad = [(left_poly[i].x(), left_poly[i].y()) for i in range(4)]
            if left_expand >= 0.999 and right_expand < 0.001:
                painter.drawPixmap(
                    0, 0, self._left_strip_full_w, H, self._left_strip_pix
                )
            else:
                tr = _perspective_transform(src_quad, dst_quad)
                painter.setTransform(tr)
                painter.drawPixmap(0, 0, self._left_strip_pix)
            painter.restore()

        # 中间书脊
        if self._spine_pix and not self._spine_pix.isNull():
            painter.drawPixmap(int(left_width), 0, self._spine_w, H, self._spine_pix)

        # 右侧：梯形时宽 TRAP_WIDTH，展开时宽 right_width；左侧展开时左缘不动、右缘向左收窄消失
        right_trap_pts = [
            (img_right, 0),
            (img_right + TRAP_WIDTH, inset),
            (img_right + TRAP_WIDTH, H - inset),
            (img_right, H),
        ]
        right_rect_pts = [
            (img_right, 0),
            (img_right + right_width, 0),
            (img_right + right_width, H),
            (img_right, H),
        ]
        right_quad = []
        right_edge_x = img_right + right_width * (1.0 - left_expand)  # 左侧展开时右梯形右缘向左收，贴到左缘时宽度为 0
        for i in range(4):
            rx = (1 - right_expand) * right_trap_pts[i][0] + right_expand * right_rect_pts[i][0]
            ry = (1 - right_expand) * right_trap_pts[i][1] + right_expand * right_rect_pts[i][1]
            if i in (1, 2):
                rx = right_edge_x  # 右缘两点随 left_expand 向左
            right_quad.append((rx, ry))
        right_poly = QPolygonF([QPointF(x, y) for x, y in right_quad])

        if self._right_strip_pix and not self._right_strip_pix.isNull():
            path_right = QPainterPath()
            path_right.addPolygon(right_poly)
            painter.save()
            painter.setClipPath(path_right)
            src_quad = [
                (0, 0), (self._right_strip_full_w, 0),
                (self._right_strip_full_w, H), (0, H),
            ]
            dst_quad = [(right_poly[i].x(), right_poly[i].y()) for i in range(4)]
            if right_expand >= 0.999 and left_expand < 0.001:
                painter.drawPixmap(
                    int(img_right), 0,
                    self._right_strip_full_w, H,
                    self._right_strip_pix,
                )
            else:
                tr = _perspective_transform(src_quad, dst_quad)
                painter.setTransform(tr)
                painter.drawPixmap(0, 0, self._right_strip_pix)
            painter.restore()

        # 最外圈红色线标记
        #painter.setPen(QPen(QColor(255, 0, 0), 2))
        #painter.setBrush(Qt.BrushStyle.NoBrush)
        #painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
        painter.end()

    def mouseMoveEvent(self, event) -> None:
        mouse_x = event.position().x()
        zone = self._zone_from_mouse_x(mouse_x)
        self._last_zone = zone
        # 展开状态下，鼠标离开该侧区域时自动收拢
        if self._left_expand_target >= 0.99 and self._right_expand_target < 0.01 and zone != "left":
            self._set_expand_targets_from_zone("middle")
        elif self._right_expand_target >= 0.99 and self._left_expand_target < 0.01 and zone != "right":
            self._set_expand_targets_from_zone("middle")
        super().mouseMoveEvent(event)

    def enterEvent(self, event) -> None:
        self._mouse_inside = True
        pos = self.mapFromGlobal(QCursor.pos())
        if self.rect().contains(pos):
            self._last_zone = self._zone_from_mouse_x(pos.x())
        super().enterEvent(event)

    def mousePressEvent(self, event) -> None:
        """仅在书脊左侧点击展开左侧，右侧点击展开右侧；中间点击可收拢。"""
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        mouse_x = event.position().x()
        zone = self._zone_from_mouse_x(mouse_x)
        self._set_expand_targets_from_zone(zone)
        super().mousePressEvent(event)

    def leaveEvent(self, event) -> None:
        self._mouse_inside = False
        self._last_zone = "middle"
        # 鼠标离开控件时自动收拢，恢复普通宽度
        self._set_expand_targets_from_zone("middle")
        super().leaveEvent(event)

    def check_mouse_position_on_scroll(self) -> None:
        """滚动时重新检查鼠标相对于自身的位置"""
        pos = self.mapFromGlobal(QCursor.pos())
        is_inside = self.rect().contains(pos)

        # 更新鼠标进入/离开状态
        if is_inside and not self._mouse_inside:
            # 滚动导致鼠标进入控件
            self._mouse_inside = True
        elif not is_inside and self._mouse_inside:
            # 滚动导致鼠标离开控件
            self._mouse_inside = False
            self._last_zone = "middle"
            self._set_expand_targets_from_zone("middle")
            return

        # 如果鼠标在控件内，仅更新记录的区域，避免滚动触发展开
        if is_inside:
            zone = self._zone_from_mouse_x(pos.x())
            if zone != self._last_zone:
                self._last_zone = zone

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            Router.instance().push("work", work_id=self._work_id)
        super().mouseDoubleClickEvent(event)
