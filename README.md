# AIWrite：自动化论文写作流水线

> 从「题目 + 章节大纲」到「LaTeX 论文源码 + Word 终稿」的一站式自动写作系统

## 1. 项目愿景

AIWrite 旨在构建一套基于大语言模型（LLM）的自动化学术写作工作流，实现从选题到生成完整论文终稿的全流程自动化/半自动化支持，减少重复劳动，让使用者将精力集中在选题、创新和思考上。

核心目标：
- **输入**：
  - 题目模版：如《基于 XXX 的系统设计与实现》《XXX 模型的设计与应用》等
  - 一套可定制的论文大纲（只需大章节）：
    - 摘要 / Abstract
    - 第 1 章 绪论
    - 第 2 章 相关技术与理论基础
    - 第 3 章 需求分析（或：问题定义与总体方案设计）
    - 第 4 章 系统总体设计
    - 第 5 章 系统实现
    - 第 6 章 系统测试与结果分析
    - 第 7 章 总结与展望
    - 参考文献
- **过程**：基于 LLM 的多阶段、多轮交互写作管线（大纲生成与确认 → 草稿生成与修改 → 最终版润色与排版）
- **输出**：
  - 结构合规、各级标题清晰的 LaTeX 源文件
  - 在用户最终确认后，转换为符合论文排版要求的 Word（`.docx`）终稿

> 设计理念：**优先生成结构严格的 LaTeX，再从 LaTeX 稳定渲染为 Word**，以确保层级标题、目录、参考文献等更加可靠。

---

## 2. 总体功能规划（MVP）

MVP 版本预期实现以下闭环：

1. **项目配置与 LLMProvider 抽象**
   - 定义统一的 `LLMProvider` 接口，屏蔽具体大模型差异
   - 采用**多模型协作**策略：思考模型生成大纲，写作模型生成正文
   - 通过配置文件或环境变量管理密钥、Base URL、模型名称、温度等参数

2. **大纲驱动 + 多轮交互的章节生成**
   - **第一步（大纲生成）**：
     - 用户只需输入题目 + 大章节标题（如"第1章 绪论"、"第2章 相关技术"等）
     - 系统调用**思考模型**（如 `doubao-seed-1-6-thinking`）自动展开小节建议
     - 用户可修改、增删、调整后确认大纲
   - **第二步（草稿生成）**：
     - 基于确认后的大纲，调用**写作模型**（如 `deepseek-v3` / `kimi-k2`）为各章节生成草稿
     - 用户可查看、局部修改或要求重生成某章节
   - **第三步（最终版生成）**：
     - 用户确认草稿后，再触发**最终版生成与润色**
     - 集中使用 Token 打磨质量，避免一次性不满意导致的大量 Token 浪费

3. **写作模板与 Prompt 工程**
   - 针对不同章节（摘要、引言、方法、实验、结论等）设计专用 Prompt 模板
   - Prompt 显式要求：
     - LaTeX 片段/小节结构（如 `\section`、`\subsection`）
     - 不生成封面、文献列表（由系统统一管理）
     - 控制篇幅与风格
   - 支持在 `outline.yaml` 或独立配置中覆写默认 Prompt

4. **LaTeX 文档装配与渲染**
   - 将 `Paper` / `Section` 树转换为 LaTeX 文档结构
   - 统一控制：
     - 文档类（例如 `ctexart`, `article`, 或期刊模板）
     - 字体、行距、页边距等基础排版要求
     - 标题层次：`\section` / `\subsection` / `\subsubsection`
   - 支持一键编译为 PDF（本地安装 `latexmk` / `xelatex` 时）

5. **LaTeX → Word 转换**
   - 提供 `latex -> docx` 的自动转换步骤（例如调用 `pandoc` 等工具）
   - 在转换前后进行基本结构检查：
     - 标题层级是否保留
     - 目录是否可在 Word 中更新
   - 可选择只输出 LaTeX 源码，或同时生成 `.docx`

6. **可组合的 PipelineStep 抽象**
   - 定义通用 `PipelineStep` 接口，用于描述一个写作步骤：
     - 例如：
       - `OutlineSuggestStep`：基于题目生成完整大纲候选（调用思考模型）
       - `OutlineRefineStep`：根据用户修改结果更新大纲
       - `SectionDraftStep`：生成章节草稿版本（调用写作模型）
       - `SectionRefineStep`：在用户确认后生成/润色最终版本
       - `LatexRenderStep`：将最终内容装配为 LaTeX
       - `WordExportStep`：从 LaTeX 导出 Word
   - 流水线由若干 `PipelineStep` 串联，**显式区分"草稿阶段"和"最终版阶段"**，便于控制 Token 消耗和交互体验

7. **基本 CLI 交互界面**
   - 命令行入口：
     - 输入：`outline.yaml`
     - 输出：`paper.tex`（必选）、`paper.docx`（可选）
   - 支持 dry-run / 分阶段执行（仅生成大纲、仅生成草稿、仅渲染 LaTeX 等）

---

## 3. 核心抽象与数据模型设计

### 3.1 LLMProvider 接口与多模型协作

本项目采用**多模型协作**架构，不同阶段使用不同特长的模型：

| 阶段 | 推荐模型 | 说明 |
|------|----------|------|
| 大纲生成与规划 | `doubao-seed-1-6-thinking-250715` | 具备深度思考能力，适合结构化规划 |
| 论文正文写作 | `deepseek-v3-1-terminus` | 长文本生成能力强，适合章节写作 |
| 论文正文写作（备选） | `kimi-k2-thinking-251104` | 思考+写作兼顾，中文表达流畅 |

统一对接不同大模型的抽象层：

- `LLMProvider`
  - `name: str`
  - `purpose: Literal["thinking", "writing", "polishing"]`（模型用途标识）
  - `invoke(prompt: str, *, system_prompt: str | None = None, options: LLMOptions) -> str`
  - 可以扩展流式输出、Token 限制等

内置实现（计划）：
- `DoubaoProvider`：对接字节豆包（doubao-seed 系列，用于思考/规划）
- `DeepSeekProvider`：对接 DeepSeek（用于写作）
- `KimiProvider`：对接 Moonshot Kimi（用于写作）
- `OpenAICompatibleProvider`：通用 OpenAI 兼容接口（可对接其他模型）

### 3.2 Paper / Section / Draft 数据模型

建议使用 `pydantic` 或 `dataclasses` 定义：

- `Paper`
  - `title: str`
  - `authors: list[str]`
  - `keywords: list[str]`
  - `language: Literal["zh", "en"]`
  - `sections: list[Section]`
  - `status: Literal["pending_outline", "outline_confirmed", "draft", "final"]`

- `Section`
  - `id: str`（如 `ch1`, `ch1.1`, `ch1.1.1`）
  - `title: str`
  - `level: int`（0=特殊区段如摘要，1=`\section`，2=`\subsection` 等）
  - `target_words: int | None`
  - `style: str | None`（如 "academic", "survey", "proposal"）
  - `notes: str | None`（作者/系统的额外说明）
  - `children: list[Section]`（小节，由思考模型自动生成）
  - `draft_latex: str | None`（草稿阶段生成的 LaTeX 正文）
  - `final_latex: str | None`（最终润色后的 LaTeX 正文）

### 3.3 PipelineStep 抽象

每个步骤负责对 `Paper` 进行一次"变换"：

- `PipelineStep`
  - `name: str`
  - `run(paper: Paper, context: PipelineContext) -> Paper`

示例步骤：
- `OutlineSuggestStep`：调用思考模型，根据题目展开小节建议
- `OutlineValidationStep`：校验大纲结构、级别是否连续
- `SectionDraftStep`：调用写作模型，为每个 `Section` 生成第一版草稿
- `SectionPolishStep`：对已有内容进行润色/语言统一
- `LatexAssembleStep`：合成整篇 LaTeX 文档字符串
- `LatexToWordStep`：调用外部工具转换为 Word

---

## 4. 多模型接入与配置说明

本项目采用多模型协作策略，不同阶段调用最适合的模型。

### 4.1 模型分工

| 用途 | 推荐模型 | 提供商 | 特点 |
|------|----------|--------|------|
| **大纲规划/思考** | `doubao-seed-1-6-thinking-250715` | 字节跳动（火山引擎） | 深度推理、结构化规划能力强 |
| **正文写作** | `deepseek-v3-1-terminus` | DeepSeek | 长文本生成、学术写作质量高 |
| **正文写作（备选）** | `kimi-k2-thinking-251104` | Moonshot | 思考+写作兼顾，中文表达流畅 |

### 4.2 需要准备什么

- 各模型提供商的账号与 API 访问权限
- **API Key**（统一使用 OpenAI 兼容格式的密钥）
- 各模型的 Base URL 与模型名称

### 4.3 建议的环境变量

在 `.env` 或系统环境变量中配置：

```text
# ========== 思考/规划模型（用于大纲生成） ==========
THINKING_API_KEY=your_api_key_here
THINKING_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
THINKING_MODEL=doubao-seed-1-6-thinking-250715

# ========== 写作模型（用于正文生成） ==========
WRITING_API_KEY=your_api_key_here
WRITING_BASE_URL=https://api.deepseek.com/v1
WRITING_MODEL=deepseek-v3-1-terminus

# ========== 备选写作模型 ==========
WRITING_ALT_API_KEY=your_api_key_here
WRITING_ALT_BASE_URL=https://api.moonshot.cn/v1
WRITING_ALT_MODEL=kimi-k2-thinking-251104

# ========== 全局配置 ==========
AIWRITE_LLM_MAX_TOKENS=8192
AIWRITE_LLM_TEMPERATURE=0.3
```

### 4.4 模型调用逻辑

系统会根据当前 PipelineStep 自动选择对应模型：

```
OutlineSuggestStep  →  THINKING_MODEL（doubao-seed-1-6-thinking）
     ↓
SectionDraftStep    →  WRITING_MODEL（deepseek-v3 或 kimi-k2）
     ↓
SectionRefineStep   →  WRITING_MODEL（复用写作模型进行润色）
```

> 后续可在 `docs/llm_config.md` 中详细说明各模型的调用参数与最佳实践。

---

## 5. LaTeX 写作与 Word 转换流水线

整体思路：**所有章节内容先生成 LaTeX 段落，最后统一渲染整篇论文，并按需转换为 Word**。

### 5.1 LaTeX 模板与论文格式

MVP 阶段采用一个相对通用、易于定制的模板，例如：

```latex
\documentclass[12pt,a4paper]{ctexart}
\usepackage{geometry}
\geometry{a4paper, margin=2.5cm}
\usepackage{setspace}
\onehalfspacing
\usepackage{hyperref}

% 这里可以预留学校/期刊要求的其他宏包

\title{<由 Paper.title 填充>}
\author{<由 Paper.authors 填充>}
\date{\today}

\begin{document}
  \maketitle
  \tableofcontents
  \clearpage

  % 章节内容由 Section 树展开

\end{document}
```

后续可根据具体学校/期刊的模板进行替换，只需要保持 `Section` 映射到合适的 `\section` 层级即可。

### 5.2 标题层级与 Section 映射

约定映射关系：

- `level = 0` → 特殊区段（摘要、参考文献等，使用自定义环境）
- `level = 1` → `\section{title}`
- `level = 2` → `\subsection{title}`
- `level = 3` → `\subsubsection{title}`

在生成 Prompt 时，明确要求模型**只生成小节内部正文**，不要重复 `\section` 命令，由系统统一包裹，或仅允许模型输出 `\paragraph` 级别的结构，以减少错误。

### 5.3 LaTeX → Word 转换

建议通过 `pandoc` 完成：

```powershell
pandoc paper.tex -o paper.docx
```

项目将提供一个 `WordExportStep` 来封装该逻辑，并在转换前后做简单校验（例如检查标题命令、是否成功生成 docx）。

---

## 6. outline.yaml 示例

用户只需提供**论文题目**和**大章节标题**，系统会自动展开小节建议供用户确认。

### 6.1 用户输入示例（只需大章节）

下面是用户初始输入的 `examples/outline_input.yaml`，只包含大章节骨架：

```yaml
paper:
  # 论文题目（必填）
  title: "基于大语言模型的自动化论文写作系统的设计与实现"

  # 作者信息
  authors:
    - "张三"

  # 关键词（可选，留空则由系统建议）
  keywords: []

  language: "zh"      # zh / en
  style: "academic"   # academic / survey / application

  # 整体目标字数
  target_words: 15000

  # 当前阶段（由系统维护）
  status: "pending_outline"   # pending_outline / outline_confirmed / draft / final

sections:
  # 摘要
  - id: "abstract-zh"
    title: "摘要"
    level: 0
    target_words: 500

  - id: "abstract-en"
    title: "Abstract"
    level: 0
    target_words: 500

  # 正文章节（用户只需列出大章节）
  - id: "ch1"
    title: "第1章 绪论"
    level: 1
    target_words: 2000

  - id: "ch2"
    title: "第2章 相关技术与理论基础"
    level: 1
    target_words: 2500

  - id: "ch3"
    title: "第3章 需求分析"
    level: 1
    target_words: 2000

  - id: "ch4"
    title: "第4章 系统总体设计"
    level: 1
    target_words: 2500

  - id: "ch5"
    title: "第5章 系统实现"
    level: 1
    target_words: 3000

  - id: "ch6"
    title: "第6章 系统测试与结果分析"
    level: 1
    target_words: 2000

  - id: "ch7"
    title: "第7章 总结与展望"
    level: 1
    target_words: 1500

  # 参考文献（占位，不由模型生成）
  - id: "refs"
    title: "参考文献"
    level: 0
```

### 6.2 系统生成的完整大纲（供用户确认）

系统使用**思考模型**（`doubao-seed-1-6-thinking`）根据题目自动展开小节，生成 `outline_suggested.yaml`：

```yaml
paper:
  title: "基于大语言模型的自动化论文写作系统的设计与实现"
  authors:
    - "张三"
  keywords:
    - "大语言模型"
    - "自动化写作"
    - "论文生成"
    - "LaTeX"
  language: "zh"
  style: "academic"
  target_words: 15000
  status: "pending_confirmation"

sections:
  - id: "abstract-zh"
    title: "摘要"
    level: 0
    target_words: 500
    notes: "概述研究背景、主要工作、技术方案和创新点。"

  - id: "abstract-en"
    title: "Abstract"
    level: 0
    target_words: 500

  - id: "ch1"
    title: "第1章 绪论"
    level: 1
    target_words: 2000
    children:
      - id: "ch1.1"
        title: "1.1 研究背景与意义"
        level: 2
        target_words: 600
        notes: "阐述大语言模型发展背景，论文写作自动化的意义。"
      - id: "ch1.2"
        title: "1.2 国内外研究现状"
        level: 2
        target_words: 800
        notes: "综述自动写作、LLM 应用、LaTeX 生成等方向的研究进展。"
      - id: "ch1.3"
        title: "1.3 本文研究内容与结构安排"
        level: 2
        target_words: 600
        notes: "概述本文工作内容，给出各章安排。"

  - id: "ch2"
    title: "第2章 相关技术与理论基础"
    level: 1
    target_words: 2500
    children:
      - id: "ch2.1"
        title: "2.1 大语言模型技术概述"
        level: 2
        notes: "介绍 Transformer、GPT、多模型协作等核心概念。"
      - id: "ch2.2"
        title: "2.2 Prompt 工程与提示词设计"
        level: 2
        notes: "介绍 Prompt 设计原则、模板化方法。"
      - id: "ch2.3"
        title: "2.3 LaTeX 排版与文档结构"
        level: 2
        notes: "介绍 LaTeX 基础、论文模板结构。"

  # ... 后续章节由思考模型类似展开 ...

  - id: "ch7"
    title: "第7章 总结与展望"
    level: 1
    target_words: 1500
    children:
      - id: "ch7.1"
        title: "7.1 本文工作总结"
        level: 2
      - id: "ch7.2"
        title: "7.2 不足与展望"
        level: 2

  - id: "refs"
    title: "参考文献"
    level: 0
    notes: "由参考文献管理工具或人工维护。"
```

### 6.3 交互流程说明

```
用户输入（大章节）              系统生成（展开小节）               用户确认/修改
outline_input.yaml  →  [思考模型]  →  outline_suggested.yaml  →  outline_confirmed.yaml
                                                                          ↓
                                                                [写作模型生成草稿]
                                                                          ↓
                                                                  draft_paper.yaml
                                                                          ↓
                                                                [用户确认/局部修改]
                                                                          ↓
                                                                [写作模型润色终稿]
                                                                          ↓
                                                                paper.tex + paper.docx
```

解析时会构造出一个 `Paper` 对象（包含当前阶段 status）和一棵 `Section` 树，后续流水线会在：
- **大纲阶段**：思考模型根据题目展开小节，用户确认后 status → `outline_confirmed`
- **草稿阶段**：写作模型为每个 Section 生成 `draft_latex`，用户可局部修改/重生成
- **最终阶段**：用户确认后，写作模型生成 `final_latex`，用于渲染 LaTeX 论文与导出 Word

---

## 7. Prompt 模板设计说明

Prompt 将根据章节类型（title/notes）和全局配置自动生成。

### 7.1 大纲生成 Prompt（思考模型）

```text
[系统提示]
你是一名经验丰富的学术论文写作导师，擅长规划计算机科学领域的本科/硕士毕业论文结构。
请根据论文题目，为每个大章节展开合理的小节结构，并给出每个小节的写作要点说明。

[用户提示]
论文题目：{paper_title}
论文类型：{style}（如 academic / survey / application）
目标总字数：{target_words}

当前大纲骨架：
{sections_skeleton}

请为每个大章节生成 2-4 个小节建议，包括：
1. 小节标题（如"1.1 研究背景与意义"）
2. 小节的写作要点说明（notes）
3. 建议字数分配

输出格式：YAML 格式的 sections 列表
```

### 7.2 章节正文 Prompt（写作模型）

```text
[系统提示]
你是一名经验丰富的学术论文写作者，擅长用严谨、清晰的中文撰写计算机科学领域论文内容。
请按照学术论文的写作规范生成内容，避免口语化表达，不要编造不存在的文献或数据。

[用户提示]
论文题目：{paper_title}
论文关键词：{keywords}

当前需要撰写的章节：{section_title}
章节编号：{section_id}（对应 LaTeX 中 level={level}）
写作要点：{notes}

写作要求：
- 目标字数约为 {target_words} 字，可上下浮动 20%
- 使用正式、客观、学术化的中文表述
- 结构上自然分段
- 适当引用相关领域的研究方向，但不要给出具体的文献编号

输出格式要求：
- 输出内容为纯 LaTeX 正文片段，不要包含 \section 或 \subsection 命令
- 如需强调概念，可以使用 \textbf{}
- 如需列举要点，可以使用 itemize 环境

请根据以上信息，生成该章节的完整草稿内容。
```

项目中会：
- 提供一组默认模板
- 允许在配置文件中按章节 id 或章节类型覆写默认模板

---

## 8. 典型使用流程

1. **准备输入文件**：创建 `outline_input.yaml`
   - 只需填写论文题目、作者信息
   - 列出大章节标题（第1章、第2章…）和目标字数

2. **配置环境变量**：在 `.env` 中配置各模型的 API Key 和 Base URL

3. **运行 CLI 生成大纲**：

   ```powershell
   # 第一步：生成大纲建议
   python -m aiwrite.cli suggest-outline --input outline_input.yaml --output outline_suggested.yaml
   ```

4. **确认/修改大纲**：编辑 `outline_suggested.yaml`，调整小节结构

5. **生成草稿**：

   ```powershell
   # 第二步：生成章节草稿
   python -m aiwrite.cli generate-draft --input outline_confirmed.yaml --output draft_paper.yaml
   ```

6. **确认/修改草稿**：查看各章节内容，可局部重生成

7. **生成最终版本**：

   ```powershell
   # 第三步：润色并输出 LaTeX + Word
   python -m aiwrite.cli finalize --input draft_paper.yaml --output-tex paper.tex --output-docx paper.docx
   ```

---

## 9. 技术栈与项目结构（规划）

**语言与框架**（建议）：
- 后端语言：Python 3.10+
- 包管理与构建：`poetry` 或 `pip + requirements.txt`
- LLM 调用：基于 HTTP 客户端（如 `httpx`/`requests`），封装为 `LLMProvider`
- 配置管理：`pydantic` / `dataclasses` + `PyYAML`
- LaTeX 组装：字符串模板 + Jinja2（可选）
- Word 导出：`pandoc`（CLI 方式封装）

**预期项目结构（草案）**：

```bash
AIWrite/
  ├─ aiwrite/
  │   ├─ __init__.py
  │   ├─ config/            # 全局与 LLM/流水线配置解析
  │   ├─ models/            # Paper / Section / Pipeline 数据模型
  │   ├─ llm/               # LLMProvider 抽象与具体实现
  │   │   ├─ base.py        # LLMProvider 基类
  │   │   ├─ doubao.py      # 豆包思考模型
  │   │   ├─ deepseek.py    # DeepSeek 写作模型
  │   │   └─ kimi.py        # Kimi 写作模型
  │   ├─ pipeline/          # PipelineStep 实现与 orchestrator
  │   ├─ prompts/           # Prompt 模板管理
  │   ├─ render/            # LaTeX 拼装与 Word 导出
  │   └─ cli.py             # 命令行入口
  ├─ examples/
  │   └─ outline_input.yaml
  ├─ docs/
  │   ├─ prompt_templates.md
  │   └─ llm_config.md
  ├─ tests/
  ├─ README.md
  ├─ pyproject.toml / requirements.txt
  └─ .env.example
```

`.env.example` 会给出所有关键环境变量示例，方便快速上手。

---

## 10. 阶段性里程碑

1. **阶段 1：文档与原型设计（当前阶段）**
   - 明确整体需求和架构抽象（LLMProvider / PipelineStep / Paper & Section）
   - 设计 `outline.yaml` 结构与 Prompt 模板
   - 搭建基础项目骨架与依赖管理

2. **阶段 2：MVP CLI + 多模型接入**
   - 实现：配置解析 + DoubaoProvider（思考）+ DeepSeekProvider/KimiProvider（写作）
   - 实现基础流水线（大纲建议、章节草稿生成、LaTeX 组装）
   - 能从示例 `outline_input.yaml` 一键生成 `paper.tex`

3. **阶段 3：LaTeX 与 Word 支持完善**
   - 增加 Word 导出步骤（调用 `pandoc`）
   - 调整 LaTeX 模板，使生成的 Word 更符合常见论文格式要求
   - 增加基础一致性检查（标题层级、空章节检测等）

4. **阶段 4：写作质量与控制能力提升**
   - 优化 Prompt 模板，减少"胡编乱造"
   - 增加章节间衔接优化、自动摘要生成等
   - 为未来的检索增强、引用管理等留出扩展点

5. **阶段 5：交互增强与插件化**
   - 提供简单 Web UI 或桌面界面
   - 插件化：文献检索、引用工具、翻译模块等

---

## 11. 本 README 的定位

本 README 旨在：

- 为开发者提供清晰的架构蓝图和概念抽象
- 为使用者展示一个从 `outline.yaml` 到 LaTeX/Word 论文的完整自动化流程
- 为后续学术写作（记录该系统本身的论文）提供素材和结构参考

后续可以在此基础上拆分出更细的文档（例如 `docs/` 目录），但本 README 已经可以作为项目说明书的主体雏形。
