# 论文 AI 编辑器项目启动文档（第一性原理版）

> 本文是该项目在**全新目录、零复用旧代码**前提下的开工 / 立项设计文档。  
> 在你给出的 Web 重建方案基础上整理、抽象并用“第一性原理”重写为一份可以指导实际开发的总蓝图。:contentReference[oaicite:0]{index=0}  
> 同时吸收了之前对论文 AI 编辑器形态的讨论与拆解。:contentReference[oaicite:1]{index=1}  

---

## 1. 背景与本质问题

### 1.1 论文写作本质

从第一性来看，论文写作是一个「**知识结构化 + 论证 + 规范表达**」的循环过程，本质可以分解为三件事：

1. **构建结构**：明确研究问题、搭建逻辑框架（大纲、章节、论点结构）  
2. **填充内容**：根据结构写出有逻辑、有证据的文本（章节草稿、图表说明）  
3. **符合规范**：符合学术风格和格式（语法、用词、引用、导出格式）

AI 在这里扮演的是一个**“文本状态变换器”**的角色：

> 当前论文状态 `S` + 用户意图 `I`  
> 通过 AI 引擎 `E` → 生成新的论文状态 `S'`

几乎所有能力（大纲生成、章节撰写、润色降重、摘要、图像描述）都可以抽象为：
  
> `S' = f(S, I, 约束条件, LLM)`

因此系统的关键，不是“堆功能”，而是：

- 用**良好的领域模型**表达论文状态
- 用**清晰的操作模型**表达用户意图
- 用**统一的 AI 引擎层**把两者映射成新的状态
- 用**任务/日志/版本机制**保证可观测、可回退、可扩展

---

## 2. 项目目标（MVP 阶段）

### 2.1 功能目标

构建一个面向论文场景的 **AI 驱动写作工作台**，用户可以：

1. 创建、管理论文项目（Paper）
2. 基于主题 / 关键词自动生成**结构化大纲**
3. 按章节触发 AI 生成**并行草稿**（支持多个章节并行生成）
4. 对小节进行**润色 / 细化 / 降重 / 扩写**
5. 生成全文**摘要**
6. 支持**图片 / 表格上传**，并由 AI 生成描述或解析为 Markdown
7. 导出为 `docx` / `tex`，包含图表占位与基本排版
8. 所有长耗时操作通过 Task 记录、支持进度查询与 WebSocket 推送

### 2.2 性能与约束

- 单论文从「无内容」到「有大纲 + 各章节草稿 + 摘要」：  
  **单用户端到端 1–2 分钟可完成**（视模型性能而定）:contentReference[oaicite:2]{index=2}  
- 支持多用户并发（通过 Worker 横向扩展）
- 模型 Key / Base URL / 模型名通过环境变量配置，可替换上游供应商

### 2.3 成功指标（可量化）

- 用户创建论文 → 在 30 秒内看到大纲
- 5 个一级章节 + 每章若干小节 → 在 1–2 分钟内生成完草稿和摘要
- 任务成功率 ≥ 95%
- 前端任务状态更新延迟 ≤ 2 秒

---

## 3. 范围与非目标

### 3.1 本阶段重点（MVP）

- 单人使用的论文 AI 编辑器（不做团队协作）
- 以 **结构化生成 + 并行草稿 + 润色/摘要 + 导出** 为主线
- 基础文献能力：可选做简单的表格解析、图像描述（非学术检索）

### 3.2 明确暂不做

- 完整的文献检索与引文管理系统（Zotero/EndNote 级别）
- 针对具体学校/期刊的复杂 LaTeX 模板
- 实时共同编辑、多用户协作、权限体系
- 真正意义上的查重服务（可预留“降重改写”的接口）

---

## 4. 核心理念与系统抽象

### 4.1 状态 / 意图 / 引擎

- **状态（State, S）**  
  - 当前的 Paper、Section 树、Figure/Table 元数据、Task 状态
- **意图（Intent, I）**  
  - “生成大纲 / 写第 2 章草稿 / 润色某段 / 扩写这一节”等
- **引擎（Engine, E）**  
  - 统一的 LLM / Vision 客户端和 Router，负责：选择模型、调用、重试、输出解析

系统以「**论文状态 S**」为唯一真相来源，所有 AI 功能都被视作对该状态的“变换”，每一次变换通过 Task + Operation（可选）记录，以支持调试和回滚。

### 4.2 核心领域对象

- Paper：论文项目
- Section：章节 / 小节（树结构）
- Figure：图片资源及描述
- Table：表格资源及解析内容
- Task：长耗时任务（生成大纲、章节草稿、图像描述、导出…）
- Event（可选）：为 WebSocket 推送设计的事件流

---

## 5. 整体架构设计

### 5.1 分层架构（逻辑）

```text
[ 前端 SPA (Vue/React) ]
      |
      | HTTP / WebSocket
      v
[ API 层 (FastAPI 路由) ]
      |
      v
[ 应用服务层 (Services / Use Cases) ]
      |
      +--> [ LLM / Vision Router ]
      |
      +--> [ 导出服务 Export ]
      |
      v
[ 领域模型层 (Paper/Section/Figure/Table/Task) ]
      |
      v
[ 持久化层 (PostgreSQL/SQLite + ORM) ]

[ 异步任务系统 (Celery + Redis) ]
      ^
      | 由 API 或内部服务投递 Task
```

### 5.2 技术选型建议

技术可换，但架构角色不应该变。

后端：

- FastAPI（HTTP + WebSocket）
- SQLAlchemy Async + PostgreSQL（可用 SQLite 做开发环境）
- Celery + Redis（任务队列与结果存储）

前端：

- Vue3 + Vite + TypeScript + Pinia + Element Plus（或 React + Zustand/Redux）

模型：

- 任意 OpenAI 兼容 LLM / Vision API，通过 LLMClient / VisionClient 封装

---

## 6. 数据模型设计（逻辑模型）

这部分先是“领域逻辑结构”，落地时再映射为 ORM 表。

### 6.1 Paper（论文）

```
Paper
- id: string
- title: string
- topic: string
- keywords: string[]
- abstract: text
- target_words: int
- status: enum("draft", "generating", "completed", "error")
- created_at: datetime
- updated_at: datetime
```

### 6.2 Section（章节 / 小节）

采用单表 + 树结构（parent_id + level + order）表示所有层级：

```
Section
- id: string
- paper_id: string
- parent_id: string | null
- level: int        # 1=一级标题; 2=二级; 3=三级...
- number: string    # 如 "1", "1.2", "2.1.3"
- title: string
- target_words: int
- draft: text       # AI 初稿
- final: text       # 用户编辑后的版本
- notes: text       # 备注
- created_at: datetime
- updated_at: datetime
```

### 6.3 Figure（图片）

```
Figure
- id: string
- paper_id: string
- section_id: string | null
- path: string         # 文件存储路径
- caption: string
- description: text    # AI 生成的描述
- type: enum("plot", "diagram", "photo", "other")
- status: enum("pending", "processing", "done", "failed")
- created_at: datetime
- updated_at: datetime
```

### 6.4 Table（表格）

```
Table
- id: string
- paper_id: string
- section_id: string | null
- path: string          # 原始文件/上传路径
- caption: string
- description: text
- content_md: text      # 解析成 Markdown 的表格
- status: enum("pending", "processing", "done", "failed")
- created_at: datetime
- updated_at: datetime
```

### 6.5 Task（任务）

对应所有需要异步执行的操作（大纲生成、章节草稿、图像描述、导出…）

```
Task
- id: string
- paper_id: string
- step: enum("outline", "draft", "refine", "abstract", "image_analyze", "table_parse", "export")
- section_id: string | null
- status: enum("queued", "running", "success", "failed", "canceled")
- progress: int           # 0-100
- eta_seconds: int | null
- elapsed_seconds: int | null
- celery_task_id: string | null
- message: text           # 错误信息或进度说明
- created_at: datetime
- updated_at: datetime
```

### 6.6 Event（可选，用于 WebSocket）

```
Event
- id: string
- task_id: string
- type: string           # "status_change" | "progress" | "error" | ...
- payload: json
- created_at: datetime
```

---

## 7. 关键业务流程（从“状态变换”视角）

### 7.1 论文创建流程

目标：从无到有创建 Paper，用户有一个“容器”来承载后续的一切生成。

步骤：

- 前端：用户输入标题、主题、关键词、目标字数
- 后端：
  - 创建 Paper 记录，初始化 status="draft"
  - 不强制生成初始 Section（可以在大纲生成后统一创建）
  - 返回 paper_id 给前端

### 7.2 大纲生成流程（step = outline）

本质：主题 + 关键词 + 学科信息 → 论文的结构（多层章节树）

步骤：

1. API `POST /api/papers/{id}/generate?step=outline`
2. 创建 Task（step="outline"）
3. 返回 task_id
4. Celery Worker：
   - 加载 Paper 基础信息
   - 构造 Prompt：
     - 说明论文类型（研究型 / 综述 / 实验 / 方法）
     - 约束输出为 JSON/YAML：包含 title, level, target_words, notes
   - 调用 LLM（思考型模型）
   - 解析结构化结果 → 转换为 Section 实体列表
   - 若已有 Section，大纲模式下可以：
     - 替换全部
     - 或支持“仅生成建议大纲，不立即写入”（后续可扩展）
   - 批量写入 Section 表
   - 更新 Paper.status → "draft" 或 "outline_ready"
   - 更新 Task.status → "success"、progress=100
5. WebSocket：
   - 推送“任务创建 → 进行中 → 完成”事件到前端

### 7.3 章节草稿生成（step = draft，支持并行）

本质：按章节将大纲映射为正文草稿（可以并行）

步骤：

1. API `POST /api/papers/{id}/generate?step=draft`
2. 选取需要生成的 Section（通常是 level=1，或者用户勾选的集合）
3. 根据章节数量创建一个总 Task 或多个子 Task：
   - 简化：一个 Paper-level Task，内部再拆章节级子状态
   - 为每个 Section 投递一个 Celery 子任务
4. Celery Worker（每个 Section 一个任务）：
   - 读取 Paper、Section 信息
   - 构建 Prompt：
     - 包含：章节标题、父章节 / 全文概览简要说明、目标字数、风格约束
     - 要求输出纯 Markdown / LaTeX 片段
   - 调用 LLM（写作型模型）
   - 将结果写入 Section.draft
   - 更新 Task.progress（例如：已完成章节数 / 总章节数）
5. 前端：
   - 通过 WebSocket 实时看到：
     - 已完成章节数
     - 估算剩余时间
   - 草稿生成后，用户可以进入具体章节进行编辑和润色

### 7.4 小节润色 / 细化（step = refine）

本质：对小节文本进行局部状态变换：更学术 / 更流畅 / 更详细 / 更简洁。

步骤：

1. 用户在前端选中某一小节（level=2，或选中一段文本）
2. API `POST /api/papers/{id}/generate?step=refine`，携带：
   - section_id
   - 模式：academic | rewrite | expand | compress
   - 目标字数（可选）
3. Worker：
   - 读取 Section.draft 或 final 中的目标片段
   - 构造 Prompt：
     - 明确「保留含义、保持术语、增强学术性」等要求
   - 调用 LLM → 返回新文本
   - 依据业务设计：
     - 覆盖原 draft/final
     - 或写入一个新的“版本记录”（高级阶段）
   - 更新 Task / 推送事件

### 7.5 摘要生成（step = abstract）

本质：将各章节草稿压缩成一个较短的摘要文本。

步骤：

1. API `POST /api/papers/{id}/generate?step=abstract`
2. Worker：
   - 抽取每个 Section 的前若干字 / 段落（控制总 token）
   - 构建 Prompt：
     - 指定摘要长度（如 200–300 字）
     - 指定语言、风格
   - 调用 LLM（思考型模型）
   - 将结果写入 Paper.abstract
   - 更新 Task 状态与 Paper.status

### 7.6 图像描述 / 表格解析（step = image_analyze / table_parse）

图像描述：

- 用户上传图片 → 生成 Figure 记录，状态 pending
- API `POST /api/papers/{id}/analyze-images`
- 可对未处理的图片批量创建任务

Worker：

- 读取图片 bytes / URL
- 调用 Vision 模型生成描述、关键词
- 写入 Figure.description，更新状态为 done

表格解析：

- 用户上传 Excel / CSV / 表格截图（截图暂简化为手动输入）

Worker：

- 对结构化表格（如 CSV） → 解析成 Markdown 表格 → 存到 Table.content_md
- 对复杂来源可以暂时降级为“描述型文本”

### 7.7 导出（step = export）

本质：将当前的 Paper/Section/Figure/Table 状态映射为一个交付文件（docx/tex）。

步骤：

1. API `POST /api/papers/{id}/export?format=word|latex`
2. 创建 Task（step="export"）
3. Worker：
   - 加载所有 Sections（按 number 排序）
   - 选取 final 优先，否则 draft
   - 按模板渲染：
     - docx：使用模板填充标题、摘要、正文、图表占位
     - tex：生成基本 article 模板，插入章节、图表引用
   - 将结果保存为临时文件，返回文件路径 / 下载链接
4. 前端：
   - 轮询或通过任务完成事件获取下载链接

---

## 8. 模型调用与 Prompt 策略

### 8.1 LLMClient / VisionClient 抽象

```python
class LLMClient:
    async def invoke(self, prompt: str, *, max_tokens: int, temperature: float, timeout: float) -> str:
        ...

class VisionClient:
    async def analyze(self, image_bytes: bytes, *, timeout: float) -> str:
        ...
```

### 8.2 Router（任务类型 → 模型 & 参数）

```
outline   → 思考型模型（temperature 适中，max_tokens 中等）
draft     → 写作型模型（max_tokens 大）
refine    → 写作型模型（max_tokens 适中，temperature 偏低）
abstract  → 思考型模型（max_tokens 小）
image_*   → Vision 模型
```

### 8.3 超时与重试

LLM 调用需设置：

- 超时（如 30–60 秒）
- 重试策略（指数退避 + 最大次数）
- 根据 HTTP 错误码分类：
  - 429 / 限流 → 可重试
  - 5xx / 网络问题 → 可重试
  - 4xx / 参数错误 → 不重试，直接标记为 failed

### 8.4 输出清洗与解析

对结构化输出（JSON/YAML）：

- 使用严格 JSON 模板约束
- 若解析失败，可做简单修复（去除前后非 JSON 部分）

对 Markdown 输出：

- 去掉 model 自带的“解释说明”
- 只保留正文

---

## 9. 任务系统、进度与幂等

### 9.1 Task 生命周期

```
queued → running → { success | failed | canceled }
```

- queued：API 创建 Task，尚未被 Worker 领取
- running：Worker 启动任务，记录 start_time
- success：任务成功完成，记录 elapsed
- failed：记录错误原因（message）
- canceled：用户主动取消或系统超时取消

### 9.2 幂等设计

每类任务设计幂等 Key，比如：

- outline: paper_id + step="outline"
- draft: paper_id + step="draft" + section_id

API 收到重复请求时：

- 若已有进行中的 Task → 返回原 Task
- 若已有成功的 Task 且结果存在 → 可直接复用或提示用户

### 9.3 WebSocket 推送

通道：`/api/ws/papers/{paper_id}`

订阅事件：

- Task 创建 / 状态变更 / 进度更新 / 错误

Worker 在关键节点触发事件：

- queued → running → progress(x%) → success/failed

---

## 10. API 概览（高层）

细节可以在真正编码阶段用 OpenAPI/Pydantic 正式定义。

### 10.1 论文与资源

- `POST /api/papers`
- `GET /api/papers`
- `GET /api/papers/{id}`
- `PATCH /api/papers/{id}`
- `DELETE /api/papers/{id}`
- `POST /api/papers/{id}/images`
- `POST /api/papers/{id}/tables`

### 10.2 生成与任务

- `POST /api/papers/{id}/generate`
  - step=outline|draft|refine|abstract
  - 可选参数：section_ids，mode 等
- `POST /api/papers/{id}/analyze-images`
- `POST /api/papers/{id}/export?format=word|latex`
- `GET /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/cancel`

### 10.3 WebSocket

- `GET /api/ws/papers/{paper_id}`

---

## 11. 目录结构（新仓库规划）

```
paper-ai-editor/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI 路由 (paper/section/task/ai...)
│   │   ├── core/           # 配置、DB、Celery 实例
│   │   ├── models/         # ORM 模型 (Paper/Section/Figure/Table/Task/Event)
│   │   ├── schemas/        # Pydantic 模型
│   │   ├── services/       # 业务用例 (paper/outline/draft/refine/abstract/export)
│   │   ├── llm/            # LLMClient / VisionClient / Router
│   │   ├── prompts/        # Prompt 模板
│   │   ├── tasks/          # Celery 任务实现
│   │   ├── export/         # docx/tex 渲染实现
│   │   └── websocket/      # WebSocket / SSE 封装
│   └── tests/
└── frontend/
    ├── src/
    │   ├── api/            # Axios 封装
    │   ├── stores/         # Pinia 状态 (papers/tasks/ui)
    │   ├── components/     # 大纲树/编辑器/进度条/上传组件
    │   ├── views/          # 论文列表/论文详情/生成面板
    │   └── router/         # 路由
    ├── index.html
    └── vite.config.ts
```

---

## 12. 开发计划（里程碑）

### M1：最小垂直闭环（1–2 周）

后端：

- Paper / Section 模型 + SQLite
- `POST /api/papers` 创建论文
- 假数据大纲（不接 LLM），返回若干 Section

前端：

- 论文列表页 + 论文编辑页
- 展示大纲树，但内容为空

### M2：接入 LLM，大纲 → 章节草稿（2–3 周）

- 接入真实 LLMClient
- 实现 step=outline 与 step=draft 任务流（含 Celery）
- 前端可点击生成大纲、生成章节草稿并查看结果
- 初步 Task 列表 / 状态展示

### M3：润色 / 摘要 / 图像解析（2–3 周）

- 实现 step=refine / step=abstract / step=image_analyze / step=table_parse
- 前端支持选中文本 → 调用润色/扩写等模式
- WebSocket 推送任务进度

### M4：导出 / 性能调优 / 文档（2–3 周）

- 实现 docx / tex 导出
- 基于实际模型延迟优化章节并行度与任务拆分
- 完成部署脚本（docker-compose）
- 编写 README / 使用手册 / 运行指南

---

## 13. 风险与应对策略

### LLM 输出结构不稳定

- 风险：大纲 JSON / YAML 解析失败
- 对策：严格提示 + 解析前先做简单清洗 + 若失败回退“纯文本大纲”模式

### 模型延迟/限流

- 风险：任务超时、用户体验差
- 对策：任务超时重试、增加 ETA 提示、允许用户取消任务

### 长文 Token 超限

- 风险：摘要 / 润色时内容被截断
- 对策：对长文先分块摘要，采用“逐块→总摘要”的两层结构

### 前端状态与后端 Task 同步问题

- 风险：页面显示结果落后于真实状态
- 对策：WebSocket + 定时轮询兜底 + Task 状态统一由后端维护
