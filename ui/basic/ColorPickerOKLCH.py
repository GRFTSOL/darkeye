import sys, os, math
import numpy as np
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QSlider, QLabel, QHBoxLayout, QSizePolicy,QLineEdit,QPushButton
from PySide6.QtGui import QPainter, QColor, QConicalGradient, QPainterPath, QImage, qRgb, QPixmap, QPen,QRegularExpressionValidator
from PySide6.QtCore import Qt, QPointF, Signal,Property,QObject,QThreadPool,QRegularExpression
from pathlib import Path


#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
root_dir = Path(__file__).resolve().parents[2]  # 上两级
sys.path.insert(0, str(root_dir))

from utils.color import oklch_to_srgb
from utils.utils import timeit
from core.crawler.Worker import Worker
from ui.basic.ColorSlider import AlphaSliderCustom
from ui.basic.Collapse import CollapsibleSection


from PySide6.QtGui import QRegularExpressionValidator, QKeyEvent
from PySide6.QtCore import QRegularExpression

class HexColorLineEdit(QLineEdit):
    """
    只能输入符合HexColor格式的QLineEdit：
    1. 只允许输入 0-9, a-f, A-F
    2. 最多 6 位（不含 #）
    3. 空时自动补 #（但允许删除到空）
    4. 粘贴时自动清理，只保留合法 hex 字符 + #（最多6位）
    5. 始终保持 # 在最前面（如果有内容）
    """
    validHexColor = Signal(str)  # 新增信号：发射 "#RRGGBB" 格式
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("")
        self._setting_text = False  # 新增标志位：是否正在程序设置文本
        self.setMaxLength(7)  # # + 最多6位

        # 只允许 0-9 a-f A-F（但我们后面还会动态控制 #）
        regex = QRegularExpression("[0-9a-fA-F]{0,6}")
        self.validator = QRegularExpressionValidator(regex)
        self.setValidator(self.validator)
        self.setStyleSheet(
            f"border-radius: 6px;"
            f"font-size: 16px;"
            f"padding: 6px;"
            f"font-family: 'Consolas';"  # 设置等宽字体
        )

        # 初始补 #
        self.textChanged.connect(self._auto_add_hash)

    def _auto_add_hash(self, text):
        """文本变化时自动处理 #"""
        if not text:
            # 允许完全清空（删除完）
            return
        
        # 去掉所有非 hex 字符（安全起见）
        cleaned = ''.join(c for c in text.upper() if c.isalnum() and c in '0123456789ABCDEF')

        if len(cleaned) > 6:
            cleaned = cleaned[:6]

        # 如果没有 #，自动加在最前面
        if not cleaned.startswith('#'):
            cleaned = '#' + cleaned

        # 避免无限循环（textChanged 信号）
        if cleaned != text:
            self.blockSignals(True)
            self.setText(cleaned)
            self.blockSignals(False)
            # 光标放到最后
            self.setCursorPosition(len(cleaned))

        if self._setting_text:
            return
        
        # 检查是否为合法 HEX 颜色（# + 6位）
        if self._is_valid_hex(cleaned):
            self.validHexColor.emit(cleaned)

    def _is_valid_hex(self, text: str) -> bool:
        """判断是否为合法 HEX 颜色（#RRGGBB 或 RRGGBB）"""
        text = text.lstrip('#')
        return len(text) == 6 and all(c in '0123456789ABCDEF' for c in text)

    def setText(self, text):
        """重写 setText，标记正在程序设置"""
        self._setting_text = True
        super().setText(text)
        self._setting_text = False

    def keyPressEvent(self, event: QKeyEvent):
        """键盘输入过滤"""
        text = event.text().upper()

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            super().keyPressEvent(event)
            return
        
        text = event.text().upper()
        
        # 允许 Ctrl+V、Ctrl+C、删除、退格、左右箭头等
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete,
                           Qt.Key.Key_Left, Qt.Key.Key_Right,
                           Qt.Key.Key_Home, Qt.Key.Key_End,
                           Qt.Key.Key_Tab):
            super().keyPressEvent(event)
            return

        # 只允许字母数字（a-f A-F 0-9）
        if text and text in '0123456789ABCDEF':
            # 额外检查总长度（不含#最多6位）
            current = self.text().lstrip('#')
            if len(current) >= 6 and self.cursorPosition() > 0:
                # 已满6位，且不是在开头插入，就不允许
                if self.cursorPosition() <= 1:  # 在 # 后面插入允许
                    super().keyPressEvent(event)
                return  # 否则阻止
            super().keyPressEvent(event)
        else:
            # 非合法字符直接忽略
            event.ignore()

    def paste(self):
        """重写粘贴行为：只保留合法 hex 字符 + #"""
        clipboard = QApplication.clipboard().text().strip().upper()

        # 提取所有 hex 字符
        cleaned = ''.join(c for c in clipboard if c in '0123456789ABCDEF')

        if not cleaned:
            return

        # 最多取6位
        cleaned = cleaned[:6]

        # 加 # 前缀
        result = '#' + cleaned

        # 插入或替换
        current_pos = self.cursorPosition()
        current_text = self.text()

        # 如果有选中，就替换选中部分；否则插入
        if self.hasSelectedText():
            self.insert(result)
        else:
            new_text = current_text[:current_pos] + result + current_text[current_pos:]
            self.setText(new_text[:7])  # 限制总长度 # + 6
            self.setCursorPosition(current_pos + len(result))

    def focusOutEvent(self, event):
        """失去焦点时强制规范格式"""
        text = self.text().upper()
        if text and not text.startswith('#'):
            self.setText('#' + text[:6])
        elif len(text.lstrip('#')) > 6:
            self.setText('#' + text.lstrip('#')[:6])
        super().focusOutEvent(event)

class OKLCH():
    '''纯放数据的model'''
    def __init__(self):
        self.L:float=0.0
        self.C:float=0.0
        self.H:float=0.0

class ViewModel_Wheel(QObject):
    L_changed=Signal(float)
    C_changed=Signal(float)
    H_changed=Signal(float)
    def __init__(self, model=None):
        super().__init__()
        self.model:OKLCH = model

    def get_L(self)->float: return self.model.L
    def set_L(self, value:float):
        value=round(value, 3)#H保留3位小数
        if self.model.L != value:
            self.model.L = value
            self.L_changed.emit(value)
    L=Property(float,get_L,set_L,notify=L_changed)
    
    def get_C(self)->float: return self.model.C
    def set_C(self, value:float):
        value=round(value, 3)#H保留3位小数
        if self.model.C != value:
            self.model.C = value
            self.C_changed.emit(value)
    
    C=Property(float,get_C,set_C,notify=C_changed)

    def get_H(self)->float: return self.model.H
    def set_H(self, value:float):
        value=round(value, 1)#H保留1位小数
        if self.model.H != value:
            self.model.H = value
            self.H_changed.emit(value)
    H=Property(float,get_H,set_H,notify=H_changed)

class OKLCHColorWheel(QWidget):
    mousePress=Signal()#鼠标松开事件
    def __init__(self,L,C,H):
        super().__init__()
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)# type: ignore[arg-type]
        #初始化
        self.oklchmodel=OKLCH()
        self.vm = ViewModel_Wheel(self.oklchmodel)
        self.vm.L=L
        self.vm.C=C
        self.vm.H=H

        self.chooseing = False  # 是否在移动指针
        self.chooseingin = False  # 内部是否在移动
        
        self.color_square_pixmap = None #中间存储图片
        self.inner_wheel_pixmap=None #内圈图片
        self.outter_wheel_pixmap=None#外圈图片
        
        self.setMouseTracking(True)  # 启用鼠标移动追踪（可选）
        self.update_layout()
        self.bind_model()

    def bind_model(self):
        '''双向绑定'''
        #这里是数据改变，视图改变
        self.vm.C_changed.connect(self.update_inner_wheel)
        self.vm.L_changed.connect(self.update_inner_wheel)
        self.vm.H_changed.connect(self.trigger_async_square_render)#当H动了，才需要计算中间的图片

        #动作就是后面的控制
        
    def resizeEvent(self, event):
        """窗口大小改变时重新计算布局的几何参数,以及重新计算图片"""
        super().resizeEvent(event)
        self.update_layout()
        #self.generate_color_square()
        self.trigger_async_square_render()
        self.generate_inner_wheel_image()
        self.generate_outter_wheel_image()
        self.update()
    
    def update_layout(self):
        '''计算并更新几何参数'''
        self.wheel_ratio=1/5 #总环厚是半径的1/4
        self.big_small_ratio=1/5 #细环厚总环厚的1/4
        self.center = self.rect().center()
        size = min(self.width(), self.height())
        self.outer_radius = size // 2-2
        self.mid_radius= self.outer_radius *(1-self.wheel_ratio)+ self.big_small_ratio*self.outer_radius*self.wheel_ratio
        self.inner_radius = self.outer_radius *(1-self.wheel_ratio)
        self.side = int(2 * self.inner_radius / 1.414 + 0.5)  # 边长
        #print(f"更新几何: 外半径={self.outer_radius}, 内半径={self.inner_radius}, 边长={self.side}")

    def update_inner_wheel(self):
        self.generate_inner_wheel_image()
        self.update()

    def paintEvent(self, event):
        """绘制事件，仅绘制，计算的都移到外面去，因为不是所有的绘制的东西都是实时更新的
        #目前0.4ms
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制调试矩形
        #painter.drawRect(self.rect())

        # 绘制色环
        self.draw_color_wheel_out(painter)
        self.draw_color_wheel_in(painter)
        
        # 绘制中间的正方形
        self.draw_color_square(painter)
        
        # 绘制指针线（指示当前 Hue）
        self.draw_hue_pointer(painter)
        
        # 绘制选择圈
        self.draw_inner_circle(painter)

    def draw_color_wheel_out(self, painter):
        if self.outter_wheel_pixmap :
            painter.drawPixmap(
                int(self.center.x() - self.outer_radius),
                int(self.center.y() - self.outer_radius),
                self.outter_wheel_pixmap
            )

    def draw_color_wheel_in(self, painter):
        """直接绘制预生成的 Pixmap"""
        if self.inner_wheel_pixmap :
            painter.drawPixmap(
                int(self.center.x() - self.mid_radius),
                int(self.center.y() - self.mid_radius),
                self.inner_wheel_pixmap
            )

    def draw_color_square(self, painter):
        """绘制颜色正方形"""
        if self.color_square_pixmap and self.side > 0:
            half_side = self.side / 2
            painter.drawPixmap(
                int(self.center.x() - half_side),
                int(self.center.y() - half_side),
                self.color_square_pixmap
            )

    def draw_hue_pointer(self, painter:QPainter):
        """绘制色环指针"""
        # 计算指针终点（在色环中径位置）
        painter.save()

        angle_rad = np.radians(90 - self.vm.H)  # Qt 坐标系转换
        end_x = self.center.x() + (self.outer_radius) * np.cos(angle_rad)
        end_y = self.center.y() - (self.outer_radius) * np.sin(angle_rad)  # Y 轴向下，取负

        start_x = self.center.x() + (self.inner_radius) * np.cos(angle_rad)
        start_y = self.center.y() - (self.inner_radius) * np.sin(angle_rad)
        start=QPointF(start_x,start_y)
        end=QPointF(end_x,end_y)

        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        
        # 计算垂直偏移（0.5像素）
        offset_x = math.sin(angle) * 1
        offset_y = -math.cos(angle) * 1
        
        # 绘制白色线
        white_start = QPointF(start.x() + offset_x, start.y() + offset_y)
        white_end = QPointF(end.x() + offset_x, end.y() + offset_y)
        
        painter.setPen(QPen(Qt.white, 1, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(white_start, white_end)
        
        # 绘制黑色线
        black_start = QPointF(start.x() - offset_x, start.y() - offset_y)
        black_end = QPointF(end.x() - offset_x, end.y() - offset_y)
        
        painter.setPen(QPen(Qt.black, 1, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(black_start, black_end)
        

        # 画指针终点小圆
        #painter.setPen(Qt.PenStyle.NoPen)
        #painter.setBrush(QColor("white"))  # 白色指针，显眼
        #painter.drawEllipse(QPointF(end_x, end_y), 6, 6)

        painter.restore()

    def draw_inner_circle(self, painter):
        """绘制中间的选择圈：白色外圈 + 灰色内圈"""
        painter.save()  # 保存当前绘制状态

        relative_coordinate=QPointF((self.vm.L-0.5)*self.side,(0.5-(self.vm.C/0.37))*self.side)
        true_point=QPointF(self.center)+QPointF(relative_coordinate)
        
        # 绘制白色外圈（稍大）
        outer_pen = QPen()
        outer_pen.setWidth(2)  # 稍粗
        outer_pen.setColor(QColor(255, 255, 255))  # 白色
        outer_pen.setStyle(Qt.SolidLine)
        outer_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(outer_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(true_point, 5, 5)  #
        
        # 绘制灰色内圈（稍小）
        inner_pen = QPen()
        inner_pen.setWidth(2)
        inner_pen.setColor(QColor(0, 0, 0))  # 灰色
        inner_pen.setStyle(Qt.SolidLine)
        inner_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(inner_pen)
        painter.drawEllipse(true_point, 7, 7)  #
        
        painter.restore()  # 恢复绘制状态

    def trigger_async_square_render(self):
        """触发后台渲染"""
        # 如果当前正在渲染，可以根据需求选择直接跳过或忽略
        # 实际开发中，连续快速移动鼠标会产生大量任务，QtConcurrent 会排队处理
        work=Worker(lambda:self.async_calculate_image( self.vm.H, self.side))
        work.signals.finished.connect(self.on_image_ready)
        QThreadPool.globalInstance().start(work)

    def async_calculate_image(self, H_val, side):
        """完全在后台线程执行的计算函数"""
        if side <= 0: return

        # 1. Numpy 向量化计算 (这里使用传入的参数而非 self.vm，保证线程安全)
        L_grid = np.linspace(0.0, 1.0, side, endpoint=True)[np.newaxis, :]
        C_grid = np.linspace(0.37, 0.0, side, endpoint=True)[:, np.newaxis]
        
        # 使用传入的 H_val
        H_grid = np.full((side, side), H_val)
        rgb_255 = oklch_to_srgb(L_grid, C_grid, H_grid, autopair=False)


        rgb_255 = rgb_255.astype(np.uint8)

        # 2. 生成 QImage (QImage 在非 GUI 线程创建是安全的，只要不 draw 到屏上)
        image = QImage(side, side, QImage.Format.Format_RGB32)
        
        # 3. 内存拷贝
        r = rgb_255[..., 0].astype(np.uint32)
        g = rgb_255[..., 1].astype(np.uint32)
        b = rgb_255[..., 2].astype(np.uint32)
        argb = (0xFF000000) | (r << 16) | (g << 8) | b
        
        bits = image.bits()
        np.copyto(np.frombuffer(bits, np.uint32), argb.flatten())

        return image

    def on_image_ready(self, image):
        """主线程回调：将 Image 转为 Pixmap 并重绘"""
        self.color_square_pixmap = QPixmap.fromImage(image)
        self.update() # 触发 paintEvent
    
    def generate_inner_wheel_image(self):
        """预渲染内圈色环为 Pixmap
        2ms
        """
        #print("计算内圈图")
        size = self.mid_radius*2 # 预留足够空间
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.transparent) # 背景透明

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center = QPointF(size / 2, size / 2)
        
        # 1. 计算当前 L, C 下的 360 度颜色
        hues = np.linspace(0, 360, 360, endpoint=False)
        # 调用你的 oklch_to_srgb
        colors_255 = oklch_to_srgb(self.vm.L, self.vm.C, hues, autopair=False)
        colors_255 = colors_255[::-1]

        # 2. 设置环形裁剪
        path = QPainterPath()
        path.addEllipse(center, self.mid_radius, self.mid_radius)
        path.addEllipse(center, self.inner_radius, self.inner_radius)
        painter.setClipPath(path)

        # 3. 绘制梯度
        gradient = QConicalGradient(center, 90)
        for i, rgb in enumerate(colors_255):
            gradient.setColorAt(i / 360.0, QColor(*rgb))

        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, self.mid_radius, self.mid_radius)
        painter.end()

        self.inner_wheel_pixmap = QPixmap.fromImage(image)

    def generate_outter_wheel_image(self):
        """预渲染外圈色环为 Pixmap
        这个只在resize和开始的时候渲染一次
        2ms
        """
        #print("计算外圈图")
        size = self.outer_radius*2 # 预留足够空间
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.transparent) # 背景透明# type: ignore[arg-type]

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center = QPointF(size / 2, size / 2)
        
        # 1. 计算当前 L, C 下的 360 度颜色
        hues = np.linspace(0, 360, 360, endpoint=False)
        # 调用你的 oklch_to_srgb
        colors_255 = oklch_to_srgb(0.76, 0.121, hues, autopair=False)
        colors_255 = colors_255[::-1]

        # 2. 设置环形裁剪
        path = QPainterPath()
        path.addEllipse(center, self.outer_radius, self.outer_radius)
        path.addEllipse(center, self.mid_radius-1, self.mid_radius-1)
        painter.setClipPath(path)

        # 3. 绘制梯度
        gradient = QConicalGradient(center, 90)
        for i, rgb in enumerate(colors_255):
            gradient.setColorAt(i / 360.0, QColor(*rgb))

        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, self.outer_radius, self.outer_radius)
        painter.end()

        self.outter_wheel_pixmap = QPixmap.fromImage(image)

    # ========== 鼠标点击更新 Hue ==========
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            
            pos = event.position()
            dx = pos.x() - self.center.x()
            dy = pos.y() - self.center.y()
            distance = np.sqrt(dx * dx + dy * dy)

            # 判断是否在环形区域内
            tolerance = 3  # 像素容差
            if (self.inner_radius - tolerance <= distance <= self.outer_radius+ tolerance):
                #print("点击在环内")
                self.chooseing = True
                self.mousePress.emit()
                self.update_H_from_pos(pos)
            # 判断是否在方框内
            half_side = self.side / 2
            if (self.center.x() - half_side <= pos.x() <= self.center.x() + half_side and 
                self.center.y() - half_side <= pos.y() <= self.center.y() + half_side):
                #print("点击在框内")
                self.chooseingin = True
                self.mousePress.emit()
                self.update_L_C_from_pos(pos)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:  # 拖拽也支持
            pos = event.position()
            if self.chooseing:
                self.update_H_from_pos(pos)
            if self.chooseingin:
                self.update_L_C_from_pos(pos)

    def mouseReleaseEvent(self, event):
        self.chooseing = False
        self.chooseingin = False
        
    def update_H_from_pos(self, pos):
        dx = pos.x() - self.center.x()
        dy = pos.y() - self.center.y()
        angle_rad = np.arctan2(-dy, dx)  # 从右边开始，顺时针
        angle_deg = np.round(np.degrees(angle_rad),1)
        if angle_deg < 0:
            angle_deg += 360
        # 转换为从顶部开始的色环角度
        self.vm.H = (90 - angle_deg) % 360
        #print(f"转盘移动后的H:{self.vm.H}")

    def update_L_C_from_pos(self, pos):
        half_side = self.side / 2
        left = self.center.x() - half_side
        bottom = self.center.y() + half_side
        
        # 计算 L 和 C
        self.vm.L = max(0.0, min(1.0, (pos.x() - left) / self.side))
        self.vm.C = max(0.0, min(0.37, (bottom - pos.y()) / self.side * 0.37))
        #print(f"方盘移动后的L:{self.vm.L},方盘移动后的L:{self.vm.C}")

    #========对外的接口===========
    def set_OKLCH(self,L=None,C=None,H=None):
        '''对外部使用'''
        if L:
            self.vm.L=L
        if C:
            self.vm.C=C
        if H:
            self.vm.H=H

    def get_OKLCH(self):
        return self.vm.L,self.vm.C,self.vm.H
    
    def get_OKLCH_hexrgb(self):
        current_rgb = oklch_to_srgb(self.vm.L,self.vm.C,self.vm.H)
        return f"#{current_rgb[0]:02X}{current_rgb[1]:02X}{current_rgb[2]:02X}"

class ColorLabel(QPushButton):
    colorclicked=Signal(str)#点击后发射当前的颜色
    def __init__(self,hex_color="#FFFFFF",show_text=True):
        super().__init__()
        self._color = hex_color
        self.show_text=show_text
        self.clicked.connect(lambda:self.colorclicked.emit(self._color))
        self.clicked.connect(self.copy2clipboard)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update()

    def copy2clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self._color)

    def update(self):
        from utils.utils import get_text_color_from_background
        text_color = get_text_color_from_background(QColor(self._color))
        if self.show_text:
            self.setText(self._color)
        # 使用单一的setStyleSheet调用，确保所有样式都生效
        self.setStyleSheet(
            f"background-color: {self._color};"
            f"border-radius: 6px;"
            f"color: {text_color};"
            f"font-size: 14px;"
            f"padding: 6px;"
        )

    def getColor(self):
        return self._color
    
    def setColor(self,color:str):
        self._color=color
        self.update()

class ColorWheelSimple(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(300, 300)
        self.setWindowTitle("OKLCH 极简拾色器")
        layout = QVBoxLayout(self)
        self.colorhistory=["#FFFFFF","#FFFFFF","#FFFFFF","#FFFFFF","#FFFFFF"]#5个历史记录
        self.colorlabellist:ColorLabel=[]

        self.wheel = OKLCHColorWheel(0.7,0.12,100)
        self.hexColorLineEdit=HexColorLineEdit()
        self.setStyleSheet(
            f"border-radius: 6px;"
            f"font-size: 16px;"
        )
        self.hexColorLineEdit.setFixedSize(80,30)

        self.wheel.vm.L_changed.connect(self.on_changed)
        self.wheel.vm.C_changed.connect(self.on_changed)
        self.wheel.vm.H_changed.connect(self.on_changed)
        
        self.wheel.mousePress.connect(self.replace)
        self.wheel.mousePress.connect(self.hexColorLineEdit.clearFocus)

        hlayout=QHBoxLayout()
        hlayout.setSpacing(3)
        for i in range(5):
            colorlabel=ColorLabel(self.colorhistory[i],show_text=False)
            colorlabel.setFixedSize(30,30)
            self.colorlabellist.append(colorlabel)
            #colorlabel.colorclicked.connect(self.setOKLCH)
            # 连接到 swap_color，并把当前 label 对象传进去
            colorlabel.colorclicked.connect(lambda _, obj=colorlabel: self.swap_color(obj))
            hlayout.addWidget(colorlabel)

        self.sync_colorlabel=ColorLabel(show_text=False)
        self.sync_colorlabel.setFixedHeight(30)
        hlayout.addWidget(self.sync_colorlabel)

        hlayout.addWidget(self.hexColorLineEdit)

        layout.addWidget(self.wheel)
        layout.addLayout(hlayout)

        self.hexColorLineEdit.validHexColor.connect(self.setOKLCH)

        self.on_changed()
    
    def swap_color(self, clicked_label: ColorLabel):
        """点击历史色块，与当前选中的颜色互换"""
        # 1. 获取当前轮盘的颜色（Hex）
        current_main_hex = self.wheel.get_OKLCH_hexrgb()
        print(current_main_hex)
        # 2. 获取被点击色块的颜色
        clicked_hex = clicked_label.getColor() # 假设你 ColorLabel 有 getColor 方法
        
        # 3. 互换：将轮盘当前色设给被点击的色块
        clicked_label.setColor(current_main_hex)
        
        # 4. 互换：将轮盘更新为被点击的色块颜色
        # 这会自动通过信号更新 sync_colorlabel 和 hexColorLineEdit
        self.setOKLCH(clicked_hex) 
        
        # 5. 同时更新底层的 colorhistory 列表，保持数据一致
        # 找到这个 label 在列表中的索引
        idx = self.colorlabellist.index(clicked_label)

        self.colorhistory[idx] = current_main_hex

    def replace(self):
        '''代替颜色'''
        self.colorhistory.append(self.wheel.get_OKLCH_hexrgb())
        self.colorhistory.pop(0)
        for i,label in enumerate(self.colorlabellist):
            label.setColor(self.colorhistory[i])
    
    def setOKLCH(self,hexcolor:str):
        '''传进来一定是合法的'''
        from utils.color import srgb_to_oklch
        L,C,H=srgb_to_oklch(hexcolor)
        self.wheel.set_OKLCH(L,C,H)

    def on_changed(self):
        '''色盘变化后'''
        self.sync_colorlabel.setColor(self.wheel.get_OKLCH_hexrgb())
        self.hexColorLineEdit.setText(self.wheel.get_OKLCH_hexrgb())

    def getHexColor(self):
        '''给外部使用获得hex格式的颜色'''
        return self.wheel.get_OKLCH_hexrgb()

    def setInitialColor(self,color):
        self.setOKLCH(color)


class ColorWheelApp(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(800, 800)
        self.setWindowTitle("OKLCH 拾色器")
        layout = QVBoxLayout(self)

        self.wheel = OKLCHColorWheel(0.7,0.12,100)
        layout.addWidget(self.wheel)


        self.colorlabel = ColorLabel(show_text=False)

        self.wheel.vm.L_changed.connect(self.on_changed)
        self.wheel.vm.C_changed.connect(self.on_changed)
        self.wheel.vm.H_changed.connect(self.on_changed)


        page1=QWidget()
        vlayout=QVBoxLayout(self)
        page1.setLayout(vlayout)


        # L 滑块
        l_layout = QVBoxLayout()
        l_label = QLabel("Lightness (L): 0.70")
        self.l_slider = QSlider(Qt.Orientation.Horizontal)
        self.l_slider.setRange(0, 1000)
        self.l_slider.setValue(70)
        self.l_slider.valueChanged.connect(lambda v: self.update_params(v / 1000, None,None, l_label))
        self.l_slider.valueChanged.connect(self.on_changed)
        l_layout.addWidget(l_label)
        l_layout.addWidget(self.l_slider)

        # C 滑块
        c_layout = QVBoxLayout()
        c_label = QLabel("Chroma (C): 0.20")
        self.c_slider = QSlider(Qt.Orientation.Horizontal)
        self.c_slider.setRange(0, 370)  # 0.00 ~ 0.370
        self.c_slider.setValue(20)
        self.c_slider.valueChanged.connect(lambda v: self.update_params(None, v / 1000,None, c_label))
        self.c_slider.valueChanged.connect(self.on_changed)
        c_layout.addWidget(c_label)
        c_layout.addWidget(self.c_slider)

        # H 滑块
        h_layout = QVBoxLayout()
        h_label = QLabel("Hue (H): 0.00")
        self.h_slider = QSlider(Qt.Orientation.Horizontal)
        self.h_slider.setRange(0, 3600)  # 0.000 ~ 0.370
        self.h_slider.setValue(0)
        self.h_slider.valueChanged.connect(lambda v: self.update_params(None, None,v/10, h_label))
        self.h_slider.valueChanged.connect(self.on_changed)
        h_layout.addWidget(h_label)
        h_layout.addWidget(self.h_slider)

        vlayout.addLayout(l_layout)
        vlayout.addLayout(c_layout)
        vlayout.addLayout(h_layout)

        self.collapse=CollapsibleSection("精准控制")
        self.collapse.addWidget(page1)

        layout.addWidget(self.colorlabel)
        layout.addWidget(self.collapse)
        layout.addStretch()


        self.on_changed()

    def update_params(self, L=None, C=None,H=None,label=None):
        if L is not None:
            self.wheel.set_OKLCH(L=L)
            label.setText(f"Lightness (L): {L:.3f}")
        if C is not None:
            self.wheel.set_OKLCH(C=C)
            label.setText(f"Chroma (C): {C:.3f}")
        if H is not None:
            self.wheel.set_OKLCH(H=H)
            label.setText(f"Hue (H): {H:.1f}")


    def on_changed(self):
        # 获取当前颜色 HEX
        L,C,H=self.wheel.get_OKLCH()
        current_rgb = oklch_to_srgb(L,C,H)
        #print(f"L={L}, C={C}, H={H}")
        hex_color = f"#{current_rgb[0]:02X}{current_rgb[1]:02X}{current_rgb[2]:02X}"
        #print("当前颜色:", hex_color)

        # 更新滑块值
        self.l_slider.setValue(round(self.wheel.vm.L * 1000))
        self.c_slider.setValue(round(self.wheel.vm.C * 1000))
        self.h_slider.setValue(round(self.wheel.vm.H * 10))

        self.colorlabel.setColor(hex_color)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    #window = ColorWheelApp()
    window = ColorWheelSimple()
    #window=OKLCHColorWheel(0.7,0.12,100)
    window.resize(300, 300)
    window.show()  
    sys.exit(app.exec())