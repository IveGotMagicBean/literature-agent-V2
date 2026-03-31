"""
LLM工厂 - 创建和管理LLM实例
支持: OpenAI, Anthropic, Ollama, DashScope（阿里云百炼）
"""

import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class LLMWrapper:
    """LLM统一包装器 - 多Provider支持"""
    
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    
    def __init__(self, provider: str, config: Dict[str, Any]):
        self.provider = provider
        self.config = config
        self.client = None
        self.model = None
        self.vision_model = None
        
        init_map = {
            "ollama": self._init_ollama,
            "openai": self._init_openai,
            "anthropic": self._init_anthropic,
            "dashscope": self._init_dashscope,
        }
        
        if provider not in init_map:
            raise ValueError(f"不支持的LLM Provider: {provider}，可选: {list(init_map.keys())}")
        
        init_map[provider]()
    
    # ==================== 初始化方法 ====================
    
    def _init_ollama(self):
        """初始化Ollama本地模型"""
        try:
            import requests
        except ImportError:
            raise ImportError("请安装requests: pip install requests")
        
        ollama_config = self.config.get("ollama", {})
        self.base_url = ollama_config.get("base_url", "http://localhost:11434")
        self.model = ollama_config.get("model", "qwen2.5:14b")
        self.vision_model = ollama_config.get("vision_model", "llava:7b")
        
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                print(f"✅ 成功连接到Ollama: {self.base_url}")
            else:
                print(f"⚠️  Ollama连接异常，状态码: {response.status_code}")
        except Exception as e:
            print(f"⚠️  无法连接到Ollama ({self.base_url}): {e}")
    
    def _init_openai(self):
        """初始化OpenAI客户端"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("请安装openai: pip install openai")
        
        kwargs = {"api_key": self.config.get("api_key", "dummy")}
        if self.config.get("base_url"):
            kwargs["base_url"] = self.config["base_url"]
        
        self.client = OpenAI(**kwargs)
        self.model = self.config.get("model", "gpt-4")
    
    def _init_anthropic(self):
        """初始化Anthropic客户端"""
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("请安装anthropic: pip install anthropic")
        
        self.client = Anthropic(api_key=self.config["api_key"])
        self.model = self.config.get("model", "claude-3-opus-20240229")
    
    def _init_dashscope(self):
        """初始化DashScope（阿里云百炼）- 使用OpenAI兼容模式"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("请安装openai: pip install openai")
        
        ds_config = self.config.get("dashscope", {})
        api_key = ds_config.get("api_key", self.config.get("api_key", ""))
        base_url = ds_config.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        if not api_key or api_key == "your-dashscope-api-key-here":
            raise ValueError(
                "请在 config/config.toml 中设置 [llm.dashscope] api_key\n"
                "获取方式：https://dashscope.console.aliyun.com/apiKey"
            )
        
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = ds_config.get("model", "qwen-plus")
        self.vision_model = ds_config.get("vision_model", "qwen-vl-max")
        
        print(f"✅ DashScope已初始化: model={self.model}, vision={self.vision_model}")
    
    # ==================== 统一聊天接口 ====================
    
    def chat(self, messages, **kwargs) -> str:
        """统一的聊天接口，支持字符串或消息列表"""
        temperature = kwargs.get("temperature", self.config.get("temperature", 0.7))
        max_tokens = kwargs.get("max_tokens", self.config.get("max_tokens", 4000))
        
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        
        dispatch = {
            "ollama": self._chat_ollama,
            "openai": self._chat_openai_compatible,
            "anthropic": self._chat_anthropic,
            "dashscope": self._chat_openai_compatible,
        }
        
        handler = dispatch.get(self.provider)
        if handler:
            return self._retry(handler, messages, temperature, max_tokens)
        return ""
    
    def stream_chat(self, messages: list, **kwargs):
        """流式聊天接口"""
        temperature = kwargs.get("temperature", self.config.get("temperature", 0.7))
        max_tokens = kwargs.get("max_tokens", self.config.get("max_tokens", 4000))
        
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        
        dispatch = {
            "ollama": self._stream_ollama,
            "openai": self._stream_openai_compatible,
            "anthropic": self._stream_anthropic,
            "dashscope": self._stream_openai_compatible,
        }
        
        handler = dispatch.get(self.provider)
        if handler:
            yield from handler(messages, temperature, max_tokens)
    
    # ==================== 重试机制 ====================
    
    def _retry(self, func, *args) -> str:
        """带重试的调用"""
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                return func(*args)
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY * (attempt + 1)
                    print(f"⚠️ LLM调用失败 (尝试 {attempt+1}/{self.MAX_RETRIES}): {e}，{delay}秒后重试")
                    time.sleep(delay)
        
        print(f"❌ LLM调用失败，已重试{self.MAX_RETRIES}次: {last_error}")
        return f"抱歉，请求失败: {str(last_error)}"
    
    # ==================== 各Provider实现 ====================
    
    def _chat_ollama(self, messages: list, temperature: float, max_tokens: int) -> str:
        """Ollama聊天"""
        import requests
        
        prompt = self._messages_to_prompt(messages)
        url = f"{self.base_url}/api/generate"
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens}
        }
        
        response = requests.post(url, json=data, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "")
    
    def _chat_openai_compatible(self, messages: list, temperature: float, max_tokens: int) -> str:
        """OpenAI兼容接口聊天（OpenAI / DashScope 共用）"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    
    def _chat_anthropic(self, messages: list, temperature: float, max_tokens: int) -> str:
        """Anthropic聊天"""
        system = ""
        anthropic_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                anthropic_messages.append({"role": msg["role"], "content": msg["content"]})
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=anthropic_messages
        )
        return response.content[0].text
    
    # ==================== 流式实现 ====================
    
    def _stream_ollama(self, messages: list, temperature: float, max_tokens: int):
        """Ollama流式聊天"""
        import requests
        import json
        
        prompt = self._messages_to_prompt(messages)
        url = f"{self.base_url}/api/generate"
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens}
        }
        
        try:
            response = requests.post(url, json=data, stream=True, timeout=120)
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            yield chunk["response"]
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Ollama流式请求失败: {e}")
            yield f"抱歉，请求失败: {str(e)}"
    
    def _stream_openai_compatible(self, messages: list, temperature: float, max_tokens: int):
        """OpenAI兼容接口流式聊天（OpenAI / DashScope 共用）"""
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"流式请求失败: {e}")
            yield f"抱歉，流式请求失败: {str(e)}"
    
    def _stream_anthropic(self, messages: list, temperature: float, max_tokens: int):
        """Anthropic流式聊天"""
        system = ""
        anthropic_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                anthropic_messages.append({"role": msg["role"], "content": msg["content"]})
        
        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=anthropic_messages
        ) as stream:
            for text in stream.text_stream:
                yield text
    
    # ==================== 工具方法 ====================
    
    def _messages_to_prompt(self, messages: list) -> str:
        """将消息列表转换为单个prompt（用于Ollama）"""
        role_map = {"system": "系统", "user": "用户", "assistant": "助手"}
        parts = []
        for msg in messages:
            role = role_map.get(msg["role"], msg["role"])
            parts.append(f"{role}: {msg['content']}\n")
        parts.append("助手: ")
        return "\n".join(parts)
    
    # ==================== 图片分析 ====================
    
    def analyze_image(self, image_path: str, prompt: str) -> str:
        """分析图片（支持视觉模型）"""
        import base64
        from pathlib import Path
        
        img_path = Path(image_path)
        if not img_path.exists():
            return f"错误：图片不存在 {image_path}"
        
        with open(img_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        suffix = img_path.suffix.lower()
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
        media_type = mime_map.get(suffix, "image/png")
        
        dispatch = {
            "ollama": self._analyze_image_ollama,
            "openai": self._analyze_image_openai_compatible,
            "anthropic": self._analyze_image_anthropic,
            "dashscope": self._analyze_image_openai_compatible,
        }
        
        handler = dispatch.get(self.provider)
        if handler:
            return self._retry(handler, image_data, media_type, prompt)
        return f"错误：{self.provider} 不支持图片分析"
    
    def _analyze_image_ollama(self, image_data: str, media_type: str, prompt: str) -> str:
        """Ollama图片分析"""
        import requests
        
        url = f"{self.base_url}/api/generate"
        data = {
            "model": self.vision_model,
            "prompt": prompt,
            "images": [image_data],
            "stream": False
        }
        
        response = requests.post(url, json=data, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "")
    
    def _analyze_image_openai_compatible(self, image_data: str, media_type: str, prompt: str) -> str:
        """OpenAI兼容接口图片分析（OpenAI / DashScope 共用）"""
        vision_model = self.vision_model or self.model
        
        response = self.client.chat.completions.create(
            model=vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1500
        )
        return response.choices[0].message.content
    
    def _analyze_image_anthropic(self, image_data: str, media_type: str, prompt: str) -> str:
        """Anthropic图片分析"""
        vision_model = self.vision_model or self.model
        
        response = self.client.messages.create(
            model=vision_model,
            max_tokens=1500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data
                            }
                        },
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
        )
        return response.content[0].text


def create_llm(config: Dict[str, Any]) -> LLMWrapper:
    """创建LLM实例"""
    return LLMWrapper(config["provider"], config)
