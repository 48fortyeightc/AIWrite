"""
完整测试：人事管理系统论文大纲生成
"""
import asyncio
from pathlib import Path
from aiwrite.config import load_config, create_thinking_provider, save_outline
from aiwrite.pipeline.init_step import OutlineInitializer

# 用户提供的大纲
OUTLINE_TEXT = """
第1章 绪论
1.1 研究背景与意义
1.2 国内/国外研究现状
1.3 本系统的主要功能与特色
1.4 技术路线与开发环境
1.5 论文结构安排

第2章 系统需求分析
2.1 可行性分析
2.2 系统业务流程分析 📌业务流程图
2.3 功能结构分析 📌功能结构图
2.4 用例分析 📌用例图
2.5 功能需求说明表 📌需求表格

第3章 系统总体设计
3.1 系统架构设计 📌系统部署架构图
3.2 模块划分与模块关系设计 📌模块划分图
3.3 数据库设计
3.3.1 实体关系设计 📌ER图
3.3.2 数据表结构设计 📌数据库表结构表格

第4章 系统详细设计
4.1 用户/权限管理模块设计 📌时序图
4.2 员工信息管理模块设计 📌时序图
4.3 考勤/请假模块设计 📌时序图
4.4 薪资/工资计算模块设计 📌时序图
4.5 报表/查询模块设计 📌流程图
4.6 界面设计 📌界面原型图

第5章 系统实现
5.1 开发环境与技术实现说明
5.2 主要功能实现展示 📌功能界面截图(登录、员工列表、考勤录入、请假申请、薪资查看)
5.3 部分关键代码

第6章 系统测试
6.1 测试环境说明
6.2 功能测试 📌测试用例表格
6.3 性能测试 📌性能测试数据图表

第7章 总结与展望
7.1 本文工作总结
7.2 系统优点与不足
7.3 后续改进与功能扩展展望
"""

async def test_full_init():
    config = load_config()
    provider = create_thinking_provider(config)
    
    print("="*60)
    print("《人事管理系统》论文大纲生成测试")
    print("="*60)
    print(f"模型: {provider.model}")
    print(f"图片目录: examples/img2")
    print("="*60)
    
    # 创建初始化器
    initializer = OutlineInitializer(
        thinking_provider=provider,
        images_path=Path("examples/img2"),
    )
    
    # 1. 扫描图片
    print("\n【步骤1】扫描并识别图片...")
    images = await initializer.scan_images()
    print(f"\n✅ 识别到 {len(images)} 张图片:")
    for img in images:
        print(f"   - {img['filename']}: {img['description'][:40]}...")
    
    # 2. 扫描表格
    print("\n【步骤2】扫描表格文件...")
    tables = initializer.scan_tables()
    print(f"✅ 发现 {len(tables)} 个表格文件")
    
    # 3. 解析大纲
    print("\n【步骤3】AI解析大纲并匹配图片...")
    result = await initializer.parse_outline(
        paper_title="基于Spring Boot的人事管理系统设计与实现",
        outline_text=OUTLINE_TEXT,
        images=images,
        tables=tables,
        target_words=15000,
    )
    
    # 4. 显示结果
    print("\n" + "="*60)
    print("解析结果")
    print("="*60)
    
    sections = result.get("sections", [])
    print(f"\n📚 章节数: {len(sections)}")
    
    # 统计匹配的图片
    def show_section(s, indent=0):
        prefix = "  " * indent
        figures = s.get("figures", [])
        tables = s.get("tables", [])
        fig_info = f" [图×{len(figures)}]" if figures else ""
        tab_info = f" [表×{len(tables)}]" if tables else ""
        print(f"{prefix}{s.get('title', '未命名')}{fig_info}{tab_info}")
        
        # 显示匹配的图片
        for f in figures:
            print(f"{prefix}  📷 {f.get('caption', '')} → {f.get('path', '')}")
        for t in tables:
            print(f"{prefix}  📊 {t.get('caption', '')} → {t.get('path', '')}")
        
        for child in s.get("children", []):
            show_section(child, indent + 1)
    
    print("\n📖 章节结构与图表匹配:")
    for s in sections:
        show_section(s)
    
    # 显示缺失的图表
    missing = result.get("missing_diagrams", [])
    if missing:
        print(f"\n⚠️ 需要生成的图表 ({len(missing)}个):")
        for d in missing:
            print(f"   - [{d.get('type', 'unknown')}] {d.get('caption', '未命名')} → {d.get('section_id', '')}")
    
    # 5. 构建 Paper 对象并保存
    print("\n【步骤4】构建Paper对象并保存...")
    paper = initializer.build_paper(result)
    
    output_path = Path("examples/hrm_system.yaml")
    save_outline(paper, output_path)
    
    print(f"\n✅ 大纲已保存到: {output_path}")
    print(f"   标题: {paper.title}")
    print(f"   关键词: {', '.join(paper.keywords)}")
    print(f"   英文关键词: {', '.join(paper.keywords_en)}")
    print(f"   目标字数: {paper.target_words}")
    
    print("\n" + "="*60)
    print("🎉 测试完成！")
    print("="*60)
    print(f"\n下一步命令:")
    print(f"  python -m aiwrite generate-draft {output_path}")
    
    return paper

if __name__ == "__main__":
    asyncio.run(test_full_init())
