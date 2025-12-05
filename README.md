# AIWrite

> 🚀 基于大语言模型的自动化学术论文写作系统

AIWrite 是一个从「题目 + 章节大纲」到「完整论文」的一站式自动写作工具。支持多模型协作、图片识别、Mermaid 图表生成，最终输出 LaTeX 源码和 Word 文档。

## ✨ 特性

- **多模型协作**：思考模型生成大纲，写作模型生成正文，视觉模型识别图片
- **智能大纲生成**：只需输入题目和主要章节，AI 自动展开详细小节结构
- **图片智能识别**：自动分析图片内容，生成学术性描述，并匹配到正确章节
- **Mermaid 图表**：本地渲染流程图、时序图、ER图、类图、思维导图等
- **双格式输出**：同时生成 LaTeX 源码和 Word 文档
- **流水线架构**：模块化设计，支持分阶段执行和断点续写

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/48fortyeightc/AIWrite.git
cd AIWrite

# 安装依赖
pip install -e .

# 安装 Playwright（用于 Mermaid 图表渲染）
playwright install chromium
```

## ⚙️ 配置

创建 `.env` 文件配置 API 密钥：

```bash
# 思考模型（用于大纲生成、摘要生成、图片识别）
THINKING_API_KEY=your_api_key
THINKING_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
THINKING_MODEL=doubao-seed-1-6-250615

# 写作模型（用于正文生成）
WRITING_API_KEY=your_api_key
WRITING_BASE_URL=https://api.deepseek.com/v1
WRITING_MODEL=deepseek-v3-1-terminus
```

---

## 🚀 完整使用流程

### 方式一：从纯文本大纲开始（推荐）

这是最简单的方式，只需准备一个文本大纲，AI 会自动完成所有工作。

#### 第1步：准备大纲文本

创建一个 `.txt` 文件，写入你的论文大纲：

```text
第1章 绪论
1.1 研究背景与意义
1.2 国内外研究现状
1.3 研究内容与方法

第2章 相关技术介绍
2.1 Spring Boot框架
2.2 Vue.js前端技术
2.3 MySQL数据库

第3章 系统需求分析
3.1 功能需求分析
3.2 非功能需求分析
3.3 用例分析

第4章 系统设计
4.1 系统架构设计
4.2 数据库设计
4.3 接口设计

第5章 系统实现
5.1 开发环境搭建
5.2 核心功能实现
5.3 系统界面展示

第6章 系统测试
6.1 测试环境
6.2 功能测试
6.3 性能测试

第7章 总结与展望
7.1 工作总结
7.2 未来展望
```

#### 第2步：运行 init 命令

```bash
# 基本用法
aiwrite init -t "基于Spring Boot的人事管理系统设计与实现" -o hrm.yaml

# 带图片目录（AI会自动识别图片并匹配到章节）
aiwrite init -t "基于Spring Boot的人事管理系统设计与实现" -o hrm.yaml -i examples/img2

# 指定目标字数
aiwrite init -t "基于Spring Boot的人事管理系统设计与实现" -o hrm.yaml -i examples/img2 -w 15000
```

运行后会提示你输入大纲文本，粘贴后按 **Ctrl+D**（Mac/Linux）或 **Ctrl+Z 然后回车**（Windows）结束输入。

#### 第3步：生成论文草稿

```bash
aiwrite generate-draft hrm.yaml
```

这一步会调用写作模型，为每个章节生成 LaTeX 格式的正文内容。

#### 第4步：润色并导出

```bash
# 完整流程：润色 + 生成摘要 + 导出 LaTeX + 导出 Word
aiwrite finalize hrm.yaml -o output/hrm -i examples/img2

# 跳过润色（如果草稿质量已经很好）
aiwrite finalize hrm.yaml -o output/hrm -i examples/img2 --skip-refine

# 只生成 LaTeX（不转换 Word）
aiwrite finalize hrm.yaml -o output/hrm --latex-only
```

最终输出：
- `output/hrm/基于Spring Boot的人事管理系统设计与实现.tex` - LaTeX 源码
- `output/hrm/基于Spring Boot的人事管理系统设计与实现.docx` - Word 文档

---

### 方式二：从 YAML 配置开始

如果你想要更精细的控制，可以直接编写 YAML 配置文件。

#### 第1步：创建 YAML 配置文件

```yaml
title: 基于Spring Boot的教育管理系统设计与实现
target_words: 15000
keywords:
  - Spring Boot
  - 教育管理系统
  - B/S架构

sections:
  - id: ch1
    title: 第1章 绪论
    level: 1
    children:
      - id: ch1-1
        title: 1.1 研究背景
        level: 2
      - id: ch1-2
        title: 1.2 研究意义
        level: 2
        figures:
          - id: fig1-1
            path: images/系统架构图.png
            caption: 系统整体架构图
```

#### 第2步：生成详细大纲（可选）

```bash
aiwrite suggest-outline my_paper.yaml
```

#### 第3步：生成草稿

```bash
aiwrite generate-draft my_paper.yaml
```

#### 第4步：润色并导出

```bash
aiwrite finalize my_paper.yaml -o output/my_paper -i examples/images
```

---

## 📖 命令速查表

| 命令 | 说明 |
|------|------|
| `aiwrite init` | 从纯文本大纲初始化论文配置（推荐起点） |
| `aiwrite suggest-outline <file>` | 为已有 YAML 生成详细小节结构 |
| `aiwrite generate-draft <file>` | 生成各章节正文草稿 |
| `aiwrite finalize <file>` | 润色 + 生成摘要 + 导出 LaTeX/Word |
| `aiwrite status <file>` | 查看论文当前进度 |
| `aiwrite analyze-images <file>` | 单独分析图片并更新描述 |

### 常用选项

| 选项 | 说明 |
|------|------|
| `-o, --output` | 输出文件/目录路径 |
| `-i, --images` | 图片目录路径 |
| `-w, --words` | 目标字数（默认 10000） |
| `--skip-refine` | 跳过润色步骤 |
| `--skip-abstract` | 跳过摘要生成 |
| `--latex-only` | 只生成 LaTeX，不转换 Word |
| `--alt` | 使用备选写作模型 |

---

## 🖼️ Mermaid 图表生成

AIWrite 支持本地渲染多种 Mermaid 图表：

```python
from aiwrite.diagram.mermaid import MermaidRenderer

renderer = MermaidRenderer()

# 流程图
code = """
flowchart TD
    A[开始] --> B{判断}
    B -->|是| C[执行]
    B -->|否| D[结束]
"""
renderer.render_to_file(code, "flowchart.png")
```

支持的图表类型：
- **flowchart** - 流程图
- **sequenceDiagram** - 时序图
- **erDiagram** - ER 图
- **classDiagram** - 类图
- **mindmap** - 思维导图
- **pie** - 饼图

---

## 📁 项目结构

```
AIWrite/
├── aiwrite/
│   ├── cli.py              # 命令行入口
│   ├── config/             # 配置管理
│   ├── diagram/            # Mermaid 图表渲染
│   ├── llm/                # LLM 提供商（豆包、DeepSeek等）
│   ├── models/             # 数据模型（Paper, Section）
│   ├── pipeline/           # 流水线步骤
│   ├── prompts/            # 提示词模板
│   ├── render/             # LaTeX/Word 渲染
│   └── utils/              # 工具函数
├── examples/               # 示例配置文件
├── output/                 # 输出目录
└── .env                    # API 配置
```

---

## ❓ 常见问题

### Q: Windows 下输入大纲后怎么结束？
A: 粘贴完大纲后，按 **Ctrl+Z** 然后按 **回车**。

### Q: 图片没有被识别怎么办？
A: 确保使用 `-i` 参数指定了正确的图片目录，且图片格式为 PNG/JPG。

### Q: 生成的 Word 没有图片？
A: 在 `finalize` 命令中使用 `-i` 参数指定图片目录。

### Q: 如何只重新生成某个章节？
A: 目前需要编辑 YAML 文件，删除该章节的 `draft_latex` 字段，然后重新运行 `generate-draft`。

### Q: 模型报错 404？
A: 检查 `.env` 中的模型名称是否正确。豆包模型需要使用正确的 endpoint ID。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📜 License

MIT License
