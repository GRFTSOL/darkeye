"""Qt Quick 3D 加载 DVD 模型演示。"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtCore import QUrl

from config import MESHES_PATH, MAPS_PATH
from core.database.query import get_works_for_dvd, get_work_ids_with_cover
from core.dvd.DvdShelfView import cover_url_to_texture_url, path_to_file_url


class Work:
    """弄一个数据类"""

    def __init__(self, work_id, serial_number, cover_url) -> None:
        self.work_id = work_id
        self.serial_number = serial_number
        self.cover_url = cover_url
        self.actress_list = []
        self.actor_list = []
        self.tag_list = []
        self.release_date = []
        self.director = []
        self.maker = None
        self.title = ""
        self.story = ""

    @classmethod
    def from_dict(cls, d: dict) -> Work:
        """从 get_works_for_dvd 返回的 dict 构建 Work 实例"""
        return cls(
            work_id=d.get("work_id"),
            serial_number=d.get("serial_number") or "",
            cover_url=d.get("image_url"),
        )


def _works_to_texture_urls(work_ids: list[int]) -> list[str]:
    """根据 work_ids 查询封面并转为贴图 URL 列表。"""
    works_data = get_works_for_dvd(work_ids)
    return [cover_url_to_texture_url(d.get("image_url")) for d in works_data]


def main(work_ids: list[int] | None = None) -> None:
    app = QApplication(sys.argv)

    dvd_dir = Path(__file__).resolve().parent
    dvd_qml_path = dvd_dir / "Dvd.qml"
    if not dvd_qml_path.exists():
        print(f"Dvd.qml 不存在: {dvd_qml_path}")
        sys.exit(1)
    dvd_qml_url = path_to_file_url(dvd_qml_path)
    print(f"使用 Dvd.qml 模型: {dvd_qml_path}")

    if work_ids is None:
        work_ids = get_work_ids_with_cover(100)
    if not work_ids:
        work_ids = []  # 无数据时用占位
    texture_urls = _works_to_texture_urls(work_ids) if work_ids else []
    dvd_count = len(texture_urls) if texture_urls else 1
    if not texture_urls:
        texture_urls = [cover_url_to_texture_url(None)]

    window = QMainWindow()
    window.setWindowTitle("Qt Quick 3D - DVD 模型")
    window.resize(800, 600)
    quick_widget = QQuickWidget()
    ctx = quick_widget.rootContext()
    ctx.setContextProperty("modelUrl", "")  # 不使用外部 glb
    ctx.setContextProperty("modelScale", 1)
    ctx.setContextProperty("dvdQmlUrl", dvd_qml_url)
    ctx.setContextProperty("dvdCount", dvd_count)
    ctx.setContextProperty("dvdSpacing", 0.0145)
    ctx.setContextProperty("dvdTextureSources", texture_urls)
    ctx.setContextProperty("dvdVisibleStart", 0)
    ctx.setContextProperty("dvdShelfLength", max(0, dvd_count - 1) * 0.0145)
    ctx.setContextProperty("cameraDistance", 0.35)
    ctx.setContextProperty("selectedDvdDistance", 0.28)

    # 默认开启 wireframe，确认模型几何后改为 False
    ctx.setContextProperty("showWireframe", False)
    ctx.setContextProperty(
        "meshesPath",
        QUrl.fromLocalFile(str(MESHES_PATH)).toString().rstrip("/") + "/",
    )
    ctx.setContextProperty(
        "mapsPath",
        QUrl.fromLocalFile(str(MAPS_PATH)).toString().rstrip("/") + "/",
    )
    quick_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)

    qml_dir = Path(__file__).resolve().parent
    qml_path = qml_dir / "dvd_scene.qml"
    quick_widget.setSource(QUrl.fromLocalFile(str(qml_path)))

    if quick_widget.status() == QQuickWidget.Error:
        print("QML 加载失败，请检查 Qt Quick 3D 模块是否可用")
        sys.exit(1)

    window.setCentralWidget(quick_widget)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
