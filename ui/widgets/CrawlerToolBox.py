from PySide6.QtWidgets import QGridLayout, QWidget
from darkeye_ui.components.token_check_box import TokenCheckBox
from darkeye_ui.components.icon_push_button import IconPushButton
from darkeye_ui.components.button import Button
class CrawlerAutoPage(QWidget):
    """自动爬虫抓取信息页面"""
    def __init__(self):
        super().__init__()
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
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
        self.btn_get_crawler = IconPushButton(icon_name="arrow_down_to_line", icon_size=24, out_size=32)

        self.cb_release_date.setChecked(True)
        self.cb_director.setChecked(True)
        self.cb_cn_title.setChecked(True)
        self.cb_jp_title.setChecked(True)
        self.cb_cn_story.setChecked(True)
        self.cb_jp_story.setChecked(True)
        self.cb_actress.setChecked(True)
        self.cb_actor.setChecked(True)
        self.cb_cover.setChecked(True)
        self.cb_tag.setChecked(True)
        self.btn_get_crawler.setToolTip("主要更新男优，发布日期，导演")

        layout.addWidget(self.cb_release_date, 0, 0)
        layout.addWidget(self.cb_director, 0, 1)
        layout.addWidget(self.cb_cover, 0, 2)
        layout.addWidget(self.cb_cn_title, 1, 0)
        layout.addWidget(self.cb_jp_title, 1, 1)
        layout.addWidget(self.cb_actress, 1, 2)
        layout.addWidget(self.cb_cn_story, 2, 0)
        layout.addWidget(self.cb_jp_story, 2, 1)
        layout.addWidget(self.cb_actor, 2, 2)
        layout.addWidget(self.cb_tag, 3, 0)
        layout.addWidget(self.btn_get_crawler, 3, 1)


class CrawlerManualNavPage(QWidget):
    """手动导航页面"""
    def __init__(self):
        super().__init__()
        linklayout = QGridLayout(self)

        self.btn_get_javlibrary = Button("javlibrary")
        self.btn_get_javlibrary.setToolTip("获得封面")
        self.btn_get_javdb = Button("javdb")
        self.btn_get_javdb.setToolTip("获得一般信息")
        self.btn_get_javtxt = Button("javtxt")
        self.btn_get_javtxt.setToolTip("获得故事与标题，但是没有封面")
        self.btn_get_minnaoav = Button("minnao-av")
        self.btn_get_minnaoav.setToolTip("女优信息")
        self.btn_get_avdanyuwiki = Button("avdanyuwiki")
        self.btn_get_avdanyuwiki.setToolTip("作品男优信息")
        self.btn_get_missav = Button("missav")
        self.btn_get_missav.setToolTip("在线观看网站")
        self.btn_get_avmoo = Button("avmoo")
        self.btn_get_avmoo.setToolTip("获得封面")
        self.btn_get_fanza = Button("fanza")
        self.btn_get_fanza.setToolTip("fanza售卖网站，非日本本土，需日本vpn且特殊插件才能访问")
        self.btn_get_netflav = Button("netflav")
        self.btn_get_netflav.setToolTip("在线观看网站")
        self.btn_get_123av = Button("123av")
        self.btn_get_123av.setToolTip("在线观看网站")
        self.btn_get_jable = Button("jable")
        self.btn_get_jable.setToolTip("在线观看网站")
        self.btn_get_supjav = Button("supjav")
        self.btn_get_supjav.setToolTip("专门看FC2")
        self.btn_get_mgs = Button("MGS")
        self.btn_get_mgs.setToolTip("PRESTIGE官方的售卖网站，非日本本土，需日本vpn且特殊插件才能访问")
        self.btn_get_jinjier = Button("金鸡儿奖")
        self.btn_get_jinjier.setToolTip("金鸡儿奖网站，挺有意思的")
        self.btn_get_gana = Button("平假名")
        self.btn_get_kana = Button("片假名")

        linklayout.addWidget(self.btn_get_javlibrary, 0, 0)
        linklayout.addWidget(self.btn_get_javdb, 0, 1)
        linklayout.addWidget(self.btn_get_javtxt, 0, 2)
        linklayout.addWidget(self.btn_get_minnaoav, 1, 0)
        linklayout.addWidget(self.btn_get_avdanyuwiki, 1, 1)
        linklayout.addWidget(self.btn_get_avmoo, 1, 2)
        linklayout.addWidget(self.btn_get_missav, 2, 0)
        linklayout.addWidget(self.btn_get_netflav, 2, 1)
        linklayout.addWidget(self.btn_get_fanza, 2, 2)
        linklayout.addWidget(self.btn_get_123av, 3, 0)
        linklayout.addWidget(self.btn_get_jable, 3, 1)
        linklayout.addWidget(self.btn_get_mgs, 3, 2)
        linklayout.addWidget(self.btn_get_supjav, 4, 0)
        linklayout.addWidget(self.btn_get_jinjier, 4, 2)
        linklayout.addWidget(self.btn_get_gana, 5, 1)
        linklayout.addWidget(self.btn_get_kana, 5, 2)


class CrawlerToolBox(QWidget):
    """给 addworktabpage 使用的部分控件；无 QToolBox，仅持有两个页面并对外暴露 widget(index) 与控件引用。"""
    def __init__(self):
        super().__init__()
        self._page1 = CrawlerAutoPage()
        self._page2 = CrawlerManualNavPage()
        # 转发 page1 控件，供 AddWorkTabPage3 等通过 self.crawler_toolbox.xxx 访问
        self.cb_release_date = self._page1.cb_release_date
        self.cb_director = self._page1.cb_director
        self.cb_cover = self._page1.cb_cover
        self.cb_cn_title = self._page1.cb_cn_title
        self.cb_jp_title = self._page1.cb_jp_title
        self.cb_cn_story = self._page1.cb_cn_story
        self.cb_jp_story = self._page1.cb_jp_story
        self.cb_actress = self._page1.cb_actress
        self.cb_actor = self._page1.cb_actor
        self.cb_tag = self._page1.cb_tag
        self.btn_get_crawler = self._page1.btn_get_crawler
        # 转发 page2 控件
        self.btn_get_javlibrary = self._page2.btn_get_javlibrary
        self.btn_get_javdb = self._page2.btn_get_javdb
        self.btn_get_javtxt = self._page2.btn_get_javtxt
        self.btn_get_minnaoav = self._page2.btn_get_minnaoav
        self.btn_get_avdanyuwiki = self._page2.btn_get_avdanyuwiki
        self.btn_get_missav = self._page2.btn_get_missav
        self.btn_get_avmoo = self._page2.btn_get_avmoo
        self.btn_get_fanza = self._page2.btn_get_fanza
        self.btn_get_netflav = self._page2.btn_get_netflav
        self.btn_get_123av = self._page2.btn_get_123av
        self.btn_get_jable = self._page2.btn_get_jable
        self.btn_get_supjav = self._page2.btn_get_supjav
        self.btn_get_mgs = self._page2.btn_get_mgs
        self.btn_get_jinjier = self._page2.btn_get_jinjier
        self.btn_get_gana = self._page2.btn_get_gana
        self.btn_get_kana = self._page2.btn_get_kana

    def widget(self, index: int) -> QWidget:
        return [self._page1, self._page2][index]
