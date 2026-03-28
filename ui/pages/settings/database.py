"""数据库相关设置页面。"""

import logging
from pathlib import Path

from PySide6.QtWidgets import QVBoxLayout, QGridLayout, QFileDialog, QWidget
from PySide6.QtGui import QIcon
from PySide6.QtCore import Slot

from config import (
    BASE_DIR,
    DATABASE,
    INI_FILE,
    ICONS_PATH,
    PRIVATE_DATABASE,
    DATABASE_BACKUP_PATH,
    PRIVATE_DATABASE_BACKUP_PATH,
    REQUIRED_PUBLIC_DB_VERSION,
    REQUIRED_PRIVATE_DB_VERSION,
)
from darkeye_ui.components import Label, Button
from controller.MessageService import MessageBoxService


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
        self.btn_commit = Button("保存设置")
        self.btn_commit.setVisible(False)

        self.btn_backupDB = Button()
        self.btn_backupDB.setText("备份公共数据库")
        self.btn_backupDB.setToolTip("将现有的数据库打上时间戳备份")
        self.btn_backupDB.setIcon(QIcon(str(ICONS_PATH / "database.svg")))

        self.btn_restoreDB = Button()
        self.btn_restoreDB.setText("还原公共数据库")
        self.btn_restoreDB.setToolTip(
            "在备份的数据库里选择一个数据还原，覆盖现有的数据库"
        )
        self.btn_restoreDB.setIcon(QIcon(str(ICONS_PATH / "database.svg")))

        self.btn_backupDB2 = Button()
        self.btn_backupDB2.setText("备份私有数据库")
        self.btn_backupDB2.setToolTip("将现有的数据库打上时间戳备份")
        self.btn_backupDB2.setIcon(QIcon(str(ICONS_PATH / "database.svg")))

        self.btn_restoreDB2 = Button()
        self.btn_restoreDB2.setText("还原私有数据库")
        self.btn_restoreDB2.setToolTip(
            "在备份的数据库里选择一个数据还原，覆盖现有的数据库"
        )
        self.btn_restoreDB2.setIcon(QIcon(str(ICONS_PATH / "database.svg")))

        self.btn_rebuildprivatelink = Button()
        self.btn_rebuildprivatelink.setText("重建私有库与公有库的链接")
        self.btn_rebuildprivatelink.setToolTip(
            "选择私有库，重建私有库的链接，这是当公共库换了的时候用的"
        )
        self.btn_rebuildprivatelink.setIcon(QIcon(str(ICONS_PATH / "database.svg")))

        self.btn_import_nfo = Button("从 NFO 导入作品")
        self.btn_import_nfo.setToolTip(
            "选择 Kodi 风格的 .nfo 文件导入一条作品（番号已存在则跳过）"
        )

        layout1 = QGridLayout()
        layout1.addWidget(self.btn_vacuum, 0, 0)
        layout1.addWidget(self.btn_cover_check, 0, 1)
        layout1.addWidget(self.btn_backupDB, 1, 0)
        layout1.addWidget(self.btn_restoreDB, 1, 1)
        layout1.addWidget(self.btn_backupDB2, 2, 0)
        layout1.addWidget(self.btn_restoreDB2, 2, 1)
        layout1.addWidget(self.btn_rebuildprivatelink, 3, 0)
        layout1.addWidget(self.btn_import_nfo, 3, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(layout1)
        layout.addWidget(self.btn_commit)
        layout.addWidget(path_label)
        layout.addWidget(path_label2)
        layout.addWidget(path_label3)
        layout.addWidget(version_label_1)
        layout.addWidget(version_label_2)

        self.signal_connect()

    def signal_connect(self):
        from core.database.db_utils import sqlite_vaccum

        self.btn_cover_check.clicked.connect(self.check_image_consistency)
        self.btn_vacuum.clicked.connect(sqlite_vaccum)
        self.btn_commit.clicked.connect(self.submit)

        self.btn_backupDB.clicked.connect(self.backup_db_public)
        self.btn_restoreDB.clicked.connect(lambda: self.restore_db_new("public"))
        self.btn_backupDB2.clicked.connect(self.backup_db_private)
        self.btn_restoreDB2.clicked.connect(lambda: self.restore_db("private"))
        self.btn_rebuildprivatelink.clicked.connect(self.rebuildprivatelink)
        self.btn_import_nfo.clicked.connect(self.import_work_from_nfo_file)

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
    def submit(self):
        logging.debug("保存设置")

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

        from core.database.backup_utils import create_resource_snapshot

        try:
            dir_path = QFileDialog.getExistingDirectory(
                self,
                "选择备份保存位置",
                str(backup_path),
            )
            if not dir_path:
                return
            create_resource_snapshot(Path(dir_path))
            self.msg.show_info("备份成功", f"备份快照到{Path(dir_path) / 'snapshot'}")
        except Exception as e:
            self.msg.show_critical("备份失败", f"{str(e)}")

    @Slot()
    def backup_db_private(self):
        backup_path = PRIVATE_DATABASE_BACKUP_PATH
        target_path = PRIVATE_DATABASE
        from core.database.backup_utils import backup_database

        try:
            dir_path = QFileDialog.getExistingDirectory(
                self,
                "选择备份保存位置",
                str(backup_path),
            )
            if not dir_path:
                return
            path = backup_database(target_path, Path(dir_path))
            self.msg.show_info("备份成功", f"备份数据库到{path}")
        except Exception as e:
            self.msg.show_critical("备份失败", f"{str(e)}")

    @Slot()
    def import_work_from_nfo_file(self):
        from core.importers import import_work_from_movie_nfo

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 NFO 文件",
            str(BASE_DIR),
            "NFO 文件 (*.nfo);;所有文件 (*.*)",
        )
        if not file_path:
            return

        ok, message = import_work_from_movie_nfo(Path(file_path))
        if ok:
            self.msg.show_info("导入成功", message)
        elif "已在库中" in message:
            self.msg.show_info("未导入", message)
        else:
            self.msg.show_warning("导入失败", message)

    @Slot()
    def backup_db(self, access_level: str):
        if access_level == "public":
            backup_path = DATABASE_BACKUP_PATH
            target_path = DATABASE
        elif access_level == "private":
            backup_path = PRIVATE_DATABASE_BACKUP_PATH
            target_path = PRIVATE_DATABASE
        else:
            logging.info("错误，未选择等级")
            return

        from core.database.backup_utils import backup_database

        try:
            path = backup_database(target_path, backup_path)
            self.msg.show_info("备份成功", f"备份数据库到{path}")
        except Exception as e:
            self.msg.show_critical("备份失败", f"{str(e)}")
