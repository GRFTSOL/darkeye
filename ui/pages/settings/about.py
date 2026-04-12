"""关于软件页面：版本、更新、链接等。"""

import logging
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QWidget,
    QApplication,
    QFileDialog,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import Qt, QUrl, QTimer, QObject, Signal

from config import (
    BASE_DIR,
    APP_VERSION,
    get_last_auto_update_check_week,
    get_latest_json_url,
    set_last_auto_update_check_week,
)
from darkeye_ui.components import Label, Button, TokenLinkCard
from darkeye_ui.components.token_radio_button import TokenRadioButton
from controller.app_context import get_theme_manager
from controller.message_service import MessageBoxService

URLOPEN_TIMEOUT_SECONDS = 8
OVERALL_TIMEOUT_SECONDS = 12


def _spawn_detached_process(cmd, cwd):
    """Start a process that survives parent process exit."""
    popen_kwargs = {
        "cwd": str(cwd),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }

    if sys.platform == "win32":
        popen_kwargs["close_fds"] = True
        detached = getattr(subprocess, "DETACHED_PROCESS", 0)
        new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        breakaway = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        start_cmd = ["cmd", "/c", "start", ""] + list(cmd)
        start_flags = no_window | detached | new_group | breakaway
        try:
            return subprocess.Popen(
                start_cmd, creationflags=start_flags, **popen_kwargs
            )
        except OSError as e:
            logging.debug(
                "分离启动子进程失败，尝试其他 creationflags: %s",
                e,
                exc_info=True,
            )

        flag_candidates = [
            detached | new_group | breakaway,
            detached | new_group,
            new_group,
        ]
        last_error = None
        for creationflags in dict.fromkeys(flag_candidates):
            try:
                return subprocess.Popen(
                    cmd, creationflags=creationflags, **popen_kwargs
                )
            except OSError as err:
                last_error = err

        raise last_error
    else:
        popen_kwargs["start_new_session"] = True
        return subprocess.Popen(cmd, **popen_kwargs)


def _updater_base_args() -> tuple[Path, list[str]]:
    """返回 (安装目录, 传给 DarkEyeUpdater.exe 的参数列表，不含可执行文件路径)。"""
    import config

    app_dir = BASE_DIR.resolve()
    current_version = str(getattr(config, "APP_VERSION", "")).strip()
    args = [
        "--install-dir",
        str(app_dir),
        "--current-version",
        current_version,
        "--main-exe",
        "DarkEye.exe",
        "--latest-json-url",
        get_latest_json_url(),
        "--keep",
        "data",
        "--pid",
        str(os.getpid()),
    ]
    return app_dir, args


def _handle_update_and_launch(msg_svc: MessageBoxService, title: str, msg: str) -> bool:
    """处理「发现新版本」流程：询问用户、启动更新程序。返回 True 表示已启动更新（应用将退出）。"""
    update_title = title or "发现新版本"
    should_update = msg_svc.ask_yes_no(
        update_title,
        f"{msg}\n\n已检测到新版本。软件将退出以完成更新，是否立即更新？",
    )
    if not should_update:
        msg_svc.show_info("已取消更新", "你已取消更新。")
        return False

    updater_exe = BASE_DIR / "DarkEyeUpdater.exe"
    if not updater_exe.exists():
        msg_svc.show_critical("更新失败", f"未找到更新程序：{updater_exe}")
        return False

    import config

    if not str(getattr(config, "APP_VERSION", "")).strip():
        msg_svc.show_critical("更新失败", "无法从配置读取当前版本号。")
        return False

    app_dir, base_args = _updater_base_args()
    cmd = [str(updater_exe)] + base_args
    try:
        _spawn_detached_process(cmd, app_dir)
    except Exception as e:
        logging.exception("启动更新程序失败")
        msg_svc.show_critical("更新失败", f"无法启动更新程序：{e}")
        return False

    msg_svc.show_info(
        "开始更新",
        msg + "\n\n已启动更新程序，软件即将退出完成更新。点击确认后软件将退出完成更新",
    )
    app = QApplication.instance()
    if app is not None:
        QTimer.singleShot(200, app.quit)
    return True


def _handle_local_package_update(msg_svc: MessageBoxService, parent: QWidget) -> bool:
    """选择本地安装包（zip / tar.zst）并启动 DarkEyeUpdater.exe。返回 True 表示已启动更新（应用将退出）。"""
    updater_exe = BASE_DIR / "DarkEyeUpdater.exe"

    if not updater_exe.exists():
        msg_svc.show_critical("更新失败", f"未找到更新程序：{updater_exe}")
        return False

    if not msg_svc.ask_yes_no(
        "覆盖安装说明",
        "本地安装将无视版本号，直接覆盖安装目录下的文件。只能升级不能降级。跨最小版本可随意升降，中版本，大版本只能升级。"
        "覆盖安装时仅保留目录下的 data 文件夹内数据，"
        "请去github上下载最新的软件包.zip文件，然后选择这个文件进行覆盖安装。"
        "其余文件将被新版本覆盖。\n\n确定继续？",
    ):
        return False

    import config

    if not str(getattr(config, "APP_VERSION", "")).strip():
        msg_svc.show_critical("更新失败", "无法从配置读取当前版本号。")
        return False

    path, _ = QFileDialog.getOpenFileName(
        parent,
        "选择本地安装包",
        "",
        "安装包 (*.zip *.tar.zst);;ZIP 压缩包 (*.zip);;Zstandard (*.tar.zst);;所有文件 (*.*)",
    )
    if not path:
        return False
    if not os.path.isfile(path):
        msg_svc.show_critical("更新失败", "所选文件无效。")
        return False

    should_update = msg_svc.ask_yes_no(
        "使用本地安装包更新",
        f"将使用以下文件更新：\n{path}\n\n软件将退出以完成更新，是否继续？",
    )
    if not should_update:
        msg_svc.show_info("已取消更新", "你已取消更新。")
        return False

    app_dir, base_args = _updater_base_args()
    cmd = [str(updater_exe)] + base_args + ["--local-package", path]
    try:
        _spawn_detached_process(cmd, app_dir)
    except Exception as e:
        logging.exception("启动更新程序失败")
        msg_svc.show_critical("更新失败", f"无法启动更新程序：{e}")
        return False

    msg_svc.show_info(
        "开始更新",
        "已启动更新程序，软件即将退出完成更新。点击确认后软件将退出完成更新",
    )
    app = QApplication.instance()
    if app is not None:
        QTimer.singleShot(200, app.quit)
    return True


def run_update_check(
    parent: QWidget,
    on_done: Callable[[bool, str, str, bool, bool], None],
    *,
    urlopen_timeout: int = URLOPEN_TIMEOUT_SECONDS,
    overall_timeout: int = OVERALL_TIMEOUT_SECONDS,
) -> None:
    """后台执行更新检查，完成后在主线程调用 on_done(ok, title, msg, is_update_available, from_timeout)。"""

    class _UpdateCheckNotifier(QObject):
        result = Signal(bool, str, str, bool, bool)

    done_state = {"notified": False}
    notifier = _UpdateCheckNotifier(parent)

    def safe_emit(
        ok: bool,
        title: str,
        msg: str,
        is_update_available: bool,
        from_timeout: bool = False,
    ):
        if done_state["notified"]:
            return
        done_state["notified"] = True
        notifier.result.emit(ok, title, msg, is_update_available, from_timeout)

    notifier.result.connect(on_done)

    def worker():
        from utils.updater import check_for_updates

        res = check_for_updates(
            APP_VERSION,
            get_latest_json_url(),
            urlopen_timeout_seconds=urlopen_timeout,
            log_latest_json=True,
        )
        return (res.success, res.title, res.message, res.is_update_available)

    def run():
        ok, title, msg, is_update_available = worker()
        safe_emit(ok, title, msg, is_update_available, False)

    threading.Thread(target=run, daemon=True).start()

    def on_timeout():
        safe_emit(
            False,
            "更新检查超时",
            f"更新检查在 {overall_timeout} 秒内未完成，请检查网络后重试。",
            False,
            True,
        )

    QTimer.singleShot(overall_timeout * 1000, on_timeout)


def maybe_auto_check_update(parent: QWidget) -> None:
    """周五 18:00 后、本周未检查过则自动检查更新；仅在有新版本时弹窗。"""
    now = datetime.now()
    if now.weekday() != 4:  # 4 = Friday
        return
    if now.hour < 18:
        return
    year, week, _ = now.isocalendar()
    week_key = f"{year}-{week}"
    if get_last_auto_update_check_week() == week_key:
        return

    msg_svc = MessageBoxService(parent)

    def on_done(
        ok: bool, title: str, msg: str, is_update_available: bool, from_timeout: bool
    ):
        if not from_timeout:
            set_last_auto_update_check_week(week_key)
        if ok and is_update_available:
            _handle_update_and_launch(msg_svc, title, msg)
        # 无新版本时静默，不弹窗

    run_update_check(parent, on_done)


class LastPage(QWidget):
    """关于软件页面"""

    def __init__(self):
        super().__init__()
        self.msg = MessageBoxService(self)
        layout = QVBoxLayout(self)
        layout1 = QHBoxLayout()
        layout2 = QHBoxLayout()
        layout3 = QHBoxLayout()
        layout4 = QHBoxLayout()
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        theme_mgr = get_theme_manager()

        links_row = QWidget()
        links_layout = QVBoxLayout(links_row)
        links_layout.setContentsMargins(0, 0, 0, 0)
        links_layout.setSpacing(10)
        for card_title, blurb, href in (
            (
                "GitHub",
                "源代码仓库与问题反馈",
                "https://github.com/de4321/darkeye",
            ),
            (
                "Discord",
                "社区讨论与支持频道",
                "https://discord.gg/N7wJVNVA",
            ),
            (
                "官网",
                "产品介绍与主页",
                "https://de4321.github.io/darkeye-webpage/",
            ),
            (
                "文档",
                "使用说明与开发文档",
                "https://de4321.github.io/darkeye/",
            ),
        ):
            links_layout.addWidget(
                TokenLinkCard(
                    card_title,
                    blurb,
                    href,
                    links_row,
                    theme_manager=theme_mgr,
                ),
                0,
                Qt.AlignmentFlag.AlignHCenter,
            )

        ref_row = QWidget()
        ref_layout = QVBoxLayout(ref_row)
        ref_layout.setContentsMargins(0, 0, 0, 0)
        ref_layout.setSpacing(10)
        for card_title, blurb, href in (
            (
                "mdcz",
                "开源媒体库元数据刮削与管理，上游mdcx的重写",
                "https://github.com/ShotHeadman/mdcz",
            ),
            (
                "Jvedio",
                "Windows 本地影片管理与刮削工具",
                "https://github.com/hitchao/Jvedio",
            ),
            (
                "JavSP",
                "JAV刮削工具",
                "https://github.com/Yuukiy/JavSP",
            ),
            (
                "JAV-JHS",
                "油猴脚本，站点体验增强",
                "https://sleazyfork.org/zh-CN/scripts/558525-jav-jhs",
            ),
        ):
            ref_layout.addWidget(
                TokenLinkCard(
                    card_title,
                    blurb,
                    href,
                    ref_row,
                    theme_manager=theme_mgr,
                ),
                0,
                Qt.AlignmentFlag.AlignHCenter,
            )

        layout1.addWidget(Label(f"当前版本{APP_VERSION}"))
        btn_check_update = Button("检查更新")
        btn_check_update.setEnabled(True)
        btn_check_update.clicked.connect(
            lambda: self._on_check_update_clicked(btn_check_update)
        )
        layout1.addWidget(btn_check_update)
        btn_local_update = Button("使用本地安装包更新…")
        btn_local_update.setToolTip(
            "选择从 GitHub Release 下载的 zip 或 tar.zst，由更新程序离线安装"
        )
        btn_local_update.clicked.connect(
            lambda: _handle_local_package_update(self.msg, self)
        )
        layout1.addWidget(btn_local_update)
        btn_feedback = Button("意见反馈")
        btn_feedback.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/de4321/darkeye/issues")
            )
        )
        layout1.addWidget(btn_feedback)
        btn_changelog = Button("版本记录")
        btn_changelog.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://de4321.github.io/darkeye/CHANGELOG/")
            )
        )
        layout1.addWidget(btn_changelog)

        radio_auto_update = TokenRadioButton("自动更新")
        radio_auto_update.setEnabled(False)
        layout2.addWidget(radio_auto_update)
        radio_notify = TokenRadioButton("有新版本时提醒我")
        radio_notify.setEnabled(False)
        layout2.addWidget(radio_notify)

        layout3.addWidget(Label("下载移动客户端"))
        btn_android = Button("Android版")
        btn_android.setEnabled(False)
        layout3.addWidget(btn_android)

        layout4.addWidget(Label("下载浏览器插件"))
        btn_firefox = Button("Firefox插件")
        btn_firefox.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/de4321/darkeye/releases")
            )
        )
        layout4.addWidget(btn_firefox)

        btn_chrome = Button("Chrome/Edge插件")
        btn_chrome.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/de4321/darkeye/releases")
            )
        )
        layout4.addWidget(btn_chrome)

        form_layout.addRow(Label("项目链接"), links_row)
        form_layout.addRow(Label("参考项目"), ref_row)
        layout.addLayout(layout1)
        layout.addLayout(layout2)
        layout.addLayout(layout3)
        layout.addLayout(layout4)
        layout.addLayout(form_layout)

    def _on_check_update_clicked(self, btn: Button) -> None:
        btn.setEnabled(False)
        btn.setText("检查中...")

        def on_done(
            ok: bool,
            title: str,
            msg: str,
            is_update_available: bool,
            from_timeout: bool,
        ):
            btn.setText("检查更新")
            btn.setEnabled(True)

            if ok and is_update_available:
                _handle_update_and_launch(self.msg, title, msg)
            elif ok:
                self.msg.show_info(title, msg)
            else:
                self.msg.show_critical(title, msg)

        run_update_check(self, on_done)
