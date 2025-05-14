# main.py
import numpy as np
import sys
import logging
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, Qt, QPoint
from config import global_config
from gui.tray_icon import SystemTray
from core.hotkey_manager import HotkeyManager
from core.api_client import DeepSeekAPI
from core.ocr_processor import OCRProcessor
from utils.screen_capture import ScreenCapture
from gui.settings_dialog import SettingsDialog
from gui.overlay_windows import FloatingWindow
from utils.text_processing import get_selected_text
import platform

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('taskseeker.log'),
        logging.StreamHandler()
    ]
)

class TaskSeekerApp(QObject):
    api_ready = pyqtSignal(bool)
    screenshot_received = pyqtSignal(np.ndarray)
    text_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._init_components()
        self._connect_signals()
        self._pending_actions = {}

    def _init_components(self):
        """初始化所有组件"""
        # 核心组件
        self.api = DeepSeekAPI()
        self.ocr = OCRProcessor()
        self.hotkeys = HotkeyManager()
        self.capture = ScreenCapture()
        
        # GUI组件
        self.tray = SystemTray()
        self.settings_dialog = SettingsDialog()
        self.floating_window = FloatingWindow()

        # 状态变量
        self.last_query_position = None
        self.current_screenshot = None

    def _connect_signals(self):
        """连接信号与槽"""
        # 系统托盘
        self.tray.show_settings.connect(self.show_settings)
        self.tray.quit_requested.connect(self.graceful_shutdown)

        # 热键管理器
        self.hotkeys.register_all({
            'screenshot': self.start_screenshot_capture,
            'text_select': self.process_text_selection
        })

        # 截屏组件
        self.capture.captured.connect(self.handle_screenshot)
        self.capture.canceled.connect(lambda: logging.info("截屏取消"))

        # API组件
        self.api_ready.connect(self.handle_api_status)
        self.check_api_connection()

        # 文本处理
        self.text_received.connect(self.handle_query_text)

        # 悬浮窗口
        self.floating_window.window_hidden.connect(self.store_window_position)
        self.floating_window.copy_requested.connect(self.copy_to_clipboard)

    def check_api_connection(self):
        """启动时验证API连接"""
        if not self.api.validate_config():
            QTimer.singleShot(1000, self.show_api_warning)
            self.api_ready.emit(False)
        else:
            self.api_ready.emit(True)

    def show_api_warning(self):
        """显示API连接警告"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText("API连接失败，请检查配置")
        msg.setWindowTitle("连接问题")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def start_screenshot_capture(self):
        """启动截屏流程"""
        try:
            # 确保程序获得焦点
            self.tray.hide()
            QApplication.processEvents()
            self.capture.start_capture()
        except Exception as e:
            logging.error(f"截屏启动失败: {str(e)}")

    def handle_screenshot(self, img: np.ndarray):
        """处理截屏结果"""
        try:
            self.current_screenshot = img
            logging.info("开始OCR识别...")
            text = self.ocr.recognize_text(img)
            self.text_received.emit(text)
        except Exception as e:
            logging.error(f"OCR处理失败: {str(e)}")

    def process_text_selection(self):
        """处理划词查询"""
        try:
            selected_text = get_selected_text()
            if selected_text and len(selected_text) > 5000:
                logging.warning("选中文本过长，已截断前5000字符")
                selected_text = selected_text[:5000]
            self.text_received.emit(selected_text)
        except Exception as e:
            logging.error(f"文本选择失败: {str(e)}")

    def handle_query_text(self, text: str):
        """处理待查询文本"""
        if not text.strip():
            return

        # 显示加载状态
        self.floating_window.show_loading()
        
        # 执行API请求
        try:
            response = self.api.generate_response(text)
            self.floating_window.update_content(response)
            self.floating_window.show()
        except Exception as e:
            logging.error(f"API请求失败: {str(e)}")
            self.floating_window.show_error("服务暂时不可用")

    def store_window_position(self, pos: QPoint):
        """记录窗口最后位置"""
        self.last_query_position = pos

    def copy_to_clipboard(self, text: str):
        """复制文本到剪贴板"""
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(text, mode=clipboard.Clipboard)
            if clipboard.supportsSelection():
                clipboard.setText(text, mode=clipboard.Selection)
        except Exception as e:
            logging.error(f"剪贴板操作失败: {str(e)}")

    def show_settings(self):
        """显示设置对话框"""
        self.settings_dialog.exec_()
        self._reload_configurations()

    def _reload_configurations(self):
        """重新加载所有配置"""
        try:
            # 热键更新
            self.hotkeys.update_config()
            self.hotkeys.register_all({
                'screenshot': self.start_screenshot_capture,
                'text_select': self.process_text_selection
            })
            
            # API配置更新
            self.api.update_config()
            self.check_api_connection()
            
            # OCR配置更新
            self.ocr.__init__()
            
            # 界面样式更新
            self.floating_window.update_style(
                font_size=global_config.get("appearance.font_size"),
                bg_color=global_config.get("appearance.background"),
                text_color=global_config.get("appearance.text_color")
            )
        except Exception as e:
            logging.error(f"配置重载失败: {str(e)}")

    def handle_api_status(self, status: bool):
        """处理API状态变化"""
        self.tray.setToolTip("DeepSeeker助手 - " + 
                            ("已连接" if status else "连接断开"))

    def graceful_shutdown(self):
        """优雅关闭程序"""
        logging.info("开始关闭程序...")
        try:
            self.hotkeys.unregister_all()
            self.capture.close()
            self.floating_window.close()
            self.tray.hide()
            QTimer.singleShot(1000, QApplication.instance().quit)
        except Exception as e:
            logging.critical(f"关闭失败: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    try:
        # 高DPI支持
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
        
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        
        # 初始化主程序
        main_app = TaskSeekerApp()
        
        # 延迟初始化确保托盘图标可见
        QTimer.singleShot(1000, main_app.check_api_connection)
        
        sys.exit(app.exec_())
    except Exception as e:
        logging.critical(f"程序启动失败: {str(e)}")
        sys.exit(1)