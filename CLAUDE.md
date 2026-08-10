# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

审计OCR + CPA知识库问答综合系统 — 两个Flask Web服务 + CLI工具 + 批量管道，集成OCR票据识别、RAG知识库问答、知识图谱、Agent批量管道。

## 启动命令

```bash
# 依赖安装
pip install flask flask-socketio psycopg2-binary requests numpy pandas openpyxl pillow jieba aiohttp

# 前置服务 (必须先启动)
ollama serve
ollama pull qwen3.5:9b                    # 视觉识别模型 (Ollama provider 时)
ollama pull qwen3-embedding:8b            # 向量嵌入模型 (4096维，RAG 必用)

# Web服务 (审计仪表盘 → :5000, CPA问答 → :5001)
python app.py
python web_app.py
# 知识图谱版问答 (5001 + /api/kg/* + /kg/explorer)
python run_kg.py

# 教材向量化导入 (首次或清空后)
python clear_embeddings.py                # 清空向量表
python import_all_cpa_8b.py               # 导入23本教材 → cpa_embeddings (4096维)

# 向量维度切换
python change_vector_dimension.py 1024    # 切换到0.6b模型 (1024维)
python change_vector_dimension.py 4096    # 切换到8b模型 (4096维)

# 知识图谱 (独立 cpa_knowledge_graph 库)
python knowledge/setup_kg_db.py           # 建库 + 建表
python knowledge/build_kg.py --book "会计" --limit 100   # 抽取实体/关系/公式

# 批量凭证管道 (audit_pipeline_db)
python pic_claw/import_batch.py --max-per-type 10     # downloaded/ 导入批次
python pic_claw/agent1_classify.py --batch-id 1 --workers 5   # Agent1 分类
python pic_claw/agent2_extract.py --batch-id 1          # Agent2 提取字段

# CLI工具
python main.py
python cpa_qa.py
```

## 架构要点

### 双服务 + 跨服务代理

- **app.py** (`:5000`) — 审计仪表盘。展示audit_results表数据，提供排序/搜索/风险过滤。**不直接调用LLM**，AI辅导通过HTTP代理转发到web_app.py。
- **web_app.py** (`:5001`) — CPA问答RAG系统。Flask + Flask-SocketIO，流式SSE输出。拥有所有LLM调用能力。
- 审计仪表盘的"问问AI"按钮：`app.py → POST web_app.py:5001/api/audit_tutor_stream → SSE流返回`
- **run_kg.py** — 在web_app上挂载知识图谱Blueprint（`/api/kg/*` + `/kg/explorer`），完全不动web_app.py代码。

### 统一模型调用层 (services/ollama_client.py)

尽管文件名带 `ollama_`，它是**所有模型供应商的统一路由入口**，不只是Ollama：

- `call_llm(prompt, model_key="main"/"fix"/"embed", image_base64="")` → 按当前供应商路由到 Ollama 原生API 或 OpenAI兼容API（DeepSeek/智谱/通义/OpenAI/豆包）。
- 当前供应商由 `data/model_config.json` 的 `current_provider` 决定，`main.py` 启动时可交互选择；`set_provider()` 支持运行时切换。
- **视觉支持按供应商区分**：`vision_support: false` 的供应商（如deepseek）不会把图片传给模型，OCR视觉识别需切换到支持视觉的供应商（ollama/zhipu/qwen/openai/doubao）。

### 四个PostgreSQL数据库

| 数据库 | 用途 | 关键表 |
|--------|------|--------|
| `cpa_knowledge` | CPA知识库 | `cpa_embeddings` (向量4096维), `cpa_qa_history`, `cpa_dream_knowledge`, `cpa_courses`/`cpa_books`/`cpa_chapters`, `cpa_entities`/`cpa_relationships` (GraphRAG) |
| `cpa_knowledge_graph` | 知识图谱独立库 | `kg_entities`, `kg_relationships`, `kg_formulas`, `kg_confusion_pairs`, `kg_communities`, `kg_build_log` |
| `audit_ocr` | 审计结果 | `audit_results`, `knowledge_base` |
| `audit_pipeline_db` | 批量管道 | `batches`, `voucher_images`, `extracted_fields`, `agent_logs`, `agent1_classify_results`, `agent2_extract_results` 等12张表 |

### 配置加载链

- `config/settings.py` 的 `AppConfig` 是单例：合并 `_default_config` 字典 + `data/config.json` 文件 → 挂载为实例属性（`cfg`）。
- `data/model_config.json` 独立管理6个模型供应商（ollama/deepseek/zhipu/qwen/openai/doubao），通过 `get_provider_config()` 读取，**每个供应商有独立的 `embed_dimension`**（ollama=4096, deepseek/qwen=1024, zhipu/doubao=2048, openai=1536）。
- `data/prompts_config.json` 存系统提示词，`data/kg_prompts.json` 存知识图谱抽取提示词（实体/关系/公式/易混）。
- **注意：`data/model_config.json` 内含真实API密钥，已入库——不要新增/泄露密钥。**

### OCR JSON修复机制

主模型识别图片 → `utils/json_handler.py` 的 `safe_json_loads()` 解析。如果JSON格式错误，自动调用 `call_ollama_model(get_fix_model(), ...)` 用fix模型修复，最多重试3次。仍失败则返回 `models/schemas.py` 的 `FALLBACK_RESULT`（标记为高风险/不通过）。`models/schemas.py` 还提供 `DEFAULT_OCR`/`DEFAULT_VALIDATION` 默认结构和 `deep_merge()` 深度合并。

### RAG检索模式

`web_app.py` 的 `search_knowledge_base()` 支持4种模式：`vector`（pgvector余弦距离）、`bm25`（PostgreSQL tsvector全文检索）、`hybrid`（0.7×向量 + 0.3×BM25加权融合）、`graph`（知识图谱关联）。

**关键点：`get_ollama_embedding()` 硬编码调用 Ollama `qwen3-embedding:8b`（4096维），与 `current_provider` 无关。** 因此即使问答/OCR已切换到DeepSeek，RAG向量检索仍依赖 Ollama 服务在运行。

### 知识图谱子系统（两套，勿混淆）

1. **GraphRAG（在 `cpa_knowledge` 库内）** — `web_app.py` 的 `search_knowledge_base_graph()` 即"graph"检索模式：jieba分词 → 匹配 `cpa_entities` → 沿 `cpa_relationships` 上下游扩散 → 取 `source_chunk_ids` 回 `cpa_embeddings` 查内容。图由 `web_app.py` 的 `/api/graph/build` 用LLM构建。
2. **独立图谱库（`cpa_knowledge_graph`）** — 更完整的图谱系统：`knowledge/build_kg.py` 从 `cpa_knowledge.cpa_embeddings` 批量抽取实体/关系/公式/易混对写入 `kg_*` 表；`run_kg.py` 挂载 `blueprints/kg_api.py`（`/api/kg/*`）并提供 `/kg/explorer` 可视化页（`templates/kg_explorer.html`）。相关服务在 `services/kg_*.py`，提示词在 `data/kg_prompts.json`。

### 教材导入三阶段流水线

`import_all_cpa_8b.py`：① `parse_markdown_content()` 按 `#章`/`##节` 标题切分（不按空行），过滤<50字符碎片，清洗图片标记和LaTeX → ② asyncio + aiohttp 异步并发生成4096维向量（Semaphore控制并发）→ ③ `execute_values` 每1000条批量INSERT。

### 做梦机制 (Dream)

`services/dream_service.py`：从 `cpa_qa_history` 中定期提炼知识点 → 存入 `cpa_dream_knowledge` → 相似知识合并去重 → 作为长期记忆供未来检索。手动触发或定时执行。

### Agent团队系统

`services/agent_service.py` + `team_service.py` + `orchestrator.py`：支持定义多个Agent（角色+模型绑定）、组建团队、多轮对话协作。前端在 `templates/agents.html` 和 `templates/teams.html`。

### 批量管道 (pic_claw/)

两阶段Agent处理14万+凭证图片，走 `audit_pipeline_db`：`import_batch.py` 导入图片到批次 → `agent1_classify.py` 分类（10大类130子类，定义在 `category_prompts.py`）→ `agent2_extract.py` 按类目提取字段 → 审计规则校验。DB访问层在 `pipeline_db.py`，JSON修复在 `json_fixer.py`。`picclaw.py` 是百度图片爬虫（Playwright + MD5去重）。

### 前端统一架构 (v2.0 GUI)

- **统一入口 :5001**：web_app.py 已注册知识图谱 blueprint（`/api/kg/*` + `/kg/explorer`），`python web_app.py` 即全功能统一入口；`run_kg.py` 保留兼容。
- **设计系统**：`templates/base.html` 统一外壳（侧边栏+顶栏+content/scripts块），`static/css/app.css`（白底靛蓝设计令牌+组件）+ `static/js/app.js`（`api()`/`showToast`/`openModal`/`renderPagination`/`escapeHtml`）。
- 10 个页面全部 `{% extends "base.html" %}`（通过 `{% set active %}` 高亮侧边栏）；不再使用 Bootstrap CDN。marked.js / ECharts / Socket.IO 按页在 `{% block head %}` 加载。
- 页面全部靠 JS `fetch('/api/...')` 自举数据，API 契约未变。流式链路：主聊天=SocketIO、团队运行/审计辅导=SSE。
- 遗留文件不动：`app.py(:5000)` 仍渲染共享模板（侧边栏指向 :5001 的路由）；`web_app_5005.py`、`audit_cpa_index.html`、`audit_dashboard.html` 为旧版/孤儿。

## 关键文件速查

| 当你需要... | 去看... |
|-------------|---------|
| 修改OCR识别逻辑 | `services/ocr_engine.py` → `audit_ocr_recognize()` |
| 修改模型调用/供应商路由 | `services/ollama_client.py` → `call_llm()` |
| 修改RAG检索/问答 | `web_app.py` → `search_knowledge_base()` + `call_deepseek_stream()` |
| 修改数据校验规则 | `services/validator.py` + `utils/converter.py` (中文大写金额转换) |
| 修改模型供应商配置 | `data/model_config.json` |
| 修改票据类型列表 | `config/constants.py` → `IMAGE_TYPES` |
| 修改CPA教材配置 | `cpazs/config_cpa.py` → `DATA_SOURCES` |
| 修改前端仪表盘 | `templates/dashboard.html` |
| 修改前端问答界面 | `templates/index.html` |
| 修改知识库管理后台 | `templates/admin.html` (5个标签页) |
| 修改系统提示词 | `data/prompts_config.json` |
| 修改审计知识库规则 | `knowledge/audit_knowledge_base.json` |
| 修改管道分类定义 | `pic_claw/picclaw.py` → `CATEGORIES` |
| 修改知识图谱构建 | `knowledge/build_kg.py` + `services/kg_*.py` |
| 修改知识图谱API | `blueprints/kg_api.py` |
| 修改JSON修复/解析 | `utils/json_handler.py` → `safe_json_loads()` |
| 修改统一界面外壳 | `templates/base.html` |
| 修改设计系统/组件 | `static/css/app.css` + `static/js/app.js` |

## 注意事项

- **端口必须同时运行**：审计仪表盘的"问问AI"功能依赖web_app.py在5001端口运行，否则代理请求会失败。
- **Ollama即使切换到云端供应商也要运行**：`get_ollama_embedding()` 硬编码走Ollama，RAG向量检索离了它就会失败。
- **向量维度一致性**：`cpa_embeddings` 和 `cpa_qa_history` 的 `embedding` 列维度必须与Ollama模型输出匹配。切换模型需运行 `change_vector_dimension.py`。
- **两个web_app.py变体**：`web_app_5005.py` 是5005端口的旧版变体，主版本是 `web_app.py` (5001端口)。
- **Bootstrap模态框冲突**：知识库管理后台使用 `.modal-box` 而非 `.modal` 类名，因与Bootstrap 5.3+自带样式冲突。
- **Ollama Embedding API路径**：用的是 `/api/embeddings`（不是 `/api/chat`），在 `cpazs/config_cpa.py` 的 `EMBEDDING_CONFIG.api_url` 中配置。
- **API密钥安全**：`data/model_config.json` 含真实密钥，修改/新增供应商时勿将新密钥提交到仓库。
