# AI 开发提示词（用于指导模型实现 AIWrite Web 重构版）

## 使用方式
将以下上下文直接提供给 AI 助手，让它据此编写/修改代码、接口和前后端实现。需要时可补充当前代码片段或错误日志，AI 应按约定输出可运行的代码与说明。

## 项目目标
- 交付一套 Web 控制面板，复用现有 `aiwrite` 核心库能力（流水线、Prompt、渲染、LLM 适配），提供从题目/大纲到全文草稿/摘要/导出的端到端体验。
- 核心指标：单用户 1–2 分钟生成全文；支持多 Worker 并行保持吞吐；接口幂等、可观测、可横向扩展。

## 技术栈约定
- 后端：FastAPI + SQLAlchemy Async + Celery + Redis（broker/result），DB 可选 SQLite/PG。
- 前端：Vue3 + Vite + TypeScript + Pinia + Element Plus。
- 核心库复用：`aiwrite/pipeline`、`aiwrite/models`、`aiwrite/llm`、`aiwrite/prompts`、`aiwrite/render`、`aiwrite/diagram`。
- 渲染：`render/word.py`、`render/latex.py`、`diagram/mermaid.py`（需 Playwright/Chromium）。
- 环境：Python 3.11+，Node 18+。

## 必要的业务与流程
1) 创建论文：上传图片/表格 → 保存到 `uploads/<paper_id>/` → 入库（Paper/Figure/Table）。
2) 生成大纲：`POST /api/papers/{id}/generate?step=outline` → Celery 调用 `OutlineSuggestStep` → 更新 sections。
3) 章节草稿：
   - 串行：`step=draft` → `ChapterDraftStep`。
   - 并行：`POST /api/papers/{id}/generate/draft-parallel` → 为每个章节创建 Celery 任务，支持多 Worker。
4) 可选：`SectionDraftStep` / `SectionRefineStep` 细粒度生成/润色。
5) 摘要：章节完成后调用 `AbstractGenerateStep`，写回 Paper.abstract。
6) 图像分析：`ImageAnalyzeStep` 批量/单张识别，补全 Figure.description。
7) 导出：`POST /api/papers/{id}/export` 生成 docx/tex，前端触发下载。
8) 进度：WebSocket `/api/ws/papers/{paper_id}` 推送状态、预计/已用时、错误。

## 数据模型（持久化）
- Paper：id/title/topic/keywords/abstract/target_word_count/status。
- Section：id/paper_id/number/title/level/target_words/draft/final/notes。
- Figure：id/paper_id/section_id/caption/path/description/type/status。
- Table：id/paper_id/section_id/caption/path/description/status。
- Task：id/paper_id/step/status/progress/celery_task_id/elapsed/payload_size/err_msg。

## API 约定（最小集）
- 论文：`POST /api/papers`，`GET /api/papers`，`GET/PATCH/DELETE /api/papers/{id}`。
- 生成：`POST /api/papers/{id}/generate`（step=outline|draft|refine，可选 section_ids）；`POST /api/papers/{id}/generate/draft-parallel`。
- 图像/表格：`POST /api/papers/{id}/images` 上传；`POST /api/papers/{id}/analyze-images`。
- 导出：`POST /api/papers/{id}/export`（format=word|latex）。
- WebSocket：`/api/ws/papers/{paper_id}`。

## 核心代码复用点
- 流水线：`pipeline/executor.py`、`pipeline/steps.py`、`pipeline/init_step.py`。
- 模型：`models/paper.py`、`models/pipeline.py`。
- LLM：`llm/provider.py` 与具体实现（doubao/deepseek 等）；通过 `.env` 配置 BASE_URL/KEY/模型名。
- Prompt：`prompts/` 模板（大纲/章节/润色/摘要/图像/mermaid）。
- 导出/图表：`render/word.py`、`render/latex.py`、`diagram/mermaid.py`。

## 并行与性能要求
- 章节级并行：Celery 拆分，每章节独立任务；Worker 数可调。
- 图像分析：优先批处理，失败回退单张；内部可用 `asyncio.gather`。
- Prompt 精简：沿用核心 Prompt，禁用深度思考参数以降低 token。
- 幂等与重试：task key = paper_id + step + section_id；LLM 调用需超时和重试策略。

## 交付物要求
- 可运行的后端 API、前端页面、Celery 任务。
- 代码需包含必要的内联说明（仅对复杂逻辑），避免冗长注释。
- 提供本地运行指令（uvicorn、npm run dev、celery 命令）与 docker-compose 部署说明（如适用）。
- 输出变更的文件路径及关键修改点摘要。

## 回答格式要求
- 用中文回答；先给实现思路/改动列表，再给关键代码片段或文件路径。
- 不必粘贴长文件全文，只给关键段落或说明如何修改。
- 若需更多上下文，先明确询问缺失信息（如当前文件结构、报错日志）。
