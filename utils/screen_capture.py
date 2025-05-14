# utils/screen_capture.py
import numpy as np
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import QPainter, QColor, QPen, QCursor
import mss

class ScreenCapture(QWidget):
    captured = pyqtSignal(np.ndarray)  # 携带截图的numpy数组信号
    canceled = pyqtSignal()            # 取消截屏信号

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_screen_params()

    def init_ui(self):
        """初始化界面参数"""
        self.setWindowTitle("截屏区域选择")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        
        # 初始化选区参数
        self.selection_start = QPoint()
        self.selection_end = QPoint()
        self.is_dragging = False

    def init_screen_params(self):
        """获取多显示器参数"""
        self.screens = []
        for screen in QApplication.screens():
            geometry = screen.geometry()
            self.screens.append({
                "left": geometry.x(),
                "top": geometry.y(),
                "width": geometry.width(),
                "height": geometry.height()
            })

    def start_capture(self):
        """启动截屏流程"""
        self.showFullScreen()
        self.activateWindow()
        self.raise_()

    def paintEvent(self, event):
        """绘制半透明遮罩和选区"""
        painter = QPainter(self)
        
        # 绘制全屏半透明遮罩
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawRect(self.rect())
        
        # 绘制当前选区
        if self.is_dragging and not self.selection_start.isNull():
            rect = self.normalized_rect()
            self.draw_selection_rect(painter, rect)

    def draw_selection_rect(self, painter, rect):
        """绘制选区矩形和尺寸提示"""
        # 绘制半透明选区
        painter.setBrush(QColor(255, 255, 255, 30))
        painter.drawRect(rect)
        
        # 绘制边框
        pen = QPen(QColor(255, 69, 0), 2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawRect(rect)
        
        # 绘制尺寸提示
        text = f"{rect.width()}×{rect.height()}"
        painter.setPen(Qt.white)
        painter.drawText(rect.bottomRight() + QPoint(5, 15), text)

    def mousePressEvent(self, event):
        """开始拖动选区"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        """更新选区范围"""
        if self.is_dragging:
            self.selection_end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        """结束选区选择"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            self.selection_end = event.pos()
            
            if self.has_valid_selection():
                self.capture_selection()
            else:
                self.canceled.emit()
            
            self.close()

    def keyPressEvent(self, event):
        """处理ESC取消操作"""
        if event.key() == Qt.Key_Escape:
            self.canceled.emit()
            self.close()

    def normalized_rect(self) -> QRect:
        """获取标准化后的选区矩形"""
        return QRect(
            min(self.selection_start.x(), self.selection_end.x()),
            min(self.selection_start.y(), self.selection_end.y()),
            abs(self.selection_start.x() - self.selection_end.x()),
            abs(self.selection_start.y() - self.selection_end.y())
        )

    def has_valid_selection(self) -> bool:
        """验证选区有效性"""
        rect = self.normalized_rect()
        return rect.width() > 10 and rect.height() > 10

    def capture_selection(self):
        """执行屏幕捕获"""
        screen_rect = self.get_active_screen()
        selection = self.normalized_rect()
        
        # 转换为全局坐标
        global_rect = QRect(
            screen_rect["left"] + selection.x(),
            screen_rect["top"] + selection.y(),
            selection.width(),
            selection.height()
        )
        
        # 使用mss截取
        with mss.mss() as sct:
            monitor = {
                "left": global_rect.x(),
                "top": global_rect.y(),
                "width": global_rect.width(),
                "height": global_rect.height()
            }
            try:
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                self.captured.emit(img)
            except Exception as e:
                self.canceled.emit()

    def get_active_screen(self) -> dict:
        """获取当前激活的显示器参数"""
        cursor_pos = QCursor.pos()
        for screen in self.screens:
            if QRect(
                screen["left"],
                screen["top"],
                screen["width"],
                screen["height"]
            ).contains(cursor_pos):
                return screen
        return self.screens[0]

if __name__ == "__main__":
    # 测试代码
    import sys
    from PIL import Image

    def handle_capture(img):
        Image.fromarray(img).show()

    app = QApplication(sys.argv)
    
    capture = ScreenCapture()
    capture.captured.connect(handle_capture)
    capture.canceled.connect(lambda: print("Capture canceled"))
    
    # 延时启动以便观察效果
    from PyQt5.QtCore import QTimer
    QTimer.singleShot(1000, capture.start_capture)
    
    sys.exit(app.exec_())