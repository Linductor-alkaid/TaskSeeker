# gui/overlay_windows.py
from PyQt5.QtCore import Qt, QPoint, QTimer, pyqtSignal, QSize, QEvent, QRectF, QRect
from PyQt5.QtWidgets import (QWidget, QTextEdit, QApplication, QPushButton, 
                             QScrollArea, QVBoxLayout, QSizeGrip, QMenu)
from PyQt5.QtGui import (QPainter, QColor, QPen, QCursor, QFont, QLinearGradient,
                        QBrush, QTextCursor, QKeyEvent, QPainterPath)
from PyQt5.QtWidgets import QGraphicsOpacityEffect  # 用于复制反馈动画
from PyQt5.QtCore import QPropertyAnimation, QAbstractAnimation  # 用于动画系统
from config import global_config
import time

class FloatingWindow(QWidget):
    closed = pyqtSignal()
    window_hidden = pyqtSignal()
    shown = pyqtSignal()
    copy_requested = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    stream_chunk_received = pyqtSignal(str)
    stream_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._init_state()
        self._load_config()
        self._init_shortcuts()
        self.streaming = False
        self.markdown_content = ""
        self.stream_buffer = []
        self.stream_start_time = None
        # 连接信号
        self.stream_chunk_received.connect(self._append_stream_chunk)
        self.stream_finished.connect(self._finalize_stream)

        self.stream_update_timer = QTimer()
        self.stream_update_timer.timeout.connect(self._flush_stream_buffer)
        self.stream_update_timer.setInterval(150)  # 150毫秒更新一次
        
        # 配置更新监听
        global_config.config_updated.connect(self._on_config_changed)

    def _init_ui(self):
        """初始化界面组件"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(200, 150)
        
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(0)
        
        # 可调整大小的容器
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet("background: rgba(245, 245, 245, 200); border-radius: 5px;")
        
        # 滚动区域
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setWidget(self.container)
        self.main_layout.addWidget(self.scroll_area)
        
        # 文本编辑区域
        self.text_edit = QTextEdit(self.container)
        self.text_edit.setReadOnly(True)
        self.text_edit.setFrameShape(QTextEdit.NoFrame)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setContextMenuPolicy(Qt.CustomContextMenu)
        self.text_edit.customContextMenuRequested.connect(self._show_context_menu)
        
        # 关闭按钮
        self.close_btn = QPushButton("×", self)
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(200, 50, 50, 200);
                color: white;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(220, 70, 70, 220);
            }
        """)
        self.close_btn.clicked.connect(self.close)
        
        # 尺寸调整手柄
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(16, 16)
        
        # 布局管理
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.addWidget(self.text_edit)
        
        # 窗口阴影效果
        self.setGraphicsEffect(None)  # 禁用继承的样式
        self._apply_shadow_effect()

    def _init_state(self):
        """初始化交互状态"""
        self.dragging = False
        self.resizing = False
        self.hidden_state = False
        self.offset = QPoint()
        self.resize_edge = None
        self.last_position = None
        self.last_size = None
        
        # 边缘检测阈值
        self.edge_margin = 8

    def start_streaming(self, prompt: str):
        """流式启动逻辑"""
        self.streaming = True
        self.is_first_chunk = True
        self.stream_buffer = []
        self.stream_start_time = time.time()
        self.error_occurred = False  # 新增错误状态标志
        self.show_loading()
        self.stream_update_timer.start()
        
    def _append_stream_chunk(self, chunk: str):
        """追加流式内容"""
        if not self.isVisible():
            self.show()
        if self.error_occurred:
            return
            
        # 如果是第一个块，替换"加载中..."
        if "加载中..." in self.text_edit.toPlainText():
            self.text_edit.setPlainText(chunk)
        else:
            self.text_edit.moveCursor(QTextCursor.End)
            self.text_edit.insertPlainText(chunk)
        
        if "[API错误" in chunk or "[请求中断" in chunk:
            self.error_occurred = True
            self.stream_buffer.append(chunk)
            self._flush_stream_buffer()
            self.stream_finished.emit()
            return
        
        self.stream_buffer.append(chunk)
            
        self.adjust_size()
        
    def _finalize_stream(self):
        """最终状态处理"""
        self.stream_update_timer.stop()
        self._flush_stream_buffer()
        
        if self.error_occurred:
            duration = time.time() - self.stream_start_time
            self.text_edit.append(f"\n[请求异常终止 耗时: {duration:.2f}s]")
            self.container.setStyleSheet("background: rgba(255, 245, 245, 0.95);")
        else:
            duration = time.time() - self.stream_start_time
            self.text_edit.append(f"\n\n[耗时 {duration:.2f}秒]")
        
        # 自动调整窗口尺寸优化
        doc_height = self.text_edit.document().size().height()
        screen_height = QApplication.desktop().availableGeometry().height()
        self.resize(self.width(), min(int(doc_height + 40), int(screen_height * 0.6)))
        
        self.streaming = False
        self.markdown_content = ""
        
    def _flush_stream_buffer(self):
        """批量处理缓冲内容"""
        if not self.stream_buffer or self.error_occurred:
            return
        
        self.markdown_content += "".join(self.stream_buffer)
        self.stream_buffer.clear()
        
        # 处理首块替换逻辑
        if self.is_first_chunk:
            self.text_edit.setMarkdown(self.markdown_content)
            self.is_first_chunk = False
        else:
            self.text_edit.moveCursor(QTextCursor.End)
            self.text_edit.setMarkdown(self.markdown_content)
        
        # # 智能滚动控制
        # scrollbar = self.text_edit.verticalScrollBar()
        # if scrollbar.value() >= scrollbar.maximum() - 50:  # 在接近底部时自动滚动
        #     self.text_edit.ensureCursorVisible()
        
        self.adjust_size()

    def _load_config(self):
        """加载外观配置"""
        # 确保正确解析颜色值
        bg_str = global_config.get("appearance.background", "rgba(245,245,245,0.9)")
        bg_color = QColor()
        if not bg_color.setNamedColor(bg_str):
            if 'rgba' in bg_str:
                parts = [int(x) for x in bg_str[5:-1].split(',')[:3]]
                alpha = int(float(bg_str.split(',')[-1].strip()[:-1])*255)
                bg_color = QColor(*parts, alpha)
            else:
                bg_color = QColor(245, 245, 245, 230)
        
        # 加载窗口透明度
        opacity = global_config.get("appearance.window_opacity", 0.95)
        self.setWindowOpacity(opacity)  # 设置窗口不透明度
        
        self.text_color = QColor(global_config.get("appearance.text_color", "#333333"))
        if not self.text_color.isValid():
            self.text_color = QColor("#333333")
        
        self._update_stylesheet(bg_color, self.text_color)

    def _init_shortcuts(self):
        """初始化快捷键"""
        self.text_edit.keyPressEvent = self._on_key_press

    def update_style(self):
        """重新加载外观配置"""
        self._load_config()  # 复用已有的配置加载逻辑
        self._apply_shadow_effect()
        self.update()

    def show_loading(self):
        """显示加载状态"""
        self.text_edit.setPlainText("加载中...")
        self.adjust_size()
        self.show()
        self.activateWindow()

    def _on_key_press(self, event: QKeyEvent):
        """中断处理"""
        if event.key() == Qt.Key_Escape and self.streaming:
            self.streaming = False
            self.stream_update_timer.stop()
            self.markdown_content += "\n\n*[用户主动中断]*"  # 使用Markdown格式
            self.text_edit.setMarkdown(self.markdown_content)
            self._finalize_stream()
            # 发射中断信号给后台
            self.stream_finished.emit()  
            return
        super().keyPressEvent(event)
    
    def show_error(self, message: str):
        """显示错误信息"""
        self.streaming = False
        self.stream_update_timer.stop()
        self._flush_stream_buffer()

        error_style = """
            #container {
                background: rgba(255, 220, 220, 0.95);
                border: 1px solid rgba(200, 100, 100, 150);
            }
            QTextEdit {
                color: #cc0000;
            }
        """
        self.container.setStyleSheet(error_style + self.container.styleSheet())
        self.text_edit.setPlainText(f"⚠️ 错误: {message}")
        self.adjust_size()
        self.show()
        self.activateWindow()
        
        # 5秒后恢复原始样式
        QTimer.singleShot(5000, self._restore_style)

    def _restore_style(self):
        """恢复默认样式"""
        self._load_config()
        self.update()

    def _on_key_press(self, event: QKeyEvent):
        """自定义快捷键处理"""
        # 复制文本
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_C:
            self.copy_text()
        # 关闭窗口
        elif event.key() == Qt.Key_Escape:
            self.hide_window()
        else:
            super().keyPressEvent(event)

    def _apply_shadow_effect(self):
        """应用窗口阴影效果"""
        self.shadow = QWidget(self)
        self.shadow.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.shadow.setGeometry(5, 5, self.width(), self.height())
        self.shadow.setStyleSheet("""
            background: transparent;
            border-radius: 5px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.15);
        """)
        self.shadow.lower()

    def _update_stylesheet(self, bg_color: QColor, text_color: QColor):
        """动态更新样式表"""
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, bg_color.lighter(110))
        gradient.setColorAt(1, bg_color.darker(110))
        
        style_sheet = f"""
            #container {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {bg_color.lighter(110).name(QColor.HexArgb)},
                    stop:1 {bg_color.darker(110).name(QColor.HexArgb)});
                border: 1px solid rgba(200,200,200,150);
            }}
            QTextEdit {{
                color: {text_color.name()};
                background: transparent;
                selection-color: {text_color.lighter(150).name()};
                selection-background-color: {text_color.darker(150).name()};
            }}
        """
        self.container.setStyleSheet(style_sheet)

    def show_content(self, markdown_text: str):
        """显示Markdown内容"""
        self.text_edit.setMarkdown(markdown_text)
        self.text_edit.moveCursor(QTextCursor.Start)
        self.adjust_size()
        self.show()
        self.activateWindow()

    def adjust_size(self):
        """带节流机制的尺寸调整（修复闪动问题）"""
        if not hasattr(self, "_last_adjust"):
            self._last_adjust = 0
        
        # 限制调整频率(至少间隔200ms)
        now = time.time()
        if now - self._last_adjust < 0.2:
            return
        
        # 保存当前滚动位置
        scrollbar = self.text_edit.verticalScrollBar()
        old_scroll_value = scrollbar.value()
        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 50
        
        doc = self.text_edit.document()
        viewport_width = self.text_edit.viewport().width()
        
        # 精确计算理想高度
        doc.setTextWidth(viewport_width)
        ideal_height = doc.size().height() + 25  # 加上padding
        screen_height = QApplication.desktop().availableGeometry().height()
        new_height = min(int(ideal_height), int(screen_height * 0.7))
        
        # 只有当高度变化超过5像素时才调整
        if abs(self.height() - new_height) > 5:
            # 冻结UI更新
            self.text_edit.setUpdatesEnabled(False)
            
            # 保持底部自动滚动状态
            self.resize(self.width(), new_height)
            
            # 解冻UI更新
            self.text_edit.setUpdatesEnabled(True)
            
            # 恢复滚动位置
            if was_at_bottom:
                scrollbar.setValue(scrollbar.maximum())
            else:
                scrollbar.setValue(old_scroll_value)
        
        self._last_adjust = now

    def mousePressEvent(self, event):
        """处理鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            # 检测是否在可操作区域
            if self._in_resize_area(event.pos()):
                self.resizing = True
                self.resize_start_pos = event.globalPos()
                self.resize_initial_size = self.size()
            else:
                self.dragging = True
                self.offset = event.globalPos() - self.pos()
                
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """处理鼠标移动事件"""
        if self.dragging:
            self.move(event.globalPos() - self.offset)
        elif self.resizing:
            delta = event.globalPos() - self.resize_start_pos
            new_width = int(self.resize_initial_size.width() + delta.x())
            new_height = int(self.resize_initial_size.height() + delta.y())
            self.resize(max(200, new_width), max(150, new_height))
            self.shadow.setGeometry(5, 5, self.width()-10, self.height()-10)
        else:
            # 更新光标形状
            edge = self._detect_edge(event.pos())
            cursor = QCursor()
            if edge in ("left", "right"):
                cursor.setShape(Qt.SizeHorCursor)
            elif edge in ("top", "bottom"):
                cursor.setShape(Qt.SizeVerCursor)
            elif edge in ("top-left", "bottom-right"):
                cursor.setShape(Qt.SizeFDiagCursor)
            elif edge in ("top-right", "bottom-left"):
                cursor.setShape(Qt.SizeBDiagCursor)
            else:
                cursor.setShape(Qt.ArrowCursor)
            self.setCursor(cursor)
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件"""
        self.dragging = False
        self.resizing = False
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        """鼠标离开窗口时重置光标"""
        self.setCursor(Qt.ArrowCursor)
        super().leaveEvent(event)

    def _detect_edge(self, pos: QPoint) -> str:
        """检测鼠标是否在窗口边缘"""
        rect = self.rect()
        edge_margin = self.edge_margin
        
        positions = {
            "left": pos.x() < edge_margin,
            "right": pos.x() > rect.width() - edge_margin,
            "top": pos.y() < edge_margin,
            "bottom": pos.y() > rect.height() - edge_margin
        }
        
        if positions["left"] and positions["top"]:
            return "top-left"
        if positions["left"] and positions["bottom"]:
            return "bottom-left"
        if positions["right"] and positions["top"]:
            return "top-right"
        if positions["right"] and positions["bottom"]:
            return "bottom-right"
        if positions["left"]:
            return "left"
        if positions["right"]:
            return "right"
        if positions["top"]:
            return "top"
        if positions["bottom"]:
            return "bottom"
        return None

    def _in_resize_area(self, pos: QPoint) -> bool:
        """判断是否在可调整大小的区域"""
        return self._detect_edge(pos) is not None

    def _show_context_menu(self, pos):
        """显示右键上下文菜单"""
        menu = QMenu(self.text_edit)
        copy_action = menu.addAction("复制")
        copy_action.triggered.connect(self.copy_text)
        menu.addSeparator()
        close_action = menu.addAction("关闭")
        close_action.triggered.connect(self.close)
        menu.exec_(self.text_edit.mapToGlobal(pos))

    def copy_text(self):
        """复制选中文本"""
        cursor = self.text_edit.textCursor()
        selected_text = cursor.selectedText()
        if selected_text:
            self.text_edit.copy()
            self.copy_requested.emit(selected_text)  # 发射带文本参数的信号
        self._show_copy_feedback()

    def _show_copy_feedback(self):
        """显示复制成功反馈"""
        effect = QGraphicsOpacityEffect(self.text_edit)
        self.text_edit.setGraphicsEffect(effect)
        
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(500)
        animation.setStartValue(1.0)
        animation.setKeyValueAt(0.5, 0.3)
        animation.setEndValue(1.0)
        animation.start(QAbstractAnimation.DeleteWhenStopped)

    def hide_window(self):
        """隐藏窗口并记录状态"""
        if not self.hidden_state:
            self.last_position = self.pos()
            self.last_size = self.size()
            self.hide()
            self.hidden_state = True
            self.window_hidden.emit()

    def show_window(self):
        """恢复显示窗口"""
        if self.hidden_state and self.last_position and self.last_size:
            self.move(self.last_position)
            self.resize(self.last_size)
            self.show()
            self.hidden_state = False
            self.shown.emit()

    def toggle_visibility(self, global_pos: QPoint):
        """切换窗口可见性"""
        if self.hidden_state:
            if self.last_position and self.last_size:
                # 判断点击位置是否在原有区域内
                target_rect = QRect(self.last_position, self.last_size)
                if target_rect.contains(global_pos):
                    self.show_window()
        else:
            self.hide_window()

    def _on_config_changed(self):
        """响应配置变更"""
        self._load_config()
        self.update()

    def resizeEvent(self, event):
        """处理窗口大小变化"""
        self.shadow.setGeometry(5, 5, self.width()-10, self.height()-10)
        self.close_btn.move(self.width() - 30, 6)
        self.size_grip.move(self.width() - 20, self.height() - 20)
        super().resizeEvent(event)

    def paintEvent(self, event):
        """自定义绘制实现亚克力效果"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 修复点：将QRect转换为QRectF
        rect_f = QRectF(self.rect())  # 转换原始矩形为浮点版本
        adjusted_rect = rect_f.adjusted(1, 1, -1, -1)  # 使用浮点调整
        
        path = QPainterPath()
        path.addRoundedRect(adjusted_rect, 5, 5)  # 现在参数类型正确
        
        painter.setClipPath(path)
        painter.fillRect(rect_f, QColor(0, 0, 0, 30))
        
        # 绘制边框
        pen = QPen(QColor(200, 200, 200, 120))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRoundedRect(adjusted_rect, 5, 5)

if __name__ == "__main__":
    # 测试代码
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    window = FloatingWindow()
    window.show_content("""## 测试内容
- **功能1**：支持Markdown渲染
- 数学公式：$E=mc^2$
- 代码块：
```python
print("Hello World")""")
    sys.exit(app.exec_())