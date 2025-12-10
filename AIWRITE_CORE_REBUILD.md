# AIWrite Web 重构版项目书（基于核心库复刻）

## 1. 项目目标
- 交付一套 Web 控制面板：从题目/大纲到全文草稿/摘要/导出，实时可视化进度与耗时。
- 复用 aiwrite 核心能力（流水线、Prompt、渲染、LLM 适配），只替换外层 Web 架构与持久化。
- 关键指标：单用户 1–2 分钟生成全文，4 个并发用户保持同级性能；接口幂等、可观测、可横向扩展。

## 2. 系统架构分层
- 核心引擎（复用）
  - `aiwrite/pipeline`：步骤协议与执行器。
  - `aiwrite/models`：Paper/Section/Figure/Table/Task 数据结构。
  - `aiwrite/llm`：思考/写作/视觉模型适配器，`LLMOptions` 控制 max_tokens/temperature/timeout。
  - `aiwrite/prompts`：大纲、章节草稿、润色、摘要、图像分析、Mermaid 生成模板。
  - `aiwrite/render` + `aiwrite/diagram`：LaTeX/Word 导出、Mermaid 渲染。
- Web 后端
  - FastAPI + SQLAlchemy Async + SQLite/PostgreSQL。
  - Celery 任务队列（多 Worker 并行章节/图像任务），Redis 作为 broker/result。
  - WebSocket 推送任务进度/耗时预估。
  - API 仅做“编排 + 持久化”，调用核心引擎完成生成。
- Web 前端
  - Vue3 + Vite + TypeScript + Pinia + Element Plus。
  - 功能：论文 CRUD、文件上传、生成入口（大纲/草稿/并行草稿/摘要）、进度面板、错误提示、导出下载。

## 3. 核心代码复刻要点（来自 aiwrite）
- 流水线执行：`pipeline/executor.py` 保留 `PipelineStep` 协议和用户确认机制；在 Web 中由 Celery 任务调用。
- 步骤实现：`pipeline/steps.py` 的大纲/章节/小节/摘要/图像分析逻辑按需拆分为可独立 Celery 任务，支持并行。
- 初始化器：`pipeline/init_step.py` 用于“文本大纲 + 本地图像/表格 → YAML 配置”可直接复用，或改为 API 版本。
- 模型层：`llm/provider.py` 及具体实现（doubao/deepseek 等）直接调用；通过环境变量配置。
- Prompt：`prompts/` 模板直接沿用，确保输出格式与核心引擎一致。
- 导出：`render/word.py`、`render/latex.py`、`diagram/mermaid.py` 直接复用，封装成导出服务。

## 4. 数据模型（Web 持久化）
- Paper：id/title/topic/keywords/abstract/target_word_count/status.
- Section：id/paper_id/number/title/level/target_words/draft/final/notes.
- Figure：id/paper_id/section_id/caption/path/description/type/status.
- Table：id/paper_id/section_id/caption/path/description/status.
- Task：id/paper_id/step(status/progress/celery_task_id/elapsed/payload_size/err_msg).

## 5. 关键流程（控制面板视角）
1) 创建论文：上传图片/表格 → 入库并保存到 `uploads/<paper_id>/`。
2) 触发大纲生成：API `POST /api/papers/{id}/generate?step=outline` → Celery 调用 `OutlineSuggestStep` → 更新 sections。
3) 触发章节草稿：
   - 串行模式：`step=draft` 调用 `ChapterDraftStep`。
   - 并行模式：`POST /api/papers/{id}/generate/draft-parallel`，为每个章节分发 Celery 任务（可开多 Worker）。
4) 润色/小节生成（可选）：`SectionDraftStep` / `SectionRefineStep`。
5) 摘要生成：全部章节完成后调用 `AbstractGenerateStep`，写回 Paper.abstract。
6) 导出：`POST /api/papers/{id}/export` 生成 docx/tex，前端触发下载。
7) 进度通知：任务开始推送预计耗时；执行中推送进度、已用时、剩余时、错误。

## 6. API 设计（核心）
- 论文：`POST /api/papers`，`GET /api/papers`，`GET/PATCH/DELETE /api/papers/{id}`。
- 生成：`POST /api/papers/{id}/generate`（step=outline|draft|refine，可选 section_ids）；`POST /api/papers/{id}/generate/draft-parallel`。
- 图像/表格：`POST /api/papers/{id}/images` 上传；`POST /api/papers/{id}/analyze-images` 调用 `ImageAnalyzeStep`。
- 导出：`POST /api/papers/{id}/export`（format=word|latex）。
- WebSocket：`/api/ws/papers/{paper_id}` 推送 task 状态。

## 7. 性能与并行策略
- 章节级并行：Celery 拆分章节任务；WorkerCount 可调（脚本示例 `start-celery-multi.ps1 -WorkerCount 4`）。
- 图像分析批处理：优先批量调用，失败回退单张；并行 `asyncio.gather`。
- Prompt 精简：沿用核心 Prompt，禁用“深度思考”参数，减少 token。
- 缓存与重试：LLM 调用增加超时与重试；任务层记录幂等 key（paper_id + step + section_id）。

## 8. 开发/部署
- 开发
  - 后端：`uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
  - 前端：`npm run dev`（Vite）
  - Celery：`celery -A app.core.celery_app worker --loglevel=info --pool=solo` 或多 Worker 脚本。
  - 环境：`.env` 配置思考/写作/视觉模型的 BASE_URL/KEY/模型名。
- 部署
  - docker-compose：Web（FastAPI）、Frontend（Vite 构建产物）、Celery、Redis、Nginx。
  - 资源：Python 3.11+，Node 18+，Chromium/Playwright（用于 Mermaid 渲染）。

## 9. 里程碑与待办
- M1：API 骨架 + 数据模型 + 上传/CRUD + WebSocket。
- M2：接入核心引擎步骤（大纲/章节/摘要/导出）并打通 Celery。
- M3：前端控制面板（生成入口、进度、错误、下载）。
- M4：性能调优（并行参数、缓存、重试、日志观测）。
- 待办与风险
  - 路由去重：确保并行 draft 仅保留单一端点实现。
  - Playwright 依赖在服务器上的可用性。
  - 模型配额与降级策略（重试/切换模型）。
  - 状态持久化一致性：长任务的幂等与超时恢复。
