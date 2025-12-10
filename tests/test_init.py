"""
测试 init 流程（非交互式）
"""
import asyncio
from pathlib import Path
from aiwrite.config import load_config, create_thinking_provider
from aiwrite.pipeline.init_step import OutlineInitializer

# 测试大纲
OUTLINE_TEXT = """
第1章 绪论
1.1 研究背景与意义
1.2 国内外研究现状
1.3 研究内容与方法

第2章 系统需求分析
2.1 系统业务流程分析
2.2 系统功能需求
2.3 系统非功能需求

第3章 系统总体设计
3.1 系统架构设计
3.2 功能模块设计
3.3 数据库设计

第4章 系统详细设计与实现
4.1 系统登录模块
4.2 员工管理模块
4.3 薪资管理模块
4.4 部门管理模块
4.5 考勤管理模块

第5章 系统测试
5.1 测试环境
5.2 功能测试
5.3 性能测试

第6章 总结与展望
6.1 总结
6.2 展望
"""

async def test_init():
    config = load_config()
    provider = create_thinking_provider(config)
    
    print(f"Provider: {provider}")
    print(f"Model: {provider.model}")
    
    # 创建初始化器
    initializer = OutlineInitializer(
        thinking_provider=provider,
        images_path=Path("examples/img2"),
    )
    
    # 1. 扫描图片
    print("\n" + "="*50)
    print("步骤 1: 扫描并识别图片")
    print("="*50)
    images = await initializer.scan_images()
    print(f"\n识别到 {len(images)} 张图片:")
    for img in images:
        print(f"  - {img['filename']}: {img['description']}")
    
    # 2. 扫描表格
    print("\n" + "="*50)
    print("步骤 2: 扫描表格")
    print("="*50)
    tables = initializer.scan_tables()
    print(f"发现 {len(tables)} 个表格文件")
    
    # 3. 解析大纲
    print("\n" + "="*50)
    print("步骤 3: 解析大纲并匹配图片")
    print("="*50)
    
    result = await initializer.parse_outline(
        paper_title="基于Spring Boot的人事管理系统设计与实现",
        outline_text=OUTLINE_TEXT,
        images=images,
        tables=tables,
        target_words=10000,
    )
    
    # 显示结果
    print("\n解析结果:")
    print(f"  - 章节数: {len(result.get('sections', []))}")
    
    # 统计匹配的图片
    def count_figures(sections):
        count = 0
        for s in sections:
            count += len(s.get('figures', []))
            count += count_figures(s.get('children', []))
        return count
    
    matched = count_figures(result.get('sections', []))
    print(f"  - 已匹配图片: {matched}")
    print(f"  - 需生成图表: {len(result.get('missing_diagrams', []))}")
    
    # 4. 构建 Paper 对象
    print("\n" + "="*50)
    print("步骤 4: 构建 Paper 对象")
    print("="*50)
    
    paper = initializer.build_paper(result)
    print(f"Paper 标题: {paper.title}")
    print(f"关键词: {paper.keywords}")
    print(f"章节结构:")
    for section in paper.sections:
        print(f"  {section.title}")
        for child in section.children:
            figs = f" [图×{len(child.figures)}]" if child.figures else ""
            print(f"    - {child.title}{figs}")
    
    print("\n✅ 测试完成!")
    return paper

if __name__ == "__main__":
    asyncio.run(test_init())
