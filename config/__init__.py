# configs/__init__.py
from PyQt5.QtCore import QObject, pyqtSignal
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

class Config(QObject):
    config_updated = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._default_config = self._load_default_config()
        self._user_config_path = self._get_user_config_path()
        self._user_config = self._load_user_config()
        self.config = self._deep_merge(self._default_config, self._user_config)

    @staticmethod
    def _load_default_config() -> Dict[str, Any]:
        """加载包内默认配置文件"""
        try:
            current_dir = Path(__file__).parent
            default_path = current_dir / "default.json"
            with open(default_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise RuntimeError("Failed to load default configuration") from e

    def _get_user_config_path(self) -> Path:
        """获取用户配置文件路径"""
        if sys.platform == "win32":
            appdata = os.getenv("APPDATA")
            config_dir = Path(appdata) / "TaskSeeker"
        else:
            config_dir = Path.home() / ".config" / "taskseeker"
        
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.json"

    def _load_user_config(self) -> Dict[str, Any]:
        """加载用户配置文件"""
        try:
            with open(self._user_config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _deep_merge(base: Dict, update: Dict) -> Dict:
        """深度合并两个字典"""
        merged = base.copy()
        for key, value in update.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = Config._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项，支持点分隔符"""
        keys = key.split(".")
        current = self.config
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """设置配置项，支持点分隔符"""
        keys = key.split(".")
        current = self.config
        for i, k in enumerate(keys[:-1]):
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value

    def save(self) -> None:
        """保存配置到用户文件"""
        with open(self._user_config_path, "w", encoding="utf-8") as f:
            json.dump(
                self.config,
                f,
                indent=4,
                ensure_ascii=False,
                sort_keys=True
            )
        self.config_updated.emit()

    def reset_to_default(self) -> None:
        """重置为默认配置"""
        self.config = self._deep_merge(self._default_config, {})
        self.save()
        self.config_updated.emit()

# 单例配置对象
global_config = Config()