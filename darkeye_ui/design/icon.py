# design/icon.py - 将路径或内联 SVG 字符串转为 QIcon
# 图标来源：resources/icons/*.svg（已内联，便于无文件依赖）
from pathlib import Path
from typing import Union

from PySide6.QtCore import QByteArray, QSize
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


def _device_pixel_ratio() -> float:
    """获取主屏设备像素比，高 DPI 下用于渲染更清晰的图标。"""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app and app.primaryScreen() is not None:
            return app.primaryScreen().devicePixelRatio()
    except Exception:
        pass
    return 1.0


# ---------- 内联图标（来自 resources/icons，stroke/fill 用 currentColor 便于主题着色） ----------

# resources/icons 内联（lucide 或简单 SVG，已统一 currentColor）
SVG_SETTINGS = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915"/><circle cx="12" cy="12" r="3"/></svg>'
SVG_BELL_RING = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M22 8c0-2.3-.8-4.3-2-6"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/><path d="M4 2C2.8 3.7 2 5.7 2 8"/></svg>'
SVG_LIBRARY_BIG = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="8" height="18" x="3" y="3" rx="1"/><path d="M7 3v18"/><path d="M20.4 18.9c.2.5-.1 1.1-.6 1.3l-1.9.7c-.5.2-1.1-.1-1.3-.6L11.1 5.1c-.2-.5.1-1.1.6-1.3l1.9-.7c.5-.2 1.1.1 1.3.6Z"/></svg>'
SVG_CIRCLE_QUESTION_MARK = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>'
SVG_CIRCLE_PLUS = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M8 12h8"/><path d="M12 8v8"/></svg>'
SVG_TRASH_2 = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 11v6"/><path d="M14 11v6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>'
SVG_CHEVRON_UP = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>'
SVG_DATABASE = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d="M3 12A9 3 0 0 0 21 12"/></svg>'
SVG_X = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>'
SVG_CHEVRON_RIGHT = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>'
SVG_MENU = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16"/><path d="M4 12h16"/><path d="M4 19h16"/></svg>'
SVG_SCROLL_TEXT = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 12h-5"/><path d="M15 8h-5"/><path d="M19 17V5a2 2 0 0 0-2-2H4"/><path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"/></svg>'
SVG_ERASER = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 21H8a2 2 0 0 1-1.42-.587l-3.994-3.999a2 2 0 0 1 0-2.828l10-10a2 2 0 0 1 2.829 0l5.999 6a2 2 0 0 1 0 2.828L12.834 21"/><path d="m5.082 11.09 8.828 8.828"/></svg>'
SVG_SAVE = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/></svg>'
SVG_SHARE_2 = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" x2="15.42" y1="13.51" y2="17.49"/><line x1="15.41" x2="8.59" y1="6.51" y2="10.49"/></svg>'
SVG_SQUARE = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="0"/></svg>'
SVG_BRUSH_CLEANING = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 22-1-4"/><path d="M19 14a1 1 0 0 0 1-1v-1a2 2 0 0 0-2-2h-3a1 1 0 0 1-1-1V4a2 2 0 0 0-4 0v5a1 1 0 0 1-1 1H6a2 2 0 0 0-2 2v1a1 1 0 0 0 1 1"/><path d="M19 14H5l-1.973 6.767A1 1 0 0 0 4 22h16a1 1 0 0 0 .973-1.233z"/><path d="m8 22 1-4"/></svg>'
SVG_ARROW_DOWN_TO_LINE = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17V3"/><path d="m6 11 6 6 6-6"/><path d="M19 21H5"/></svg>'
SVG_ARROW_UP_TO_LINE = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3h14"/><path d="m18 13-6-6-6 6"/><path d="M12 7v14"/></svg>'
SVG_SQUARE_PEN = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.375 2.625a1 1 0 0 1 3 3l-9.013 9.014a2 2 0 0 1-.853.505l-2.873.84a.5.5 0 0 1-.62-.62l.84-2.873a2 2 0 0 1 .506-.852z"/></svg>'
SVG_LIST_PLUS = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 5H3"/><path d="M11 12H3"/><path d="M16 19H3"/><path d="M18 9v6"/><path d="M21 12h-6"/></svg>'
SVG_EYE = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>'
SVG_LANGUAGES = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/></svg>'
SVG_MARS = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 3h5v5"/><path d="m21 3-6.75 6.75"/><circle cx="10" cy="14" r="6"/></svg>'
SVG_FILM = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 3v18"/><path d="M3 7.5h4"/><path d="M3 12h18"/><path d="M3 16.5h4"/><path d="M17 3v18"/><path d="M17 7.5h4"/><path d="M17 16.5h4"/></svg>'
SVG_CHART_LINE = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="m19 9-5 5-4-4-3 3"/></svg>'
SVG_EYE_OFF = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"/><path d="M14.084 14.158a3 3 0 0 1-4.242-4.242"/><path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"/><path d="m2 2 20 20"/></svg>'
SVG_LIST_X = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 5H3"/><path d="M11 12H3"/><path d="M16 19H3"/><path d="m15.5 9.5 5 5"/><path d="m20.5 9.5-5 5"/></svg>'
SVG_BELL = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/></svg>'
SVG_TRIANGLE_DOWN = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m13.73 20.03a2 2 0 0 1-3.46 0l-8-14a2 2 0 0 1 1.73-3h16a2 2 0 0 1 1.73 3z"/></svg>'
SVG_SPROUT = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9.536V7a4 4 0 0 1 4-4h1.5a.5.5 0 0 1 .5.5V5a4 4 0 0 1-4 4 4 4 0 0 0-4 4c0 2 1 3 1 5a5 5 0 0 1-1 3"/><path d="M4 9a5 5 0 0 1 8 4 5 5 0 0 1-8-4"/><path d="M5 21h14"/></svg>'
SVG_TRIANGLE_UP = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13.73 4a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/></svg>'
SVG_VENUS = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15v7"/><path d="M9 19h6"/><circle cx="12" cy="9" r="6"/></svg>'
SVG_CHEVRON_LEFT = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>'
SVG_TV = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m17 2-5 5-5-5"/><rect width="20" height="15" x="2" y="7" rx="2"/></svg>'
SVG_LAYOUT_PANEL_LEFT = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="18" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/></svg>'
SVG_COPY = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="0"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>'
SVG_CHEVRON_DOWN = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>'
SVG_REFRESH_CW = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg>'
SVG_SEARCH = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21 21-4.34-4.34"/><circle cx="11" cy="11" r="8"/></svg>'
SVG_HOUSE = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>'
SVG_PLUS='<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>'
SVG_CHECK = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
SVG_MINUS = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/></svg>'

SVG_ARROW_UP='<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>'
SVG_ARROW_DOWN='<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="m19 12-7 7-7-7"/></svg>'
SVG_ARROW_LEFT='<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg>'
SVG_ARROW_RIGHT='<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>'

# love-off / love-on：固定配色，保留原样（非 currentColor）
SVG_LOVE_OFF = '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><path d="m9.268 2.994a8.476 8.476 0 0 0-5.256 2.451 8.476 8.476 0 0 0 0 11.99l11.99 11.99 11.99-11.99a8.476 8.476 0 0 0 0-11.99 8.476 8.476 0 0 0-11.99 0.001953 8.476 8.476 0 0 0-6.734-2.453zm0.8496 1.99c0.3742 0.004111 0.7479 0.03777 1.115 0.1172 1.95 0.2866 3.333 1.769 4.77 2.975 0.579-0.4938 1.158-0.9882 1.736-1.482 2.325-2.155 6.262-2.135 8.566 0.04297 2.612 2.16 2.886 6.457 0.6406 8.979-3.607 3.699-7.302 7.315-10.94 10.98l-9.947-9.947c-1.617-1.419-2.715-3.536-2.48-5.723 0.1633-2.909 2.554-5.447 5.422-5.879 0.3716-0.04244 0.7469-0.06856 1.121-0.06445z" fill="#ccc"/></svg>'
SVG_LOVE_ON = '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><path d="m4.012 5.446a8.476 8.476 0 0 0 2.6e-6 11.99l11.99 11.99 11.99-11.99a8.476 8.476 0 0 0 0-11.99 8.476 8.476 0 0 0-11.99 0.0021 8.476 8.476 0 0 0-11.99-0.0021z" fill="#ff2a2a" stroke-width="0"/></svg>'



BUILTIN_ICONS = {
    "x": SVG_X,
    "check": SVG_CHECK,
    "plus": SVG_PLUS,
    "minus": SVG_MINUS,
    "chevron_up": SVG_CHEVRON_UP,
    "chevron_down": SVG_CHEVRON_DOWN,
    "chevron_left": SVG_CHEVRON_LEFT,
    "chevron_right": SVG_CHEVRON_RIGHT,
    "arrow_up": SVG_ARROW_UP,
    "arrow_down": SVG_ARROW_DOWN,
    "arrow_left": SVG_ARROW_LEFT,
    "arrow_right": SVG_ARROW_RIGHT,
    "settings": SVG_SETTINGS,
    "bell": SVG_BELL,
    "bell_ring": SVG_BELL_RING,
    "arrow_down_to_line": SVG_ARROW_DOWN_TO_LINE,
    "arrow_up_to_line": SVG_ARROW_UP_TO_LINE,
    "list_x": SVG_LIST_X,
    "list_plus": SVG_LIST_PLUS,
    "save": SVG_SAVE,
    "share_2": SVG_SHARE_2,
    "library_big": SVG_LIBRARY_BIG,
    "circle_question_mark": SVG_CIRCLE_QUESTION_MARK,
    "circle_plus": SVG_CIRCLE_PLUS,
    "triangle_up": SVG_TRIANGLE_UP,
    "triangle_down": SVG_TRIANGLE_DOWN,
    "trash_2": SVG_TRASH_2,
    "database": SVG_DATABASE,
    "menu": SVG_MENU,
    "scroll_text": SVG_SCROLL_TEXT,
    "eraser": SVG_ERASER,
    "square": SVG_SQUARE,
    "brush_cleaning": SVG_BRUSH_CLEANING,
    "square_pen": SVG_SQUARE_PEN,
    "eye": SVG_EYE,
    "eye_off": SVG_EYE_OFF,
    "languages": SVG_LANGUAGES,
    "mars": SVG_MARS,
    "venus": SVG_VENUS,
    "film": SVG_FILM,
    "chart_line": SVG_CHART_LINE,

    "sprout": SVG_SPROUT,

    "tv": SVG_TV,
    "layout_panel_left": SVG_LAYOUT_PANEL_LEFT,
    "copy": SVG_COPY,
    "refresh_cw": SVG_REFRESH_CW,
    "search": SVG_SEARCH,
    "house": SVG_HOUSE,
    "love_off": SVG_LOVE_OFF,
    "love_on": SVG_LOVE_ON,
}


def _normalize_size(size: Union[int, tuple]) -> tuple:
    if isinstance(size, int):
        return (size, size)
    return (size[0], size[1])


def _load_svg_string(svg_source: Union[str, Path]) -> str:
    """返回用于渲染的 SVG 字符串。svg_source 为内联 XML 或文件路径。"""
    s = svg_source
    if isinstance(s, Path):
        return s.read_text(encoding="utf-8")
    s = s.strip()
    if s.startswith("<") or "<?xml" in s[:100]:
        return s
    path = Path(s)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return s


def _apply_color(svg_data: str, color: str) -> str:
    """将 SVG 中的 currentColor 替换为指定颜色。"""
    if 'fill="none"' in svg_data or "fill='none'" in svg_data:
        svg_data = svg_data.replace('stroke="currentColor"', f'stroke="{color}"')
        svg_data = svg_data.replace("stroke='currentColor'", f"stroke='{color}'")
    if "currentColor" in svg_data:
        svg_data = svg_data.replace('fill="currentColor"', f'fill="{color}"')
        svg_data = svg_data.replace("fill='currentColor'", f"fill='{color}'")
        svg_data = svg_data.replace('stroke="currentColor"', f'stroke="{color}"')
        svg_data = svg_data.replace("stroke='currentColor'", f"stroke='{color}'")
    return svg_data


def svg_to_icon(
    svg_source: Union[str, Path, QIcon],
    size: Union[int, tuple] = 16,
    color: Union[str, None] = None,
) -> QIcon:
    """从文件路径、内联 SVG 字符串或已有 QIcon 得到 QIcon。

    - svg_source 为 str 且形如 XML（以 < 开头或含 <?xml）时视为内联 SVG 字符串。
    - 为 str/Path 且为路径时读取文件内容再渲染。
    - 为 QIcon 时直接返回。
    - size: 渲染尺寸，int 为宽高同，或 (w, h)。
    - color: 可选，替换 SVG 中 currentColor 后渲染。
    """
    if isinstance(svg_source, QIcon):
        return svg_source

    w, h = _normalize_size(size)
    svg_data = _load_svg_string(svg_source)
    if color:
        svg_data = _apply_color(svg_data, color)

    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
    if not renderer.isValid():
        return QIcon()

    ratio = _device_pixel_ratio()
    rw, rh = int(w * ratio), int(h * ratio)
    rw, rh = max(1, rw), max(1, rh)
    image = QImage(rw, rh, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    pixmap = QPixmap.fromImage(image)
    if ratio > 1.0:
        pixmap.setDevicePixelRatio(ratio)
    return QIcon(pixmap)


def get_builtin_icon(
    name: str,
    size: Union[int, tuple] = 16,
    color: Union[str, None] = None,
) -> QIcon:
    """用内置图标名取 QIcon。name 见 BUILTIN_ICONS 的键（如 close, check, settings, search, house, ...）。"""
    svg = BUILTIN_ICONS.get(name)
    if svg is None:
        return QIcon()
    return svg_to_icon(svg, size=size, color=color)


def render_svg_to_file(
    svg_source: Union[str, Path],
    file_path: Union[str, Path],
    size: Union[int, tuple] = 24,
    color: Union[str, None] = None,
) -> str:
    """将 SVG 渲染为 PNG 写入 file_path，返回用于 QSS url() 的路径（正斜杠）。"""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = _normalize_size(size)
    icon = svg_to_icon(svg_source, size=size, color=color)
    pix = icon.pixmap(QSize(w, h))
    if not pix.isNull():
        pix.save(str(path), "PNG")
    return path.as_posix()
