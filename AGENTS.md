# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 项目概述

审计OCR + CPA知识库问答综合系统 — 两个Flask Web服务 + CLI工具，集成OCR票据识别、RAG知识库问答、Agent批量管道。

## 启动命令

```bash
# 依赖安装
pip install flask flask-socketio psycopg2-binary requests numpy pandas openpyxl pillow jieba aiohttp

# 前置服务 (必须先启动)
ollama serve                              # Ollama本地模型服务
ollama pull qwen3.5:9b                    # 视觉识别模型
ollama pull qwen3-embedding:8b            # 向量嵌入模型 (4096维)

# Web服务 (两个终端)
python app.py                             # 审计仪表盘 → http://localhost:5000
python web_app.py                         # CPA知识库问答 → http://localhost:5001

# 教材向量化导入 (首次或清空后)
python clear_embeddings.py                # 清空向量表
python import_all_cpa_8b.py               # 导入23本教材 → cpa_embeddings (4096维)

# 向量维度切换
python change_vector_dimension.py 1024    # 切换到0.6b模型 (1024维)
python change_vector_dimension.py 4096    # 切换到8b模型 (4096维)

# CLI工具
python main.py                            # CLI菜单：审计OCR识别
python cpa_qa.py                          # CLI版CPA问答
```

## 架构要点

### 双服务 + 跨服务代理

- **app.py** (`:5000`) — 审计仪表盘。展示audit_results表数据，提供排序/搜索/风险过滤。**不直接调用LLM**，AI辅导通过HTTP代理转发到web_app.py。
- **web_app.py** (`:5001`) — CPA问答RAG系统。Flask + Flask-SocketIO，流式SSE输出。拥有所有LLM调用能力（DeepSeek API、Ollama embedding）。
- 审计仪表盘的"问问AI"按钮：`app.py → GET/POST web_app.py:5001/api/audit_tutor_stream → SSE流返回`

### 三个PostgreSQL数据库

| 数据库 | 用途 | 关键表 |
|--------|------|--------|
| `cpa_knowledge` | CPA知识库 | `cpa_embeddings` (向量4096维), `cpa_qa_history`, `cpa_dream_knowledge` |
| `audit_ocr` | 审计结果 | `audit_results`, `knowledge_base` |
| `audit_pipeline_db` | 批量管道 (建设中) | `batches`, `voucher_images`, `extracted_fields`, `agent_logs` 等10张表 |

### 配置加载链

`config/settings.py` 的 `AppConfig` 是单例：合并 `_default_config` 字典 + `data/config.json` 文件 → 挂载为实例属性。`data/model_config.json` 独立管理6个模型供应商（ollama/deepseek/zhipu/qwen/openai/doubao），通过 `get_provider_config()` 读取。

### OCR JSON修复机制

主模型(qwen3.5:9b)识别图片 → `safe_json_loads()` 解析。如果JSON格式错误，自动调用 `fix_json_with_deepseek()` 用DeepSeek修复，最多重试3次。仍失败则返回FALLBACK_RESULT（标记为高风险/不通过）。

### RAG检索模式

`web_app.py` 的 `search_knowledge_base()` 支持4种模式：`vector`（pgvector余弦距离）、`bm25`（PostgreSQL tsvector全文检索）、`hybrid`（0.7×向量 + 0.3×BM25加权融合）、`graph`（知识图谱关联）。

### 教材导入三阶段流水线

`import_all_cpa_8b.py`：① `parse_markdown_content()` 按 `#章`/`##节` 标题切分（不按空行），过滤<50字符碎片，清洗图片标记和LaTeX → ② asyncio + aiohttp 异步并发生成4096维向量（Semaphore控制并发）→ ③ `execute_values` 每1000条批量INSERT。

### 做梦机制 (Dream)

`services/dream_service.py`：从 `cpa_qa_history` 中定期提炼知识点 → 存入 `cpa_dream_knowledge` → 相似知识合并去重 → 作为长期记忆供未来检索。手动触发或定时执行。

### Agent团队系统

`services/agent_service.py` + `team_service.py` + `orchestrator.py`：支持定义多个Agent（角色+模型绑定）、组建团队、多轮对话协作。前端在 `templates/agents.html` 和 `templates/teams.html`。

### 批量管道 (pic_claw/)

两阶段Agent处理14万+凭证图片：Agent1分类（10大类130子类）→ Agent2按类目提取字段 → 审计规则校验。`picclaw.py` 同时包含百度图片爬虫（Playwright + MD5去重）。

## 关键文件速查

| 当你需要... | 去看... |
|-------------|---------|
| 修改OCR识别逻辑 | `services/ocr_engine.py` → `audit_ocr_recognize()` |
| 修改RAG检索/问答 | `web_app.py` → `search_knowledge_base()` + `call_deepseek_stream()` |
| 修改数据校验规则 | `services/validator.py` |
| 修改模型供应商配置 | `data/model_config.json` |
| 修改票据类型列表 | `config/constants.py` → `IMAGE_TYPES` |
| 修改CPA教材配置 | `cpazs/config_cpa.py` → `DATA_SOURCES` |
| 修改前端仪表盘 | `templates/dashboard.html` |
| 修改前端问答界面 | `templates/index.html` |
| 修改知识库管理后台 | `templates/admin.html` (5个标签页) |
| 修改系统提示词 | `data/prompts_config.json` |
| 修改审计知识库规则 | `knowledge/audit_knowledge_base.json` |
| 修改管道分类定义 | `pic_claw/picclaw.py` → `CATEGORIES` |

## 注意事项

- **端口必须同时运行**：审计仪表盘的"问问AI"功能依赖web_app.py在5001端口运行，否则代理请求会失败。
- **向量维度一致性**：`cpa_embeddings` 和 `cpa_qa_history` 的 `embedding` 列维度必须与Ollama模型输出匹配。切换模型需运行 `change_vector_dimension.py`。
- **两个web_app.py变体**：`web_app_5005.py` 是5005端口的旧版变体，主版本是 `web_app.py` (5001端口)。
- **Bootstrap模态框冲突**：知识库管理后台使用 `.modal-box` 而非 `.modal` 类名，因与Bootstrap 5.3+自带样式冲突。
- **Ollama Embedding API路径**：用的是 `/api/embeddings`（不是 `/api/chat`），在 `cpazs/config_cpa.py` 的 `EMBEDDING_CONFIG.api_url` 中配置。
