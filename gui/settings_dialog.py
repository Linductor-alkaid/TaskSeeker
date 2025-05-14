# gui/settings_dialog.py
from PyQt5.QtWidgets import (QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QColorDialog, QSpinBox,
                             QDoubleSpinBox, QComboBox, QTextEdit, QKeySequenceEdit,
                             QMessageBox, QFormLayout, QGroupBox)
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtCore import Qt, pyqtSignal
from config import global_config

class SettingsDialog(QDialog):
    config_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumSize(600, 500)

        self._create_widgets()
        self._setup_layout()
        self._load_current_config()
        self._connect_signals()

    def _create_widgets(self):
        """创建所有界面组件"""
        # 快捷键设置
        self.screenshot_key_edit = QKeySequenceEdit()
        self.text_select_key_edit = QKeySequenceEdit()
        
        # API设置
        self.api_token_edit = QLineEdit()
        self.api_token_edit.setEchoMode(QLineEdit.Password)
        self.api_endpoint_edit = QLineEdit()
        self.api_model_combo = QComboBox()
        self.api_model_combo.addItems(["deepseek-chat", "deepseek-R1"])
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(1, 4096)
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        
        # 外观设置
        self.bg_color_btn = QPushButton("选择颜色")
        self.text_color_btn = QPushButton("选择颜色")
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 36)
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(10, 100)
        self.opacity_spin.setSuffix("%")
        
        # 系统提示
        self.system_prompt_edit = QTextEdit()
        
        # 操作按钮
        self.save_btn = QPushButton("保存")
        self.cancel_btn = QPushButton("取消")
        self.default_btn = QPushButton("恢复默认")

    def _setup_layout(self):
        """组织界面布局"""
        tab_widget = QTabWidget()
        
        # 快捷键标签页
        hotkey_tab = QWidget()
        form = QFormLayout()
        form.addRow("截屏快捷键:", self.screenshot_key_edit)
        form.addRow("划词快捷键:", self.text_select_key_edit)
        hotkey_tab.setLayout(form)
        
        # API标签页
        api_tab = QWidget()
        api_layout = QFormLayout()
        api_layout.addRow("API Token:", self.api_token_edit)
        api_layout.addRow("API 端点:", self.api_endpoint_edit)
        api_layout.addRow("模型:", self.api_model_combo)
        api_layout.addRow("最大tokens:", self.max_tokens_spin)
        api_layout.addRow("温度系数:", self.temperature_spin)
        api_tab.setLayout(api_layout)
        
        # 外观标签页
        appearance_tab = QWidget()
        appearance_layout = QFormLayout()
        appearance_layout.addRow("背景颜色:", self.bg_color_btn)
        appearance_layout.addRow("文字颜色:", self.text_color_btn)
        appearance_layout.addRow("字体大小:", self.font_size_spin)
        appearance_layout.addRow("窗口透明度:", self.opacity_spin)
        appearance_tab.setLayout(appearance_layout)
        
        # 系统提示标签页
        prompt_tab = QWidget()
        prompt_layout = QVBoxLayout()
        prompt_layout.addWidget(QLabel("系统提示词:"))
        prompt_layout.addWidget(self.system_prompt_edit)
        prompt_tab.setLayout(prompt_layout)
        
        tab_widget.addTab(hotkey_tab, "快捷键")
        tab_widget.addTab(api_tab, "API设置")
        tab_widget.addTab(appearance_tab, "外观")
        tab_widget.addTab(prompt_tab, "系统提示")

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.default_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)

        main_layout = QVBoxLayout()
        main_layout.addWidget(tab_widget)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

    def _load_current_config(self):
        """从配置加载当前设置"""
        # 快捷键
        self.screenshot_key_edit.setKeySequence(
            QKeySequence(global_config.get("hotkeys.screenshot"))
        )
        self.text_select_key_edit.setKeySequence(
            QKeySequence(global_config.get("hotkeys.text_select"))
        )
        
        # API设置
        self.api_token_edit.setText(global_config.get("api.token", ""))
        self.api_endpoint_edit.setText(global_config.get("api.endpoint"))
        self.api_model_combo.setCurrentText(global_config.get("api.model"))
        self.max_tokens_spin.setValue(global_config.get("api.max_tokens"))
        self.temperature_spin.setValue(global_config.get("api.temperature"))
        
        # 外观
        self.font_size_spin.setValue(global_config.get("appearance.font_size"))
        self.opacity_spin.setValue(int(global_config.get("appearance.window_opacity", 95) * 100))
        
        # 系统提示
        self.system_prompt_edit.setText(global_config.get("api.system_prompt", ""))

        bg_color = QColor(global_config.get("appearance.background", "#F5F5F5"))
        self.bg_color_btn.setStyleSheet(f"background-color: {bg_color.name(QColor.HexArgb)};")
        
        text_color = QColor(global_config.get("appearance.text_color", "#333333"))
        self.text_color_btn.setStyleSheet(f"background-color: {text_color.name(QColor.HexArgb)};")

    def _connect_signals(self):
        """连接信号与槽"""
        self.bg_color_btn.clicked.connect(lambda: self._pick_color("background"))
        self.text_color_btn.clicked.connect(lambda: self._pick_color("text_color"))
        self.save_btn.clicked.connect(self._save_settings)
        self.cancel_btn.clicked.connect(self.reject)
        self.default_btn.clicked.connect(self._reset_default)

    def _pick_color(self, color_type):
        """处理颜色选择"""
        current_color = QColor()
        current_color.setNamedColor(
            global_config.get(f"appearance.{color_type}", "#FFFFFF")
        )
        
        color = QColorDialog.getColor(
            initial=current_color,
            parent=self,
            title=f"选择{color_type}颜色"
        )
        
        if color.isValid():
            # 实时更新按钮颜色预览
            btn = self.bg_color_btn if color_type == "background" else self.text_color_btn
            btn.setStyleSheet(f"background-color: {color.name(QColor.HexArgb)};")
            # 暂时保存颜色值，直到用户点击保存
            setattr(self, f"_{color_type.replace('.', '_')}", color)

    def _validate_settings(self):
        """验证输入有效性"""
        # 检查快捷键冲突
        key1 = self.screenshot_key_edit.keySequence().toString()
        key2 = self.text_select_key_edit.keySequence().toString()
        if key1 == key2:
            QMessageBox.warning(self, "冲突警告", "快捷键不能重复设置")
            return False
        
        # 检查API必填项
        if not self.api_token_edit.text().strip():
            QMessageBox.warning(self, "参数错误", "API Token不能为空")
            return False
            
        return True

    def _save_settings(self):
        """保存配置到全局设置"""
        if not self._validate_settings():
            return
        
        try:
            # 快捷键
            global_config.set("hotkeys.screenshot", 
                self.screenshot_key_edit.keySequence().toString())
            global_config.set("hotkeys.text_select",
                self.text_select_key_edit.keySequence().toString())
            
            # API设置
            global_config.set("api.token", self.api_token_edit.text())
            global_config.set("api.endpoint", self.api_endpoint_edit.text())
            global_config.set("api.model", self.api_model_combo.currentText())
            global_config.set("api.max_tokens", self.max_tokens_spin.value())
            global_config.set("api.temperature", self.temperature_spin.value())
            
            # 外观
            if hasattr(self, "_background"):
                global_config.set("appearance.background",
                    self._qcolor_to_rgba(self._background))
            if hasattr(self, "_text_color"):
                global_config.set("appearance.text_color",
                    self._qcolor_to_rgba(self._text_color))
            global_config.set("appearance.font_size", self.font_size_spin.value())
            global_config.set("appearance.window_opacity", self.opacity_spin.value() / 100)
            
            # 系统提示
            global_config.set("api.system_prompt", self.system_prompt_edit.toPlainText())
            
            global_config.save()
            self.config_updated.emit()
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"配置保存失败: {str(e)}")

    def _reset_default(self):
        """恢复默认设置"""
        if QMessageBox.Yes == QMessageBox.question(
            self, "确认重置", "确定要恢复默认设置吗？当前修改将丢失"):
            
            global_config.reset_to_default()
            self._load_current_config()
            self.config_updated.emit()

    @staticmethod
    def _qcolor_to_rgba(color: QColor) -> str:
        """支持多种格式的转换"""
        if color.alpha() == 255:
            return color.name()
        return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()/255:.2f})"

if __name__ == "__main__":
    # 测试代码
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    def on_update():
        print("配置已更新")
    
    dialog = SettingsDialog()
    dialog.config_updated.connect(on_update)
    dialog.exec_()
    
    sys.exit(app.exec_())