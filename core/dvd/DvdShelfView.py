"""3D DVD 虚拟化书架视图，接收 work_ids 列表，按 3D 相机位置驱动可见范围加载。"""
from __future__ import annotations

from pathlib import Path
from time import perf_counter

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot, QTimer
from PySide6.QtGui import QCursor, QColor
from PySide6.QtWidgets import QApplication, QMenu, QVBoxLayout, QWidget, QSizePolicy
from PySide6.QtQuickWidgets import QQuickWidget

from config import get_video_path, MESHES_PATH, MAPS_PATH, HDR_PATH, WORKCOVER_PATH
from controller.MessageService import MessageBoxService
from core.database.query import (
    get_workinfo_by_workid,
    get_works_for_dvd,
    get_worktaginfo_by_workid,
    get_actress_from_work_id,
    get_actor_from_work_id,
)
from core.database.query.private import query_work
from core.database.insert import insert_liked_work
from core.database.delete import delete_favorite_work
from core.database.update import mark_delete
from utils.utils import find_video, play_video, get_text_color_from_background


def path_to_file_url(path: Path) -> str:
    """将本地路径转为 QML 可用的 file:// URL。"""
    return QUrl.fromLocalFile(str(path.resolve())).toString()


def cover_url_to_texture_url(image_url: str | None) -> str:
    """将 image_url（相对路径或空）转为 QML 可用的 file:// 贴图 URL。"""
    if image_url:
        full_path = WORKCOVER_PATH / image_url
        if full_path.exists():
            return path_to_file_url(full_path)
    return path_to_file_url(MAPS_PATH / "0.png")


VISIBLE_MARGIN = 30  # 相机 x 对应 DVD 位置前后各 30 本为可见范围
HYSTERESIS = 30  # 滞后：相机需移出当前范围此距离才触发更新，减少频繁重建导致的回弹
MAX_RANGE = 60  # 可见范围最大 item 数，超出时从远端收缩
WINDOW_RANGE = min(MAX_RANGE, VISIBLE_MARGIN * 2 + 1)
MAX_SHIFT_PER_UPDATE = 10  # 单次最多平移 10 个索引，避免一次性大幅跳动
UPDATE_INTERVAL_MS = 16  # 约 60FPS：滚动时节流刷新而非停止后防抖
SELECT_OPEN_DELAY_MS = 550
DVD_SPACING = 0.0145
CAMERA_SMOOTH_TIME_S = 0.11
CAMERA_MAX_SPEED = DVD_SPACING * 96
CAMERA_SETTLE_EPSILON = DVD_SPACING * 0.02
CAMERA_SETTLE_VELOCITY = DVD_SPACING * 0.1
DVD_QML = "Dvd.qml"
DVD_SCENE = "dvd_scene.qml"


class DvdBridge(QObject):
    """QML 与 Python 的桥接，cameraX 为 3D 坐标，由滚轮控制，Python 根据其计算可见范围。"""

    cameraXChanged = Signal(float)
    cameraTargetXChanged = Signal(float)
    expandedWorkFavoritedChanged = Signal()
    expandedWorkTitleChanged = Signal()
    expandedWorkStoryChanged = Signal()
    expandedWorkCodeChanged = Signal()
    expandedWorkReleaseDateChanged = Signal()
    expandedWorkTagsChanged = Signal()
    expandedWorkActressesChanged = Signal()
    expandedWorkActorsChanged = Signal()
    expandedWorkDirectorChanged = Signal()
    expandedWorkStudioChanged = Signal()

    def __init__(self, view: "DvdShelfView") -> None:
        super().__init__()
        self._view = view
        self._camera_x = 0.0
        self._camera_target_x = 0.0
        self._expanded_favorited = False
        self._expanded_work_title = ""
        self._expanded_work_story = ""
        self._expanded_work_code = ""
        self._expanded_work_release_date = ""
        self._expanded_work_tags: list = []
        self._expanded_work_actresses: list = []
        self._expanded_work_actors: list = []
        self._expanded_work_director = ""
        self._expanded_work_studio = ""

    def _get_camera_x(self) -> float:
        return self._camera_x

    def _set_camera_x(self, v: float) -> None:
        if abs(self._camera_x - v) > 1e-9:
            self._camera_x = v
            self.cameraXChanged.emit(v)

    cameraX = Property(float, _get_camera_x, _set_camera_x, notify=cameraXChanged)

    def _get_camera_target_x(self) -> float:
        return self._camera_target_x

    def _set_camera_target_x(self, v: float) -> None:
        if abs(self._camera_target_x - v) > 1e-9:
            self._camera_target_x = v
            self.cameraTargetXChanged.emit(v)

    cameraTargetX = Property(
        float,
        _get_camera_target_x,
        _set_camera_target_x,
        notify=cameraTargetXChanged,
    )

    def _get_expanded_favorited(self) -> bool:
        return self._expanded_favorited

    def _set_expanded_favorited(self, v: bool) -> None:
        if self._expanded_favorited != v:
            self._expanded_favorited = v
            self.expandedWorkFavoritedChanged.emit()

    expandedWorkFavorited = Property(
        bool, _get_expanded_favorited, _set_expanded_favorited,
        notify=expandedWorkFavoritedChanged,
    )

    def _get_expanded_work_title(self) -> str:
        return self._expanded_work_title

    def _set_expanded_work_title(self, v: str) -> None:
        if self._expanded_work_title != v:
            self._expanded_work_title = v
            self.expandedWorkTitleChanged.emit()

    expandedWorkTitle = Property(
        str, _get_expanded_work_title, _set_expanded_work_title,
        notify=expandedWorkTitleChanged,
    )

    def _get_expanded_work_story(self) -> str:
        return self._expanded_work_story

    def _set_expanded_work_story(self, v: str) -> None:
        if self._expanded_work_story != v:
            self._expanded_work_story = v
            self.expandedWorkStoryChanged.emit()

    expandedWorkStory = Property(
        str, _get_expanded_work_story, _set_expanded_work_story,
        notify=expandedWorkStoryChanged,
    )

    def _get_expanded_work_code(self) -> str:
        return self._expanded_work_code

    def _set_expanded_work_code(self, v: str) -> None:
        if self._expanded_work_code != v:
            self._expanded_work_code = v
            self.expandedWorkCodeChanged.emit()

    expandedWorkCode = Property(
        str, _get_expanded_work_code, _set_expanded_work_code,
        notify=expandedWorkCodeChanged,
    )

    def _get_expanded_work_release_date(self) -> str:
        return self._expanded_work_release_date

    def _set_expanded_work_release_date(self, v: str) -> None:
        if self._expanded_work_release_date != v:
            self._expanded_work_release_date = v
            self.expandedWorkReleaseDateChanged.emit()

    expandedWorkReleaseDate = Property(
        str, _get_expanded_work_release_date, _set_expanded_work_release_date,
        notify=expandedWorkReleaseDateChanged,
    )

    def _get_expanded_work_tags(self):
        return self._expanded_work_tags

    def _set_expanded_work_tags(self, v):
        if self._expanded_work_tags != v:
            self._expanded_work_tags = v
            self.expandedWorkTagsChanged.emit()

    expandedWorkTags = Property(
        list, _get_expanded_work_tags, _set_expanded_work_tags,
        notify=expandedWorkTagsChanged,
    )

    def _get_expanded_work_actresses(self):
        return self._expanded_work_actresses

    def _set_expanded_work_actresses(self, v):
        if self._expanded_work_actresses != v:
            self._expanded_work_actresses = v
            self.expandedWorkActressesChanged.emit()

    expandedWorkActresses = Property(
        list, _get_expanded_work_actresses, _set_expanded_work_actresses,
        notify=expandedWorkActressesChanged,
    )

    def _get_expanded_work_actors(self):
        return self._expanded_work_actors

    def _set_expanded_work_actors(self, v):
        if self._expanded_work_actors != v:
            self._expanded_work_actors = v
            self.expandedWorkActorsChanged.emit()

    expandedWorkActors = Property(
        list, _get_expanded_work_actors, _set_expanded_work_actors,
        notify=expandedWorkActorsChanged,
    )

    def _get_expanded_work_director(self):
        return self._expanded_work_director

    def _set_expanded_work_director(self, v):
        if self._expanded_work_director != v:
            self._expanded_work_director = v
            self.expandedWorkDirectorChanged.emit()

    expandedWorkDirector = Property(
        str, _get_expanded_work_director, _set_expanded_work_director,
        notify=expandedWorkDirectorChanged,
    )

    def _get_expanded_work_studio(self):
        return self._expanded_work_studio

    def _set_expanded_work_studio(self, v):
        if self._expanded_work_studio != v:
            self._expanded_work_studio = v
            self.expandedWorkStudioChanged.emit()

    expandedWorkStudio = Property(
        str, _get_expanded_work_studio, _set_expanded_work_studio,
        notify=expandedWorkStudioChanged,
    )

    def set_expanded_favorited(self, v: bool) -> None:
        if self._expanded_favorited != v:
            self._expanded_favorited = v
            self.expandedWorkFavoritedChanged.emit()

    def set_expanded_work_meta(
        self, title: str, story: str, code: str = "", release_date: str = ""
    ) -> None:
        self._set_expanded_work_title(title)
        self._set_expanded_work_story(story)
        self._set_expanded_work_code(code)
        self._set_expanded_work_release_date(release_date)

    @Slot(float)
    def onCameraXChanged(self, camera_x: float) -> None:
        self._view._on_camera_x_changed(camera_x)

    @Slot(float)
    def setCameraX(self, v: float) -> None:
        self._view.set_camera_target(v)

    @Slot(float, float)
    def scrollCameraBy(self, delta: float, max_camera_x: float) -> None:
        self._view.scroll_camera_by(delta, max_camera_x)

    @Slot(str)
    def copyToClipboard(self, text: str) -> None:
        """将文本复制到系统剪贴板。"""
        if text:
            QApplication.clipboard().setText(text)

    @Slot(int)
    def onCdClicked(self, virtual_index: int) -> None:
        self._view.show_video_menu_for_index(virtual_index)

    @Slot(int)
    def refreshExpandedFavoriteState(self, virtual_index: int) -> None:
        self._view._refresh_expanded_favorite_state(virtual_index)

    @Slot(int)
    def refreshExpandedWorkMeta(self, virtual_index: int) -> None:
        self._view._refresh_expanded_work_meta(virtual_index)

    @Slot(int)
    def onHeartClicked(self, virtual_index: int) -> None:
        self._view._on_heart_clicked(virtual_index)

    @Slot(int)
    def onEditClicked(self, virtual_index: int) -> None:
        self._view._on_edit_clicked(virtual_index)

    @Slot(int)
    def onDeleteClicked(self, virtual_index: int) -> None:
        self._view._on_delete_clicked(virtual_index)

    @Slot(int)
    def onTagClicked(self, tag_id: int) -> None:
        self._view._on_tag_clicked(tag_id)

    @Slot(int)
    def onActressClicked(self, actress_id: int) -> None:
        self._view._on_actress_clicked(actress_id)

    @Slot(int)
    def onActorClicked(self, actor_id: int) -> None:
        self._view._on_actor_clicked(actor_id)

    @Slot()
    def onDirectorClicked(self) -> None:
        self._view._on_director_clicked()

    @Slot()
    def onStudioClicked(self) -> None:
        self._view._on_studio_clicked()


class DvdShelfView(QWidget):
    """3D DVD 书架视图，虚拟化加载，由 3D 场景内相机位置决定可见范围。
    一次性接受完成的work_id列表，只是在渲染上是按可见窗口加载，现在是ID预加载加窗口虚拟化
    """

    def __init__(self, parent: QWidget | None = None, min_height: int = 600) -> None:
        super().__init__(parent)
        self._work_ids: list[int] = []
        self._load_start = -1
        self._load_end = -2
        self._texture_cache: dict[int, str] = {}
        self._dvd_dir = Path(__file__).resolve().parent.parent.parent / "core" / "dvd"

        self._bridge = DvdBridge(self)
        self._camera_target_x = 0.0
        self._camera_velocity_x = 0.0
        self._last_camera_animation_ts = perf_counter()
        self._camera_animation_timer = QTimer(self)
        self._camera_animation_timer.setSingleShot(False)
        self._camera_animation_timer.setInterval(UPDATE_INTERVAL_MS)
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(False)
        self._update_timer.setInterval(UPDATE_INTERVAL_MS)
        self._pending_camera_x: float | None = None
        self._programmatic_open_token = 0
        self._quick_widget = QQuickWidget(self)
        self._quick_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self._quick_widget.setMinimumHeight(min_height)
        self._quick_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        #self._quick_widget.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._quick_widget)

        self._setup_qml()
        self._bridge.cameraXChanged.connect(self._on_camera_x_changed)

    def _setup_qml(self) -> None:
        dvd_qml_path = self._dvd_dir / DVD_QML
        dvd_qml_url = path_to_file_url(dvd_qml_path)
        qml_path = self._dvd_dir / DVD_SCENE

        ctx = self._quick_widget.rootContext()
        ctx.setContextProperty("modelUrl", "")
        ctx.setContextProperty("modelScale", 1)
        ctx.setContextProperty("dvdQmlUrl", dvd_qml_url)
        ctx.setContextProperty("dvdCount", 0)
        ctx.setContextProperty("dvdTextureSources", [])
        ctx.setContextProperty("dvdVisibleStart", 0)
        ctx.setContextProperty("dvdShelfLength", 0.0)
        ctx.setContextProperty("dvdSpacing", DVD_SPACING)
        ctx.setContextProperty("cameraDistance", 0.25)
        ctx.setContextProperty("selectedDvdDistance", 0.2)
        ctx.setContextProperty("showWireframe", False)
        ctx.setContextProperty("dvdBridge", self._bridge)
        ctx.setContextProperty(
            "meshesPath",
            QUrl.fromLocalFile(str(MESHES_PATH)).toString().rstrip("/") + "/",
        )
        ctx.setContextProperty(
            "mapsPath",
            QUrl.fromLocalFile(str(MAPS_PATH)).toString().rstrip("/") + "/",
        )
        ctx.setContextProperty(
            "hdrPath",
            QUrl.fromLocalFile(str(HDR_PATH)).toString().rstrip("/") + "/",
        )
        self._quick_widget.setSource(QUrl.fromLocalFile(str(qml_path)))
        self._camera_animation_timer.timeout.connect(self._advance_camera_animation)
        self._update_timer.timeout.connect(self._apply_pending_camera_update)

    def work_count(self) -> int:
        return len(self._work_ids)

    def set_work_ids(self, work_ids: list[int]) -> None:
        '''这里一次性设置好所有的work_ids'''
        self._programmatic_open_token += 1
        self._reset_scene_interaction_state()
        self._work_ids = work_ids
        self._load_start = -1
        self._load_end = -2
        self._update_timer.stop()
        self._pending_camera_x = None
        self._bridge.set_expanded_favorited(False)
        self._bridge.set_expanded_work_meta("", "", "", "")
        self._bridge.expandedWorkTags = []
        self._bridge.expandedWorkActresses = []
        self._bridge.expandedWorkActors = []
        self._bridge.expandedWorkDirector = ""
        self._bridge.expandedWorkStudio = ""
        self._jump_camera_to(0.0)

        N = len(self._work_ids)
        if N == 0:
            self._update_qml(0, [], 0, 0.0)
            return

        self._pending_camera_x = 0.0
        self._apply_pending_camera_update()

    @staticmethod
    def _smooth_damp(
        current: float,
        target: float,
        current_velocity: float,
        smooth_time: float,
        max_speed: float,
        delta_time: float,
    ) -> tuple[float, float]:
        smooth_time = max(1e-4, smooth_time)
        delta_time = max(1e-4, delta_time)
        omega = 2.0 / smooth_time
        x = omega * delta_time
        exp = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x)

        change = current - target
        original_target = target
        max_change = max_speed * smooth_time
        change = max(-max_change, min(max_change, change))
        target = current - change

        temp = (current_velocity + omega * change) * delta_time
        new_velocity = (current_velocity - omega * temp) * exp
        output = target + (change + temp) * exp

        if (original_target - current > 0.0) == (output > original_target):
            output = original_target
            new_velocity = 0.0

        return output, new_velocity

    def _jump_camera_to(self, camera_x: float) -> None:
        camera_x = max(0.0, float(camera_x))
        self._camera_animation_timer.stop()
        self._camera_target_x = camera_x
        self._camera_velocity_x = 0.0
        self._last_camera_animation_ts = perf_counter()
        self._bridge._set_camera_target_x(camera_x)
        self._bridge._set_camera_x(camera_x)

    def set_camera_target(self, camera_x: float) -> None:
        camera_x = max(0.0, float(camera_x))
        self._camera_target_x = camera_x
        self._bridge._set_camera_target_x(camera_x)

        if (
            abs(self._bridge._get_camera_x() - camera_x) <= CAMERA_SETTLE_EPSILON
            and abs(self._camera_velocity_x) <= CAMERA_SETTLE_VELOCITY
        ):
            self._camera_velocity_x = 0.0
            self._bridge._set_camera_x(camera_x)
            return

        if not self._camera_animation_timer.isActive():
            self._last_camera_animation_ts = perf_counter()
            self._camera_animation_timer.start()

    def scroll_camera_by(self, delta: float, max_camera_x: float) -> None:
        target = max(0.0, min(float(max_camera_x), self._camera_target_x + float(delta)))
        self.set_camera_target(target)

    def _advance_camera_animation(self) -> None:
        now = perf_counter()
        delta_time = min(0.05, max(0.001, now - self._last_camera_animation_ts))
        self._last_camera_animation_ts = now

        current_x = self._bridge._get_camera_x()
        next_x, next_velocity = self._smooth_damp(
            current_x,
            self._camera_target_x,
            self._camera_velocity_x,
            CAMERA_SMOOTH_TIME_S,
            CAMERA_MAX_SPEED,
            delta_time,
        )
        self._camera_velocity_x = next_velocity

        if (
            abs(self._camera_target_x - next_x) <= CAMERA_SETTLE_EPSILON
            and abs(self._camera_velocity_x) <= CAMERA_SETTLE_VELOCITY
        ):
            self._camera_animation_timer.stop()
            self._camera_velocity_x = 0.0
            self._bridge._set_camera_x(self._camera_target_x)
            return

        self._bridge._set_camera_x(next_x)

    def _on_camera_x_changed(self, camera_x: float) -> None:
        N = len(self._work_ids)
        if N == 0:
            return

        self._pending_camera_x = camera_x
        if not self._update_timer.isActive():
            self._update_timer.start()

    def _calc_target_window(self, center_index: float, total_count: int) -> tuple[int, int]:
        if total_count <= 0:
            return 0, -1
        if total_count <= WINDOW_RANGE:
            return 0, total_count - 1

        max_start = total_count - WINDOW_RANGE
        target_start = int(center_index) - VISIBLE_MARGIN
        target_start = max(0, min(max_start, target_start))
        return target_start, target_start + WINDOW_RANGE - 1

    def _apply_pending_camera_update(self) -> None:
        if self._pending_camera_x is None:
            self._update_timer.stop()
            return
        camera_x = self._pending_camera_x
        self._pending_camera_x = None

        N = len(self._work_ids)
        if N == 0:
            self._update_timer.stop()
            return

        center_index = camera_x / DVD_SPACING
        target_start, target_end = self._calc_target_window(center_index, N)
        needs_follow_up = False

        if self._load_start < 0 or self._load_end < self._load_start:
            load_start, load_end = target_start, target_end
        else:
            # 滞后阈值内不触发更新，减少无效重建
            if center_index < self._load_start + HYSTERESIS or center_index > self._load_end - HYSTERESIS:
                desired_shift = target_start - self._load_start
                if desired_shift > MAX_SHIFT_PER_UPDATE:
                    desired_shift = MAX_SHIFT_PER_UPDATE
                    needs_follow_up = True
                elif desired_shift < -MAX_SHIFT_PER_UPDATE:
                    desired_shift = -MAX_SHIFT_PER_UPDATE
                    needs_follow_up = True

                load_start = self._load_start + desired_shift
                if N > WINDOW_RANGE:
                    load_start = max(0, min(N - WINDOW_RANGE, load_start))
                else:
                    load_start = 0
                load_end = min(N - 1, load_start + WINDOW_RANGE - 1)
            else:
                if self._pending_camera_x is None:
                    self._update_timer.stop()
                return

        if load_start == self._load_start and load_end == self._load_end:
            if needs_follow_up and self._pending_camera_x is None:
                self._pending_camera_x = camera_x
            elif self._pending_camera_x is None:
                self._update_timer.stop()
            return

        self._load_start = load_start
        self._load_end = load_end

        visible_ids = self._work_ids[load_start : load_end + 1]
        works_data = get_works_for_dvd(visible_ids)
        works_by_id = {
            int(d.get("work_id")): d for d in works_data
            if d.get("work_id") is not None
        }

        texture_urls: list[str] = []
        for wid in visible_ids:
            cached_url = self._texture_cache.get(wid)
            if cached_url:
                texture_urls.append(cached_url)
                continue
            img_url = (works_by_id.get(wid) or {}).get("image_url")
            tex_url = cover_url_to_texture_url(img_url)
            self._texture_cache[wid] = tex_url
            texture_urls.append(tex_url)

        shelf_length = (N - 1) * DVD_SPACING if N > 1 else 0.0
        self._update_qml(len(texture_urls), texture_urls, load_start, shelf_length)

        if needs_follow_up and self._pending_camera_x is None:
            self._pending_camera_x = camera_x
        elif self._pending_camera_x is None:
            self._update_timer.stop()

    def _update_qml(
        self,
        dvd_count: int,
        texture_urls: list[str],
        visible_start: int,
        shelf_length: float = 0.0,
    ) -> None:
        ctx = self._quick_widget.rootContext()
        ctx.setContextProperty("dvdTextureSources", texture_urls)
        ctx.setContextProperty("dvdCount", dvd_count)
        ctx.setContextProperty("dvdVisibleStart", visible_start)
        ctx.setContextProperty("dvdShelfLength", shelf_length)

    def _root_scene_object(self) -> QObject | None:
        return self._quick_widget.rootObject()

    def _set_scene_selection_state(
        self, selected_delegate_index: int, expanded_delegate_index: int
    ) -> None:
        root = self._root_scene_object()
        if root is None:
            return
        root.setProperty("selectedDelegateIndex", selected_delegate_index)
        root.setProperty("expandedDelegateIndex", expanded_delegate_index)

    def _reset_scene_interaction_state(self) -> None:
        root = self._root_scene_object()
        if root is None:
            return
        root.setProperty("hoveredDelegateIndex", -1)
        root.setProperty("pressedDelegateIndex", -1)
        root.setProperty("pressedObjectHit", None)
        root.setProperty("fullyExpandedDelegateIndex", -1)
        root.setProperty("_pendingCollapseSelectedIndex", -1)
        root.setProperty("_pendingCollapseCloseSpeedMultiplier", 1.0)
        root.setProperty("_frozenSelectedDelegateIndex", -1)
        root.setProperty("_frozenSelectedVirtualIndex", -1)
        root.setProperty("selectedDelegateIndex", -1)
        root.setProperty("expandedDelegateIndex", -1)

    def _expand_delegate_if_token_matches(self, delegate_index: int, token: int) -> None:
        if token != self._programmatic_open_token:
            return
        root = self._root_scene_object()
        if root is None:
            return
        current_selected = int(root.property("selectedDelegateIndex"))
        if current_selected != delegate_index:
            return
        root.setProperty("expandedDelegateIndex", delegate_index)

    def _select_and_open_virtual_index_if_token_matches(
        self, virtual_index: int, token: int
    ) -> None:
        if token != self._programmatic_open_token:
            return
        if not (self._load_start <= virtual_index <= self._load_end):
            return
        delegate_index = virtual_index - self._load_start
        root = self._root_scene_object()
        if root is None:
            return
        root.setProperty("selectedDelegateIndex", delegate_index)
        root.setProperty("expandedDelegateIndex", -1)
        QTimer.singleShot(
            SELECT_OPEN_DELAY_MS,
            lambda idx=delegate_index, current_token=token:
                self._expand_delegate_if_token_matches(idx, current_token),
        )

    @Slot(int, result=bool)
    def loadworkid(self, work_id: int) -> bool:
        try:
            virtual_index = self._work_ids.index(int(work_id))
        except (ValueError, TypeError):
            return False

        target_camera_x = virtual_index * DVD_SPACING
        self._programmatic_open_token += 1
        token = self._programmatic_open_token

        self._reset_scene_interaction_state()
        self._load_start = -1
        self._load_end = -2
        self._update_timer.stop()
        self._jump_camera_to(target_camera_x)
        self._pending_camera_x = target_camera_x
        self._apply_pending_camera_update()
        QTimer.singleShot(
            0,
            lambda idx=virtual_index, current_token=token:
                self._select_and_open_virtual_index_if_token_matches(idx, current_token),
        )
        return True

    def show_video_menu_for_index(self, virtual_index: int) -> None:
        """点击 CD 后弹出视频菜单供选择，复用 SingleWorkPage 的 show_video_menu 逻辑。"""
        if not (0 <= virtual_index < len(self._work_ids)):
            return
        work_id = self._work_ids[virtual_index]
        info = get_workinfo_by_workid(work_id)
        serial_number = (info or {}).get("serial_number", "").strip()
        if not serial_number:
            return

        video_paths = find_video(serial_number, get_video_path())
        if not video_paths:
            msg = MessageBoxService(self)
            msg.show_info("提示", "没有可播放的视频")
            return

        menu = QMenu(self)
        for path in video_paths:
            action = menu.addAction(path.name)
            action.setData(str(path))

        chosen_action = menu.exec(QCursor.pos())
        if chosen_action:
            play_video(Path(chosen_action.data()))

    def _refresh_expanded_favorite_state(self, virtual_index: int) -> None:
        """刷新展开作品的收藏状态，供 QML 爱心图标显示。"""
        if not (0 <= virtual_index < len(self._work_ids)):
            self._bridge.set_expanded_favorited(False)
            return
        work_id = self._work_ids[virtual_index]
        self._bridge.set_expanded_favorited(query_work(work_id))

    @staticmethod
    def _pick_first_nonempty_text(info: dict | None, keys: tuple[str, ...]) -> str:
        if not info:
            return ""
        for key in keys:
            value = info.get(key, "")
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return ""

    def _refresh_expanded_work_meta(self, virtual_index: int) -> None:
        if not (0 <= virtual_index < len(self._work_ids)):
            self._bridge.set_expanded_work_meta("", "", "", "")
            self._bridge.expandedWorkTags = []
            self._bridge.expandedWorkActresses = []
            self._bridge.expandedWorkActors = []
            self._bridge.expandedWorkDirector = ""
            self._bridge.expandedWorkStudio = ""
            return

        work_id = self._work_ids[virtual_index]
        info = get_workinfo_by_workid(work_id) or {}

        title = self._pick_first_nonempty_text(info, ("cn_title", "jp_title", "serial_number"))
        story = self._pick_first_nonempty_text(info, ("cn_story", "jp_story", "story"))
        code = str(info.get("serial_number", "") or "").strip()
        release_date = str(info.get("release_date", "") or "").strip()
        self._bridge.set_expanded_work_meta(title, story, code, release_date)

        raw_tags = get_worktaginfo_by_workid(work_id) or []
        tags = []
        for t in raw_tags:
            tag_copy = dict(t)
            bg = str(t.get("color") or "#cccccc")
            tag_copy["text_color"] = get_text_color_from_background(QColor(bg))
            tags.append(tag_copy)
        actresses = get_actress_from_work_id(work_id) or []
        actors = get_actor_from_work_id(work_id) or []
        director = str(info.get("director", "") or "").strip()
        studio = str(info.get("studio_name", "") or "").strip()
        self._bridge.expandedWorkTags = tags
        self._bridge.expandedWorkActresses = actresses
        self._bridge.expandedWorkActors = actors
        self._bridge.expandedWorkDirector = director
        self._bridge.expandedWorkStudio = studio

    def _on_heart_clicked(self, virtual_index: int) -> None:
        """爱心点击：切换收藏状态，参考 SingleWorkPage.on_clicked_heart。"""
        if not (0 <= virtual_index < len(self._work_ids)):
            return
        work_id = self._work_ids[virtual_index]
        is_fav = query_work(work_id)
        if is_fav:
            delete_favorite_work(work_id)
        else:
            insert_liked_work(work_id)
        self._bridge.set_expanded_favorited(not is_fav)
        from controller.GlobalSignalBus import global_signals
        global_signals.like_work_changed.emit()

    def _on_edit_clicked(self, virtual_index: int) -> None:
        """编辑点击：跳转作品编辑页，参考 SingleWorkPage.on_modify_clicked。"""
        if not (0 <= virtual_index < len(self._work_ids)):
            return
        work_id = self._work_ids[virtual_index]
        info = get_workinfo_by_workid(work_id)
        serial_number = (info or {}).get("serial_number", "").strip()
        if not serial_number:
            return
        from ui.navigation.router import Router
        Router.instance().push("work_edit", serial_number=serial_number)

    def _on_delete_clicked(self, virtual_index: int) -> None:
        """删除点击：标记删除，参考 SingleWorkPage.on_clicked_delete。"""
        if not (0 <= virtual_index < len(self._work_ids)):
            return
        work_id = self._work_ids[virtual_index]
        msg = MessageBoxService(self)
        if msg.ask_yes_no("确认删除", "确定要删除该作品吗？"):
            if mark_delete(work_id):
                msg.show_info("成功", "已标记删除")
                from controller.GlobalSignalBus import global_signals
                global_signals.work_data_changed.emit()

    def _on_tag_clicked(self, tag_id: int) -> None:
        """标签点击：跳转作品列表页（按 tag 筛选）。"""
        from ui.navigation.router import Router
        Router.instance().push("mutiwork", tag_id=tag_id)

    def _on_actress_clicked(self, actress_id: int) -> None:
        """女优点击：跳转女优详情页。"""
        from ui.navigation.router import Router
        Router.instance().push("single_actress", actress_id=actress_id)

    def _on_actor_clicked(self, actor_id: int) -> None:
        """男优点击：跳转作品列表页（按 actor 筛选）。"""
        from ui.navigation.router import Router
        Router.instance().push("mutiwork", actor_id=actor_id)

    def _on_director_clicked(self) -> None:
        """导演点击：暂不跳转。"""
        pass

    def _on_studio_clicked(self) -> None:
        """厂商点击：暂不跳转。"""
        pass
