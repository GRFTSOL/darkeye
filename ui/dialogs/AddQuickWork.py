import csv
import json
import logging
from pathlib import Path
import re
from typing import TYPE_CHECKING
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QInputDialog,
    QWidget,
    QLabel,
    QFrame,
    QFileDialog,
)
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent

from controller.app_context import get_theme_manager
from controller.message_service import MessageBoxService

from darkeye_ui.design.icon import get_builtin_icon
from darkeye_ui.components.button import Button
from darkeye_ui.components.label import Label
from darkeye_ui.components.token_table_widget import TokenTableWidget
from darkeye_ui.components.icon_push_button import IconPushButton
from ui.widgets.CrawlerToolBox import CrawlerAutoPage
from utils.serial_number import extract_serial_from_string
from utils.utils import get_video_names_from_paths

if TYPE_CHECKING:
    from darkeye_ui.design.theme_manager import ThemeManager
    from darkeye_ui.design.tokens import ThemeTokens


VIDEO_EXTENSIONS = {
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".wmv",
    ".flv",
    ".rmvb",
    ".ts",
}


def _normalize_csv_serial_value(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None

    extracted = extract_serial_from_string(text)
    if extracted:
        return extracted
    return text.upper()


def _read_csv_first_column_serials(path: Path) -> list[str]:
    if path.suffix.lower() != ".csv":
        raise ValueError("仅支持导入 CSV 文件")

    last_decode_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            serials: list[str] = []
            with path.open("r", encoding=encoding, newline="") as csv_file:
                reader = csv.reader(csv_file)
                for row in reader:
                    if not row:
                        continue
                    serial = _normalize_csv_serial_value(row[0])
                    if serial:
                        serials.append(serial)
            return serials
        except UnicodeDecodeError as exc:
            last_decode_error = exc

    if last_decode_error is not None:
        raise last_decode_error
    return []


def _drop_zone_qss_from_tokens(t: "ThemeTokens") -> str:
    return (
        "#quickWorkVideoDropZone {"
        f"border: {t.border_width} dashed {t.color_border};"
        f"border-radius: {t.radius_md};"
        f"background-color: {t.color_bg_input};"
        "}"
        "#quickWorkVideoDropZoneTitle {"
        f"color: {t.color_text};"
        f"font-family: {t.font_family_base};"
        f"font-size: {t.font_size_base};"
        "font-weight: 600;"
        "}"
        "#quickWorkVideoDropZoneHint {"
        f"color: {t.color_text_placeholder};"
        f"font-family: {t.font_family_base};"
        f"font-size: {t.font_size_base};"
        "}"
    )


class QuickWorkVideoDropZone(QFrame):
    serialsDropped = Signal(list, list)

    def __init__(
        self,
        theme_manager: "ThemeManager | None" = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self.setAcceptDrops(True)
        self.setMinimumHeight(132)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Plain)
        self.setObjectName("quickWorkVideoDropZone")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        title = Label("拖入视频")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("quickWorkVideoDropZoneTitle")
        hint = Label("支持视频文件或文件夹\n根据文件名识别番号\n并追加到左侧列表")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        hint.setObjectName("quickWorkVideoDropZoneHint")

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addStretch()

        self._apply_token_styles()
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_token_styles)

    def _apply_token_styles(self) -> None:
        if self._theme_manager is None:
            self.setStyleSheet(
                "#quickWorkVideoDropZone {"
                "border: 2px dashed gray;"
                "border-radius: 10px;"
                "background: transparent;"
                "}"
                "#quickWorkVideoDropZoneTitle {"
                "font-size: 16px;"
                "font-weight: 600;"
                "}"
                "#quickWorkVideoDropZoneHint {"
                "font-size: 13px;"
                "color: gray;"
                "}"
            )
            return

        t = self._theme_manager.tokens()
        self.setStyleSheet(_drop_zone_qss_from_tokens(t))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasUrls():
            return

        serials: list[str] = []
        failed_paths: list[str] = []

        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if not local_path:
                continue

            path = Path(local_path)
            if path.is_dir():
                folder_serials, no_serial = get_video_names_from_paths([path])
                serials.extend(folder_serials)
                failed_paths.extend(path_str for _, path_str in no_serial)
                continue

            if not path.is_file():
                failed_paths.append(str(path))
                continue

            if path.suffix.lower() not in VIDEO_EXTENSIONS:
                failed_paths.append(str(path))
                continue

            serial = extract_serial_from_string(path.stem)
            if serial:
                serials.append(serial)
            else:
                failed_paths.append(str(path))
                logging.warning("无法提取番号: 名称=%s 路径=%s", path.stem, path)

        event.acceptProposedAction()
        self.serialsDropped.emit(serials, failed_paths)


class AddQuickWork(QDialog):
    # 快速记录作品番号的窗口，能在局外响应
    _BTN_COMMIT_FULL = "快速添加"
    _BTN_COMMIT_SELECTIVE = "选择性补充信息"

    def __init__(self):
        super().__init__()
        logging.info("----------快速记录作品番号窗口----------")
        self.setWindowTitle("快速记录作品番号(W)")
        self.setWindowIcon(get_builtin_icon("film"))
        self.setMinimumSize(780, 520)
        self.resize(800, 540)
        self.msg = MessageBoxService(self)
        self._sort_ascending = True
        self._use_selective_crawl = False

        self.init_ui()

    def init_ui(self):
        # 1. 顶部工具栏
        top_layout = QHBoxLayout()
        self.btn_add = Button("添加")
        self.btn_del = Button("删除")
        self.btn_del_all = Button("删除全部")
        self.btn_clean = Button("去后缀")
        self.btn_clean_prefix = Button("删前缀行")
        self.btn_sort = Button("排序")
        self.btn_import_csv = Button("从 CSV 导入")

        self.btn_add.clicked.connect(self.add_row)
        self.btn_del.clicked.connect(self.delete_rows)
        self.btn_del_all.clicked.connect(self.delete_all_rows)
        self.btn_clean.clicked.connect(self.clean_suffix)
        self.btn_clean_prefix.clicked.connect(self.clean_prefix)
        self.btn_sort.clicked.connect(self.sort_rows)
        self.btn_import_csv.clicked.connect(self.import_csv)

        top_layout.addWidget(self.btn_add)
        top_layout.addWidget(self.btn_del)
        top_layout.addWidget(self.btn_del_all)
        top_layout.addWidget(self.btn_clean)
        top_layout.addWidget(self.btn_clean_prefix)
        top_layout.addWidget(self.btn_sort)
        top_layout.addWidget(self.btn_import_csv)

        # 2. 中间列表区域
        self.table = TokenTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["选择", "番号"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.drop_zone = QuickWorkVideoDropZone(theme_manager=get_theme_manager())
        self.drop_zone.serialsDropped.connect(self.handle_dropped_serials)

        # 3. 底部提交按钮（漏斗筛选后为选择性补充）
        self.btn_commit = Button(self._BTN_COMMIT_FULL)
        self.btn_commit.clicked.connect(self.submit)
        self.btn_commit.setMinimumHeight(40)
        self._update_commit_button_appearance()

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addLayout(top_layout)
        left_layout.addWidget(self.table)
        left_layout.addWidget(self.btn_commit)

        self.crawler_auto_page = CrawlerAutoPage()
        self.crawler_auto_page.btn_get_crawler = IconPushButton(
            icon_name="funnel", icon_size=24, out_size=32
        )
        self.crawler_auto_page.btn_get_crawler.setToolTip(
            "与「批量更新」页空字段补充相同：只按全库查询与右侧勾选字段筛选，"
            "结果直接覆盖左侧表格（不读取、不合并左侧原有行）。无匹配时会清空左侧。"
            "再点底部「选择性补充信息」按每条作品的空白字段入队爬取。"
        )
        self.crawler_auto_page.append_row_widget(
            self.crawler_auto_page.btn_get_crawler, column=1
        )
        self.crawler_auto_page.btn_get_crawler.clicked.connect(self.apply_funnel_filter)

        crawler_hint = Label(
            "未点漏斗就提交：对左侧番号全量爬取。如果左侧添加了已有的番号则会对现有的番号进行全量覆盖。\n"
            "勾选字段后点漏斗：只查全库，筛出的番号直接覆盖左侧（与原先左侧内容无关）；"
            "无匹配则清空左侧。再提交则逐条只爬各条仍空白的勾选字段。"
        )
        crawler_hint.setWordWrap(True)

        right_wrap = QWidget()
        right_layout = QVBoxLayout(right_wrap)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(crawler_hint)
        right_layout.addWidget(self.crawler_auto_page)
        right_layout.addStretch()
        right_layout.addWidget(self.drop_zone)


        main_layout = QHBoxLayout(self)
        main_layout.addWidget(left_panel, stretch=3)
        main_layout.addWidget(right_wrap, stretch=2)

        # 初始化添加一行
        self.add_row()

    def _update_commit_button_appearance(self) -> None:
        """随是否已漏斗筛选更新底部按钮文案与说明。"""
        if self._use_selective_crawl:
            self.btn_commit.setText(self._BTN_COMMIT_SELECTIVE)
            self.btn_commit.setToolTip(
                "仅按每条作品的空白勾选字段入队爬取，补充信息（与批量「空字段补充」一致）。"
            )
        else:
            self.btn_commit.setText(self._BTN_COMMIT_FULL)
            self.btn_commit.setToolTip("对左侧勾选番号全量爬取并写入库。")

    def _get_selected_crawler_fields(self) -> set[str]:
        """读取爬虫勾选项，映射为标准字段名（与批量更新页一致）。"""
        selected: set[str] = set()
        field_map = {
            "release_date": self.crawler_auto_page.cb_release_date,
            "director": self.crawler_auto_page.cb_director,
            "cover": self.crawler_auto_page.cb_cover,
            "cn_title": self.crawler_auto_page.cb_cn_title,
            "jp_title": self.crawler_auto_page.cb_jp_title,
            "cn_story": self.crawler_auto_page.cb_cn_story,
            "jp_story": self.crawler_auto_page.cb_jp_story,
            "actress": self.crawler_auto_page.cb_actress,
            "actor": self.crawler_auto_page.cb_actor,
            "tag": self.crawler_auto_page.cb_tag,
            "runtime": self.crawler_auto_page.cb_runtime,
            "maker": self.crawler_auto_page.cb_maker,
            "series": self.crawler_auto_page.cb_series,
            "label": self.crawler_auto_page.cb_label,
            "fanart": self.crawler_auto_page.cb_fanart,
        }
        for field_name, checkbox in field_map.items():
            if checkbox.isChecked():
                selected.add(field_name)
        return selected

    def _is_row_empty_for_field(self, row: dict, field_name: str) -> bool:
        """按约定规则判断单字段是否为空（与 UpdateManyTabPage 一致）。"""
        if field_name in {"actress", "actor", "tag"}:
            count_key = f"{field_name}_count"
            return int(row.get(count_key) or 0) <= 0
        if field_name in {"maker", "label", "series"}:
            return row.get(f"{field_name}_id") is None
        if field_name == "cover":
            val = row.get("image_url")
            return val is None or str(val).strip() == ""
        if field_name == "fanart":
            raw = row.get("fanart")
            if raw is None:
                return True
            s = str(raw).strip()
            if not s or s == "[]":
                return True
            try:
                parsed = json.loads(s)
            except (json.JSONDecodeError, TypeError):
                return True
            if not isinstance(parsed, list) or len(parsed) == 0:
                return True
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                if (
                    str(item.get("url") or "").strip()
                    or str(item.get("file") or "").strip()
                ):
                    return False
            return True
        if field_name == "runtime":
            val = row.get("runtime")
            try:
                return val is None or int(val) <= 0
            except (TypeError, ValueError):
                return True
        val = row.get(field_name)
        return val is None or str(val).strip() == ""

    @Slot()
    def apply_funnel_filter(self):
        """全库筛选（同 bulk_crawl_empty_fields 数据源）；结果直接覆盖左侧，不读左侧原表格。"""
        from core.database.query.work import get_works_for_bulk_crawl_fields

        selected_fields = self._get_selected_crawler_fields()
        logging.info("AddQuickWork 漏斗筛选触发，勾选字段: %s", sorted(selected_fields))
        if not selected_fields:
            self.msg.show_info("提示", "请先勾选至少一个字段")
            return

        all_rows = get_works_for_bulk_crawl_fields()
        filtered: list[str] = []
        for row in all_rows:
            serial = str(row.get("serial_number") or "").strip()
            if not serial:
                continue
            per_work_fields = {
                f for f in selected_fields if self._is_row_empty_for_field(row, f)
            }
            if not per_work_fields:
                continue
            filtered.append(serial)

        if not filtered:
            self._use_selective_crawl = False
            self._populate_serial_table([])
            self._update_commit_button_appearance()
            self.msg.show_info(
                "提示",
                "没有匹配到需要更新的作品（勾选字段在该批作品中均已非空），左侧已清空。",
            )
            return

        self._populate_serial_table(filtered)
        self._use_selective_crawl = True
        self._update_commit_button_appearance()
        logging.info(
            "AddQuickWork 漏斗筛选: 全库 -> %s 条, 字段 %s",
            len(filtered),
            sorted(selected_fields),
        )
        self.msg.show_info(
            "筛选完成",
            f"已从全库筛出 {len(filtered)} 条番号填入左侧。"
            f"请点击「{self._BTN_COMMIT_SELECTIVE}」按每条作品的空白勾选字段入队。",
        )

    def _populate_serial_table(self, serial_list):
        """清空表格后按列表重建行（全选勾选）。漏斗/外部加载用来整体覆盖左侧。"""
        self.table.setRowCount(0)
        for serial in serial_list:
            self._append_serial_row(serial)

    def _append_serial_row(self, serial: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        chk_item.setCheckState(Qt.Checked)
        self.table.setItem(row, 0, chk_item)

        text_item = QTableWidgetItem(serial)
        self.table.setItem(row, 1, text_item)

    def _append_serials_to_table(self, serials: list[str]) -> tuple[int, int]:
        normalized_serials = [
            str(serial).strip().upper() for serial in serials if str(serial).strip()
        ]
        unique_serials = list(dict.fromkeys(normalized_serials))
        existing_serials = {
            self.table.item(row, 1).text().strip().lower()
            for row in range(self.table.rowCount())
            if self.table.item(row, 1) is not None
            and self.table.item(row, 1).text().strip()
        }

        added_count = 0
        skipped_count = 0
        for serial in unique_serials:
            if serial.lower() in existing_serials:
                skipped_count += 1
                continue
            self._append_serial_row(serial)
            existing_serials.add(serial.lower())
            added_count += 1
        return added_count, skipped_count

    @Slot(list, list)
    def handle_dropped_serials(
        self, serials: list[str], failed_paths: list[str]
    ) -> None:
        added_count, skipped_count = self._append_serials_to_table(serials)

        if added_count == 0 and skipped_count == 0 and not failed_paths:
            self.msg.show_info("提示", "未检测到可处理的拖入项目")
            return

        parts: list[str] = []
        if added_count:
            parts.append(f"已添加 {added_count} 条番号")
        if skipped_count:
            parts.append(f"跳过 {skipped_count} 条重复番号")
        if failed_paths:
            parts.append(f"{len(failed_paths)} 个文件未能识别番号")
        if not parts:
            parts.append("没有新增番号")

        detail_lines: list[str] = []
        if failed_paths:
            preview = "\n".join(failed_paths[:5])
            detail_lines.append(preview)
            if len(failed_paths) > 5:
                detail_lines.append("...")

        message = "；".join(parts)
        if detail_lines:
            message = f"{message}\n\n未识别文件：\n" + "\n".join(detail_lines)
        self.msg.show_info("拖入完成", message)

    def add_row(self):
        """在表格末尾插入一个空行"""
        self._append_serial_row("")
        row = self.table.rowCount() - 1
        text_item = self.table.item(row, 1)

        # 自动聚焦到新行的文本列
        if text_item is not None:
            self.table.editItem(text_item)
            self.table.setCurrentItem(text_item)

    def delete_rows(self):
        """删除选中的行（高亮行）"""
        # 获取所有选中的范围
        selected_ranges = self.table.selectedRanges()
        # 倒序删除，避免索引错乱
        rows_to_delete = set()
        for ranges in selected_ranges:
            for row in range(ranges.topRow(), ranges.bottomRow() + 1):
                rows_to_delete.add(row)

        for row in sorted(rows_to_delete, reverse=True):
            self.table.removeRow(row)

    def delete_all_rows(self):
        """删除表格中的全部行。"""
        self.table.setRowCount(0)

    def clean_suffix(self):
        """去后缀：处理所有复选框选中的行"""
        # 常见的需要去除的后缀正则，不区分大小写
        suffix_pattern = re.compile(r"(-C|-h|_uncensored|ch|pl)$", re.IGNORECASE)

        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.Checked:
                text_item = self.table.item(row, 1)
                if text_item:
                    original_text = text_item.text().strip()
                    # 正则替换
                    new_text = suffix_pattern.sub("", original_text)
                    if new_text != original_text:
                        text_item.setText(new_text)

    def clean_prefix(self):
        """删前缀行：输入前缀字符串，删除已勾选且番号以此前缀开头的整行（前缀比较不区分大小写）。"""
        prefix, ok = QInputDialog.getText(
            self,
            "删前缀行",
            "输入前缀（删除已勾选且以此前缀开头的番号行）：",
        )
        if not ok:
            return
        prefix = prefix.strip()
        if not prefix:
            self.msg.show_warning("提示", "前缀不能为空")
            return
        plower = prefix.lower()
        rows_to_delete = []
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.Checked:
                text_item = self.table.item(row, 1)
                if text_item:
                    original_text = text_item.text().strip()
                    if original_text.lower().startswith(plower):
                        rows_to_delete.append(row)
        for row in reversed(rows_to_delete):
            self.table.removeRow(row)

    def sort_rows(self):
        """按番号列排序当前所有行（点击在升序/降序间切换）。"""
        rows = []
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            text_item = self.table.item(row, 1)
            if chk_item is None or text_item is None:
                continue
            rows.append(
                {
                    "checked": chk_item.checkState(),
                    "text": text_item.text(),
                }
            )
        rows.sort(
            key=lambda r: r["text"].strip().lower(), reverse=not self._sort_ascending
        )
        self._sort_ascending = not self._sort_ascending

        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            chk_item = QTableWidgetItem()
            chk_item.setFlags(
                Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )
            chk_item.setCheckState(r["checked"])
            self.table.setItem(row, 0, chk_item)
            text_item = QTableWidgetItem(r["text"])
            self.table.setItem(row, 1, text_item)

    @Slot()
    def import_csv(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 CSV 文件",
            "",
            "CSV (*.csv);;All Files (*.*)",
        )
        if not file_path:
            return

        path = Path(file_path)
        if path.suffix.lower() != ".csv":
            self.msg.show_warning("提示", "仅支持导入 CSV 文件")
            return

        try:
            serials = _read_csv_first_column_serials(path)
        except UnicodeDecodeError:
            self.msg.show_warning(
                "导入失败",
                "CSV 编码无法识别，请将文件保存为 UTF-8 或 GBK 后重试。",
            )
            return
        except OSError as exc:
            logging.warning("读取 CSV 失败: %s", exc)
            self.msg.show_warning("导入失败", f"无法读取文件：{exc}")
            return
        except ValueError as exc:
            self.msg.show_warning("导入失败", str(exc))
            return

        added_count, skipped_count = self._append_serials_to_table(serials)
        if added_count == 0 and skipped_count == 0:
            self.msg.show_info("导入完成", "CSV 第一列中没有可导入的番号")
            return

        parts: list[str] = []
        if added_count:
            parts.append(f"已添加 {added_count} 条番号")
        if skipped_count:
            parts.append(f"跳过 {skipped_count} 条重复番号")
        self.msg.show_info("导入完成", "；".join(parts))

    def load_serials(self, serial_list):
        """加载番号列表到表格中（外部调用时恢复为全量爬取）。"""
        self._use_selective_crawl = False
        self._populate_serial_table(serial_list)
        self._update_commit_button_appearance()

    def submit(self):
        """提交：收集所有复选框选中的番号"""
        serial_list = []
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.Checked:
                text_item = self.table.item(row, 1)
                if text_item:
                    serial = text_item.text().strip()
                    if serial:
                        serial_list.append(serial)
        logging.info(serial_list)
        if not serial_list:
            self.msg.show_warning("提示", "没有选中任何有效的番号")
            return

        from core.crawler.crawler_manager import get_manager

        manager = get_manager()
        if self._use_selective_crawl:
            selected_fields = self._get_selected_crawler_fields()
            if not selected_fields:
                self.msg.show_info("提示", "筛选后提交请先勾选至少一个要爬取的字段")
                return
            manager.start_crawl(serial_list, selected_fields=set(selected_fields))
        else:
            manager.start_crawl(serial_list)

        self.msg.show_info("提示", "已转入后台处理，您可以继续其他操作。")
        self.accept()
