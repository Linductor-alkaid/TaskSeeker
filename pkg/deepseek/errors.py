"""自定义异常模块"""

class DeepSeekError(Exception):
    """所有DeepSeek异常的基类"""
    pass

class AuthenticationError(DeepSeekError):
    """认证失败异常"""
    def __init__(self, message="Invalid API key or authentication failed"):
        super().__init__(message)

class RateLimitError(DeepSeekError):
    """API速率限制异常"""
    def __init__(self, message="API rate limit exceeded"):
        super().__init__(message)

class APIError(DeepSeekError):
    """通用API请求错误"""
    def __init__(self, status_code: int, message: str):
        super().__init__(f"API request failed with status {status_code}: {message}")
        self.status_code = status_code

class InvalidRequestError(DeepSeekError):
    """无效请求参数异常"""
    def __init__(self, field: str, message: str):
        super().__init__(f"Invalid request parameter '{field}': {message}")

class ServiceUnavailableError(DeepSeekError):
    """服务不可用异常"""
    def __init__(self, message="Service temporarily unavailable"):
        super().__init__(message)

class RetryExhaustedError(DeepSeekError):
    """重试次数耗尽异常"""
    def __init__(self, attempts: int):
        super().__init__(f"Operation failed after {attempts} retry attempts")