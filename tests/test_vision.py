"""
测试 Vision 功能 - 使用 thinking provider (doubao-seed-1-6 支持多模态)
"""
import asyncio
from pathlib import Path
from aiwrite.config import load_config, create_thinking_provider

async def test_vision():
    config = load_config()
    # 使用 thinking provider (doubao-seed-1-6 支持多模态)
    provider = create_thinking_provider(config)
    
    print(f"Provider: {provider}")
    print(f"Model: {provider.model}")
    
    # 测试识别 img2 目录下的所有图片
    img_dir = Path("examples/img2")
    images = list(img_dir.glob("*.png"))
    
    prompt = """请简洁描述这张图片的内容，用于论文写作。

要求：
1. 一句话概括图片类型和主要内容
2. 不超过 50 个字
3. 如果是系统图/流程图/时序图等，指出是什么类型的图
"""
    
    print(f"\n发现 {len(images)} 张图片")
    
    for image_path in sorted(images):
        print(f"\n正在识别: {image_path.name}")
        try:
            response = await provider.invoke_vision(
                prompt=prompt,
                image_paths=[image_path],
            )
            print(f"  → {response.content}")
        except Exception as e:
            print(f"  → 错误: {e}")

if __name__ == "__main__":
    asyncio.run(test_vision())
