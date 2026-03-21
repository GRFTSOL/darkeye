# main.spec
# 适用于 project 结构的 PyInstaller 打包配置

import sys
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules
# 如果需要支持路径兼容
project_path = os.path.abspath(".")
sys.path.insert(0, project_path)

binding_binaries = []

# 收集 PySide6 相关的 Qt6*.dll（包括 Qt6QuickWidgets.dll 等）
EXCLUDED_SUBMODULES = {
    "core.dvd.demo_dvd",
    "ui.widgets.text.test_WikiTextEdit_interactive",
}


def collect_project_submodules(package_name: str):
    return [m for m in collect_submodules(package_name) if m not in EXCLUDED_SUBMODULES]


def collect_binding_dir(rel_path: str):
    """收集指定相对目录里的 .pyd 和 .dll"""
    base = Path(project_path) / rel_path
    if not base.exists():
        return
    for f in base.iterdir():
        if f.suffix.lower() in {".pyd", ".dll"}:
            # 第二个参数 '.' = 放到打包后根目录（与 DarkEye.exe 同级）
            binding_binaries.append((str(f), "."))

# 强制导图视图绑定
collect_binding_dir(r"cpp_bindings/forced_direct_view")
# color_wheel 绑定
collect_binding_dir(r"cpp_bindings/color_wheel")

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[project_path],
    binaries=binding_binaries,
    datas=[
        # 静态资源（icons、封面、演员图、数据库）#这里就只把公共数据库复制过去了
        ('resources/icons', 'resources/icons'),
        ('resources/develop_resources/public/', 'data/public'),
        ('resources/develop_resources/crawler_nav_buttons.json', 'data/'),
        ('resources/config', 'resources/config'),
        ('resources/sql/', 'resources/sql/'),
        ('resources/avwiki/', 'resources/avwiki/'),
        ('resources/help/', 'resources/help/'),
        ('styles', 'styles'),
        ('resources/hdr/', 'resources/hdr/'),
        ('resources/maps/', 'resources/maps/'),
        ('resources/meshes/', 'resources/meshes/'),
        ('darkeye_ui/styles', 'darkeye_ui/styles'),
        ('core/dvd/icons','core/dvd/icons'),
        ('core/dvd/dvd_scene.qml','core/dvd/'),
        ('core/dvd/Dvd.qml','core/dvd/'),#这个qml要手动收集
        ('DarkEyeUpdater.exe','.'),#这个qml要手动收集
    ],
    hiddenimports=[
        *collect_project_submodules('core'),
        *collect_project_submodules('ui'),
        *collect_project_submodules('controller'),
        'matplotlib.backends.backend_agg',  # 只打包 agg 后端
        # 明确列出用到的 PySide6 模块，避免被误判为未使用而裁掉
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PyForceView',
        'PyColorWheel',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'PySide6.QtWebEngine',                                    #精简pyside6
        'PySide6.QtBluetooth',
        'PySide6.QtNfc',
        'PySide6.QtWebChannel',
        'PySide6.QtWebSockets',
        'PySide6.QtWebView',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtNetworkAuth',
        'PySide6.QtPositioning',
        'PySide6.QtLocation',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DAnimation',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtStateMachine',
        'PySide6.QtTest',
        'PySide6.QtTextToSpeech',
        'PySide6.QtRemoteObjects',
        'PySide6.QtQuickControls2',
        'PySide6.QtQuickTest',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'matplotlib.tests',                                           #精简matplotlib
        'matplotlib.examples',
        'matplotlib.backends.backend_gtk3agg',
        'matplotlib.backends.backend_macosx',
        'matplotlib.backends.backend_wxagg',
        'matplotlib.backends.backend_webagg',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_gtk',
        'matplotlib.backends.backend_wx',
        'matplotlib.backends.backend_pdf',
        'matplotlib.backends.backend_ps',
        'matplotlib.backends.backend_svg',
        'matplotlib.backends.backend_cairo',
        'numpy.testing',                                            #精简numpy
        'numpy.tests',
        'numpy.core.tests',
        'numpy.lib.tests',
        'numpy.linalg.tests',
        'numpy.ma.tests',
        'numpy.random.tests',
        'numpy.fft.tests',
        'numpy.f2py',
        'numpy.f2py.tests',
        'numpy.distutils',
        'numpy.distutils.tests',
        'numpy.doc',
        #'numpy.random',  # 项目需要随机数，保留功能模块
        'numpy.fft',
        'scipy',#这个模块不要
        'PIL.ImageShow',                                           #精简PIL
        'PIL.ImageTk',
        'PIL.SpiderImagePlugin',
        'PIL._tkinter_finder',
        'PIL.BmpImagePlugin',       # 支持 BMP 格式
        'PIL.IcoImagePlugin',       # 支持 ICO 格式
        'PIL.CurImagePlugin',       # 支持 CUR 格式
        'PIL.PcxImagePlugin',       # 支持 PCX 格式
        'PIL.TgaImagePlugin',       # 支持 TGA 格式
        'PIL.XbmImagePlugin',       # 支持 XBM 格式
        'PIL.XpmImagePlugin',       # 支持 XPM 格式
        'PIL.MspImagePlugin',       # 支持 MSP 格式
        'PIL.WalImagePlugin',       # 支持 WAL 格式
        'PIL.FliImagePlugin',       # 支持 FLI/FLC 格式
        'PIL.GbrImagePlugin',       # 支持 GBR 格式
        'PIL.SunImagePlugin',       # 支持 Sun Raster 格式
        'PIL.SgiImagePlugin',       # 支持 SGI 格式
        'sqlite3.test',                                       #一些python自带的
        'tkinter',
        'pytest',
        'test',
        'pydoc',
        'tabnanny',
        'pydoc_data',
        'pkg_resources',
        'setuptools',
        'pip',
        'wheel',
        'virtualenv',
        #老旧/很少用的网络与协议模块
        'cgi',
        'cgitb',
        'smtpd',
        'nntplib',
        'poplib',
        'imaplib',
        'smtplib',
        'telnetlib',
        'xmlrpc.client',
        'xmlrpc.server',
        #音频、多媒体、教学/演示相关
        'aifc',
        'sunau',
        'wave',
        'audioop',
        'turtle',
        'idlelib',
        'ossaudiodev',
        #过时的构建/迁移工具
        'distutils',
        'lib2to3',
        '2to3',
        # 调试和测试模块
        'doctest',
        # 'unittest',  # 不能排除：pyparsing（matplotlib 依赖）的 testing 子模块会 import unittest
        'pdb',
        'trace',
        # 构建和部署模块
        'setuptools',
        'venv',

        # 不常用的数据格式和工具
        'uu',
        'lzma',
        #'bz2',
        'wsgiref',
        'xml.etree.cElementTree',
        # 特定环境的模块
        #'msvcrt',
        '_osx_support',
        'binhex',
        'xdrlib',
        'filecmp',
        'chunk',
        'imghdr',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DarkEye',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=['Qt6Core.dll', 'Qt6Gui.dll','Qt6Widgets.dll','Qt6Qml.dll','Qt6Quick.dll','Qt6Pdf.dll'],
    console=False,  # 改为 True 可显示终端日志窗口
    icon='resources/icons/logo.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=['Qt6Core.dll', 'Qt6Gui.dll','Qt6Widgets.dll','Qt6Qml.dll','Qt6Quick.dll','Qt6Pdf.dll'],
    name='DarkEye'
)
