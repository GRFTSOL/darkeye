# 有关图像处理的工具类
from PySide6.QtWidgets import QPushButton, QApplication, QMainWindow
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QImage
from PySide6.QtCore import QSize, Signal, Qt, QByteArray
from PySide6.QtSvg import QSvgRenderer


def create_colored_icon(svg_path, color, size=32):
    """
    为单色SVG图标着色

    Args:
        svg_path: SVG文件路径
        color: 颜色值，如 "#FF0000"、"red" 或 QColor
        size: 图标大小

    Returns:
        QIcon: 着色后的图标
    """

    # 1. 加载原始图标
    original_icon = QIcon(svg_path)

    # 2. 获取原始pixmap
    pixmap = original_icon.pixmap(size, size)

    # 3. 创建新的pixmap
    colored_pixmap = QPixmap(size, size)
    colored_pixmap.fill(Qt.transparent)

    # 4. 创建QPainter
    painter = QPainter(colored_pixmap)

    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)

    # 5. 设置混合模式：用指定颜色填充非透明区域
    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
    painter.drawPixmap(0, 0, pixmap)

    # 6. 设置混合模式：用颜色替换已有颜色
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    if isinstance(color, str):
        color = QColor(color)
    painter.fillRect(colored_pixmap.rect(), color)

    # 7. 结束绘制
    painter.end()

    # 8. 创建新图标
    return QIcon(colored_pixmap)


def create_colored_icon_vector(
    svg_path: str, color_hex: str, height=32, width=32
) -> QIcon:
    """通过修改源码保持矢量的清晰着色"""
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_data = f.read()

    # 替换颜色（假设 Lucide 图标使用 stroke="currentColor" 或指定色）
    # 针对 Lucide 图标，通常修改 stroke
    if 'fill="none"' in svg_data:  # 线条形图标
        new_svg = svg_data.replace('stroke="currentColor"', f'stroke="{color_hex}"')
    # 如果是填充型图标，修改 fill
    if 'fill="currentColor"' in svg_data:
        new_svg = svg_data.replace('fill="currentColor"', f'fill="{color_hex}"')

    pixmap = QPixmap.fromImage(svgdata_to_qimage(new_svg, height, width))

    # 使用 QByteArray 加载，避免转成位图
    # pixmap = QPixmap()
    # pixmap.loadFromData(QByteArray(new_svg.encode('utf-8')))
    return QIcon(pixmap)


def svgdata_to_qimage(svg_data, width, height) -> QImage:
    """把svg的数据转成qimage"""
    # 1. 创建一个透明的 QImage
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(0)  # 填充透明

    # 2. 创建渲染器并绘制
    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
    painter = QPainter(image)
    renderer.render(painter)  # 将 SVG 渲染到 painter 所在的 image 上
    painter.end()

    return image


def svg_to_qimage(svg_path: str, width, height) -> QImage:
    """把svg转成qimage"""
    # 1. 创建一个透明的 QImage
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(0)  # 填充透明

    # 2. 创建渲染器并绘制
    renderer = QSvgRenderer(svg_path)
    painter = QPainter(image)
    renderer.render(painter)  # 将 SVG 渲染到 painter 所在的 image 上
    painter.end()

    return image
