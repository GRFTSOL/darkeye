#!/usr/bin/env python3
"""Nuitka 打包：与 build-nuitka_debug.ps1 / build-nuitka_release.ps1 对齐，可选 release 或 debug。"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _rmtree_if_exists(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _unlink_if_exists(path: Path) -> None:
    if path.is_file():
        path.unlink()


def clean_build_artifacts(repo_root: Path) -> None:
    print("Cleaning old build and dist folders...")
    _rmtree_if_exists(repo_root / "dist")
    _rmtree_if_exists(repo_root / "__pycache__")


def nuitka_tail_args() -> list[str]:
    """与两份 .ps1 一致：自第一个 include-data-dir 起直至 output（不含 jobs / 控制台 / report）。"""
    return [
        "--include-data-dir=resources/develop_resources/public=data/public",
        "--include-data-file=resources/develop_resources/crawler_nav_buttons.json=data/crawler_nav_buttons.json",
        "--include-data-file=resources/develop_resources/actress_nav_buttons.json=data/actress_nav_buttons.json",
        "--include-data-file=DarkEyeUpdater.exe=DarkEyeUpdater.exe",
        "--include-data-dir=resources/icons=resources/icons",
        "--include-data-dir=resources/config=resources/config",
        "--include-data-dir=resources/sql=resources/sql",
        "--include-data-dir=resources/avwiki=resources/avwiki",
        "--include-data-dir=resources/styles=resources/styles",
        "--include-data-dir=resources/hdr=resources/hdr",
        "--include-data-dir=resources/maps=resources/maps",
        "--include-data-dir=resources/meshes=resources/meshes",
        "--include-data-dir=darkeye_ui/styles=darkeye_ui/styles",
        "--include-data-dir=core/dvd/icons=core/dvd/icons",
        "--include-data-dir=extensions/firefox_capture=extensions/firefox_capture",
        "--include-data-dir=extensions/chrome_capture=extensions/chrome_capture",
        "--include-data-file=core/dvd/dvd_scene.qml=core/dvd/dvd_scene.qml",
        "--include-data-file=core/dvd/Dvd.qml=core/dvd/Dvd.qml",
        "--enable-plugin=pyside6",
        "--include-qt-plugins=qml",
        "--noinclude-qt-plugins=multimedia,webengine,positioning,location,sensors,webchannel,websockets,remoteobjects,nfc,bluetooth,serialport",
        "--noinclude-qt-plugins=printsupport,sqldrivers,texttospeech,gamepads,virtualkeyboard,qmltooling",
        "--noinclude-qt-plugins=geoservices,networkinformation,canbus,webview,generic",
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
        "--include-package-data=wordcloud",
        "--nofollow-import-to=cv2",
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
        "--nofollow-import-to=PySide6.QtSql",
        "--nofollow-import-to=PySide6.QtQuickTest",
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
        "--nofollow-import-to=contourpy",
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
        "--nofollow-import-to=cgi",
        "--nofollow-import-to=cgitb",
        "--nofollow-import-to=smtpd",
        "--nofollow-import-to=nntplib",
        "--nofollow-import-to=poplib",
        "--nofollow-import-to=imaplib",
        "--nofollow-import-to=smtplib",
        "--nofollow-import-to=telnetlib",
        "--nofollow-import-to=xmlrpc.client",
        "--nofollow-import-to=xmlrpc.server",
        "--nofollow-import-to=aifc",
        "--nofollow-import-to=sunau",
        "--nofollow-import-to=wave",
        "--nofollow-import-to=audioop",
        "--nofollow-import-to=turtle",
        "--nofollow-import-to=idlelib",
        "--nofollow-import-to=doctest",
        "--nofollow-import-to=pdb",
        "--nofollow-import-to=trace",
        "--nofollow-import-to=distutils",
        "--nofollow-import-to=venv",
        "--nofollow-import-to=lib2to3",
        "--nofollow-import-to=2to3",
        "--nofollow-import-to=uu",
        "--nofollow-import-to=lzma",
        "--nofollow-import-to=wsgiref",
        "--nofollow-import-to=xml.etree.cElementTree",
        "--nofollow-import-to=_osx_support",
        "--nofollow-import-to=binhex",
        "--nofollow-import-to=xdrlib",
        "--nofollow-import-to=filecmp",
        "--nofollow-import-to=chunk",
        "--nofollow-import-to=imghdr",
        "--nofollow-import-to=ossaudiodev",
        "--nofollow-import-to=yaml",
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
        "--noinclude-dlls=qt6quicktest.dll",
        "--noinclude-dlls=qt6quicktemplates2.dll",
        "--noinclude-dlls=qt6quick3dspatialaudio.dll",
        "--noinclude-dlls=qt6scxml*.dll",
        "--noinclude-dlls=qt6quickparticles.dll",
        "--noinclude-dlls=qt6quickshapes.dll",
        "--noinclude-dlls=qt6quickeffects.dll",
        "--noinclude-dlls=qt6quicklayouts.dll",
        "--noinclude-dlls=qt6quicktimelineblendtrees.dll",
        "--noinclude-dlls=qt6quickvectorimagegenerator.dll",
        "--noinclude-dlls=qt6quickvectorimage.dll",
        "--noinclude-dlls=qt6sql.dll",
        "--noinclude-dlls=qt6qmllocalstorage.dll",
        "--noinclude-dlls=qt6qmlnetwork.dll",
        "--noinclude-dlls=qt6qmlxmllistmodel.dll",
        "--noinclude-dlls=qt6quick3deffects.dll",
        "--noinclude-dlls=qt6quick3dhelpersimpl.dll",
        "--noinclude-dlls=qt6quick3dparticles.dll",
        "--noinclude-dlls=qt6quick3dparticleeffects.dll",
        "--noinclude-dlls=qt6quick3dxr.dll",
        "--output-dir=dist",
        "--output-filename=DarkEye.exe",
    ]


def nuitka_argv(release: bool) -> list[str]:
    header: list[str] = [
        "--msvc=latest",
        "--standalone",
        "--show-progress",
        "--show-memory",
        "--show-modules",
    ]
    if release:
        header.append("--lto=yes")
    mid = [
        "--jobs=30",
        "--windows-console-mode=disable" if release else "--windows-console-mode=force",
        "--windows-icon-from-ico=resources/logo.ico",
    ]
    out = header + mid
    if not release:
        out.append("--report=report.xml")
    out.extend(nuitka_tail_args())
    return out


def trim_dist_output(dist_dir: Path) -> None:
    """与 .ps1 中 Remove-Item 一致的精简步骤。"""
    main_dist = dist_dir / "main.dist"
    if not main_dist.is_dir():
        return

    qml_rm = [
        "PySide6/qml/QtMultimedia",
        "PySide6/qml/QtGraphs",
        "PySide6/qml/QtLocation",
        "PySide6/qml/QtPositioning",
        "PySide6/qml/QtSensors",
        "PySide6/qml/QtTest",
        "PySide6/qml/QtTextToSpeech",
        "PySide6/qml/QtWebChannel",
        "PySide6/qml/QtWebEngine",
        "PySide6/qml/QtWebSockets",
        "PySide6/qml/QtWebView",
        "PySide6/qml/QtRemoteObjects",
        "PySide6/qml/QtScxml",
        "PySide6/qml/QtDataVisualization",
        "PySide6/qml/Qt",
        "PySide6/qml/Qt5Compat",
        "PySide6/qml/Qt3D",
        "PySide6/qml/QtCharts",
        "PySide6/qml/QtQuick/Controls",
        "PySide6/qml/QtQuick/VirtualKeyboard",
        "PySide6/qml/QtQuick/NativeStyle",
    ]
    for rel in qml_rm:
        _rmtree_if_exists(main_dist / rel.replace("/", os.sep))

    plugin_rm = [
        "PySide6/plugins/tls",
        "PySide6/plugins/styles",
        "PySide6/plugins/qmltooling",
        "PySide6/plugins/generic",
        "PySide6/plugins/networkinformation",
        "PySide6/plugins/platforminputcontexts",
    ]
    for rel in plugin_rm:
        _rmtree_if_exists(main_dist / rel.replace("/", os.sep))

    for name in ("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll"):
        _unlink_if_exists(main_dist / name)

    for rel in (
        "PIL/_imagingcms.pyd",
        "PIL/_imagingmath.pyd",
        "numpy/_core/_multiarray_tests.pyd",
        "matplotlib/_qhull.pyd",
        "matplotlib/_tri.pyd",
        "PySide6/qt-plugins/platforms/qdirect2d.dll",
        "PySide6/qt-plugins/platforms/qminimal.dll",
        "PySide6/qt-plugins/platforms/qoffscreen.dll",
        "PySide6/qt-plugins/tls/qcertonlybackend.dll",
        "PySide6/qt-plugins/tls/qopensslbackend.dll",
        "PySide6/qt-plugins/tls/qschannelbackend.dll",
    ):
        _unlink_if_exists(main_dist / rel.replace("/", os.sep))


def run_pack(repo_root: Path) -> None:
    pack_script = repo_root / "scripts" / "pack.py"
    print("Running pack (tar.zst + latest.json)...")
    subprocess.run([sys.executable, str(pack_script)], cwd=repo_root, check=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Nuitka 打包 DarkEye（release / debug）")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--release",
        action="store_true",
        help="发布版：LTO、无控制台、打包后运行 scripts/pack.py",
    )
    mode.add_argument(
        "--debug",
        action="store_true",
        help="调试版：无 LTO、强制控制台、生成 report.xml、不运行 pack.py",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    release = bool(args.release)
    os.chdir(REPO_ROOT)

    clean_build_artifacts(REPO_ROOT)
    start = time.perf_counter()

    argv = [sys.executable, "-m", "nuitka"] + nuitka_argv(release) + ["main.py"]
    print("Building with Nuitka...")
    subprocess.run(argv, cwd=REPO_ROOT, check=True)

    trim_dist_output(REPO_ROOT / "dist")

    if release:
        run_pack(REPO_ROOT)

    elapsed = time.perf_counter() - start
    print("Build complete.")
    print(f"Elapsed time: {elapsed:.3f} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
