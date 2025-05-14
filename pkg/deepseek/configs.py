# pkg/deepseek/configs.py
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, SecretStr
from dotenv import load_dotenv
import logging

class DeepSeekConfig(BaseModel):
    """深度求索API客户端配置模型"""
    api_key: SecretStr = Field(..., description="API访问密钥（从环境变量DEEPSEEK_API_KEY加载）")
    base_url: str = Field("https://api.deepseek.com", description="API基础地址")
    timeout: int = Field(30, gt=0, description="请求超时时间（秒）")
    max_retries: int = Field(3, ge=0, le=5, description="最大重试次数")
    enable_telemetry: bool = Field(True, description="是否启用性能监控")
    default_model: str = Field("deepseek-chat", description="默认使用的模型")
    workspace: Path = Field(Path("/workspace"), description="安全沙箱工作目录")
    log_level: str = Field("INFO", description="日志级别")
    retry_max_attempts: int = Field(3, ge=0, le=10, description="最大重试次数")
    retry_max_delay: float = Field(30.0, gt=0, description="最大重试延迟(秒)")
    retry_on_status_codes: List[int] = Field(
        [429, 500, 502, 503, 504], 
        description="触发重试的HTTP状态码"
    )

    class Config:
        env_prefix = "DEEPSEEK_"  # 环境变量前缀
        env_file_encoding = "utf-8"
        secrets_dir = "/run/secrets"  # Docker secrets路径

    @field_validator("api_key", mode='before')
    def validate_api_key(cls, v):
        """API密钥预处理验证"""
        if not v:
            raise ValueError("API密钥不能为空")
        return v

    @field_validator("log_level")
    def validate_log_level(cls, v):
        """日志级别校验"""
        v = v.upper()
        if v not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValueError("无效的日志级别")
        return v

    @field_validator("workspace")
    def validate_workspace(cls, v):
        """工作目录初始化"""
        if not v.exists():
            v.mkdir(parents=True, exist_ok=True)
        return v

def load_config(
    env_file: Optional[str] = None,
    secrets: Optional[Dict[str, str]] = None
) -> DeepSeekConfig:
    """
    加载配置（优先级：显式参数 > 环境变量 > .env文件 > 默认值）
    :param env_file: 指定.env文件路径
    :param secrets: 从密钥管理服务加载的敏感信息
    """
    # 1. 加载环境变量文件
    loaded = _load_env_files(env_file)

    # 新增校验逻辑
    if not loaded:
        logging.warning("No .env files found. Using environment variables and defaults")
    
    # 2. 合并密钥管理服务数据
    env_vars = {**os.environ, **(_parse_secrets(secrets) if secrets else {})}
    
    # 3. 构建配置字典
    config_data = {
        "api_key": env_vars.get("DEEPSEEK_API_KEY"),
        "base_url": env_vars.get("DEEPSEEK_BASE_URL"),
        "timeout": env_vars.get("DEEPSEEK_TIMEOUT"),
        "max_retries": env_vars.get("DEEPSEEK_MAX_RETRIES"),
        "enable_telemetry": env_vars.get("DEEPSEEK_ENABLE_TELEMETRY"),
        "default_model": env_vars.get("DEEPSEEK_DEFAULT_MODEL"),
        "workspace": env_vars.get("DEEPSEEK_WORKSPACE"),
        "log_level": env_vars.get("DEEPSEEK_LOG_LEVEL")
    }
    
    # 4. 过滤空值并转换类型
    return DeepSeekConfig.model_validate({
        k: v for k, v in config_data.items() if v is not None
    })

def _load_env_files(env_file: Optional[str] = None) -> bool:
    """加载环境变量文件"""
    env_paths = [
        env_file,  # 显式指定的文件
        Path(".env"),  # 当前目录
        Path.home() / ".deepseek.env",  # 用户目录
        Path("/etc/deepseek/.env")  # 系统配置
    ]
    
    for path in filter(None, env_paths):
        if isinstance(path, str):
            path = Path(path)
        if path.exists():
            load_dotenv(path, override=True)
            logging.info(f"Loaded environment from {path}")
            return True
    return False

def _parse_secrets(secrets: Dict[str, str]) -> Dict[str, str]:
    """解析密钥管理服务数据"""
    # 示例：转换AWS Secrets Manager格式
    return {
        k.upper().replace("-", "_"): v
        for k, v in secrets.items()
    }

# 单例配置实例
_config: Optional[DeepSeekConfig] = None

def get_config() -> DeepSeekConfig:
    """获取全局配置（单例模式）"""
    global _config
    if _config is None:
        _config = load_config()
        
        # 初始化日志配置
        logging.basicConfig(
            level=_config.log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    return _config