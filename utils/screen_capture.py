# utils/screen_capture.py
import numpy as np
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import QPainter, QColor, QPen, QCursor, QScreen
import mss

class ScreenCapture(QWidget):
    captured = pyqtSignal(np.ndarray)
    canceled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.current_screen_geometry = QRect()

    def init_ui(self):
        """初始化无边框透明窗口"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        
        # 初始化选区参数
        self.selection_start = QPoint()
        self.selection_end = QPoint()
        self.is_dragging = False

    def start_capture(self):
        """覆盖当前显示器"""
        # 获取鼠标所在屏幕
        current_screen = QApplication.screenAt(QCursor.pos())
        if not current_screen:
            current_screen = QApplication.primaryScreen()

        self.current_screen = current_screen
        
        # 记录当前屏幕参数
        self.current_screen_geometry = current_screen.geometry()
        
        # 设置窗口尺寸为当前屏幕尺寸
        self.setGeometry(self.current_screen_geometry)
        self.show()
        self.activateWindow()
        self.raise_()

    def paintEvent(self, event):
        """绘制半透明遮罩"""
        painter = QPainter(self)
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawRect(self.rect())
        
        # 绘制当前选区
        if self.is_dragging and not self.selection_start.isNull():
            rect = self.normalized_rect()
            self.draw_selection_rect(painter, rect)

    def draw_selection_rect(self, painter, rect):
        """优化边框绘制效果"""
        # 半透明填充
        painter.setBrush(QColor(255, 255, 255, 0))
        painter.drawRect(rect)
        
        # 虚线边框
        pen = QPen(QColor(255, 69, 0), 2)
        pen.setDashPattern([4, 4])
        painter.setPen(pen)
        painter.drawRect(rect)
        
        # 尺寸标注
        text = f"{rect.width()}×{rect.height()}"
        painter.setPen(Qt.white)
        painter.setFont(self.font())
        painter.drawText(rect.bottomRight() + QPoint(5, 15), text)

    def mousePressEvent(self, event):
        """支持右键取消"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.selection_start = event.pos()
            self.selection_end = event.pos()
        elif event.button() == Qt.RightButton:
            self.canceled.emit()
            self.close()
        self.update()

    def mouseMoveEvent(self, event):
        """实时更新选区"""
        if self.is_dragging:
            self.selection_end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        """释放时校验选区有效性"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            if self.has_valid_selection():
                self.capture_selection()
            else:
                self.canceled.emit()
            self.close()

    def keyPressEvent(self, event):
        """增强按键支持"""
        if event.key() in [Qt.Key_Escape, Qt.Key_C]:
            self.canceled.emit()
            self.close()

    def normalized_rect(self) -> QRect:
        """数学坐标矫正"""
        return QRect(
            min(self.selection_start.x(), self.selection_end.x()),
            min(self.selection_start.y(), self.selection_end.y()),
            abs(self.selection_start.x() - self.selection_end.x()),
            abs(self.selection_start.y() - self.selection_end.y())
        )

    def has_valid_selection(self) -> bool:
        """最小尺寸校验"""
        rect = self.normalized_rect()
        return rect.width() >= 10 and rect.height() >= 10

    def capture_selection(self):
        """跨显示器截图支持"""
        rect = self.normalized_rect()
        # 获取当前屏幕的缩放比例
        device_pixel_ratio = self.current_screen.devicePixelRatio() if hasattr(self, 'current_screen') else 1.0
        # 转换为物理像素坐标
        phys_rect = (
            int(self.current_screen_geometry.x() + rect.x() * device_pixel_ratio),
            int(self.current_screen_geometry.y() + rect.y() * device_pixel_ratio),
            int(rect.width() * device_pixel_ratio),
            int(rect.height() * device_pixel_ratio)
        )
        
        try:
            with mss.mss() as sct:
                screenshot = sct.grab({
                    "left": phys_rect[0],
                    "top": phys_rect[1],
                    "width": phys_rect[2],
                    "height": phys_rect[3]
                })
                self.captured.emit(np.array(screenshot))
        except Exception as e:
            self.canceled.emit()

if __name__ == "__main__":
    # 测试时启用高DPI支持
    import sys
    from PyQt5.QtCore import Qt, QTimer
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    window = ScreenCapture()
    
    from PIL import Image
    def show_image(img):
        Image.fromarray(img).show()
    
    window.captured.connect(show_image)
    window.canceled.connect(lambda: print("Cancelled"))
    QTimer.singleShot(1000, window.start_capture)
    
    sys.exit(app.exec_())