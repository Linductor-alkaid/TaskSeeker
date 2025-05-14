from .configs import get_config
from openai import OpenAI, APIError as OpenAIAPIError
from .errors import (
    AuthenticationError,
    RateLimitError,
    APIError,
    InvalidRequestError,
    ServiceUnavailableError
)
from .utils.retry import deepseek_retry

class DeepSeekClient:
    def __init__(self, api_key=None, base_url="https://api.deepseek.com", model="deepseek-chat", system_prompt=""):
        config = get_config()
        self.api_key = api_key if api_key is not None else config.api_key.get_secret_value()
        self.base_url = base_url or config.base_url
        self.model = model
        self.system_prompt = system_prompt
        self.messages = []
        self.config = config  # 保存配置对象用于重试

        self._init_clients()

    def _init_clients(self):
        """初始化OpenAI客户端"""
        self.client = self._create_client(self.base_url)
        self.client_Beta = self._create_client("https://api.deepseek.com/beta")

    @deepseek_retry
    def _create_client(self, base_url: str) -> OpenAI:
        """带重试机制的客户端创建方法"""
        try:
            return OpenAI(api_key=self.api_key, base_url=base_url)
        except Exception as e:
            self._handle_openai_error(e)

    def _handle_openai_error(self, error: Exception):
        """转换OpenAI异常为自定义异常"""
        if isinstance(error, OpenAIAPIError):
            status_code = getattr(error.response, 'status_code', 500)
            if status_code == 401:
                raise AuthenticationError() from error
            elif status_code == 429:
                raise RateLimitError() from error
            elif status_code >= 500:
                raise ServiceUnavailableError() from error
            else:
                raise APIError(status_code, str(error)) from error
        raise error

    @deepseek_retry
    def chat(self, usermessages, max_tokens=1024, temperature=0.8, stream=False):
        try:
            messages = []
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})
            messages.append({"role": "user", "content": usermessages})
            
            self.messages.extend(messages)  # 保留历史记录
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream
            )
            assistant_message = {
                "role": response.choices[0].message.role,
                "content": response.choices[0].message.content
            }
            self.messages.append(assistant_message)
            return assistant_message
        except Exception as e:
            self._handle_openai_error(e)

    @deepseek_retry
    def FIM_completions(self, prompt, suffix=None, max_tokens=128):
        try:
            response = self.client_Beta.completions.create(
                model=self.model,
                prompt=prompt,
                suffix=suffix,
                max_tokens=max_tokens,
            )
            return response.choices[0].text
        except Exception as e:
            self._handle_openai_error(e)

    @deepseek_retry
    def json_output(self, usermassages):
        try:
            if self.system_prompt is not None:
                messages = [{"role": "system", "content": self.system_prompt}]
                self.messages.append(messages[0])
            messages = [{"role": "user", "content": usermassages}]
            self.messages.append(messages[0])
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                response_format={'type': 'json_object'}
            )
            return response.choices[0].message.content
        except Exception as e:
            self._handle_openai_error(e)

    
    def clear(self):
        """
        清空对话历史
        """
        self.messages = []
    
    

if __name__ == '__main__':
    client = DeepSeekClient()
    print(client.chat("你好"))
