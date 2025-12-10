"""
Mermaid 图表渲染器

使用 Playwright + Mermaid.js 本地渲染图表为 PNG
"""

from __future__ import annotations

import asyncio
import base64
import tempfile
from pathlib import Path
from typing import Literal

from rich.console import Console

console = Console()


# Mermaid HTML 模板
MERMAID_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background: white;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        #container {{
            display: inline-block;
        }}
    </style>
</head>
<body>
    <div id="container">
        <pre class="mermaid">
{mermaid_code}
        </pre>
    </div>
    <script>
        mermaid.initialize({{ 
            startOnLoad: true,
            theme: 'neutral',
            securityLevel: 'loose',
            flowchart: {{
                useMaxWidth: false,
                htmlLabels: true
            }},
            themeVariables: {{
                primaryColor: '#e0e0e0',
                primaryTextColor: '#333333',
                primaryBorderColor: '#999999',
                lineColor: '#666666',
                secondaryColor: '#f5f5f5',
                tertiaryColor: '#fafafa'
            }}
        }});
    </script>
</body>
</html>
"""

# 离线版 Mermaid HTML 模板（不依赖 CDN）
MERMAID_OFFLINE_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background: white;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        #container {{
            display: inline-block;
        }}
    </style>
</head>
<body>
    <div id="container">
        <pre class="mermaid">
{mermaid_code}
        </pre>
    </div>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ 
            startOnLoad: true,
            theme: 'neutral',
            securityLevel: 'loose',
            themeVariables: {{
                primaryColor: '#e0e0e0',
                primaryTextColor: '#333333',
                primaryBorderColor: '#999999',
                lineColor: '#666666',
                secondaryColor: '#f5f5f5',
                tertiaryColor: '#fafafa'
            }}
        }});
    </script>
</body>
</html>
"""


class MermaidRenderer:
    """
    Mermaid 图表渲染器
    
    使用 Playwright 在无头浏览器中渲染 Mermaid 图表
    """
    
    def __init__(self, use_offline: bool = False):
        """
        初始化渲染器
        
        Args:
            use_offline: 是否使用离线模式（需要本地 Mermaid.js）
        """
        self.use_offline = use_offline
        self._browser = None
        self._playwright = None
    
    async def _ensure_browser(self):
        """确保浏览器已启动"""
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch()
            except ImportError:
                raise ImportError(
                    "需要安装 playwright: pip install playwright && playwright install chromium"
                )
    
    async def _close_browser(self):
        """关闭浏览器"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
    
    async def render_async(
        self,
        mermaid_code: str,
        output_path: str | Path,
        width: int = 1200,
        height: int = 800,
    ) -> Path:
        """
        异步渲染 Mermaid 代码为 PNG 图片
        
        Args:
            mermaid_code: Mermaid 代码
            output_path: 输出文件路径
            width: 视口宽度
            height: 视口高度
            
        Returns:
            输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        await self._ensure_browser()
        
        # 创建临时 HTML 文件
        html_content = MERMAID_HTML_TEMPLATE.format(mermaid_code=mermaid_code)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_html_path = f.name
        
        try:
            # 创建页面并渲染
            page = await self._browser.new_page()
            await page.set_viewport_size({"width": width, "height": height})
            
            # 加载 HTML
            await page.goto(f"file://{temp_html_path}")
            
            # 等待 Mermaid 渲染完成
            await page.wait_for_selector(".mermaid svg", timeout=10000)
            await asyncio.sleep(0.5)  # 额外等待确保渲染完成
            
            # 获取 SVG 元素并截图
            container = await page.query_selector("#container")
            if container:
                await container.screenshot(path=str(output_path))
            else:
                await page.screenshot(path=str(output_path))
            
            await page.close()
            
            return output_path
            
        finally:
            # 清理临时文件
            Path(temp_html_path).unlink(missing_ok=True)
    
    def render(
        self,
        mermaid_code: str,
        output_path: str | Path,
        width: int = 1200,
        height: int = 800,
    ) -> Path:
        """
        同步渲染 Mermaid 代码为 PNG 图片
        
        Args:
            mermaid_code: Mermaid 代码
            output_path: 输出文件路径
            width: 视口宽度
            height: 视口高度
            
        Returns:
            输出文件路径
        """
        return asyncio.get_event_loop().run_until_complete(
            self.render_async(mermaid_code, output_path, width, height)
        )
    
    async def render_multiple_async(
        self,
        diagrams: list[tuple[str, str | Path]],
        width: int = 1200,
        height: int = 800,
    ) -> list[Path]:
        """
        批量渲染多个图表
        
        Args:
            diagrams: (mermaid_code, output_path) 元组列表
            width: 视口宽度
            height: 视口高度
            
        Returns:
            输出文件路径列表
        """
        results = []
        for mermaid_code, output_path in diagrams:
            result = await self.render_async(mermaid_code, output_path, width, height)
            results.append(result)
        return results
    
    def __del__(self):
        """清理资源"""
        if self._browser:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._close_browser())
                else:
                    loop.run_until_complete(self._close_browser())
            except:
                pass


# 预定义的图表模板
DIAGRAM_TEMPLATES = {
    "use_case": """
graph TD
    subgraph 系统
        UC1[{功能1}]
        UC2[{功能2}]
        UC3[{功能3}]
    end
    
    Actor1((用户1)) --> UC1
    Actor1 --> UC2
    Actor2((用户2)) --> UC2
    Actor2 --> UC3
""",
    
    "sequence": """
sequenceDiagram
    participant U as 用户
    participant S as 系统
    participant DB as 数据库
    
    U->>S: 请求操作
    S->>DB: 查询数据
    DB-->>S: 返回结果
    S-->>U: 显示结果
""",
    
    "er": """
erDiagram
    USER ||--o{ ORDER : creates
    ORDER ||--|{ ORDER_ITEM : contains
    PRODUCT ||--o{ ORDER_ITEM : "ordered in"
    
    USER {{
        int id PK
        string name
        string email
    }}
    ORDER {{
        int id PK
        date created_at
        int user_id FK
    }}
""",
    
    "flowchart": """
flowchart TD
    A[开始] --> B{{判断条件}}
    B -->|是| C[处理1]
    B -->|否| D[处理2]
    C --> E[结束]
    D --> E
""",
    
    "pie": """
pie title 数据分布
    "类别A" : 40
    "类别B" : 30
    "类别C" : 20
    "类别D" : 10
""",
    
    "class": """
classDiagram
    class User {{
        +int id
        +String name
        +String email
        +login()
        +logout()
    }}
    class Order {{
        +int id
        +Date createTime
        +create()
        +cancel()
    }}
    User "1" --> "*" Order : creates
""",
}


def get_template(template_type: str) -> str:
    """获取预定义模板"""
    return DIAGRAM_TEMPLATES.get(template_type, "")
