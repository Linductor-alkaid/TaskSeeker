import time
import logging
from typing import Callable, Any
from functools import wraps
from ..errors import (
    APIError,
    RateLimitError,
    ServiceUnavailableError,
    RetryExhaustedError
)

logger = logging.getLogger(__name__)

def deepseek_retry(func: Callable) -> Callable:
    """
    带指数退避的智能重试装饰器
    自动从实例的config属性获取配置
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs) -> Any:
        config = self.config  # 从实例获取配置
        
        max_attempts = config.retry_max_attempts + 1  # 包含初始尝试
        max_delay = config.retry_max_delay
        retry_codes = config.retry_on_status_codes
        
        attempt = 1
        while True:
            try:
                return func(self, *args, **kwargs)
            except (APIError, RateLimitError, ServiceUnavailableError) as e:
                status_code = getattr(e, 'status_code', None)
                
                # 检查是否需要重试
                if isinstance(e, RateLimitError):
                    logger.warning("Rate limited, applying backoff...")
                elif status_code and status_code not in retry_codes:
                    raise
                    
                # 计算退避时间
                delay = min(2 ** attempt + 1, max_delay)
                if attempt >= max_attempts:
                    raise RetryExhaustedError(max_attempts) from e
                    
                logger.warning(f"Attempt {attempt} failed: {str(e)}. Retrying in {delay:.1f}s...")
                time.sleep(delay)
                attempt += 1
                
            except Exception as e:
                raise  # 其他异常直接抛出
    return wrapper