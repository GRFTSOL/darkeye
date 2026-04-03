from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout

from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt
from config import ICONS_PATH
from darkeye_ui.components.label import Label


class TermsDialog(QDialog):
    """使用条款弹窗"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("用户使用条款")

        self.setWindowIcon(QIcon(str(ICONS_PATH / "logo.svg")))
        self.setModal(True)
        self.setFixedSize(500, 400)

        layout = QVBoxLayout(self)
        text = Label()
        text.setTextFormat(Qt.TextFormat.RichText)  # 启用富文本格式
        text.setWordWrap(True)  # 自动换行
        text.setText(
            "<h3>欢迎使用 <b>暗之眼</b>！</h3>"
            "<p>—— 帮助你在黑暗界中睁开一只眼，探索广阔的暗黑界。</p>"
            "<p><b>在使用前，请仔细阅读以下使用条款：</b></p>"
            "<ol>"
            "<li>本软件仅供学习与研究用途。</li>"
            "<li>本软件为免费个人使用，未经许可不得用于商业用途。</li>"
            "<li>本软件作者编写出该软件旨在学习 Python,C++,Qt，提高编程水平</li>"
            "<li>用户在使用本软件前，请用户了解并遵守当地法律法规，如果本软件使用过程中存在违反当地法律法规的行为，请勿使用该软件</li>"
            "<li>用户需自行承担使用风险,若用户在当地产生一切违法行为由用户承担。</li>"
            "<li>本软件不会收集任何数据，所有数据均存储在个人用户电脑上。</li>"
            "<li>开发者不对因使用本软件造成的任何损失负责。</li>"
            "<li>开发者不对数据丢失或损坏负责。</li>"
            "<li>本软件仅供 18 岁以上成年人使用。</li>"
            "<li>请不要在微信里传播软件。</li>"
            "<li>源代码和二进制程序请在下载后24小时内删除。</li>"
            "<li>本条款的最终解释权归开发者所有。</li>"
            "<li>若用户不同意上述条款任意一条，请勿使用本软件。</li>"
            "</ol>"
            "<p>点击 <b>“我同意”</b> 表示您已阅读并接受以上内容。</p>"
        )

        layout.addWidget(text)

        button_layout = QHBoxLayout()
        self.agree_btn = QPushButton("我同意")
        self.disagree_btn = QPushButton("不同意")
        button_layout.addWidget(self.agree_btn)
        button_layout.addWidget(self.disagree_btn)
        layout.addLayout(button_layout)

        self.agree_btn.clicked.connect(self.accept)
        self.disagree_btn.clicked.connect(self.reject)
