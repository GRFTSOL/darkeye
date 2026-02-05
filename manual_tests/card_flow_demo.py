import sys
import random
from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsObject, QGraphicsItem, QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Qt, QRectF, Property, QPropertyAnimation, QEasingCurve, QAbstractAnimation
from PySide6.QtGui import QBrush, QColor, QFont, QPainter

class CardItem(QGraphicsObject):
    """自定义卡片图元"""
    def __init__(self, title, desc, color, width=200, height=300, parent=None):
        super().__init__(parent)
        self.width = width
        self.height = height
        self.color = color
        self.title_text = title
        self.desc_text = desc
        
        # 启用设备坐标缓存以提高渲染性能
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

    def boundingRect(self):
        # 定义图元的边界矩形（以中心为原点）
        return QRectF(-self.width/2, -self.height/2, self.width, self.height)

    def paint(self, painter, option, widget):
        rect = self.boundingRect()
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 1. 绘制背景（圆角矩形）
        painter.setBrush(QBrush(self.color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 15, 15)
        
        # 2. 绘制占位图片区域（上半部分）
        img_rect = QRectF(rect.left() + 10, rect.top() + 10, rect.width() - 20, rect.height() * 0.45)
        painter.setBrush(QBrush(QColor(255, 255, 255, 60)))
        painter.drawRoundedRect(img_rect, 10, 10)
        
        # 3. 绘制标题（居中大字）
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Microsoft YaHei", 16, QFont.Bold)
        painter.setFont(font)
        
        # 计算标题区域
        title_rect = QRectF(rect.left() + 10, img_rect.bottom() + 15, rect.width() - 20, 30)
        painter.drawText(title_rect, Qt.AlignCenter, self.title_text)
        
        # 4. 绘制描述（下方小字）
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(220, 220, 220))
        
        desc_rect = QRectF(rect.left() + 15, title_rect.bottom() + 10, rect.width() - 30, rect.height() - title_rect.bottom() - 20)
        painter.drawText(desc_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, self.desc_text)

class CardFlowView(QGraphicsView):
    """水平卡片流视图容器"""
    def __init__(self):
        super().__init__()
        # 初始化场景
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # 视图设置
        self.setBackgroundBrush(QBrush(QColor(40, 44, 52))) # 深色背景
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFrameShape(QGraphicsView.NoFrame)
        
        # 数据与布局参数
        self.cards = []
        self.card_width = 220
        self.card_height = 320
        self.spacing = 40 # 卡片间距
        self._current_offset = 0.0 # 当前水平偏移量
        
        # 交互状态
        self.last_mouse_x = 0
        self.dragging = False
        
        # 动画对象
        self.anim = QPropertyAnimation(self, b"offset")
        self.anim.setDuration(500)
        self.anim.setEasingCurve(QEasingCurve.OutBack) # 弹性回弹曲线

    # 定义 offset 属性供动画使用
    def get_offset(self):
        return self._current_offset

    def set_offset(self, value):
        self._current_offset = value
        self.update_layout() # 每次偏移变化都更新布局

    offset = Property(float, get_offset, set_offset)

    def add_card(self, title, desc, color):
        """添加新卡片"""
        item = CardItem(title, desc, color, self.card_width, self.card_height)
        self.scene.addItem(item)
        self.cards.append(item)
        self.update_layout()

    def update_layout(self):
        """核心布局逻辑：无限循环模式"""
        if not self.cards:
            return
            
        viewport_width = self.viewport().width()
        viewport_center_x = viewport_width / 2
        viewport_center_y = self.viewport().height() / 2
        
        # 单个卡片占用的步长
        stride = self.card_width + self.spacing
        # 整个卡片队列的总长度（周期）
        total_length = len(self.cards) * stride
        
        # 视口半宽 + 卡片宽度作为可见/透明度衰减范围
        visible_range = viewport_width / 2 + self.card_width 
        
        for i, card in enumerate(self.cards):
            # 1. 计算卡片的原始位置（不考虑循环）
            # 初始状态下第0张在中心
            raw_x = i * stride + self._current_offset
            
            # 2. 核心：通过取模运算实现无限循环
            # 我们希望卡片的位置 x 始终落在相对于 viewport_center_x 的某个合理区间内
            # 先计算相对于中心的偏移
            relative_x = raw_x
            
            # 使用取模运算将 relative_x 映射到 [-total_length/2, total_length/2] 区间内
            # 这样无论 offset 滚到多远，卡片都会被“搬运”回来
            mod_x = (relative_x + total_length / 2) % total_length - total_length / 2
            
            # 最终屏幕坐标 x
            x = viewport_center_x + mod_x
            
            # 设置位置
            card.setPos(x, viewport_center_y)
            
            # 3. 计算距离中心的距离
            dist = abs(x - viewport_center_x)
            
            # 4. 计算透明度（线性衰减）
            opacity = 1.0 - (dist / visible_range)
            opacity = max(0.0, min(1.0, opacity)) 
            
            # 5. 性能优化与显示
            # 在无限循环模式下，我们需要确保当卡片应该从左边出来时，不要因为 opacity 为 0 就完全隐藏
            # 实际上只要模运算正确，位置是对的，逻辑是一样的
            card.setVisible(opacity > 0)
            if opacity > 0:
                card.setOpacity(opacity)
                scale = 1.0 - (dist / visible_range) * 0.3
                scale = max(0.7, scale)
                card.setScale(scale)
                card.setZValue(100 - dist)

    def resizeEvent(self, event):
        """窗口大小改变时重新计算场景和布局"""
        super().resizeEvent(event)
        self.scene.setSceneRect(0, 0, self.viewport().width(), self.viewport().height())
        self.update_layout()

    def mousePressEvent(self, event):
        """鼠标按下：开始拖拽"""
        # 如果动画正在运行（例如正在抽奖），禁止交互
        if self.anim.state() == QAbstractAnimation.Running:
            return

        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.last_mouse_x = event.pos().x()
            self.anim.stop() # 停止正在进行的动画
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动：更新偏移量"""
        if self.dragging:
            delta = event.pos().x() - self.last_mouse_x
            self.last_mouse_x = event.pos().x()
            
            # 无限模式：不再限制 offset 范围
            new_offset = self._current_offset + delta
            self.set_offset(new_offset)
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放：自动回弹吸附"""
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self.setCursor(Qt.ArrowCursor)
            
            # 吸附逻辑 (Snap)
            item_stride = self.card_width + self.spacing
            
            # 无限模式下，只需要吸附到最近的 stride 倍数即可
            # 不需要关心 index 是多少，因为布局是用模运算处理的
            
            # 计算当前 offset 对应的是第几个“槽位”（可以是负数，也可以很大）
            # round(offset / stride) * stride
            target_offset = round(self._current_offset / item_stride) * item_stride
            
            # 启动回弹动画
            self.anim.setStartValue(self._current_offset)
            self.anim.setEndValue(target_offset)
            self.anim.start()
            
        super().mouseReleaseEvent(event)

    def start_random_spin(self):
        """开始随机抽卡"""
        if not self.cards:
            return
            
        # 1. 随机选择目标
        target_idx = random.randint(0, len(self.cards) - 1)
        print(f"Target Card Index: {target_idx}")
        
        # 2. 计算步长和周期
        stride = self.card_width + self.spacing
        cycle_len = len(self.cards) * stride
        
        # 3. 决定转多少圈 (5-10圈)
        rounds = 5
        
        # 4. 计算目标偏移量
        current_offset = self._current_offset
        min_spin_distance = rounds * cycle_len
        
        # 计算相位差
        # 目标位置在周期内的相位是: -target_idx * stride
        # 我们希望最终位置是 target_phase (mod cycle_len)
        target_phase = (-target_idx * stride) % cycle_len
        current_phase = current_offset % cycle_len
        
        # 计算向左（减小方向）需要走多远才能到达目标相位
        phase_diff = current_phase - target_phase
        if phase_diff < 0:
            phase_diff += cycle_len
            
        total_move = min_spin_distance + phase_diff
        target_offset = current_offset - total_move
        
        # 5. 启动动画
        self.anim.stop()
        self.anim.setDuration(4000) # 4秒
        self.anim.setEasingCurve(QEasingCurve.OutQuart) # 快速启动，缓慢停止
        self.anim.setStartValue(current_offset)
        self.anim.setEndValue(target_offset)
        self.anim.start()

class MainDemoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Infinite Card Flow & Spin Demo")
        self.resize(1000, 700)
        
        layout = QVBoxLayout(self)
        
        # 1. 卡片视图
        self.view = CardFlowView()
        layout.addWidget(self.view)
        
        # 2. 控制按钮
        self.btn_spin = QPushButton("Start Lucky Spin! (随机抽卡)")
        self.btn_spin.setFixedHeight(50)
        font = QFont("Arial", 14, QFont.Bold)
        self.btn_spin.setFont(font)
        self.btn_spin.clicked.connect(self.view.start_random_spin)
        layout.addWidget(self.btn_spin)

        # 添加测试数据
        test_data = [
            ("Inception", "A thief who steals corporate secrets through the use of dream-sharing technology.", QColor(231, 76, 60)),
            ("Interstellar", "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.", QColor(46, 204, 113)),
            ("The Matrix", "A computer hacker learns from mysterious rebels about the true nature of his reality.", QColor(52, 152, 219)),
            ("Avatar", "A paraplegic Marine dispatched to the moon Pandora on a unique mission becomes torn between following his orders and protecting the world he feels is his home.", QColor(155, 89, 182)),
            ("Titanic", "A seventeen-year-old aristocrat falls in love with a kind but poor artist aboard the luxurious, ill-fated R.M.S. Titanic.", QColor(241, 196, 15)),
            ("Gladiator", "A former Roman General sets out to exact vengeance against the corrupt emperor who murdered his family and sent him into slavery.", QColor(230, 126, 34)),
            ("Joker", "In Gotham City, mentally troubled comedian Arthur Fleck is disregarded and mistreated by society.", QColor(149, 165, 166))
        ]
        
        for title, desc, color in test_data:
            self.view.add_card(title, desc, color)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = MainDemoWindow()
    window.show()
    
    sys.exit(app.exec())
