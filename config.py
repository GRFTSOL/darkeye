# config.py
import sys
import configparser
from pathlib import Path
from PySide6.QtCore import QSettings, QSize, QPoint
import logging

# 所有的配置文件都在这里，包括资源的地址等等


# ==========================================================
APP_VERSION = "1.2.3"
REQUIRED_PUBLIC_DB_VERSION = "2"  # 软件所需要的公共数据库版本
REQUIRED_PRIVATE_DB_VERSION = "1.1"  # 软件所需要的私有数据库版本
# ==========================================================


# ==========  路径适配打包 ==========
def resource_path(relative_path):
    """获取资源的绝对路径，兼容 PyInstaller 和 Nuitka 打包"""

    if getattr(sys, "frozen", False):  # 检查程序是否为打包版本（通用标记）
        if hasattr(
            sys, "_MEIPASS"
        ):  # 兼容 PyInstaller 的 _MEIPASS 模式 这个是给--onefile模式使用的
            base_path = Path(sys._MEIPASS)
        else:  # 兼容 Nuitka 和其他打包器，它们通常使用可执行文件的路径
            base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).parent  # 如果是未打包的开发环境，使用脚本所在路径

    return base_path / relative_path


# ==========  加载 settings.ini ==========
INI_FILE = resource_path("data/settings.ini")
parser = configparser.ConfigParser()
parser.read(INI_FILE, encoding="utf-8")

settings = QSettings(str(INI_FILE), QSettings.Format.IniFormat)  # QSettings管理


BASE_DIR = resource_path("")

# 这里后面还有绝对路径与相对路径的切换的问题


def get_path(key: str, default_value: str) -> Path:
    """用于通用从.ini中读取相对路径地址的函数"""
    path = settings.value(key)

    if path == None:  # 配置中无地址，写入默认地址，结束函数
        logging.info(f"Settings.ini文件中不存在{key}地址配置,写入默认地址")
        settings.setValue(key, default_value)
        settings.sync()
        path = default_value
        return resource_path(path)

    if not Path(
        path
    ).exists():  # 配置中有地址，但是地址在电脑中是不存在的，也写入默认地址，并结束函数
        logging.info(
            f"Settings.ini文件中存在{key}地址配置,{path}地址不存在于电脑中，覆盖写入默认地址"
        )
        settings.setValue(key, default_value)
        settings.sync()
        path = default_value
        return resource_path(path)

    return resource_path(path)  # 正常情况下返回地址


DATABASE = get_path("Paths/Database", "data/public/public.db")  # 公共数据库文件地址
DATABASE_BACKUP_PATH = get_path(
    "Paths/DatabaseBackups", "data/public/public_backup/"
)  # 公共数据库备份地址

ACTRESSIMAGES_PATH = get_path(
    "Paths/Actressimages", "data/public/actressimages/"
)  # 女优头像的地址
ACTORIMAGES_PATH = get_path(
    "Paths/Actorimages", "data/public/actorimages/"
)  # 男优头像的地址
WORKCOVER_PATH = get_path(
    "Paths/WorkCovers", "data/public/workcovers/"
)  # 作品封面的地址
FANART_PATH = get_path(
    "Paths/Fanart", "data/public/fanart/"
)  # 作品 Fanart 附图目录（与封面分离）

PRIVATE_DATABASE = get_path(
    "Paths/PrivateDatabase", "data/private/private.db"
)  # 私有数据库文件地址
PRIVATE_DATABASE_BACKUP_PATH = get_path(
    "Paths/PrivateDatabaseBackups", "data/private/private_backup/"
)  # 私有数据库库备份地址

USER_SHORTCUT_PATH = resource_path("data/shortcuts.json")  # 用户快捷键列表文件地址
CRAWLER_NAV_BUTTONS_PATH = resource_path(
    "data/crawler_nav_buttons.json"
)  # 手动导航按钮配置
ADD_WORK_WORKSPACE_LAYOUT_PATH = resource_path(
    "data/add_work_workspace_layout.json"
)  # 添加作品页 myads 工作区布局（随 data 备份）

TEMP_PATH = get_path("Paths/Temp", "data/temp/")  # 存一些临时文件，包括图片等等

# 上面是用户保留，系统升级不修改的
# -------------------------------------------------#
# 下面是系统，会随着系统升级修改的
# 固定相对路径（resource_path），不写入 settings.ini

SENSITIVE_WORDS_PATH = resource_path(
    "resources/config/sensitive_words.txt"
)  # 敏感词文件地址
TAG_MAP_PATH = resource_path("resources/config/tag_map.json")  # 标签映射文件地址
SQLPATH = resource_path("resources/sql/")
ICONS_PATH = resource_path("resources/icons/")  # 软件图标的地址
LOG_FILE = resource_path("log/app.log")  # log文件的位置
MESHES_PATH = resource_path("resources/meshes/")  # DVD 模型 mesh 文件目录
MAPS_PATH = resource_path("resources/maps/")  # DVD 贴图目录
HDR_PATH = resource_path("resources/hdr/")  # HDR 环境图目录
AVWIKI_PATH = resource_path("resources/avwiki/")  # AV 知识库 md 根目录
QSS_PATH = resource_path(
    "resources/styles/"
)  # QSS 固定为项目下 styles/，不写入 settings.ini


def get_video_path() -> list[Path]:
    """获得视频地址，这个是用户自己填的绝对路径,可以有多个
    .ini中的配置形式是 C:/,D:/ 中间用逗号隔开，默认为空
    这里返回的是Path列表
    """
    key = "Paths/Videos"
    path_value = settings.value(key, "")
    if not path_value:
        return []
    path_list = [Path(p) for p in str(path_value).split(",") if p.strip()]
    return path_list


def update_video_path(new_paths: list[Path]):
    """更新视频地址,写入.ini文件"""
    new_paths_strs = [str(p) for p in new_paths]
    key = "Paths/Videos"
    if len(new_paths) > 1:
        value = ",".join(new_paths_strs)
    else:
        value = new_paths_strs[0]
    logging.info(f"地址配置,更新视频地址")
    settings.setValue(key, value)
    settings.sync()


def get_local_video_player_exe() -> str:
    """本地视频播放器可执行文件路径；空表示使用系统默认关联程序。"""
    val = settings.value("Video/LocalPlayerExe", "", type=str)
    return (val or "").strip()


def set_local_video_player_exe(path: str | None) -> None:
    """持久化本地播放器路径；传入空或 None 表示使用系统默认。"""
    settings.setValue("Video/LocalPlayerExe", (path or "").strip())
    settings.sync()


def check_file():
    """检查文件夹是否存在并建立"""
    TEMP_PATH.mkdir(parents=True, exist_ok=True)
    WORKCOVER_PATH.mkdir(parents=True, exist_ok=True)
    FANART_PATH.mkdir(parents=True, exist_ok=True)
    ACTRESSIMAGES_PATH.mkdir(parents=True, exist_ok=True)


def get_size_pos():
    """获得.ini中的size和pos数据"""
    size = settings.value("window/size", QSize(800, 600))
    pos = settings.value("window/pos", QPoint(100, 100))
    return size, pos


def set_size_pos(size: QSize, pos: QPoint):
    """将size和pos数据写入.ini"""
    settings.setValue("window/size", size)
    settings.setValue("window/pos", pos)


def is_max_window():
    """获得.ini中的是否最大化的值，默认是没有"""
    return settings.value("window/maximized", False, type=bool)


def set_max_window(is_max_window: bool):
    """记录窗口在退出的时候是否最大化的"""
    settings.setValue("window/maximized", is_max_window)


def is_first_lunch() -> bool:
    """判断软件是否第一次启动"""
    if settings.value("window/first_lunch", True, type=bool):
        settings.setValue("window/first_lunch", False)
        return True
    else:
        return False


def set_first_luch(value: bool):
    """设置启动值"""
    settings.setValue("window/first_lunch", value)


def get_theme_id() -> str:
    """从 .ini 读取主题 ID（ThemeId 的 name，如 LIGHT/DARK/RED），默认 LIGHT"""
    return settings.value("App/Theme", "LIGHT", type=str)


def set_theme_id(theme_id) -> None:
    """将主题 ID 写入 .ini，支持 ThemeId 或 str"""
    from darkeye_ui.design import ThemeId

    if isinstance(theme_id, ThemeId):
        theme_id = theme_id.name
    settings.setValue("App/Theme", theme_id)
    settings.sync()


def get_work_large_cover_view() -> bool:
    """作品页是否使用大图卡片（CoverCard2）瀑布列宽，默认标准视图"""
    return settings.value("WorkPage/LargeCoverView", False, type=bool)


def set_work_large_cover_view(enabled: bool) -> None:
    """持久化作品页封面视图模式"""
    settings.setValue("WorkPage/LargeCoverView", enabled)
    settings.sync()


def get_work_tag_selector_visible() -> bool:
    """作品页标签边栏是否可见，默认显示。"""
    return settings.value("WorkPage/TagSelectorVisible", True, type=bool)


def set_work_tag_selector_visible(visible: bool) -> None:
    """持久化作品页标签边栏显示状态。"""
    settings.setValue("WorkPage/TagSelectorVisible", visible)
    settings.sync()


def get_shelf_tag_selector_visible() -> bool:
    """书架页标签边栏是否可见，默认显示。"""
    return settings.value("ShelfPage/TagSelectorVisible", True, type=bool)


def set_shelf_tag_selector_visible(visible: bool) -> None:
    """持久化书架页标签边栏显示状态。"""
    settings.setValue("ShelfPage/TagSelectorVisible", visible)
    settings.sync()


def get_custom_primary() -> str | None:
    """从 .ini 读取自定义主色（仅亮色/暗色主题生效），不存在或为空则返回 None"""
    val = settings.value("App/CustomPrimary", "", type=str)
    return val if (val and val.strip()) else None


def set_custom_primary(hex_color: str | None) -> None:
    """将自定义主色写入 .ini，传入 None 时清除"""
    settings.setValue("App/CustomPrimary", hex_color or "")
    settings.sync()


def get_last_auto_update_check_week() -> str:
    """获取上次自动检查更新的 ISO 周（格式 year-week，如 "2025-12"）"""
    return settings.value("Update/LastAutoCheckWeek", "", type=str) or ""


def set_last_auto_update_check_week(week_key: str) -> None:
    """记录本次自动检查更新的周"""
    settings.setValue("Update/LastAutoCheckWeek", week_key)
    settings.sync()


def get_translation_engine() -> str:
    return settings.value("Translation/Engine", "google", type=str).strip().lower()


def set_translation_engine(value: str) -> None:
    settings.setValue("Translation/Engine", (value or "google").strip().lower())
    settings.sync()


def get_translation_model() -> str:
    return settings.value("Translation/Model", "", type=str).strip()


def set_translation_model(value: str) -> None:
    settings.setValue("Translation/Model", (value or "").strip())
    settings.sync()


def get_translation_base_url() -> str:
    return settings.value("Translation/BaseUrl", "", type=str).strip()


def set_translation_base_url(value: str) -> None:
    settings.setValue("Translation/BaseUrl", (value or "").strip())
    settings.sync()


def get_translation_api_key() -> str:
    return settings.value("Translation/ApiKey", "", type=str).strip()


def set_translation_api_key(value: str) -> None:
    settings.setValue("Translation/ApiKey", (value or "").strip())
    settings.sync()


def get_translation_timeout_s() -> float:
    return float(settings.value("Translation/TimeoutS", 12.0, type=float))


def set_translation_timeout_s(value: float) -> None:
    settings.setValue("Translation/TimeoutS", max(1.0, float(value)))
    settings.sync()


def get_translation_retries() -> int:
    return int(settings.value("Translation/Retries", 2, type=int))


def set_translation_retries(value: int) -> None:
    settings.setValue("Translation/Retries", max(0, int(value)))
    settings.sync()


def get_translation_fallback() -> str:
    fallback = settings.value("Translation/Fallback", "empty", type=str).strip()
    return fallback if fallback in {"empty", "source"} else "empty"


def set_translation_fallback(value: str) -> None:
    normalized = (value or "empty").strip().lower()
    settings.setValue(
        "Translation/Fallback",
        normalized if normalized in {"empty", "source"} else "empty",
    )
    settings.sync()


def get_translation_engine_settings():
    from core.translation.base import TranslationEngineConfig

    return TranslationEngineConfig(
        engine=get_translation_engine(),
        model=get_translation_model(),
        base_url=get_translation_base_url(),
        api_key=get_translation_api_key(),
    )


def get_translation_runtime_settings():
    from core.translation.base import TranslationRuntimeConfig

    return TranslationRuntimeConfig(
        timeout_s=get_translation_timeout_s(),
        retries=get_translation_retries(),
        fallback=get_translation_fallback(),
    )


# ========== 更新清单 URL（随版本发布的 ini，非用户 settings.ini）==========
_UPDATE_INI = resource_path("resources/config/update.ini")
# 内置兜底：资源文件缺失或字段无效时使用（与 resources/config/update.ini 保持一致）
DEFAULT_LATEST_JSON_URL = "https://yinruizhe.asia/latest.json"
DEFAULT_AVWIKI_LATEST_JSON_URL = "https://yinruizhe.asia/avwiki/avwiki_latest.json"


def get_latest_json_url() -> str:
    """
    从随安装包发布的 resources/config/update.ini 读取 latest.json 地址。
    该文件随版本发布/升级覆盖，不放在 data/settings.ini，避免用户配置与版本脱节。
    """
    p = _UPDATE_INI
    if not p.is_file():
        logging.warning("未找到 resources/config/update.ini，使用内置默认更新地址")
        return DEFAULT_LATEST_JSON_URL
    cp = configparser.ConfigParser()
    try:
        cp.read(p, encoding="utf-8")
        url = cp.get("Update", "LatestJsonUrl", fallback="").strip()
        if url:
            return url
        logging.warning("update.ini 中 LatestJsonUrl 为空，使用内置默认更新地址")
    except OSError:
        logging.exception(
            "读取 resources/config/update.ini 时发生路径/权限等系统错误，"
            "使用内置默认更新地址"
        )
    except UnicodeDecodeError:
        logging.exception(
            "resources/config/update.ini 无法按 UTF-8 解码，使用内置默认更新地址"
        )
    except configparser.Error:
        logging.exception(
            "resources/config/update.ini 解析失败（格式无效），使用内置默认更新地址"
        )
    return DEFAULT_LATEST_JSON_URL


def get_avwiki_latest_json_url() -> str:
    """
    从随安装包发布的 resources/config/update.ini 读取 avwiki 清单地址。
    该地址用于知识库资源手动更新，与应用本体更新地址解耦。
    """
    p = _UPDATE_INI
    if not p.is_file():
        logging.warning("未找到 resources/config/update.ini，使用内置 AVWiki 更新地址")
        return DEFAULT_AVWIKI_LATEST_JSON_URL
    cp = configparser.ConfigParser()
    try:
        cp.read(p, encoding="utf-8")
        url = cp.get("Update", "AvwikiLatestJsonUrl", fallback="").strip()
        if url:
            return url
        logging.warning(
            "update.ini 中 AvwikiLatestJsonUrl 为空，使用内置 AVWiki 更新地址"
        )
    except OSError:
        logging.exception(
            "读取 resources/config/update.ini 时发生路径/权限等系统错误，"
            "使用内置 AVWiki 更新地址"
        )
    except UnicodeDecodeError:
        logging.exception(
            "resources/config/update.ini 无法按 UTF-8 解码，使用内置 AVWiki 更新地址"
        )
    except configparser.Error:
        logging.exception(
            "resources/config/update.ini 解析失败（格式无效），使用内置 AVWiki 更新地址"
        )
    return DEFAULT_AVWIKI_LATEST_JSON_URL
