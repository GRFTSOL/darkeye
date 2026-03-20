"""关于软件页面：版本、更新、链接等。"""

import os
import subprocess
import sys
import threading

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QFormLayout, QWidget, QApplication
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import Qt, QUrl, QTimer, QObject, Signal

from config import BASE_DIR, APP_VERSION
from darkeye_ui.components import Label, Button
from darkeye_ui.components.token_radio_button import TokenRadioButton
from controller.MessageService import MessageBoxService


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


class LastPage(QWidget):
    """关于软件页面"""

    def __init__(self):
        super().__init__()
        self.msg = MessageBoxService(self)
        layout = QVBoxLayout(self)
        layout1 = QHBoxLayout()
        layout2 = QHBoxLayout()
        layout3 = QHBoxLayout()
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

        form_layout.addRow(Label("项目链接"), links_row)
        layout.addLayout(layout1)
        layout.addLayout(layout2)
        layout.addLayout(layout3)
        layout.addLayout(form_layout)

    def _on_check_update_clicked(self, btn: Button) -> None:
        latest_json_url = "http://yinruizhe.asia/latest.json"

        btn.setEnabled(False)
        btn.setText("检查中...")

        overall_timeout_seconds = 12
        urlopen_timeout_seconds = 8
        done_state = {"notified": False}

        def safe_on_done(ok: bool, title: str, msg: str, is_update_available: bool):
            if done_state["notified"]:
                return
            done_state["notified"] = True

            self._update_check_notifier = None

            btn.setText("检查更新")
            btn.setEnabled(True)

            if ok and is_update_available:
                update_title = title or "发现新版本"
                should_update = self.msg.ask_yes_no(
                    update_title,
                    f"{msg}\n\n已检测到新版本。软件将退出以完成更新，是否立即更新？",
                )
                if not should_update:
                    self.msg.show_info("已取消更新", "你已取消更新。")
                    return

                import config

                updater_exe = BASE_DIR / "DarkEyeUpdater.exe"
                if not updater_exe.exists():
                    self.msg.show_critical(
                        "更新失败", f"未找到更新程序：{updater_exe}"
                    )
                    return

                current_version = str(getattr(config, "APP_VERSION", "")).strip()
                if not current_version:
                    self.msg.show_critical(
                        "更新失败", "无法从配置读取当前版本号。"
                    )
                    return

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
                    latest_json_url,
                    "--keep",
                    "data",
                    "--pid",
                    str(os.getpid()),
                ]
                try:
                    _spawn_detached_process(cmd, app_dir)
                except Exception as e:
                    import logging

                    logging.exception("启动更新程序失败")
                    self.msg.show_critical(
                        "更新失败", f"无法启动更新程序：{e}"
                    )
                    return

                self.msg.show_info(
                    "开始更新",
                    msg
                    + "\n\n已启动更新程序，软件即将退出完成更新。点击确认后软件将退出完成更新",
                )
                app = QApplication.instance()
                if app is not None:
                    QTimer.singleShot(200, app.quit)
                return

            if ok:
                self.msg.show_info(title, msg)
            else:
                self.msg.show_critical(title, msg)

        class _UpdateCheckNotifier(QObject):
            result = Signal(bool, str, str, bool)

        notifier = _UpdateCheckNotifier(self)
        self._update_check_notifier = notifier
        notifier.result.connect(safe_on_done)

        def worker():
            from core.updater import check_for_updates

            res = check_for_updates(
                APP_VERSION,
                latest_json_url,
                urlopen_timeout_seconds=urlopen_timeout_seconds,
                log_latest_json=True,
            )
            return (res.success, res.title, res.message, res.is_update_available)

        def run():
            ok, title, msg, is_update_available = worker()
            notifier.result.emit(ok, title, msg, is_update_available)

        threading.Thread(target=run, daemon=True).start()

        def on_timeout():
            safe_on_done(
                False,
                "更新检查超时",
                f"更新检查在 {overall_timeout_seconds} 秒内未完成，请检查网络后重试。",
                False,
            )

        QTimer.singleShot(overall_timeout_seconds * 1000, on_timeout)
