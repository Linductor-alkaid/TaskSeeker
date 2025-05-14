# main.py
import numpy as np
import sys
import logging
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, Qt, QPoint, QThread, QMutex
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

class Worker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(Exception)
    
    def __init__(self, task, *args, **kwargs):
        super().__init__()
        self.task = task
        self.args = args
        self.kwargs = kwargs
        self.mutex = QMutex()

    def run(self):
        try:
            self.mutex.lock()
            result = self.task(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(e)
        finally:
            self.mutex.unlock()

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

        # 线程控制
        self.ocr_thread = None
        self.api_thread = None

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
            
            # 终止已存在的线程并清除引用
            if self.ocr_thread is not None:
                if self.ocr_thread.isRunning():
                    self.ocr_thread.quit()
                    self.ocr_thread.wait()
                self.ocr_thread = None  # 清除旧引用

            # 创建新线程
            self.ocr_thread = QThread()
            self.ocr_worker = Worker(self.ocr.recognize_text, img)
            self.ocr_worker.moveToThread(self.ocr_thread)
            
            # 信号连接
            self.ocr_thread.started.connect(self.ocr_worker.run)
            self.ocr_worker.finished.connect(self.text_received.emit)
            self.ocr_worker.error.connect(lambda e: logging.error(f"OCR错误: {str(e)}"))
            self.ocr_worker.finished.connect(self.ocr_thread.quit)
            self.ocr_worker.finished.connect(self.ocr_worker.deleteLater)
            self.ocr_thread.finished.connect(self.ocr_thread.deleteLater)
            self.ocr_thread.finished.connect(lambda: setattr(self, 'ocr_thread', None))  # 新增
            
            # 启动线程
            self.ocr_thread.start()
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
        
        # 终止已存在的API线程并清除引用
        if self.api_thread is not None:
            if self.api_thread.isRunning():
                self.api_thread.quit()
                self.api_thread.wait()
            self.api_thread = None  # 清除旧引用

        # 创建新线程
        self.api_thread = QThread()
        self.api_worker = Worker(self.api.generate_response, text)
        self.api_worker.moveToThread(self.api_thread)
        
        # 信号连接
        self.api_thread.started.connect(self.api_worker.run)
        self.api_worker.finished.connect(
            lambda response: self.floating_window.show_content(response))
        self.api_worker.finished.connect(self.floating_window.show)
        self.api_worker.error.connect(
            lambda e: self.floating_window.show_error(f"API错误: {str(e)}"))
        self.api_worker.finished.connect(self.api_thread.quit)
        self.api_worker.finished.connect(self.api_worker.deleteLater)
        self.api_thread.finished.connect(self.api_thread.deleteLater)
        self.api_thread.finished.connect(lambda: setattr(self, 'api_thread', None))  # 新增
        
        # 启动线程
        self.api_thread.start()

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
        try:
            # 确保对话框获得焦点
            self.settings_dialog.setWindowState(
                self.settings_dialog.windowState() & ~Qt.WindowMinimized)
            self.settings_dialog.activateWindow()
            self.settings_dialog.raise_()
            
            # 强制置顶并模态显示
            self.settings_dialog.setWindowFlags(
                self.settings_dialog.windowFlags() | Qt.WindowStaysOnTopHint)
            self.settings_dialog.exec_()
            
            # 恢复窗口标志
            self.settings_dialog.setWindowFlags(
                self.settings_dialog.windowFlags() & ~Qt.WindowStaysOnTopHint)
            
            self._reload_configurations()
        except Exception as e:
            logging.error(f"设置窗口异常: {str(e)}")

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
            self.floating_window.update_style()
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
            # 终止所有线程
            if self.ocr_thread and self.ocr_thread.isRunning():
                self.ocr_thread.quit()
                self.ocr_thread.wait(1000)
                
            if self.api_thread and self.api_thread.isRunning():
                self.api_thread.quit()
                self.api_thread.wait(1000)
                
            # 原有关闭逻辑...
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