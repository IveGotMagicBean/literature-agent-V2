"""
LLM工厂 - 创建和管理LLM实例
支持: OpenAI, Anthropic, Ollama
"""

from typing import Dict, Any


class LLMWrapper:
    """LLM包装器 - 统一接口"""
    
    def __init__(self, provider: str, config: Dict[str, Any]):
        self.provider = provider
        self.config = config
        self.client = None
        self.model = None
        self.vision_model = None
        
        if provider == "ollama":
            self._init_ollama()
        elif provider == "openai":
            self._init_openai()
        elif provider == "anthropic":
            self._init_anthropic()
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
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
        
        # 测试连接
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                print(f"✅ 成功连接到Ollama: {self.base_url}")
            else:
                print(f"⚠️  Ollama连接异常，状态码: {response.status_code}")
        except Exception as e:
            print(f"⚠️  无法连接到Ollama ({self.base_url}): {e}")
            print("   请确保Ollama正在运行: ollama serve")
    
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
    
    def chat(self, messages, **kwargs) -> str:
        """统一的聊天接口，支持字符串或消息列表"""
        temperature = kwargs.get("temperature", self.config.get("temperature", 0.7))
        max_tokens = kwargs.get("max_tokens", self.config.get("max_tokens", 4000))
        
        # 如果传入的是字符串，转换为消息列表
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        
        if self.provider == "ollama":
            return self._chat_ollama(messages, temperature, max_tokens)
        elif self.provider == "openai":
            return self._chat_openai(messages, temperature, max_tokens)
        elif self.provider == "anthropic":
            return self._chat_anthropic(messages, temperature, max_tokens)
        
        return ""
    
    def _chat_ollama(self, messages: list, temperature: float, max_tokens: int) -> str:
        """Ollama聊天"""
        import requests
        import json
        
        # 转换消息格式
        prompt = self._messages_to_prompt(messages)
        
        url = f"{self.base_url}/api/generate"
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        try:
            response = requests.post(url, json=data, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except Exception as e:
            print(f"Ollama请求失败: {e}")
            return f"抱歉，请求失败: {str(e)}"
    
    def _chat_openai(self, messages: list, temperature: float, max_tokens: int) -> str:
        """OpenAI聊天"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    
    def _chat_anthropic(self, messages: list, temperature: float, max_tokens: int) -> str:
        """Anthropic聊天"""
        # 转换消息格式
        system = ""
        anthropic_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=anthropic_messages
        )
        return response.content[0].text
    
    def stream_chat(self, messages: list, **kwargs):
        """流式聊天接口"""
        temperature = kwargs.get("temperature", self.config.get("temperature", 0.7))
        max_tokens = kwargs.get("max_tokens", self.config.get("max_tokens", 4000))
        
        if self.provider == "ollama":
            yield from self._stream_ollama(messages, temperature, max_tokens)
        elif self.provider == "openai":
            yield from self._stream_openai(messages, temperature, max_tokens)
        elif self.provider == "anthropic":
            yield from self._stream_anthropic(messages, temperature, max_tokens)
    
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
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
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
    
    def _stream_openai(self, messages: list, temperature: float, max_tokens: int):
        """OpenAI流式聊天"""
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def _stream_anthropic(self, messages: list, temperature: float, max_tokens: int):
        """Anthropic流式聊天"""
        # 转换消息格式
        system = ""
        anthropic_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=anthropic_messages
        ) as stream:
            for text in stream.text_stream:
                yield text
    
    def _messages_to_prompt(self, messages: list) -> str:
        """将消息列表转换为单个prompt（用于Ollama）"""
        prompt_parts = []
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                prompt_parts.append(f"系统: {content}\n")
            elif role == "user":
                prompt_parts.append(f"用户: {content}\n")
            elif role == "assistant":
                prompt_parts.append(f"助手: {content}\n")
        
        # 添加助手提示
        prompt_parts.append("助手: ")
        
        return "\n".join(prompt_parts)
    
    def analyze_image(self, image_path: str, prompt: str) -> str:
        """
        分析图片（支持视觉模型）
        
        Args:
            image_path: 图片路径
            prompt: 分析提示
            
        Returns:
            分析结果文本
        """
        import base64
        from pathlib import Path
        
        # 读取并编码图片
        img_path = Path(image_path)
        if not img_path.exists():
            return f"错误：图片不存在 {image_path}"
        
        with open(img_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # 根据provider调用不同的视觉API
        if self.provider == "ollama":
            return self._analyze_image_ollama(image_data, prompt)
        elif self.provider == "openai":
            return self._analyze_image_openai(image_data, prompt)
        elif self.provider == "anthropic":
            return self._analyze_image_anthropic(image_data, prompt)
        else:
            return f"错误：{self.provider} 不支持图片分析"
    
    def _analyze_image_ollama(self, image_data: str, prompt: str) -> str:
        """Ollama图片分析"""
        import requests
        
        url = f"{self.base_url}/api/generate"
        data = {
            "model": self.vision_model,  # 使用视觉模型（如llava）
            "prompt": prompt,
            "images": [image_data],
            "stream": False
        }
        
        try:
            response = requests.post(url, json=data, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except Exception as e:
            print(f"Ollama图片分析失败: {e}")
            return f"分析失败: {str(e)}"
    
    def _analyze_image_openai(self, image_data: str, prompt: str) -> str:
        """OpenAI图片分析（GPT-4 Vision）"""
        # 使用gpt-4-vision-preview或gpt-4o
        vision_model = self.config.get("vision_model", "gpt-4o")
        
        try:
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
                                    "url": f"data:image/png;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI图片分析失败: {e}")
            return f"分析失败: {str(e)}"
    
    def _analyze_image_anthropic(self, image_data: str, prompt: str) -> str:
        """Anthropic图片分析（Claude Vision）"""
        # 使用Claude 3或更新的视觉模型
        vision_model = self.config.get("vision_model", "claude-3-opus-20240229")
        
        try:
            response = self.client.messages.create(
                model=vision_model,
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Anthropic图片分析失败: {e}")
            return f"分析失败: {str(e)}"


def create_llm(config: Dict[str, Any]) -> LLMWrapper:
    """创建LLM实例"""
    return LLMWrapper(config["provider"], config)
