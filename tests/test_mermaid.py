"""
测试 Mermaid 图表生成功能
"""
import asyncio
from pathlib import Path
from aiwrite.diagram import MermaidRenderer

async def test_mermaid():
    renderer = MermaidRenderer()
    
    # 测试用例
    test_cases = [
        {
            "name": "流程图",
            "code": """flowchart TD
    A[开始] --> B{用户登录}
    B -->|成功| C[进入系统首页]
    B -->|失败| D[显示错误信息]
    D --> B
    C --> E[选择功能模块]
    E --> F[员工管理]
    E --> G[薪资管理]
    E --> H[考勤管理]
""",
            "output": "output/test_mermaid/flowchart.png"
        },
        {
            "name": "时序图",
            "code": """sequenceDiagram
    participant U as 用户
    participant S as 系统
    participant DB as 数据库
    
    U->>S: 输入用户名密码
    S->>DB: 验证用户信息
    DB-->>S: 返回验证结果
    alt 验证成功
        S-->>U: 登录成功，跳转首页
    else 验证失败
        S-->>U: 显示错误提示
    end
""",
            "output": "output/test_mermaid/sequence.png"
        },
        {
            "name": "ER图",
            "code": """erDiagram
    EMPLOYEE ||--o{ ATTENDANCE : has
    EMPLOYEE {
        int id PK
        string name
        string department
        date hire_date
    }
    DEPARTMENT ||--o{ EMPLOYEE : contains
    DEPARTMENT {
        int id PK
        string name
        string manager
    }
    ATTENDANCE {
        int id PK
        int employee_id FK
        date date
        time check_in
        time check_out
    }
""",
            "output": "output/test_mermaid/er.png"
        },
        {
            "name": "饼图",
            "code": """pie title 员工部门分布
    "技术部" : 45
    "市场部" : 25
    "财务部" : 15
    "人事部" : 10
    "其他" : 5
""",
            "output": "output/test_mermaid/pie.png"
        },
    ]
    
    # 创建输出目录
    output_dir = Path("output/test_mermaid")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("测试 Mermaid 图表生成")
    print("=" * 50)
    
    for case in test_cases:
        print(f"\n生成 {case['name']}...")
        output_path = Path(case["output"])
        
        try:
            await renderer.render_async(case["code"], output_path)
            print(f"  ✅ 成功: {output_path}")
        except Exception as e:
            print(f"  ❌ 失败: {e}")
    
    print("\n" + "=" * 50)
    print(f"图表已保存到 {output_dir}")

if __name__ == "__main__":
    asyncio.run(test_mermaid())
