"""DeepSeek 官方SDK Python实现"""

__version__ = "0.1.0"  # 版本号遵循语义化版本规范

# 核心接口导出
from .client import DeepSeekClient
from .configs import get_config, DeepSeekConfig

# 异常体系导出
from .errors import (
    DeepSeekError,
    AuthenticationError,
    RateLimitError,
    APIError,
    InvalidRequestError,
    ServiceUnavailableError,
    RetryExhaustedError
)

# 工具模块导出
from .utils.retry import deepseek_retry

__all__ = [
    "DeepSeekClient",
    "get_config",
    "DeepSeekConfig",
    "deepseek_retry",
    "DeepSeekError",
    "AuthenticationError", 
    "RateLimitError",
    "APIError",
    "InvalidRequestError",
    "ServiceUnavailableError",
    "RetryExhaustedError",
    "__version__"
]