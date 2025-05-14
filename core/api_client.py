# core/api_client.py
import logging
from typing import Optional, Dict, Generator, Union
from config import global_config
from pkg.deepseek.client import DeepSeekClient
from pkg.deepseek.errors import AuthenticationError, RateLimitError, APIError
from pkg.deepseek.utils.retry import deepseek_retry
from pkg.deepseek.configs import get_config

logger = logging.getLogger(__name__)

class DeepSeekAPI:
    def __init__(self):
        self.config = get_config()
        self._init_client()
        self._max_retries = global_config.get("api.max_retries", 3)
        self._timeout = global_config.get("api.timeout", 30)

    def _init_client(self):
        """从全局配置初始化客户端"""
        try:
            self.client = DeepSeekClient(
                api_key=global_config.get("api.token"),
                base_url=global_config.get("api.endpoint"),
                model=global_config.get("api.model"),
                system_prompt=global_config.get("api.system_prompt", "")
            )
        except AuthenticationError as e:
            logger.critical("API认证失败，请检查token配置")
            raise

    @property
    def default_params(self) -> Dict:
        """获取API默认参数"""
        return {
            "temperature": global_config.get("api.temperature", 0.7),
            "max_tokens": global_config.get("api.max_tokens", 1024),
            # "top_p": global_config.get("api.top_p", 1.0),
        }

    @deepseek_retry
    def generate_response(
        self,
        prompt: str,
        stream: bool = False
    ) -> Union[str, Generator[str, None, None]]:
        """
        生成模型响应（自动集成系统提示）
        
        参数:
            prompt: 用户输入内容
            stream: 是否启用流式响应
            
        返回:
            str: 完整响应文本（非流式）
            Generator: 流式响应生成器
        """
        try:
            response = self.client.chat(
                usermessages=prompt,
                stream=stream,
                **self.default_params
            )
            
            if stream:
                return self._handle_stream_response(response)
            return self._handle_full_response(response)
            
        except RateLimitError as e:
            logger.warning("API速率限制，请稍后重试")
            raise
        except APIError as e:
            logger.error(f"API请求失败: {str(e)}")
            return "服务暂时不可用，请稍后重试"

    def _handle_full_response(self, response: Dict) -> str:
        """处理完整响应"""
        if "content" not in response:
            logger.error("无效的API响应格式")
            return "响应解析失败"
        return response["content"]

    def _handle_stream_response(self, response: Generator) -> Generator[str, None, None]:
        """处理流式响应"""
        try:
            for chunk in response:
                if "content" in chunk:
                    yield chunk["content"]
                elif "error" in chunk:
                    logger.error(f"流式响应错误: {chunk['error']}")
                    break
        except APIError as e:
            logger.error(f"流式请求中断: {str(e)}")

    def code_completion(self, prefix: str, suffix: str = "") -> str:
        """
        代码补全功能
        
        参数:
            prefix: 代码前缀
            suffix: 代码后缀（可选）
        """
        try:
            return self.client.FIM_completions(
                prefix=prefix,
                suffix=suffix,
                **self.default_params
            )
        except APIError as e:
            logger.error(f"代码补全失败: {str(e)}")
            return ""

    def structured_output(
        self,
        prompt: str,
        json_schema: Optional[Dict] = None
    ) -> Dict:
        """
        结构化输出生成
        
        参数:
            prompt: 用户提示
            json_schema: 期望的JSON结构（可选）
        """
        try:
            return self.client.json_output(
                prompt=prompt,
                schema=json_schema,
                **self.default_params
            )
        except APIError as e:
            logger.error(f"结构化输出失败: {str(e)}")
            return {}

    def validate_config(self) -> bool:
        """验证当前配置有效性"""
        try:
            test_response = self.client.chat("测试连接", max_tokens=5)
            return "content" in test_response
        except Exception as e:
            return False

    def update_config(self):
        """响应配置更新后重新初始化客户端"""
        self._init_client()

if __name__ == "__main__":
    # 测试用例
    import sys
    logging.basicConfig(level=logging.INFO)
    
    # 初始化前需确保配置正确
    global_config.set("api.token", "your-api-key")
    
    api = DeepSeekAPI()
    
    # 测试普通响应
    response = api.generate_response("你好！")
    print(f"普通响应: {response}")
    
    # 测试流式响应
    print("流式响应:")
    for chunk in api.generate_response("请介绍量子计算", stream=True):
        print(chunk, end="", flush=True)
    
    # 测试代码补全
    code_prefix = "def quick_sort(arr):\n    "
    completion = api.code_completion(code_prefix)
    print(f"\n代码补全结果:\n{code_prefix}{completion}")