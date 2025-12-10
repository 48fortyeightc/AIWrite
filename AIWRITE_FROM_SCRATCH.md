# AIWrite Web 重建方案（零复用版，第一性原理）

## 1. 问题与目标
- 输入：论文题目/主题、关键字、目标字数，用户可上传图片/表格。
- 输出：结构化大纲、摘要，支持 docx/tex 导出与图表嵌入。
- 约束：端到端时延单用户 1–2 分钟；可水平扩展支撑多用户；界面实时显示进度、耗时、错误。

## 2. 功能需求
- 论文管理：创建/查询/更新/删除；上传图片/表格并与论文关联。
- 生成链路：
  1) 大纲生成（主题→章节/小节结构）。
  2) 章节草稿生成（按章节并行）。
  3) 小节润色/细化（可选）。
  4) 摘要生成（汇总全篇）。
  5) 图像描述（批量/单张）、表格解析（转 Markdown/文本）。
  6) 导出 docx/tex；可附带图表。
- 进度与预估：所有长任务需返回 task_id，支持状态查询与 WebSocket 推送；展示预计/已用时。
- 配置：模型 Key/Base URL/模型名等以环境变量管理；不同任务可选不同模型（思考/写作/视觉）。

## 3. 架构与分层
- 前端（/frontend）
  - 技术：Vue3 + Vite + TS + Pinia + Element Plus。
  - 页面：登录（如需）、论文列表、论文详情（大纲/章节/图片/表格）、生成面板、进度面板、导出面板。
  - 状态：论文数据、任务状态、WebSocket 推送、全局提示。
- 后端（/backend）
  - 技术：FastAPI + SQLAlchemy Async + PostgreSQL（或 SQLite 开发态）。
  - 异步任务：Celery + Redis（broker/result）；Worker 支持多进程。
  - API 层：REST + WebSocket；只做编排与持久化。
  - 领域层：纯 Python 逻辑，独立于框架，便于测试。
  - 服务层：LLM 调度（思考/写作/视觉）、Prompt 构建、任务编排、导出器。
  - 适配层：具体模型客户端（如 OpenAI/通用兼容接口、视觉模型接口）、存储适配（本地/对象存储）。
- 任务执行模型
  - 单点入口创建 Task 记录（paper_id + step + section_id 可选）。
  - Celery Worker 拉取任务，调用领域服务执行；结果回写 DB 并推送事件。
  - WebSocket 通过事件表/Redis 通道推送进度。

## 4. 关键数据模型（逻辑层）
- Paper：id/title/topic/keywords/abstract/target_words/status/created_at/updated_at。
- Section：id/paper_id/number/title/level/target_words/draft/final/notes。
- Figure：id/paper_id/section_id/caption/path/description/type/status。
- Table：id/paper_id/section_id/caption/path/description/status/content_md。
- Task：id/paper_id/step(status/progress/eta_seconds/elapsed_seconds/celery_task_id/message/section_id)。
- Event（可选）：task_id/type/payload/created_at，用于 WebSocket 推送。

## 5. 核心流程设计
- 大纲生成
  - 输入：Paper 元数据 + 关键词。
  - Prompt：约束输出为结构化 JSON/YAML，包含章节 id/标题/层级/目标字数/备注。
  - 逻辑：调用思考模型 → 解析 → 写入 Section（level=1/2）。
- 章节草稿（并行）
  - 输入：Paper + Section（level=1），可携带前文摘要作为上下文。
  - Prompt：限制推理过程，要求直接输出正文 Markdown/LaTeX 片段；控制 token 上限。
  - 执行：每章节一个 Celery 任务；完成后写回 draft，更新 Task 进度。
- 小节润色/细化（可选）
  - 输入：Section（level=2）+ 父章节摘要。
  - 逻辑：同上，生成或润色 draft。
- 摘要生成
  - 输入：已生成的章节草稿（截断长度）。
  - 输出：200–300 字摘要，写回 Paper.abstract。
- 图像处理
  - 批量描述：并行调用视觉模型，失败回退单张；写回 Figure.description。
  - 表格解析：Excel/CSV 读取转 Markdown 存储 content_md。
- 导出
  - docx：基于模板填充标题/摘要/章节/图表。
  - tex：模板渲染正文与图表；图表路径指向已下载/本地缓存。

## 6. 模型调用策略（从零实现）
- Client 抽象：`LLMClient.invoke(prompt, *, max_tokens, temperature, top_p, timeout)`，`VisionClient.analyze(image_bytes|url)`。
- Router：按任务类型选择模型（outline/abstract → thinking；draft/refine → writing；image → vision）。
- 超时与重试：指数退避，错误分类（限流/超时/不可恢复）。
- 输出清洗：去除推理碎片，解析 JSON/YAML/Markdown，必要时做正则兜底。

## 7. 任务与进度
- 创建任务：API 写 Task，状态 queued，估算 ETA（章节数*单次预估）。
- Worker 更新：running → progress（0-100）→ success/failed，记录 elapsed 和 message。
- WebSocket：订阅 paper_id 推送 Task 状态、ETA/elapsed、错误。
- 幂等：任务 key = paper_id + step + section_id；重复请求直接返回已有任务或复用结果。

## 8. API 设计（新实现）
- `POST /api/papers` 创建；`GET /api/papers` 列表；`GET/PATCH/DELETE /api/papers/{id}`。
- `POST /api/papers/{id}/images` 上传文件；`POST /api/papers/{id}/tables` 上传表格。
- `POST /api/papers/{id}/generate`（step=outline|draft|refine|abstract；可选 section_ids）。
- `POST /api/papers/{id}/generate/draft-parallel`（并行章节）。
- `POST /api/papers/{id}/analyze-images`。
- `POST /api/papers/{id}/export`（format=word|latex）。
- `GET /api/tasks/{id}` 查询；`POST /api/tasks/{id}/cancel` 取消。
- WebSocket：`/api/ws/papers/{paper_id}` 监听任务事件。

## 9. 目录规划（新仓库）
```
backend/
  app/
    api/            # FastAPI 路由
    core/           # 配置、DB 会话、Celery 实例
    models/         # ORM 定义（Paper/Section/Figure/Table/Task/Event）
    schemas/        # Pydantic 模型
    services/       # 业务：paper/section/task/figure/table
    llm/            # LLM/Vision 客户端 + router
    prompts/        # Prompt 模板
    tasks/          # Celery 任务实现（outline/draft/refine/abstract/image/export）
    export/         # docx/tex 渲染
    websocket/      # 推送封装
  tests/
frontend/
  src/
    api/            # axios 封装
    stores/         # pinia 状态
    components/     # 进度条、任务卡、上传组件
    views/          # 列表、详情、生成面板
    router/
  vite.config.ts
docker-compose.yml
Dockerfile.backend
Dockerfile.frontend
```

## 10. 核心代码逻辑（概要示例）
- LLM Router
  - 输入：task_type（outline/draft/refine/abstract/image），返回对应 client 与默认参数。
  - 责任：超时/重试、错误分类、metrics 打点。
- Celery 任务（例：章节草稿）
  - 取 Section → 构建 Prompt → 调用 writing client → 清洗/保存 draft → 更新 Task 进度与 Paper 状态 → 推送事件。
- WebSocket 推送
  - Worker 在关键阶段发送事件（queued/running/progress/success/fail）。
  - API 层提供 SSE/WebSocket 订阅 paper_id。
- 导出服务
  - 聚合 Paper/Section/Figure/Table 内容 → 渲染模板 → 返回文件流；清理临时文件。

## 11. 性能与可靠性
- 并行：章节级任务分发；图像批量 + gather；Worker 数可调。
- 预估：按章节数与平均耗时估算 ETA；实时更新 elapsed。
- 重试：LLM 调用幂等；任务级可配置重试次数，避免重复落库。
- 监控：日志结构化（task, step, section_id, model, tokens, elapsed）；必要时添加 Prometheus 指标。

## 12. 交付与验收
- 必须可本地运行（uvicorn + celery + redis + npm dev）。
- 必须具备：论文 CRUD、上传、生成（大纲/并行草稿/摘要）、任务查询/推送、导出。
- 性能验收：单论文 5 章并行，1–2 分钟内产出草稿与摘要。
- 文档：提供运行指南、环境变量说明、主要接口示例。
