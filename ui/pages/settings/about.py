"""关于软件页面：版本、更新、链接等。"""

import logging
import os
import subprocess
import sys
import threading
from datetime import datetime
from typing import Callable

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QFormLayout, QWidget, QApplication
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import Qt, QUrl, QTimer, QObject, Signal

from config import BASE_DIR, APP_VERSION, get_last_auto_update_check_week, set_last_auto_update_check_week
from darkeye_ui.components import Label, Button
from darkeye_ui.components.token_radio_button import TokenRadioButton
from controller.MessageService import MessageBoxService

LATEST_JSON_URL = "http://yinruizhe.asia/latest.json"
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
            return subprocess.Popen(start_cmd, creationflags=start_flags, **popen_kwargs)
        except OSError:
            pass

        flag_candidates = [
            detached | new_group | breakaway,
            detached | new_group,
            new_group,
        ]
        last_error = None
        for creationflags in dict.fromkeys(flag_candidates):
            try:
                return subprocess.Popen(cmd, creationflags=creationflags, **popen_kwargs)
            except OSError as err:
                last_error = err

        raise last_error
    else:
        popen_kwargs["start_new_session"] = True
        return subprocess.Popen(cmd, **popen_kwargs)


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

    import config

    updater_exe = BASE_DIR / "DarkEyeUpdater.exe"
    if not updater_exe.exists():
        msg_svc.show_critical("更新失败", f"未找到更新程序：{updater_exe}")
        return False

    current_version = str(getattr(config, "APP_VERSION", "")).strip()
    if not current_version:
        msg_svc.show_critical("更新失败", "无法从配置读取当前版本号。")
        return False

    app_dir = BASE_DIR.resolve()
    cmd = [
        str(updater_exe),
        "--install-dir",
        str(app_dir),
        "--current-version",
        current_version,
        "--main-exe",
        "DarkEye.exe",
        "--latest-json-url",
        LATEST_JSON_URL,
        "--keep",
        "data",
        "--pid",
        str(os.getpid()),
    ]
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

    def safe_emit(ok: bool, title: str, msg: str, is_update_available: bool, from_timeout: bool = False):
        if done_state["notified"]:
            return
        done_state["notified"] = True
        notifier.result.emit(ok, title, msg, is_update_available, from_timeout)

    notifier.result.connect(on_done)

    def worker():
        from core.updater import check_for_updates

        res = check_for_updates(
            APP_VERSION,
            LATEST_JSON_URL,
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

    def on_done(ok: bool, title: str, msg: str, is_update_available: bool, from_timeout: bool):
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

        githubLabel = Label()
        githubLabel.setText('<a href="https://github.com/de4321/darkeye">GitHub</a>')
        githubLabel.setTextFormat(Qt.RichText)
        githubLabel.setTextInteractionFlags(Qt.TextBrowserInteraction)
        githubLabel.setOpenExternalLinks(True)

        discordLabel = Label()
        discordLabel.setText('<a href="https://discord.gg/N7wJVNVA">Discord</a>')
        discordLabel.setTextFormat(Qt.RichText)
        discordLabel.setTextInteractionFlags(Qt.TextBrowserInteraction)
        discordLabel.setOpenExternalLinks(True)

        websiteLabel = Label()
        websiteLabel.setText(
            '<a href="https://de4321.github.io/darkeye-webpage/">官网</a>'
        )
        websiteLabel.setTextFormat(Qt.RichText)
        websiteLabel.setTextInteractionFlags(Qt.TextBrowserInteraction)
        websiteLabel.setOpenExternalLinks(True)

        documentLabel = Label()
        documentLabel.setText('<a href="https://de4321.github.io/darkeye/">文档</a>')
        documentLabel.setTextFormat(Qt.RichText)
        documentLabel.setTextInteractionFlags(Qt.TextBrowserInteraction)
        documentLabel.setOpenExternalLinks(True)

        links_row = QWidget()
        links_layout = QHBoxLayout(links_row)
        links_layout.setContentsMargins(0, 0, 0, 0)
        links_layout.addWidget(githubLabel)
        links_layout.addWidget(discordLabel)
        links_layout.addWidget(websiteLabel)
        links_layout.addWidget(documentLabel)
        links_layout.addStretch()

        layout1.addWidget(Label(f"当前版本{APP_VERSION}"))
        btn_check_update = Button("检查更新")
        btn_check_update.setEnabled(True)
        btn_check_update.clicked.connect(
            lambda: self._on_check_update_clicked(btn_check_update)
        )
        layout1.addWidget(btn_check_update)
        btn_feedback = Button("意见反馈")
        btn_feedback.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/de4321/darkeye/issues")
            )
        )
        layout1.addWidget(btn_feedback)
        btn_changelog = Button("版本记录")
        btn_changelog.setEnabled(False)
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
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/de4321/darkeye/releases"))
        )
        layout4.addWidget(btn_firefox)

        btn_chrome = Button("Chrome/Edge插件")
        btn_chrome.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/de4321/darkeye/releases"))
        )
        layout4.addWidget(btn_chrome)



        form_layout.addRow(Label("项目链接"), links_row)
        layout.addLayout(layout1)
        layout.addLayout(layout2)
        layout.addLayout(layout3)
        layout.addLayout(layout4)
        layout.addLayout(form_layout)



    def _on_check_update_clicked(self, btn: Button) -> None:
        btn.setEnabled(False)
        btn.setText("检查中...")

        def on_done(ok: bool, title: str, msg: str, is_update_available: bool, from_timeout: bool):
            btn.setText("检查更新")
            btn.setEnabled(True)

            if ok and is_update_available:
                _handle_update_and_launch(self.msg, title, msg)
            elif ok:
                self.msg.show_info(title, msg)
            else:
                self.msg.show_critical(title, msg)

        run_update_check(self, on_done)
