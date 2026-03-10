import logging
import threading
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage
from PySide6.QtCore import Qt, QSize

# 从 config 导入路径（需要根据实际项目结构调整）
try:
    from config import ACTRESSIMAGES_PATH, WORKCOVER_PATH
except ImportError:
    # 如果配置不存在，使用默认路径
    ACTRESSIMAGES_PATH = Path("data/images/actress")
    WORKCOVER_PATH = Path("data/images/work")

# 从 database 导入连接（需要根据实际项目结构调整）
def get_actress_image(actress_id: int) -> QImage:
    """根据女优ID获取女优照片"""
    try:
        from core.database.connection import get_connection
        from config import DATABASE
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            q = """
            SELECT image_urlA FROM actress WHERE actress_id=?
            """
            cursor.execute(q, (actress_id,))
            result = cursor.fetchone()
            if result and result[0]:
                imagepath = result[0]
                image = QImage(str(ACTRESSIMAGES_PATH / imagepath))
                return image
    except Exception as e:
        logging.warning(f"Failed to load actress image for id {actress_id}: {e}")
    return QImage()


def get_work_image(work_id: int) -> QImage:
    """根据作品ID获取作品封面"""
    try:
        from core.database.connection import get_connection
        from config import DATABASE
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            q = """
            SELECT image_url FROM work WHERE work_id=?
            """
            cursor.execute(q, (work_id,))
            result = cursor.fetchone()
            if result and result[0]:
                imagepath = result[0]
                img = QImage(str(WORKCOVER_PATH / imagepath))
                if img.isNull():
                    return QImage()
                w, h = img.width(), img.height()
                crop_x = w - h * 0.7
                crop_w = h * 0.7
                # 裁剪右侧区域
                img = img.copy(int(crop_x), 0, int(crop_w), h)
                # 缩放到固定尺寸
                img = img.scaled(
                    QSize(140, 200),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                return img
    except Exception as e:
        logging.warning(f"Failed to load work image for id {work_id}: {e}")
    return QImage()


class AsyncImageLoader(QObject):
    """异步图片加载器，使用后台线程加载图片避免阻塞UI"""
    image_loaded = Signal()

    def __init__(self):
        super().__init__()
        self.cache: Dict[str, QImage] = {}
        self.loading: set = set()

    def get_actress_image(self, actress_id: int) -> Optional[QImage]:
        """获取女优图片，使用缓存和异步加载"""
        key = f"a{actress_id}"
        if key in self.cache:
            return self.cache[key]

        if key not in self.loading:
            self.loading.add(key)
            threading.Thread(target=self._load_actress, args=(actress_id,), daemon=True).start()

        return None

    def get_work_image(self, work_id: int) -> Optional[QImage]:
        """获取作品图片，使用缓存和异步加载"""
        key = f"w{work_id}"
        if key in self.cache:
            return self.cache[key]

        if key not in self.loading:
            self.loading.add(key)
            threading.Thread(target=self._load_work, args=(work_id,), daemon=True).start()

        return None

    def _load_actress(self, actress_id: int):
        """后台线程加载女优图片"""
        try:
            img = get_actress_image(actress_id)
            self.cache[f"a{actress_id}"] = img
            self.image_loaded.emit()
        except Exception as e:
            logging.warning(f"Async load actress error: {e}")
        finally:
            self.loading.discard(f"a{actress_id}")

    def _load_work(self, work_id: int):
        """后台线程加载作品图片"""
        try:
            img = get_work_image(work_id)
            self.cache[f"w{work_id}"] = img
            self.image_loaded.emit()
        except Exception as e:
            logging.warning(f"Async load work error: {e}")
        finally:
            self.loading.discard(f"w{work_id}")


# 全局图片加载器实例
global_image_loader = AsyncImageLoader()
