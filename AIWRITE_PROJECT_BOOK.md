# AIWrite 项目书

## 1. 项目概述
- 定位：基于大语言模型的“题目/大纲 ➜ 完整论文”自动化写作系统，覆盖 CLI 与 Web 双形态。
- 用户：需快速产出学术论文或报告的学生、工程师、科研团队。
- 价值：自动生成大纲、并行产出章节草稿、识别图表并嵌入、自动摘要与导出 Word/LaTeX，显著缩短从选题到定稿的周期。

## 2. 目标与范围
- 主要目标：将论文生成时长从 6–12 分钟降至 1–2 分钟（并行多 Worker），输出可编辑的 docx/tex。
- 范围内：论文大纲/草稿生成、图表识别与插入、Mermaid 图表渲染、实时进度通知、导出、基本任务管理。
- 范围外（当前未覆盖）：正式期刊模板适配、参考文献自动抓取与格式化、AI 审稿/查重、用户权限/团队协作。

## 3. 功能模块
- 论文管理：创建、查询、更新、删除；上传图片/表格并关联到论文。
- AI 生成：
  - 大纲生成（step=outline）：精简 Prompt，关闭深度思考，加速响应。
  - 章节草稿生成（step=draft）：支持单任务与“章节级” Celery 并行分发。
  - 内容润色（step=refine，按需）。
  - 自动摘要：章节完成后汇总全文生成 200–300 字摘要。
- 图表能力：
  - 图片识别：并行调用视觉模型生成学术描述并匹配章节。
  - Mermaid 渲染：支持流程图、时序图、ER 图、类图、思维导图、饼图（Playwright 渲染）。
- 导出：Web 端当前支持 docx（`POST /api/papers/{id}/export`）；CLI 端支持 LaTeX/Word。
- 任务与进度：Celery 任务队列，WebSocket `/ws/papers/{paper_id}` 推送实时进度与耗时预估。
- CLI 工具：`aiwrite init/suggest-outline/generate-draft/finalize/status/analyze-images` 覆盖从初始化到导出全链路。

## 4. 核心流程
1) 新建论文（上传图片/表格）→ 存储到 `uploads/<paper_id>/`，写入数据库记录（Paper/Figure/Table）。
2) 生成大纲：`POST /api/papers/{id}/generate?step=outline` → Celery 触发 `generate_outline_task` → 更新 Paper/Section。
3) 生成章节草稿：
   - 串行/批量：`step=draft` 触发 `generate_draft_task`。
   - 并行模式：`POST /api/papers/{id}/generate/draft-parallel` 触发 `generate_draft_parallel_task`，按章节拆分到多 Worker。
4) 自动摘要：全部章节生成后（`paper_tasks.py`）收集正文上下文，调用 `llm_service.generate_abstract` 更新 Paper.abstract。
5) 导出：Web 端 `POST /api/papers/{id}/export`（docx）；CLI `aiwrite finalize` 支持 LaTeX/Word。
6) 实时体验：任务开始即推送“预计耗时”；执行中推送已用/剩余时间、进度、错误说明。

## 5. 技术架构
- 后端（`web/backend`）
  - 框架：FastAPI（API）、SQLAlchemy 2.0 Async（ORM）、SQLite（默认存储）。
  - 异步任务：Celery，支持多 Worker 并行；核心任务集中在 `app/tasks/paper_tasks.py`。
  - 业务层：`services` 封装论文/章节/图表/任务逻辑；`api/papers.py` 提供 REST。
  - LLM 适配：`services/llm_service.py` 统一封装思考/写作/视觉模型；支持 Doubao、DeepSeek。
  - 导出：复用 CLI 的 aiwrite 渲染器（LaTeX/Word），Web 当前使用 `aiwrite.render.word.WordExporter` 输出 docx。
  - 进度通知：WebSocket 通道推送 Celery 任务状态与时间预估。
- 前端（`web/frontend`）
  - 技术栈：Vue 3 + Vite + TypeScript + Pinia + Element Plus + Axios。
  - 能力：论文 CRUD、文件上传、生成入口（大纲/草稿/并行草稿）、任务进度展示、导出下载。
- CLI 内核（`aiwrite/`）
  - 管道：`pipeline/` 组织 init ➜ outline ➜ draft ➜ refine ➜ export 全流程。
  - Prompt：`prompts/` 管理大纲、写作等提示词模板。
  - 渲染：`render/` 负责 LaTeX/Word；`diagram/mermaid` 用 Playwright 渲染图表。
  - 数据模型：`models/` 描述 Paper/Section/Figure/Table；`config/` 读取 `.env`。

## 6. 数据与存储
- 核心实体：Paper（标题、主题、关键字、摘要、目标字数、状态）、Section（层级、标题、编号、draft）、Figure/Table（路径、描述、状态）、Task（步骤、celery_task_id、状态、耗时）。
- 文件：用户上传图片/表格存放于 `web/backend/uploads/<paper_id>/`；导出文档按请求临时生成。
- 配置：`.env` 需提供思考/写作模型的 API Key、Base URL、模型名等（示例见根目录 `.env.example` 与 `web/.env.example`）。

## 7. 主要接口（Web）
- 论文：`POST /api/papers` 创建；`GET /api/papers` 列表；`GET/PATCH/DELETE /api/papers/{id}` 详情/更新/删除。
- 生成：`POST /api/papers/{id}/generate`（step=outline|draft|refine，可选 section_ids）；`POST /api/papers/{id}/generate/draft-parallel` 并行草稿。
- 导出：`POST /api/papers/{id}/export`（format=word）。
- WebSocket：`/api/ws/papers/{paper_id}` 推送任务状态。

## 8. 部署与运行
- 开发模式：
  1) 后端：`uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
  2) 前端：`npm run dev`（`web/frontend`）
  3) Celery：`celery -A app.core.celery_app worker --loglevel=info --pool=solo`（或 `start-celery-multi.ps1 -WorkerCount 4` 开多 Worker）
- Docker：`web/docker-compose.yml` 提供前后端 + Celery + Nginx 编排（需在 `.env` 配置模型密钥）。
- 依赖：Python 3.11+、Node 18+、Playwright（Mermaid 渲染）、LLM/视觉模型访问凭证。

## 9. 性能与优化摘要
- 并行化：图片识别、图表生成使用 `asyncio.gather`；章节草稿拆分为多 Celery 任务，可线性扩展 Worker 数；图表也异步生成。
- Prompt 精简：大纲提示词大幅减 Token，禁用深度思考，提升 5× 响应速度。
- 进度体验：时间预估 + 已用时实时推送，降低等待焦虑。
- 自动摘要：章节完成后无人工干预生成，形成完整论文结构。
- 结果：单用户从 6–12 分钟缩短到 1–2 分钟；4 Worker 并发可支撑 4 用户同时 1–2 分钟出稿。

## 10. 里程碑与风险
- 已完成：大纲/草稿/并行草稿/摘要/导出/图表识别与渲染、前端进度显示、时间预估。
- 待关注：
  - 模型配额与失败兜底（需监控 API 失败重试策略）。
  - Mermaid 渲染在部分平台需确保 Playwright 依赖可用。
  - 导出格式扩展（Web 端当前仅 docx；LaTeX 由 CLI 负责）。
  - API 中存在重复定义的 `draft-parallel` 路由，后续可统一为一个实现。

