# gui/tray_icon.py
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import QSize, Qt, pyqtSignal
from config import global_config

class SystemTray(QSystemTrayIcon):
    show_settings = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化托盘图标
        self._init_icon()
        self.setToolTip("TaskSeeker Assistant\nRight click for menu")
        
        # 创建上下文菜单
        self.menu = QMenu()
        self._create_actions()
        self._build_context_menu()
        
        # 事件绑定
        self.activated.connect(self._on_tray_activate)
        
        # 显示托盘图标
        self.show()

    def _init_icon(self):
        """初始化托盘图标（使用内置图标）"""
        icon_data = """
            iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABHNCSVQICAgIfAhkiAAAAAlwSFlz
            AAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAG7SURB
            VFiF7ZdNSwJRFIaPqSOmYl+0KIIW0UJatGgTtGjTLygoiH5B/QHXLXJRi1oEQQstCoKCoE1EQRBF
            QdQmKFHxAxVHx3Gc8aPFDM5cZ+69E7QIH5x7z3nPe+acmTtX0nVdR4xY/juA/wuSJEkAFEUB4N3W
            NE3MZRgQBEE4A0mSJAA+nw8Aq9UKgMPhAMDpdALgcrkAcLvdALjd7r8H8Hq9ABiGAYBhGADYbDYx
            l2FAiJvNJgB2ux0Au90u5jIMCLHX6wXA5/MB4Pf7AfD7/WIuw4AQBwIBAAKBAACBQEDMZRgQ4lAo
            BEAoFAIgHA4DEA6HxVyGASEOh8MAzM3NATA/Pw/AwsKCmMswIMTRaBSAaDQKQCwWAyAej4u5DANC
            nEwmAUilUgCk02kAMpmMmMswIMTZbBaAXC4HQD6fByCfz4u5DANCPDk5CcDU1BQA09PTAMzMzIi5
            DANCPD4+DsDY2BgAY2NjAIyPj4u5DANCPDIyAsDw8DAAw8PDAAwNDYm5DANCPDg4CMDg4CCqqqKq
            KgADAwNiLsOAECuKAsDq6iqaprG2tgbA1taWmMswIMQ7OzsA7O7uYrFY2NvbA2B/f1/MZRj4eA0/
            PDzk6OiI4+NjAE5OTsRchgEhPj095ezsjPPzcwAuLi7EXIYBIS6VSlxeXnJ1dQXA9fW1mMswIMQ3
            NzfUajVqtRoAt7e3Yi7DgBBXq1Xq9TqNRgOARqMh5jIMCPHLywsvLy+8vr4C8Pb2JuYyDAjx+/s7
            7XabTqcDQKfTEXMZBoT4AxhjxPILv4hMJmP6d3x9fQm5DAPfAD4q2CqB4xLxAAAAAElFTkSuQmCC
        """
        pixmap = QPixmap()
        pixmap.loadFromData(bytes(icon_data.encode('utf-8')), format="png")
        self.setIcon(QIcon(pixmap))

    def _create_actions(self):
        """创建菜单动作"""
        # 设置
        self.settings_action = QAction("设置...", self.menu)
        self.settings_action.triggered.connect(self.show_settings.emit)
        
        # 退出
        self.quit_action = QAction("退出", self.menu)
        self.quit_action.triggered.connect(self.quit_requested.emit)

    def _build_context_menu(self):
        """构建右键菜单"""
        self.menu.addAction(self.settings_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)
        self.setContextMenu(self.menu)

    def _on_tray_activate(self, reason):
        """处理托盘交互事件"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_settings.emit()
        elif reason == QSystemTrayIcon.Context:
            self.contextMenu().exec_(self.geometry().center())

if __name__ == "__main__":
    # 测试代码
    import sys
    app = QApplication(sys.argv)
    
    def show_settings():
        print("显示设置对话框")
    
    def quit_app():
        app.quit()
    
    tray = SystemTray()
    tray.show_settings.connect(show_settings)
    tray.quit_requested.connect(quit_app)
    
    sys.exit(app.exec_())