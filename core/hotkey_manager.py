# core/hotkey_manager.py
import platform
import logging
from pynput import keyboard
from pynput.keyboard import Key, KeyCode, Controller
from typing import Dict, Callable, Optional
from config import global_config
from functools import partial

logger = logging.getLogger(__name__)

class HotkeyManager:
    def __init__(self):
        self._os_type = platform.system()
        self._listeners: Dict[str, keyboard.HotKey] = {}
        self._current_hotkeys: Dict[str, str] = {}
        self._keyboard_controller = Controller()
        
        # 初始化平台特定配置
        self._key_mapping = self._init_key_mapping()
        
        # 加载初始配置
        self._load_config()

    def _init_key_mapping(self) -> Dict[str, Key]:
        """初始化平台专用键位映射"""
        base_mapping = {
            'ctrl': Key.ctrl,
            'shift': Key.shift,
            'alt': Key.alt,
            'cmd': Key.cmd,
            'super': Key.cmd if self._os_type == 'Darwin' else Key.cmd_r
        }
        
        # Windows特殊处理
        if self._os_type == 'Windows':
            base_mapping.update({
                'win': Key.cmd,
                'menu': Key.menu
            })
        return base_mapping

    def _parse_hotkey(self, hotkey_str: str) -> Optional[list]:
        """将配置字符串解析为pynput键序列"""
        try:
            keys = []
            for part in hotkey_str.lower().split('+'):
                part = part.strip()
                if part in self._key_mapping:
                    keys.append(self._key_mapping[part])
                else:
                    if len(part) == 1:
                        keys.append(KeyCode.from_char(part))
                    else:
                        keys.append(getattr(Key, part))
            return keys
        except Exception as e:
            logger.error(f"解析热键失败: {hotkey_str} - {str(e)}")
            return None

    def _load_config(self):
        """从全局配置加载热键设置"""
        self._current_hotkeys = {
            'screenshot': global_config.get('hotkeys.screenshot'),
            'text_select': global_config.get('hotkeys.text_select')
        }

    def _register_hotkey(self, hotkey_type: str, callback: Callable):
        """注册单个热键"""
        hotkey_str = self._current_hotkeys[hotkey_type]
        parsed = self._parse_hotkey(hotkey_str)
        
        if not parsed:
            logger.warning(f"无效的热键配置: {hotkey_str}")
            return

        def _on_activate():
            logger.info(f"热键触发: {hotkey_type}")
            callback()

        listener = keyboard.HotKey(
            parsed,
            _on_activate
        )
        
        # 创建全局监听器
        self._listeners[hotkey_type] = listener
        keyboard.Listener(
            on_press=lambda key: listener.press(key),
            on_release=lambda key: listener.release(key)
        ).start()

    def register_all(self, callbacks: Dict[str, Callable]):
        """注册所有热键"""
        self.unregister_all()
        
        for hotkey_type, callback in callbacks.items():
            if hotkey_type in self._current_hotkeys:
                self._register_hotkey(hotkey_type, callback)
            else:
                logger.warning(f"未知的热键类型: {hotkey_type}")

    def unregister_all(self):
        """注销所有热键"""
        for listener in self._listeners.values():
            listener._state.clear()  # 清空热键状态
        self._listeners.clear()

    def update_config(self):
        """响应配置更新"""
        old_hotkeys = self._current_hotkeys.copy()
        self._load_config()
        
        # 仅当热键变更时重新注册
        if old_hotkeys != self._current_hotkeys:
            logger.info("检测到热键配置变更，重新注册...")
            self.unregister_all()
            # TODO: 需要主程序重新绑定回调

    def simulate_hotkey(self, hotkey_type: str):
        """模拟触发热键（用于调试）"""
        if hotkey_str := self._current_hotkeys.get(hotkey_type):
            keys = self._parse_hotkey(hotkey_str)
            with self._keyboard_controller.pressed(*keys):
                pass

if __name__ == "__main__":
    # 测试代码
    import time
    logging.basicConfig(level=logging.INFO)
    
    def test_callback():
        print("截屏热键触发!")
    
    def text_callback():
        print("划词热键触发!")
    
    manager = HotkeyManager()
    manager.register_all({
        'screenshot': test_callback,
        'text_select': text_callback
    })
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.unregister_all()