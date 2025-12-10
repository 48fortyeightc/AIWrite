"""
多模态视觉模型 Provider
支持图片识别功能
"""

from __future__ import annotations

import base64
import httpx
from pathlib import Path

from ..models.pipeline import LLMOptions
from .base import LLMProvider, LLMPurpose, LLMResponse


class VisionProvider(LLMProvider):
    """
    视觉模型 Provider
    
    支持图片输入的多模态模型：
    - 豆包 doubao-seed-1.6-vision
    - GPT-4V
    - Claude 3.5
    等
    """

    @property
    def name(self) -> str:
        return "vision"

    def _encode_image(self, image_path: str | Path) -> tuple[str, str]:
        """将图片编码为 base64"""
        path = Path(image_path)
        
        # 根据扩展名确定 MIME 类型
        suffix = path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(suffix, "image/png")
        
        with open(path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        return image_data, mime_type

    async def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        *,
        system_prompt: str | None = None,
        options: LLMOptions | None = None,
    ) -> LLMResponse:
        """
        分析单张图片
        
        Args:
            image_path: 图片路径
            prompt: 分析提示词
            system_prompt: 系统提示词
            options: LLM 选项
            
        Returns:
            LLMResponse
        """
        options = options or LLMOptions()
        
        image_data, mime_type = self._encode_image(image_path)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 构建多模态消息
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_data}"
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        })

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

    async def invoke(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        options: LLMOptions | None = None,
    ) -> LLMResponse:
        """
        普通文本调用（兼容 LLMProvider 接口）
        """
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


class DoubaoVisionProvider(VisionProvider):
    """豆包视觉模型 Provider"""

    @property
    def name(self) -> str:
        return "doubao_vision"


def create_vision_provider(
    api_key: str,
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
    model: str = "doubao-1-5-vision-pro-32k-250115",
    purpose: LLMPurpose = LLMPurpose.THINKING,
) -> VisionProvider:
    """
    创建视觉模型 Provider
    
    Args:
        api_key: API Key
        base_url: Base URL
        model: 模型名称（默认使用豆包视觉模型）
        purpose: 模型用途
        
    Returns:
        VisionProvider 实例
    """
    return DoubaoVisionProvider(
        api_key=api_key,
        base_url=base_url,
        model=model,
        purpose=purpose,
    )
