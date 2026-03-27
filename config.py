# config.py
import sys
import configparser
from pathlib import Path
from PySide6.QtCore import QSettings,QSize,QPoint
import logging
#所有的配置文件都在这里，包括资源的地址等等


#==========================================================
APP_VERSION = "1.2.0"
REQUIRED_PUBLIC_DB_VERSION = "2"#软件所需要的公共数据库版本
REQUIRED_PRIVATE_DB_VERSION = "1.1"#软件所需要的私有数据库版本
#==========================================================


# ==========  路径适配打包 ==========
def resource_path(relative_path):
    """获取资源的绝对路径，兼容 PyInstaller 和 Nuitka 打包"""
    
    if getattr(sys, 'frozen', False):# 检查程序是否为打包版本（通用标记）
        if hasattr(sys, "_MEIPASS"):# 兼容 PyInstaller 的 _MEIPASS 模式 这个是给--onefile模式使用的
            base_path = Path(sys._MEIPASS)
        else:# 兼容 Nuitka 和其他打包器，它们通常使用可执行文件的路径
            base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).parent # 如果是未打包的开发环境，使用脚本所在路径

    return base_path / relative_path

# ==========  加载 settings.ini ==========
INI_FILE = resource_path("data/settings.ini")
parser = configparser.ConfigParser()
parser.read(INI_FILE, encoding="utf-8")

settings = QSettings(str(INI_FILE), QSettings.Format.IniFormat)#QSettings管理



BASE_DIR = resource_path("")

#这里后面还有绝对路径与相对路径的切换的问题

def get_PATH(key:str,default_value:str)->Path:
    '''用于通用从.ini中读取相对路径地址的函数'''
    path=settings.value(key)

    if path==None:#配置中无地址，写入默认地址，结束函数
        logging.info(f"Settings.ini文件中不存在{key}地址配置,写入默认地址")
        settings.setValue(key, default_value)
        settings.sync()
        path = default_value
        return resource_path(path)

    if not Path(path).exists():#配置中有地址，但是地址在电脑中是不存在的，也写入默认地址，并结束函数
        logging.info(f"Settings.ini文件中存在{key}地址配置,{path}地址不存在于电脑中，覆盖写入默认地址")
        settings.setValue(key, default_value)
        settings.sync()
        path = default_value
        return resource_path(path)
    
    return resource_path(path)#正常情况下返回地址

DATABASE = get_PATH("Paths/Database","data/public/public.db")#公共数据库文件地址
DATABASE_BACKUP_PATH=get_PATH("Paths/DatabaseBackups","data/public/public_backup/")#公共数据库备份地址

ACTRESSIMAGES_PATH=get_PATH("Paths/Actressimages","data/public/actressimages/")#女优头像的地址
ACTORIMAGES_PATH=get_PATH("Paths/Actorimages","data/public/actorimages/")#男优头像的地址
WORKCOVER_PATH=get_PATH("Paths/WorkCovers","data/public/workcovers/")#作品封面的地址
FANART_PATH=get_PATH("Paths/Fanart","data/public/fanart/")#作品 Fanart 附图目录（与封面分离）

PRIVATE_DATABASE=get_PATH("Paths/PrivateDatabase","data/private/private.db")#私有数据库文件地址
PRIVATE_DATABASE_BACKUP_PATH=get_PATH("Paths/PrivateDatabaseBackups","data/private/private_backup/")#私有数据库库备份地址
USER_SHORTCUT_PATH=get_PATH("Paths/ShortcutMap","data/shortcuts.json")#用户快捷键列表文件地址
CRAWLER_NAV_BUTTONS_PATH=get_PATH("Paths/CrawlerNavButtons","data/crawler_nav_buttons.json")#手动导航按钮配置
TEMP_PATH=get_PATH("Paths/Temp","data/temp/")#存一些临时文件，包括图片等等

#上面是用户保留，系统升级不修改的
#-------------------------------------------------#
#下面是系统，会随着系统升级修改的
SENSITIVE_WORDS_PATH=get_PATH("Paths/SensitiveWords","resources/config/sensitive_words.txt")#敏感词文件地址
TAG_MAP_PATH=get_PATH("Paths/TagMap","resources/config/tag_map.json")#敏感词文件地址


SQLPATH=get_PATH("Paths/Sql","resources/sql/")
ICONS_PATH = get_PATH("Paths/Icons","resources/icons/")#软件图标的地址

LOG_FILE=get_PATH("Paths/LogFile","log/app.log")#log文件的位置
QSS_PATH=get_PATH("Paths/QSS","styles/")#qss文件的位置
MESHES_PATH=get_PATH("Paths/Meshes","resources/meshes/")#DVD 模型 mesh 文件目录
MAPS_PATH=get_PATH("Paths/Maps","resources/maps/")#DVD 贴图目录
HDR_PATH=get_PATH("Paths/Hdr","resources/hdr/")#HDR 环境图目录
AVWIKI_PATH=get_PATH("Paths/AvWiki","resources/avwiki/")#AV 知识库 md 根目录
HELP_MD_PATH=get_PATH("Paths/HelpMd","resources/help/help.md")#帮助页 md 文件地址

def get_video_path()->list[Path]:
    '''获得视频地址，这个是用户自己填的绝对路径,可以有多个
    .ini中的配置形式是 C:/,D:/ 中间用逗号隔开，默认为空
    这里返回的是Path列表
    '''
    key = "Paths/Videos"
    path_value = settings.value(key, "")
    if not path_value:
        return []
    path_list = [Path(p) for p in str(path_value).split(",") if p.strip()]
    return path_list

def update_video_path(new_paths:list[Path]):
    '''更新视频地址,写入.ini文件'''
    new_paths_strs = [str(p) for p in new_paths]
    key = "Paths/Videos"
    if len(new_paths) > 1:
        value = ",".join(new_paths_strs)
    else:
        value = new_paths_strs[0]
    logging.info(f"地址配置,更新视频地址")
    settings.setValue(key, value)
    settings.sync()



def check_file():
    '''检查文件夹是否存在并建立'''
    TEMP_PATH.mkdir(parents=True, exist_ok=True) 
    WORKCOVER_PATH.mkdir(parents=True, exist_ok=True)
    FANART_PATH.mkdir(parents=True, exist_ok=True)
    ACTRESSIMAGES_PATH.mkdir(parents=True, exist_ok=True) 

def get_size_pos():
    '''获得.ini中的size和pos数据'''
    size = settings.value("window/size", QSize(800, 600))
    pos = settings.value("window/pos", QPoint(100, 100))
    return size,pos

def set_size_pos(size:QSize,pos:QPoint):
    '''将size和pos数据写入.ini'''
    settings.setValue("window/size", size)
    settings.setValue("window/pos", pos)

def is_max_window():
    '''获得.ini中的是否最大化的值，默认是没有'''
    return settings.value("window/maximized", False, type=bool)

def set_max_window(is_max_window:bool):
    '''记录窗口在退出的时候是否最大化的'''
    settings.setValue("window/maximized", is_max_window)

def is_first_lunch()->bool:
    '''判断软件是否第一次启动'''
    if  settings.value("window/first_lunch", True, type=bool):
        settings.setValue("window/first_lunch", False)
        return True
    else:
        return False

def set_first_luch(value:bool):
    '''设置启动值'''
    settings.setValue("window/first_lunch", value)


def get_theme_id() -> str:
    '''从 .ini 读取主题 ID（ThemeId 的 name，如 LIGHT/DARK/RED），默认 LIGHT'''
    return settings.value("App/Theme", "LIGHT", type=str)


def set_theme_id(theme_id) -> None:
    '''将主题 ID 写入 .ini，支持 ThemeId 或 str'''
    from darkeye_ui.design import ThemeId
    if isinstance(theme_id, ThemeId):
        theme_id = theme_id.name
    settings.setValue("App/Theme", theme_id)
    settings.sync()


def get_custom_primary() -> str | None:
    '''从 .ini 读取自定义主色（仅亮色/暗色主题生效），不存在或为空则返回 None'''
    val = settings.value("App/CustomPrimary", "", type=str)
    return val if (val and val.strip()) else None


def set_custom_primary(hex_color: str | None) -> None:
    '''将自定义主色写入 .ini，传入 None 时清除'''
    settings.setValue("App/CustomPrimary", hex_color or "")
    settings.sync()


def get_last_auto_update_check_week() -> str:
    '''获取上次自动检查更新的 ISO 周（格式 year-week，如 "2025-12"）'''
    return settings.value("Update/LastAutoCheckWeek", "", type=str) or ""


def set_last_auto_update_check_week(week_key: str) -> None:
    '''记录本次自动检查更新的周'''
    settings.setValue("Update/LastAutoCheckWeek", week_key)
    settings.sync()


# ========== 更新清单 URL（随版本发布的 ini，非用户 settings.ini）==========
_UPDATE_INI = resource_path("resources/config/update.ini")
# 内置兜底：资源文件缺失或字段无效时使用（与 resources/config/update.ini 保持一致）
DEFAULT_LATEST_JSON_URL = "https://yinruizhe.asia/latest.json"


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
    except Exception:
        logging.exception("读取 resources/config/update.ini 失败，使用内置默认更新地址")
    return DEFAULT_LATEST_JSON_URL