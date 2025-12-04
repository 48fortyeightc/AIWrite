# AIWrite

> 🚀 基于大语言模型的自动化学术论文写作系统

AIWrite 是一个从「题目 + 章节大纲」到「完整论文」的一站式自动写作工具。支持多模型协作、图片识别、表格插入，最终输出 LaTeX 源码和 Word 文档。

## ✨ 特性

- **多模型协作**：思考模型生成大纲，写作模型生成正文，视觉模型识别图片
- **智能大纲生成**：只需输入题目和主要章节，AI 自动展开详细小节结构
- **图片智能识别**：自动分析图片内容，生成学术性描述，并在正确位置插入
- **表格自动插入**：支持从 Excel 文件（.xls/.xlsx）读取数据并插入 Word
- **双格式输出**：同时生成 LaTeX 源码和 Word 文档
- **流水线架构**：模块化设计，支持分阶段执行和断点续写

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/48fortyeightc/AIWrite.git
cd AIWrite

# 安装依赖
pip install -e .

# 安装可选依赖（图片识别和 Excel 支持）
pip install xlrd openpyxl
```

## ⚙️ 配置

创建 `.env` 文件配置 API 密钥：

```bash
# 思考模型（用于大纲生成、摘要生成）
THINKING_API_KEY=your_api_key
THINKING_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
THINKING_MODEL=doubao-seed-1-6-thinking-250715

# 写作模型（用于正文生成）
WRITING_API_KEY=your_api_key
WRITING_BASE_URL=https://api.deepseek.com/v1
WRITING_MODEL=deepseek-v3-1-terminus

# 视觉模型（用于图片识别，可选）
VISION_API_KEY=your_api_key
VISION_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
VISION_MODEL=doubao-1-5-vision-pro-32k-250115
```

## 🚀 快速开始

### 1. 准备大纲文件

创建 YAML 格式的大纲文件（参考 `examples/` 目录）：

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
        figures:
          - id: fig1-1
            path: images/系统架构图.png
            caption: 系统整体架构图
```

### 2. 生成大纲小节

```bash
aiwrite outline examples/my_paper.yaml
```

### 3. 生成草稿

```bash
aiwrite draft examples/my_paper.yaml
```

### 4. 润色并导出

```bash
aiwrite finalize examples/my_paper.yaml -o output/my_paper --images examples
```

## 📖 命令说明

| 命令 | 说明 |
|------|------|
| `aiwrite outline <file>` | 生成大纲小节结构 |
| `aiwrite draft <file>` | 生成各章节草稿 |
| `aiwrite refine <file>` | 润色所有章节 |
| `aiwrite abstract <file>` | 生成中英文摘要 |
| `aiwrite finalize <file>` | 完整流程：润色 + 摘要 + 导出 |
| `aiwrite export <file>` | 仅导出 LaTeX 和 Word |
| `aiwrite analyze-images <file>` | 分析图片并更新描述 |

### 常用选项

```bash
-o, --output <dir>    # 输出目录
--images <dir>        # 图片基础路径
--skip-refine         # 跳过润色步骤
--skip-abstract       # 跳过摘要生成
```

## 📁 项目结构

```
aiwrite/
├── cli.py              # 命令行入口
├── config/             # 配置管理
├── llm/                # LLM 提供者（写作/思考/视觉模型）
├── models/             # 数据模型（Paper, Section, Figure, Table）
├── pipeline/           # 流水线步骤
├── prompts/            # Prompt 模板
├── render/             # 渲染器（LaTeX, Word）
└── utils/              # 工具函数（Excel 解析等）
```

## 🖼️ 图片和表格支持

### 图片

在大纲中定义图片：

```yaml
figures:
  - id: fig1-1
    path: images/系统架构图.png
    caption: 系统整体架构图
```

AI 会自动：
1. 使用视觉模型分析图片内容
2. 在正文中生成 `{{FIGURE:caption:description}}` 占位符
3. 导出 Word 时插入真实图片

### 表格

在大纲中定义表格：

```yaml
tables:
  - id: tab1-1
    path: images/用户表.xls
    caption: 用户表结构
```

导出 Word 时会自动读取 Excel 并插入表格。

## 🔧 支持的模型

| 用途 | 推荐模型 | 说明 |
|------|----------|------|
| 思考/大纲 | doubao-seed-1-6-thinking | 深度推理，结构化规划 |
| 正文写作 | deepseek-v3-1-terminus | 长文本，学术写作 |
| 图片识别 | doubao-1-5-vision-pro | 图片内容分析 |

## 📄 输出示例

运行完整流程后，会在输出目录生成：

```
output/my_paper/
├── 论文标题.tex      # LaTeX 源码
├── 论文标题.docx     # Word 文档（含图片和表格）
└── my_paper.yaml     # 更新后的大纲文件
```

## 🛠️ 工作流程

```
用户输入大纲 → 思考模型展开小节 → 用户确认
                                    ↓
                           写作模型生成草稿
                                    ↓
                           写作模型润色内容
                                    ↓
                           思考模型生成摘要
                                    ↓
                         导出 LaTeX + Word
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📜 许可证

MIT License
