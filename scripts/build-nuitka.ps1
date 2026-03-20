
# 清理旧的构建目录
Write-Host "Cleaning old build and dist folders..."

#if (Test-Path build) {Remove-Item build -Recurse -Force}

if (Test-Path dist) {Remove-Item dist -Recurse -Force}

# 如果存在 __pycache__，也清掉
if (Test-Path __pycache__) {
    Remove-Item __pycache__ -Recurse -Force
}

# 1. 记录开始时间
$startTime = Get-Date

# 使用 Nuitka 打包
Write-Host "Building with Nuitka..."

$nuitkaArgs = @(
    "--msvc=latest",
    "--standalone",
    "--show-progress",
    "--show-memory",
    "--show-modules",
    "--lto=yes",#开启lto优化
    "--jobs=10",#开10个线程，不让电脑卡死
    # 打开控制台黑框便于调试
    #"--windows-console-mode=force",
    "--windows-icon-from-ico=resources/icons/logo.ico",
    #"--enable-plugin=anti-bloat",#这个是默认开启的
    "--report=report.xml",

    # 对齐 main.spec 中的资源目录
    "--include-data-dir=resources/develop_resources/public=data/public",
    "--include-data-file=resources/develop_resources/crawler_nav_buttons.json=data/crawler_nav_buttons.json",
    "--include-data-file=DarkEyeUpdater.exe=DarkEyeUpdater.exe",
    # 其他资源目录
    "--include-data-dir=resources/icons=resources/icons",
    "--include-data-dir=resources/config=resources/config",
    "--include-data-dir=resources/sql=resources/sql",
    "--include-data-dir=resources/avwiki=resources/avwiki",
    "--include-data-dir=resources/help=resources/help",
    "--include-data-dir=styles=styles",
    "--include-data-dir=resources/hdr=resources/hdr",
    "--include-data-dir=resources/maps=resources/maps",
    "--include-data-dir=resources/meshes=resources/meshes",
    "--include-data-dir=darkeye_ui/styles=darkeye_ui/styles",
    "--include-data-dir=core/dvd/icons=core/dvd/icons",
    #qml要手动收集
    "--include-data-file=core/dvd/dvd_scene.qml=core/dvd/dvd_scene.qml",
    "--include-data-file=core/dvd/Dvd.qml=core/dvd/Dvd.qml",
    # C++ 绑定：.pyd 由 Nuitka 作为扩展模块自动包含，再当 data 会冲突；只手动包含 .dll 依赖，这个.pyd好像对自动收集
    "--include-data-files=cpp_bindings/forced_direct_view/*.dll=cpp_bindings/forced_direct_view/",
    "--include-data-files=cpp_bindings/color_wheel/*.dll=cpp_bindings/color_wheel/",

    # 插件与压缩
    "--enable-plugin=pyside6",
    "--include-qt-plugins=qml",#要用qml的时候一定要把这个加上

    # 如需使用 UPX，可取消下面两行注释并确保路径正确
    # "--enable-plugin=upx",
    # "--upx-binary=C:/upx-5.0.2-win64",
    "--noinclude-qt-plugins=multimedia,webengine,positioning,location,sensors,webchannel,websockets,remoteobjects,nfc,bluetooth,serialport",
    "--noinclude-qt-plugins=printsupport,sqldrivers,texttospeech,gamepads,virtualkeyboard,qmltooling",
    "--noinclude-qt-plugins=geoservices,networkinformation,canbus,webview,generic",

    # 额外包含的模块/包（对应 main.spec 的 hiddenimports）
    "--include-module=sqlite3",
    "--include-module=matplotlib.backends.backend_agg",
    "--include-module=matplotlib.backends.backend_qtagg",
    "--include-module=PySide6.QtCore",
    "--include-module=PySide6.QtGui",
    "--include-module=PySide6.QtWidgets",
    "--include-module=PySide6.QtNetwork",
    "--include-module=PySide6.QtQml",
    "--include-module=PySide6.QtQuick",
    "--include-module=PySide6.QtQuick3D",
    "--include-module=PySide6.QtQuickWidgets",
    "--include-module=PySide6.QtOpenGL",
    "--include-module=PySide6.QtOpenGLWidgets",
    # 这两个模块在当前环境中不可作为 Python 模块导入，先不强制包含
    # "--include-module=PyForceView",
    # "--include-module=PyColorWheel",
    #"--include-package=core",
    #"--include-package=ui",
    #"--include-package=controller",

    # 排除/不跟随导入（对应 main.spec 的 excludes）
    "--nofollow-import-to=cv2",
    # 这个压缩是不需要的，是打包脚本时才用
    "--nofollow-import-to=zstandard",
    "--nofollow-import-to=PySide6.QtWebEngine",
    "--nofollow-import-to=PySide6.QtMultimedia",
    "--nofollow-import-to=PySide6.QtBluetooth",
    "--nofollow-import-to=PySide6.QtNfc",
    "--nofollow-import-to=PySide6.QtPositioning",
    "--nofollow-import-to=PySide6.QtRemoteObjects",
    "--nofollow-import-to=PySide6.QtSensors",
    "--nofollow-import-to=PySide6.QtSerialPort",
    "--nofollow-import-to=PySide6.QtWebChannel",
    "--nofollow-import-to=PySide6.QtWebSockets",
    "--nofollow-import-to=PySide6.Qt3D",
    "--nofollow-import-to=PySide6.Qt3DAnimation",
    "--nofollow-import-to=PySide6.Qt3DCore",
    "--nofollow-import-to=PySide6.Qt3DExtras",
    "--nofollow-import-to=PySide6.Qt3DInput",
    "--nofollow-import-to=PySide6.Qt3DLogic",
    "--nofollow-import-to=PySide6.Qt3DRender",
    "--nofollow-import-to=PySide6.QtPdf",
    "--nofollow-import-to=PySide6.QtPdfWidgets",
    "--nofollow-import-to=PySide6.QtQuickControls2",
    "--nofollow-import-to=matplotlib.tests",
    "--nofollow-import-to=matplotlib.examples",
    "--nofollow-import-to=matplotlib.backends.backend_gtk3agg",
    "--nofollow-import-to=matplotlib.backends.backend_macosx",
    "--nofollow-import-to=matplotlib.backends.backend_wxagg",
    "--nofollow-import-to=matplotlib.backends.backend_webagg",
    "--nofollow-import-to=matplotlib.backends.backend_tkagg",
    "--nofollow-import-to=matplotlib.backends.backend_gtk",
    "--nofollow-import-to=matplotlib.backends.backend_wx",
    "--nofollow-import-to=matplotlib.backends.backend_pdf",
    "--nofollow-import-to=matplotlib.backends.backend_ps",
    "--nofollow-import-to=matplotlib.backends.backend_svg",
    "--nofollow-import-to=matplotlib.backends.backend_cairo",
    "--nofollow-import-to=numpy.testing",
    "--nofollow-import-to=numpy.f2py",
    "--nofollow-import-to=numpy.distutils",
    "--nofollow-import-to=numpy.doc",
    "--nofollow-import-to=numpy.random",
    "--nofollow-import-to=numpy.fft",

    "--nofollow-import-to=PIL.ImageShow",
    "--nofollow-import-to=PIL.ImageTk",
    "--nofollow-import-to=PIL.SpiderImagePlugin",
    "--nofollow-import-to=PIL._tkinter_finder",
    "--nofollow-import-to=PIL.BmpImagePlugin",
    "--nofollow-import-to=PIL.IcoImagePlugin",
    "--nofollow-import-to=PIL.CurImagePlugin",
    "--nofollow-import-to=PIL.PcxImagePlugin",
    "--nofollow-import-to=PIL.TgaImagePlugin",
    "--nofollow-import-to=PIL.XbmImagePlugin",
    "--nofollow-import-to=PIL.XpmImagePlugin",
    "--nofollow-import-to=PIL.MspImagePlugin",
    "--nofollow-import-to=PIL.WalImagePlugin",
    "--nofollow-import-to=PIL.FliImagePlugin",
    "--nofollow-import-to=PIL.GbrImagePlugin",
    "--nofollow-import-to=PIL.SunImagePlugin",
    "--nofollow-import-to=PIL.SgiImagePlugin",

    "--nofollow-import-to=pandas.tests",
    "--nofollow-import-to=seaborn.tests",
    "--nofollow-import-to=scipy",
    "--nofollow-import-to=sklearn",
    "--nofollow-import-to=sqlalchemy.tests",
    "--nofollow-import-to=sqlite3.test",
    "--nofollow-import-to=tkinter",
    "--nofollow-import-to=pytest",
    "--nofollow-import-to=test",
    "--nofollow-import-to=pydoc",
    "--nofollow-import-to=pkg_resources",
    "--nofollow-import-to=setuptools",
    "--nofollow-import-to=pip",
    "--nofollow-import-to=wheel",
    "--nofollow-import-to=virtualenv",
    "--nofollow-import-to=doctest",
    #"--nofollow-import-to=unittest",#这个东西会用到，不能排除
    "--nofollow-import-to=pdb",
    "--nofollow-import-to=trace",
    "--nofollow-import-to=distutils",
    "--nofollow-import-to=venv",
    "--nofollow-import-to=lib2to3",
    "--nofollow-import-to=uu",
    "--nofollow-import-to=lzma",
    "--nofollow-import-to=wsgiref",
    "--nofollow-import-to=xml.etree.cElementTree",
    "--nofollow-import-to=_osx_support",
    "--nofollow-import-to=ossaudiodev",

    #不要移动的dll
    "--noinclude-dlls=qt6web*.dll",
    "--noinclude-dlls=qt6pdf*.dll",
    "--noinclude-dlls=qt63d*.dll",
    "--noinclude-dlls=qt6sensors*.dll",
    "--noinclude-dlls=qt6quickcontrols2*.dll",
    "--noinclude-dlls=qt6positioning*.dll",
    "--noinclude-dlls=qt6multimedia*.dll",
    "--noinclude-dlls=qt6location*.dll",
    "--noinclude-dlls=qt6datavisualization*.dll",   
    "--noinclude-dlls=qt6labs*.dll",   
    "--noinclude-dlls=qt6remoteobjects*.dll",
    "--noinclude-dlls=qt6virtualkeyboard*.dll",
    "--noinclude-dlls=qt6chartsqml.dll",
    "--noinclude-dlls=qt6quickdialogs2*.dll",
    "--noinclude-dlls=qt6graphs.dll",
    "--noinclude-dlls=qt6spatialaudio.dll",
    "--noinclude-dlls=qt6statemachine*.dll",
    "--noinclude-dlls=qt6texttospeech.dll",
    "--noinclude-dlls=qt6test.dll",
    "--noinclude-dlls=qt6quicktemplates2.dll",


    #后面是输出的地址和文件名
    "--output-dir=dist",
    "--output-filename=DarkEye.exe"
)

nuitka @nuitkaArgs main.py

#手动删除
Remove-Item ".\dist\main.dist\PySide6\qml\QtMultimedia" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtGraphs" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtLocation" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtPositioning" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtSensors" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtTest" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtTextToSpeech" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtWebChannel" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtWebEngine" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtWebSockets" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtWebView" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtRemoteObjects" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtScxml" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtDataVisualization" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\Qt" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\Qt5Compat" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\Qt3D" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtCharts" -Recurse -Force -ErrorAction SilentlyContinue


Remove-Item ".\dist\main.dist\PySide6\qml\QtQuick\Controls" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtQuick\VirtualKeyboard" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\qml\QtQuick\NativeStyle" -Recurse -Force -ErrorAction SilentlyContinue

# tls/styles 删除前需确认：与网络、界面样式相关，若程序需 HTTPS 或自定义样式请勿删
Remove-Item ".\dist\main.dist\PySide6\plugins\tls" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\plugins\styles" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\plugins\qmltooling" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\plugins\generic" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist\main.dist\PySide6\plugins\networkinformation" -Recurse -Force -ErrorAction SilentlyContinue
# platforminputcontexts 与输入法相关，若需中文输入等请勿删
Remove-Item ".\dist\main.dist\PySide6\plugins\platforminputcontexts" -Recurse -Force -ErrorAction SilentlyContinue



Write-Host "Build complete."
# 3. 记录结束时间
$endTime = Get-Date

# 4. 计算耗时
$timeElapsed = $endTime - $startTime

# 5. 输出结果
Write-Host ("Elapsed time: {0} seconds" -f $timeElapsed.TotalSeconds)
