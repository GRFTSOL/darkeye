from PySide6.QtWidgets import QGridLayout, QWidget
from darkeye_ui.components.token_check_box import TokenCheckBox
from darkeye_ui.components.icon_push_button import IconPushButton


class CrawlerAutoPage(QWidget):
    """自动爬虫抓取信息页面"""

    def __init__(self):
        super().__init__()
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.cb_release_date = TokenCheckBox("发布日期")
        self.cb_director = TokenCheckBox("导演")
        self.cb_cover = TokenCheckBox("封面")
        self.cb_cn_title = TokenCheckBox("中文标题")
        self.cb_jp_title = TokenCheckBox("日文标题")
        self.cb_cn_story = TokenCheckBox("中文故事")
        self.cb_jp_story = TokenCheckBox("日文故事")
        self.cb_actress = TokenCheckBox("女优")
        self.cb_actor = TokenCheckBox("男优")
        self.cb_tag = TokenCheckBox("标签")
        self.cb_runtime = TokenCheckBox("时长")
        self.cb_maker = TokenCheckBox("片商")
        self.cb_series = TokenCheckBox("系列")
        self.cb_label = TokenCheckBox("厂牌")
        self.cb_fanart = TokenCheckBox("剧照")

        self.layout.addWidget(self.cb_release_date, 0, 0)
        self.layout.addWidget(self.cb_director, 0, 1)
        self.layout.addWidget(self.cb_cover, 0, 2)
        self.layout.addWidget(self.cb_cn_title, 1, 0)
        self.layout.addWidget(self.cb_jp_title, 1, 1)
        self.layout.addWidget(self.cb_actress, 1, 2)
        self.layout.addWidget(self.cb_cn_story, 2, 0)
        self.layout.addWidget(self.cb_jp_story, 2, 1)
        self.layout.addWidget(self.cb_actor, 2, 2)
        self.layout.addWidget(self.cb_tag, 3, 0)
        self.layout.addWidget(self.cb_runtime, 3, 1)
        self.layout.addWidget(self.cb_maker, 3, 2)
        self.layout.addWidget(self.cb_label, 4, 0)
        self.layout.addWidget(self.cb_series, 4, 1)
        self.layout.addWidget(self.cb_fanart, 4, 2)

    def append_row_widget(
        self, widget: QWidget, column: int = 0, column_span: int = 1
    ) -> None:
        """在网格下一空行追加控件（行号随已有行数自动递增）。"""
        row = self.layout.rowCount()
        self.layout.addWidget(widget, row, column, 1, column_span)
