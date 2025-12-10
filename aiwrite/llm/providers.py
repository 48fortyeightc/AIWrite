"""
OpenAI 兼容接口 Provider（通用实现，可用于 DeepSeek、Kimi、豆包等）
"""

from __future__ import annotations

from pathlib import Path

import httpx

from ..models.pipeline import LLMOptions
from .base import (
    LLMProvider,
    LLMPurpose,
    LLMResponse,
    encode_image_to_base64,
    get_image_media_type,
)


class OpenAICompatibleProvider(LLMProvider):
    """
    OpenAI 兼容接口 Provider
    
    支持所有使用 OpenAI API 格式的模型服务商：
    - DeepSeek
    - Moonshot (Kimi)
    - 火山引擎 (豆包)
    - OpenAI
    - Azure OpenAI
    等
    """

    @property
    def name(self) -> str:
        return "openai_compatible"

    async def invoke(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        options: LLMOptions | None = None,
    ) -> LLMResponse:
        options = options or LLMOptions()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": options.max_tokens,
            "temperature": options.temperature,
            "top_p": options.top_p,
        }

        async with httpx.AsyncClient(timeout=options.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        )


class DoubaoProvider(OpenAICompatibleProvider):
    """豆包（字节跳动火山引擎）Provider - 支持 Vision"""

    @property
    def name(self) -> str:
        return "doubao"

    async def invoke_vision(
        self,
        prompt: str,
        image_paths: list[str | Path],
        *,
        system_prompt: str | None = None,
        options: LLMOptions | None = None,
    ) -> LLMResponse:
        """
        调用豆包 Vision 模型识别图片
        
        Args:
            prompt: 用户提示词
            image_paths: 图片路径列表
            system_prompt: 系统提示词
            options: 调用选项
            
        Returns:
            LLM 响应
        """
        options = options or LLMOptions()

        # 构建包含图片的 content 列表
        content_parts = []
        
        # 添加所有图片
        for img_path in image_paths:
            img_path = Path(img_path)
            if img_path.exists():
                base64_image = encode_image_to_base64(img_path)
                media_type = get_image_media_type(img_path)
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{base64_image}"
                    }
                })
        
        # 添加文本提示
        content_parts.append({
            "type": "text",
            "text": prompt
        })

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": content_parts})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": options.max_tokens,
            "temperature": options.temperature,
        }

        async with httpx.AsyncClient(timeout=options.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        )


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek Provider"""

    @property
    def name(self) -> str:
        return "deepseek"


class KimiProvider(OpenAICompatibleProvider):
    """Kimi (Moonshot) Provider"""

    @property
    def name(self) -> str:
        return "kimi"


def create_provider(
    provider_type: str,
    api_key: str,
    base_url: str,
    model: str,
    purpose: LLMPurpose = LLMPurpose.WRITING,
) -> LLMProvider:
    """
    工厂方法：创建 LLM Provider
    
    Args:
        provider_type: 提供商类型 (doubao, deepseek, kimi, openai_compatible)
        api_key: API Key
        base_url: Base URL
        model: 模型名称
        purpose: 模型用途
        
    Returns:
        LLMProvider 实例
    """
    providers = {
        "doubao": DoubaoProvider,
        "deepseek": DeepSeekProvider,
        "kimi": KimiProvider,
        "openai_compatible": OpenAICompatibleProvider,
    }
    
    provider_class = providers.get(provider_type, OpenAICompatibleProvider)
    return provider_class(
        api_key=api_key,
        base_url=base_url,
        model=model,
        purpose=purpose,
    )
