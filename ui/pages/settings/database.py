"""数据库相关设置页面。"""

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QVBoxLayout,
    QGridLayout,
    QFileDialog,
    QWidget,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
)
from PySide6.QtCore import Slot

from config import (
    BASE_DIR,
    DATABASE,
    INI_FILE,
    PRIVATE_DATABASE,
    DATABASE_BACKUP_PATH,
    PRIVATE_DATABASE_BACKUP_PATH,
    REQUIRED_PUBLIC_DB_VERSION,
    REQUIRED_PRIVATE_DB_VERSION,
    get_webdav_enabled,
    set_webdav_enabled,
    get_webdav_profile_name,
    set_webdav_profile_name,
    get_webdav_base_url,
    set_webdav_base_url,
    get_webdav_remote_root,
    set_webdav_remote_root,
    get_webdav_timeout_seconds,
    set_webdav_timeout_seconds,
    get_webdav_auto_upload_on_backup,
    set_webdav_auto_upload_on_backup,
)
from darkeye_ui.components import Label, Button, ToggleSwitch, TokenSpinBox
from darkeye_ui.components.input import LineEdit
from controller.message_service import MessageBoxService
from darkeye_ui.design.icon import get_builtin_icon


def _get_detected_db_version(db_path) -> str:
    """查询指定数据库文件当前记录的版本，失败返回「未检测到」。"""
    try:
        from core.database.connection import get_connection
        from core.database.migrations import get_db_version

        conn = get_connection(db_path, readonly=True)
        v = get_db_version(conn)
        conn.close()
        return v if v is not None else "无版本"
    except Exception as e:
        logging.debug("get_detected_db_version failed: %s", e)
        return "未检测到"


class DBSettingPage(QWidget):
    """数据库相关设置页面"""

    def __init__(self):
        super().__init__()

        self.msg = MessageBoxService(self)
        path_label = Label(f"软件的工作文件夹{str(BASE_DIR)}")
        path_label2 = Label(f"软件的公共数据库文件位置{str(DATABASE)}")
        path_label3 = Label(f"ini文件的位置{INI_FILE}")

        req_public = REQUIRED_PUBLIC_DB_VERSION
        req_private = REQUIRED_PRIVATE_DB_VERSION
        cur_public = _get_detected_db_version(DATABASE)
        cur_private = _get_detected_db_version(PRIVATE_DATABASE)
        version_label_1 = Label(
            f"软件所需公共数据库版本：{req_public}  |  当前公共数据库版本：{cur_public}"
        )
        version_label_2 = Label(
            f"软件所需私有数据库版本：{req_private}  |  当前私有数据库版本：{cur_private}"
        )

        self.btn_vacuum = Button("数据库清理碎片")
        self.btn_cover_check = Button("图片数据一致性检查")

        self.btn_backupDB = Button()
        self.btn_backupDB.setText("全量备份公共数据库")
        self.btn_backupDB.setToolTip("将现有的数据库包括图片打上时间戳备份")
        self.btn_backupDB.setIcon(get_builtin_icon(name="database"))

        self.btn_restoreDB = Button()
        self.btn_restoreDB.setText("全量还原公共数据库")
        self.btn_restoreDB.setToolTip(
            "在备份的数据库里选择一个数据还原，覆盖现有的数据库"
        )
        self.btn_restoreDB.setIcon(get_builtin_icon(name="database"))

        self.btn_backupDB_simple = Button()
        self.btn_backupDB_simple.setText("精简备份公共数据库")
        self.btn_backupDB_simple.setToolTip("仅备份公共数据库 .db 文件")
        self.btn_backupDB_simple.setIcon(get_builtin_icon(name="database"))

        self.btn_restoreDB_simple = Button()
        self.btn_restoreDB_simple.setText("精简还原公共数据库")
        self.btn_restoreDB_simple.setToolTip("从 .db 备份文件还原公共数据库")
        self.btn_restoreDB_simple.setIcon(get_builtin_icon(name="database"))

        self.btn_backupDB2 = Button()
        self.btn_backupDB2.setText("备份私有数据库")
        self.btn_backupDB2.setToolTip("将现有的数据库打上时间戳备份")
        self.btn_backupDB2.setIcon(get_builtin_icon(name="database"))

        self.btn_restoreDB2 = Button()
        self.btn_restoreDB2.setText("还原私有数据库")
        self.btn_restoreDB2.setToolTip(
            "在备份的数据库里选择一个数据还原，覆盖现有的数据库"
        )
        self.btn_restoreDB2.setIcon(get_builtin_icon(name="database"))

        self.btn_rebuildprivatelink = Button()
        self.btn_rebuildprivatelink.setText("重建私有库与公有库的链接")
        self.btn_rebuildprivatelink.setToolTip(
            "选择私有库，重建私有库的链接，这是当公共库换了的时候用的"
        )
        self.btn_rebuildprivatelink.setIcon(get_builtin_icon(name="database"))

        layout1 = QGridLayout()
        layout1.addWidget(self.btn_vacuum, 0, 0)
        layout1.addWidget(self.btn_cover_check, 0, 1)
        layout1.addWidget(self.btn_backupDB, 1, 0)
        layout1.addWidget(self.btn_restoreDB, 1, 1)
        layout1.addWidget(self.btn_backupDB_simple, 2, 0)
        layout1.addWidget(self.btn_restoreDB_simple, 2, 1)
        layout1.addWidget(self.btn_backupDB2, 3, 0)
        layout1.addWidget(self.btn_restoreDB2, 3, 1)
        layout1.addWidget(self.btn_rebuildprivatelink, 4, 0, 1, 2)

        self.webdav_enabled = ToggleSwitch()
        self.webdav_profile_edit = LineEdit(self)
        self.webdav_profile_edit.setPlaceholderText("default")
        self.webdav_base_url_edit = LineEdit(self)
        self.webdav_base_url_edit.setPlaceholderText("https://dav.example.com")
        self.webdav_remote_root_edit = LineEdit(self)
        self.webdav_remote_root_edit.setPlaceholderText("/darkeye")
        self.webdav_timeout_spin = TokenSpinBox(self)
        self.webdav_timeout_spin.setRange(3, 300)
        self.webdav_auto_upload = ToggleSwitch()
        self.webdav_cred_status = Label("")

        self.btn_webdav_save_creds = Button("保存凭据")
        self.btn_webdav_update_creds = Button("更新凭据")
        self.btn_webdav_clear_creds = Button("清除凭据")
        self.btn_webdav_test = Button("测试连接")
        self.btn_webdav_upload_latest = Button("上传最近一次本地备份")
        self.btn_webdav_list = Button("浏览云端备份")
        self.btn_webdav_restore = Button("从云端下载并恢复")

        creds_row_widget = QWidget(self)
        creds_row_layout = QHBoxLayout(creds_row_widget)
        creds_row_layout.setContentsMargins(0, 0, 0, 0)
        creds_row_layout.addWidget(self.btn_webdav_save_creds)
        creds_row_layout.addWidget(self.btn_webdav_update_creds)
        creds_row_layout.addWidget(self.btn_webdav_clear_creds)

        action_row_widget = QWidget(self)
        action_row_layout = QHBoxLayout(action_row_widget)
        action_row_layout.setContentsMargins(0, 0, 0, 0)
        action_row_layout.addWidget(self.btn_webdav_test)
        action_row_layout.addWidget(self.btn_webdav_upload_latest)
        action_row_layout.addWidget(self.btn_webdav_list)
        action_row_layout.addWidget(self.btn_webdav_restore)

        webdav_form = QFormLayout()
        webdav_form.addRow(Label("启用 WebDAV"), self.webdav_enabled)
        webdav_form.addRow(Label("Profile"), self.webdav_profile_edit)
        webdav_form.addRow(Label("Base URL"), self.webdav_base_url_edit)
        webdav_form.addRow(Label("Remote Root"), self.webdav_remote_root_edit)
        webdav_form.addRow(Label("超时(秒)"), self.webdav_timeout_spin)
        webdav_form.addRow(Label("备份后自动上传"), self.webdav_auto_upload)
        webdav_form.addRow(Label("凭据状态"), self.webdav_cred_status)
        webdav_form.addRow(Label("凭据管理"), creds_row_widget)
        webdav_form.addRow(Label("云端操作"), action_row_widget)

        layout = QVBoxLayout(self)
        layout.addLayout(layout1)
        layout.addWidget(Label("<h3>WebDAV 云备份</h3>"))
        layout.addLayout(webdav_form)
        layout.addWidget(path_label)
        layout.addWidget(path_label2)
        layout.addWidget(path_label3)
        layout.addWidget(version_label_1)
        layout.addWidget(version_label_2)

        self._load_webdav_settings()
        self.signal_connect()

    def signal_connect(self):
        from core.database.db_utils import sqlite_vaccum

        self.btn_cover_check.clicked.connect(self.check_image_consistency)
        self.btn_vacuum.clicked.connect(sqlite_vaccum)

        self.btn_backupDB.clicked.connect(self.backup_db_public)
        self.btn_restoreDB.clicked.connect(lambda: self.restore_db_new("public"))
        self.btn_backupDB_simple.clicked.connect(self.backup_db_public_simple)
        self.btn_restoreDB_simple.clicked.connect(lambda: self.restore_db("public"))
        self.btn_backupDB2.clicked.connect(self.backup_db_private)
        self.btn_restoreDB2.clicked.connect(lambda: self.restore_db("private"))
        self.btn_rebuildprivatelink.clicked.connect(self.rebuildprivatelink)
        self.btn_webdav_save_creds.clicked.connect(self._save_webdav_credentials)
        self.btn_webdav_update_creds.clicked.connect(self._save_webdav_credentials)
        self.btn_webdav_clear_creds.clicked.connect(self._clear_webdav_credentials)
        self.btn_webdav_test.clicked.connect(self._test_webdav_connection)
        self.btn_webdav_upload_latest.clicked.connect(self._upload_latest_backup)
        self.btn_webdav_list.clicked.connect(self._list_webdav_backups)
        self.btn_webdav_restore.clicked.connect(self._restore_from_webdav)
        self.webdav_enabled.toggled.connect(self._on_webdav_setting_changed)
        self.webdav_profile_edit.editingFinished.connect(self._on_webdav_setting_changed)
        self.webdav_base_url_edit.editingFinished.connect(self._on_webdav_setting_changed)
        self.webdav_remote_root_edit.editingFinished.connect(self._on_webdav_setting_changed)
        self.webdav_timeout_spin.valueChanged.connect(self._on_webdav_setting_changed)
        self.webdav_auto_upload.toggled.connect(self._on_webdav_setting_changed)

    @Slot()
    def rebuildprivatelink(self):
        from core.database.migrations import rebuild_privatelink

        rebuild_privatelink()
        self.msg.show_info("重建成功", "私有库与公有库的链接重建完成。")

    @Slot()
    def check_image_consistency(self):
        from core.database.db_utils import image_consistency

        image_consistency(True, "cover")
        image_consistency(True, "actress")
        image_consistency(True, "actor")
        self.msg.show_info("提示", "处理好图片一致性问题，删除多余图片")

    @Slot()
    def restore_db(self, access_level: str):
        if access_level == "public":
            backup_path = DATABASE_BACKUP_PATH
            target_path = DATABASE
        elif access_level == "private":
            backup_path = PRIVATE_DATABASE_BACKUP_PATH
            target_path = PRIVATE_DATABASE
        else:
            logging.info("错误，未选择等级")
            return

        from core.database.backup_utils import restore_backup_safely

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择一个数据库",
            str(backup_path),
            "*.db",
        )

        if not file_path:
            return

        if not self.msg.ask_yes_no(
            "确认恢复", "是否用该备份覆盖现有数据库？操作不可撤销！"
        ):
            return

        success = restore_backup_safely(Path(file_path), target_path)
        if success:
            self.msg.show_info("恢复成功", "数据库恢复完成。")
        else:
            self.msg.show_critical("恢复失败", "数据库恢复失败，请检查文件是否有效。")

    @Slot()
    def restore_db_new(self, access_level: str):
        if access_level == "public":
            backup_path = DATABASE_BACKUP_PATH
            target_path = DATABASE
        elif access_level == "private":
            backup_path = PRIVATE_DATABASE_BACKUP_PATH
            target_path = PRIVATE_DATABASE
        else:
            logging.info("错误，未选择等级")
            return

        from core.database.backup_utils import restore_snapshot

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择一个meta.json",
            str(backup_path),
            "JSON 文件 (*.json)",
        )

        if not file_path:
            return

        if not self.msg.ask_yes_no(
            "确认恢复", "是否用该备份覆盖现有数据库？操作不可撤销！"
        ):
            return

        success = restore_snapshot(Path(file_path))
        if success:
            self.msg.show_info("恢复成功", "数据库恢复完成。")
        else:
            self.msg.show_critical("恢复失败", "数据库恢复失败，请检查文件是否有效。")

    @Slot()
    def backup_db_public(self):
        backup_path = DATABASE_BACKUP_PATH
        from core.database.backup_service import (
            backup_public_snapshot_and_optional_upload,
        )

        try:
            dir_path = QFileDialog.getExistingDirectory(
                self,
                "选择备份保存位置",
                str(backup_path),
            )
            if not dir_path:
                return
            result = backup_public_snapshot_and_optional_upload(
                snapshot_root=Path(dir_path), force_upload=False
            )
            if result.ok:
                self.msg.show_info("备份成功", result.message)
            else:
                self.msg.show_warning("备份提示", result.message)
        except Exception as e:
            self.msg.show_critical("备份失败", f"{str(e)}")

    @Slot()
    def backup_db_private(self):
        backup_path = PRIVATE_DATABASE_BACKUP_PATH
        from core.database.backup_service import backup_private_and_optional_upload

        try:
            dir_path = QFileDialog.getExistingDirectory(
                self,
                "选择备份保存位置",
                str(backup_path),
            )
            if not dir_path:
                return
            result = backup_private_and_optional_upload(
                local_backup_dir=Path(dir_path), force_upload=False
            )
            if result.ok:
                self.msg.show_info("备份成功", result.message)
            else:
                self.msg.show_warning("备份提示", result.message)
        except Exception as e:
            self.msg.show_critical("备份失败", f"{str(e)}")

    @Slot()
    def backup_db_public_simple(self):
        backup_path = DATABASE_BACKUP_PATH
        from core.database.backup_service import (
            backup_public_simple_and_optional_upload,
        )

        try:
            dir_path = QFileDialog.getExistingDirectory(
                self,
                "选择备份保存位置",
                str(backup_path),
            )
            if not dir_path:
                return
            result = backup_public_simple_and_optional_upload(
                local_backup_dir=Path(dir_path), force_upload=False
            )
            if result.ok:
                self.msg.show_info("备份成功", result.message)
            else:
                self.msg.show_warning("备份提示", result.message)
        except Exception as e:
            self.msg.show_critical("备份失败", f"{str(e)}")

    def _load_webdav_settings(self) -> None:
        self.webdav_enabled.setChecked(get_webdav_enabled())
        self.webdav_profile_edit.setText(get_webdav_profile_name())
        self.webdav_base_url_edit.setText(get_webdav_base_url())
        self.webdav_remote_root_edit.setText(get_webdav_remote_root())
        self.webdav_timeout_spin.setValue(get_webdav_timeout_seconds())
        self.webdav_auto_upload.setChecked(get_webdav_auto_upload_on_backup())
        self._refresh_credential_status()

    def _persist_webdav_settings(self, show_message: bool = False) -> None:
        set_webdav_enabled(self.webdav_enabled.isChecked())
        set_webdav_profile_name(self.webdav_profile_edit.text())
        set_webdav_base_url(self.webdav_base_url_edit.text())
        set_webdav_remote_root(self.webdav_remote_root_edit.text())
        set_webdav_timeout_seconds(int(self.webdav_timeout_spin.value()))
        set_webdav_auto_upload_on_backup(self.webdav_auto_upload.isChecked())
        self._refresh_credential_status()
        if show_message:
            self.msg.show_info("保存成功", "WebDAV 设置已保存。")

    @Slot()
    def _on_webdav_setting_changed(self, *_args) -> None:
        self._persist_webdav_settings(show_message=False)

    @Slot()
    def _save_webdav_credentials(self) -> None:
        from core.database.webdav_credential_store import save_credentials

        profile = self.webdav_profile_edit.text().strip() or "default"
        username, ok = QInputDialog.getText(
            self,
            "保存 WebDAV 凭据",
            "请输入用户名：",
            QLineEdit.EchoMode.Normal,
        )
        if not ok:
            return
        password, ok = QInputDialog.getText(
            self,
            "保存 WebDAV 凭据",
            "请输入密码：",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        if not username.strip() or not password:
            self.msg.show_warning("保存失败", "用户名和密码不能为空。")
            return
        save_credentials(profile, username.strip(), password)
        self._refresh_credential_status()
        self.msg.show_info("保存成功", "WebDAV 凭据已写入系统凭据管理器。")

    @Slot()
    def _clear_webdav_credentials(self) -> None:
        from core.database.webdav_credential_store import clear_credentials

        profile = self.webdav_profile_edit.text().strip() or "default"
        clear_credentials(profile)
        self._refresh_credential_status()
        self.msg.show_info("清除成功", "WebDAV 凭据已清除。")

    @Slot()
    def _test_webdav_connection(self) -> None:
        from core.database.backup_service import test_webdav_connection

        self._persist_webdav_settings(show_message=False)
        result = test_webdav_connection()
        if result.ok:
            self.msg.show_info("连接成功", result.message)
        else:
            self.msg.show_warning("连接失败", result.message)

    @Slot()
    def _upload_latest_backup(self) -> None:
        from core.database.backup_service import (
            backup_public_simple_and_optional_upload,
            backup_private_and_optional_upload,
        )

        self._persist_webdav_settings(show_message=False)
        scope, ok = QInputDialog.getItem(
            self,
            "选择上传对象",
            "请选择要上传的备份：",
            ["public", "private"],
            0,
            False,
        )
        if not ok:
            return
        if scope == "private":
            result = backup_private_and_optional_upload(force_upload=True)
        else:
            result = backup_public_simple_and_optional_upload(force_upload=True)
        if result.ok:
            self.msg.show_info("上传成功", result.message)
        else:
            self.msg.show_warning("上传失败", result.message)

    @Slot()
    def _list_webdav_backups(self) -> None:
        from core.database.backup_service import list_webdav_backups

        self._persist_webdav_settings(show_message=False)
        result, files = list_webdav_backups()
        if not result.ok:
            self.msg.show_warning("列举失败", result.message)
            return
        if not files:
            self.msg.show_info("提示", "云端暂无备份文件。")
            return
        preview = "\n".join(files)
        self.msg.show_info("云端备份列表", f"{result.message}\n\n{preview}")

    @Slot()
    def _restore_from_webdav(self) -> None:
        from core.database.backup_service import (
            list_webdav_backups,
            restore_from_webdav_object,
        )

        self._persist_webdav_settings(show_message=False)
        result, files = list_webdav_backups(db_scope="public", backup_type="simple")
        if not result.ok:
            self.msg.show_warning("获取列表失败", result.message)
            return
        if not files:
            self.msg.show_info("提示", "云端暂无可恢复备份。")
            return
        item, ok = QInputDialog.getItem(
            self,
            "选择云端备份",
            "请选择要恢复的备份：",
            files,
            0,
            False,
        )
        if not ok or not item:
            return
        if not self.msg.ask_yes_no(
            "确认恢复", "是否从云端下载并覆盖现有数据库？操作不可撤销！"
        ):
            return
        restore_result = restore_from_webdav_object(
            item, db_scope="public", backup_type="simple"
        )
        if restore_result.ok:
            self.msg.show_info("恢复成功", restore_result.message)
        else:
            self.msg.show_critical("恢复失败", restore_result.message)

    def _refresh_credential_status(self) -> None:
        from core.database.webdav_credential_store import has_credentials

        profile = self.webdav_profile_edit.text().strip() or "default"
        if has_credentials(profile):
            self.webdav_cred_status.setText("已保存")
        else:
            self.webdav_cred_status.setText("未保存")
