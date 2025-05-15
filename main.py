# main.py
import weakref
import numpy as np
import sys
import logging
import types
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, Qt, QPoint, QThread, QMutex, QMutexLocker
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
    chunk_received = pyqtSignal(str)
    
    def __init__(self, task, *args, **kwargs):
        super().__init__()
        self.task = task
        self.args = args
        self.kwargs = kwargs
        self._mutex = QMutex(QMutex.Recursive)
        self._active = True

    def run(self):
        try:
            if not self._mutex.tryLock(100):
                raise TimeoutError("获取线程锁超时")
            
            if not self._active:
                return
            
            # 处理生成器类型的任务
            result_generator = self.task(*self.args, **self.kwargs)
            if isinstance(result_generator, types.GeneratorType):
                for chunk in result_generator:
                    if not self._active:
                        break
                    self.chunk_received.emit(chunk)
                self.finished.emit(None)
            else:
                self.finished.emit(result_generator)
        except Exception as e:
            self.error.emit(e)
        finally:
            self._mutex.unlock()

    def cancel(self):
        self._mutex.lock()
        self._active = False
        self._mutex.unlock()

class TaskSeekerApp(QObject):
    api_ready = pyqtSignal(bool)
    screenshot_received = pyqtSignal(np.ndarray)
    text_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._init_components()
        self._connect_signals()
        self._pending_actions = {}
        self.api_thread = None
        self.ocr_thread = None
        self._api_worker = None
        self._ocr_worker = None
        self.thread_lock = QMutex(QMutex.Recursive)

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

    def on_screenshot_canceled(self):
        """处理截图取消时的清理"""
        self.tray.show()  # 恢复托盘显示
        QApplication.processEvents()  # 确保UI更新

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
        self.capture.canceled.connect(self.on_screenshot_canceled)
        self.capture.canceled.connect(lambda: logging.info("截屏取消"))

        # API组件
        self.api_ready.connect(self.handle_api_status)
        # self.check_api_connection()

        # 文本处理
        self.text_received.connect(self.handle_query_text)

        # 悬浮窗口
        self.floating_window.window_hidden.connect(self.store_window_position)
        self.floating_window.copy_requested.connect(self.copy_to_clipboard)

    def _safe_stop_thread(self, worker, thread):
        """增强型线程终止方法"""
        if thread is not None and isinstance(thread, QThread):
            try:
                if worker is not None:
                    worker.cancel()
                thread.quit()
                if not thread.wait(1500):
                    thread.terminate()
                    thread.wait()
            except RuntimeError as e:
                logging.warning(f"线程终止异常: {str(e)}")
            finally:
                if worker is not None:
                    worker.deleteLater()
                thread.deleteLater()
                # 显式重置引用
                if thread is self.api_thread:
                    self.api_thread = None
                    self._api_worker = None
                elif thread is self.ocr_thread:
                    self.ocr_thread = None
                    self._ocr_worker = None

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
            logging.info("截屏完成，开始OCR处理")

            self.tray.show()
            
            # 停止现有OCR线程
            self._safe_stop_thread(self._ocr_worker, self.ocr_thread)
            
            self.ocr_thread = QThread()
            self._ocr_worker = Worker(self.ocr.recognize_text, img)
            self._ocr_worker.moveToThread(self.ocr_thread)
            
            # 使用弱引用避免循环引用
            weak_self = weakref.proxy(self)
            self.ocr_thread.started.connect(self._ocr_worker.run)
            self._ocr_worker.finished.connect(
                lambda text: weak_self.text_received.emit(text) if text is not None else None
            )
            self._ocr_worker.error.connect(
                lambda e: logging.error(f"OCR错误: {str(e)}"))
            
            # 自动清理资源
            self._ocr_worker.finished.connect(self.ocr_thread.quit)
            self.ocr_thread.finished.connect(
                lambda: self._safe_stop_thread(weak_self._ocr_worker, weak_self.ocr_thread))
            
            self.ocr_thread.start()
        except Exception as e:
            logging.error(f"OCR处理失败: {str(e)}")
        finally:
            self.tray.show()  # 确保显示托盘
            QApplication.processEvents()

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
        """处理文本，增强流式请求控制"""
        if not text.strip():
            return

        with QMutexLocker(self.thread_lock):
            # 停止现有API请求
            self._safe_stop_thread(self._api_worker, self.api_thread)
            
            # 初始化新线程
            self.api_thread = QThread()
            self._api_worker = Worker(self.api.generate_response, text)
            self._api_worker.moveToThread(self.api_thread)
            
            # 弱引用防止循环引用
            weak_self = weakref.proxy(self)
            weak_window = weakref.proxy(self.floating_window)
            
            # 连接流式信号
            self._api_worker.chunk_received.connect(
                lambda chunk: weak_window.stream_chunk_received.emit(chunk))
            self._api_worker.finished.connect(
                lambda: weak_window.stream_finished.emit())
            self._api_worker.error.connect(
                lambda e: weak_window.stream_finished.emit())
            
            # 连接线程信号
            self.api_thread.started.connect(self._api_worker.run)
            self.floating_window.stream_finished.connect(
                lambda: weak_self._safe_stop_thread(weak_self._api_worker, weak_self.api_thread))
            
            # 启动流程
            self.floating_window.start_streaming(text)
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
            # self.check_api_connection()
            
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
            # 按照依赖顺序关闭
            self._safe_stop_thread(self._ocr_worker, self.ocr_thread)
            self._safe_stop_thread(self._api_worker, self.api_thread)
            
            self.hotkeys.unregister_all()
            self.capture.close()
            self.floating_window.close()
            self.tray.hide()
            
            QTimer.singleShot(1000, lambda: QApplication.instance().quit())
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