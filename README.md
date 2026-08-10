# 审计OCR + CPA知识库问答综合系统

基于 AI 大模型的 **智能审计票据识别**、**CPA 考试辅导问答** 与 **批量凭证两阶段 Agent 管道处理** 综合平台。

---

## 一、系统概览

本项目是集 **审计票据OCR识别**、**审计数据看板**、**CPA 知识库问答（RAG）**、**批量凭证Agent智能化处理** 于一体的综合系统。

| 子系统 | 端口 | 服务文件 | 用途 |
|--------|:----:|----------|------|
| 审计仪表盘 | 5000 | `app.py` | 审计数据可视化、风险分析、AI 辅导 |
| CPA 问答 | 5001 | `web_app.py` | 知识库管理、RAG 问答、多模式检索 |
| CLI 审计 | - | `main.py` | 命令行批量 OCR 识别 |
| 批量凭证管道 | - | `pic_claw/` | 两阶段 Agent 分类 + 提取（建设中） |

---

## 二、核心功能

### 2.1 审计 OCR 识别系统

基于 Ollama 本地大模型（Qwen3.5:9b）的视觉识别能力，对审计票据图片进行智能识别，提取结构化数据：

- **图片扫描**：遍历 `input_pic/` 文件夹，支持 png/jpg/jpeg/webp/gif 格式
- **多模型视觉识别**：主模型 Qwen3.5:9b，备用支持智谱AI、阿里通义千问、OpenAI、火山引擎豆包
- **JSON 修复**：DeepSeek 模型对识别结果二次修复（格式错误/字段缺失时自动调用）
- **数据校验**：日期格式、发票金额逻辑、统一社会信用代码校验规则
- **结果输出**：按类型分类保存图片 + 信息文件、生成 Excel 报告、写入 PostgreSQL

### 2.2 审计数据仪表盘

实时展示审计结果的 Web 看板：

- **数据概览**：总记录数、风险等级分布、通过率统计
- **表格展示**：支持 9 个字段可点击列头排序、每列独立搜索过滤、风险等级切换
- **记录详情**：点击查看完整 OCR 文本、提取字段、风险评分
- **AI 审计辅导**：选中记录点击"问问AI"，自动关联审计知识库 + CPA 教材生成分析

### 2.3 CPA 知识库问答系统 (RAG)

基于 RAG 架构的 CPA 考试智能问答：

- **教材向量化**：已导入 23 本 CPA 教材（会计/审计/税法/经济法/财管/战略），共四万+ 知识块
- **多模式检索**：支持向量检索 / BM25 全文检索 / 混合检索 / 知识图谱检索
- **流式回答**：DeepSeek API 流式输出，前端逐 token 渲染 Markdown
- **问答历史**：自动保存问答对，支持追问上下文传递、历史记录回溯
- **做梦机制**：从历史问答中提炼知识点定时合并，增强长期记忆
- **知识库管理后台**：分标签页管理教材 / 问答历史 / 审计辅导 / 归档知识

### 2.4 智能审计管道（建设中）

面向 14 万+ 凭证图片的批量处理管道：

- **两阶段 Agent**：Agent1 从 10 大类 130 子类中分类凭证 → Agent2 按类目提取关键字段
- **批次管理**：批次导入 → 状态追踪 → 进度统计
- **全流程追踪**：OCR → Agent1 分类 → Agent2 提取 → 审计规则校验
- **独立数据库**：`audit_pipeline_db`，与现有 CPA 问答系统完全独立

### 2.5 批量凭证图片爬虫

`pic_claw/picclaw.py` 实现了基于 Playwright 的百度图片自动爬取工具：

- **130 种凭证类型**：基于预定义的 CATEGORIES 列表逐类下载
- **自动去重**：MD5 校验 + 文件大小过滤
- **已完成采集**：约 14 万张图片，覆盖全部 130 种子类
- **分类目录**：按类别名称存储于 `pic_claw/downloaded/` 目录下

---

## 三、数据库架构

### 3.1 审计数据库（audit_ocr）

| 表名 | 用途 | 记录数参考 |
|------|------|:----------:|
| audit_results | 审计识别结果（OCR 文本、提取字段、风险评分） | 运行时动态 |

### 3.2 CPA 知识库数据库（cpa_knowledge）

| 表名 | 用途 | 向量维度 |
|------|------|:--------:|
| cpa_embeddings | 教材知识库（chunk 文本 + 4096 维向量） | 4096 |
| cpa_qa_history | 历史问答对 + 向量 | 4096 |
| cpa_courses | 6 个 CPA 科目 | - |
| cpa_books | 23 本教材元数据 | - |
| cpa_chapters | 章节树形结构 | - |
| cpa_dream_knowledge | 做梦提炼的知识点 | - |

### 3.3 批量管道数据库（audit_pipeline_db）

| 表名 | 用途 |
|------|------|
| document_categories | 10 大类定义（发票类、差旅票据类等） |
| document_types | 130 种子类定义（含搜索关键词 + 预期提取字段模板） |
| batches | 批次管理（进度、状态、错误统计） |
| voucher_images | 图片元数据 + 三状态状态机（classify/ocr/audit） |
| ocr_results | OCR 识别原始文本 + JSON |
| agent_logs | Agent1 分类 + Agent2 提取执行日志 |
| extracted_fields | 动态 key-value 提取字段 |
| audit_results | 审计结果（风险评级、违规项） |
| audit_rules | 可配置审计规则引擎 |
| pipeline_logs | 全流程追踪日志 |

---

## 四、技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 后端语言 | Python 3.10+ | 主开发语言 |
| Web 框架 | Flask 3.x | 双 Web 服务 |
| 实时通信 | Flask-SocketIO / SSE | 流式推送 |
| 数据库 | PostgreSQL 16 + pgvector | 存储 + 向量检索 |
| OCR 视觉 | Ollama + Qwen3.5:9b | 票据识别（本地） |
| 向量模型 | Ollama + qwen3-embedding:8b | 4096 维文本向量化 |
| 回答生成 | DeepSeek API / Ollama | 智能问答 |
| 前端 | Bootstrap 5 + marked.js | 响应式界面 + Markdown |
| 爬虫 | Playwright + aiohttp | 百度图片批量采集 |
| 分词 | jieba + CPA 自定义词典 | 中文分词 |

### 模型供应商支持

| 供应商 | 本地/云端 | 视觉识别 | 配置位置 |
|--------|:--------:|:--------:|----------|
| Ollama | 本地 | ✅ | `data/model_config.json` |
| 智谱AI | 云端 | ✅ | 同上 |
| 阿里通义千问 | 云端 | ✅ | 同上 |
| OpenAI | 云端 | ✅ | 同上 |
| DeepSeek | 云端 | ❌ | 同上 |
| 火山引擎豆包 | 云端 | ✅ | 同上 |

---

## 五、项目结构

```
审计OCR+CPA问答综合系统/
│
├── app.py                   # 审计仪表盘 Web 服务（端口5000）
├── web_app.py               # CPA 知识库问答 Web 服务（端口5001）
├── main.py                  # CLI 菜单入口（审计 OCR 主程序）
├── cpa_qa.py                # CLI 版 CPA 问答
│
├── config/                  # 配置模块
│   ├── settings.py          # 全局配置单例 + 6供应商切换
│   └── constants.py         # 票据类型常量（186种）
│
├── data/                    # 配置文件目录
│   ├── config.json          # 应用配置（数据库/Ollama）
│   ├── model_config.json    # 6个供应商 API 配置
│   ├── prompts_config.json  # 系统提示词模板
│   └── cpa_dict.txt         # jieba 分词词典
│
├── services/                # 核心业务服务
│   ├── ollama_client.py     # 统一模型调用（Ollama/DeepSeek/智谱...）
│   ├── ocr_engine.py        # OCR 识别引擎
│   ├── embedding_service.py # 向量生成
│   ├── knowledge_retriever.py # 审计知识库检索
│   ├── validator.py         # 数据校验规则
│   ├── db_service.py        # 数据库写入
│   ├── cpa_tutor.py         # CPA 知识点辅导
│   ├── dream_service.py     # 做梦机制（知识提炼合并）
│   ├── agent_service.py     # Agent 定义管理
│   ├── team_service.py      # Agent 团队管理
│   └── orchestrator.py      # 多 Agent 编排
│
├── models/                  # 数据模型
│   └── schemas.py           # 默认 JSON 结构 + 深度合并
│
├── templates/               # 前端模板
│   ├── dashboard.html       # 审计仪表盘主页
│   ├── index.html           # CPA 问答界面
│   ├── admin.html           # 知识库管理后台（5标签页）
│   ├── kb_browser.html      # 知识库浏览器
│   ├── knowledge_base.html  # 审计知识库页面
│   ├── agents.html          # Agent 管理界面
│   ├── teams.html           # 团队管理界面
│   ├── team_chat.html       # 团队对话界面
│   └── settings.html        # 系统设置页面
│
├── cpazs/                   # CPA 教材知识库
│   ├── config_cpa.py        # 23本教材配置
│   ├── schema.sql           # 建表 SQL
│   └── md格式/              # 教材 Markdown（含轻一/官方教材）
│
├── knowledge/               # 审计知识库
│   ├── audit_knowledge_base.json  # 审计规则知识库
│   ├── setup_kb_table.py          # 知识库建表
│   └── *.md                 # 审计规则文档（凭证识别/金额转换/风险评估）
│
├── pic_claw/                # 批量凭证图片管道
│   ├── picclaw.py           # 百度图片爬虫 + CATEGORIES 分类定义
│   ├── downloaded/          # 130个分类目录，约 14 万张图片
│   └── ...Agent 管道脚本（开发中）
│
├── sql/                     # 数据库管理脚本
│   ├── 01_create_audit_pipeline.sql  # audit_pipeline_db 建表
│   ├── _create_db.py                 # 创建数据库
│   ├── _run_create_tables.py         # 执行建表
│   └── _import_categories.py         # 导入 130 种分类
│
├── input_pic/               # 待识别的票据图片
├── output/                  # 审计结果输出
│   ├── 分类结果/            # 按类目保存的图片 + txt
│   └── audit_ocr_result.xlsx  # Excel 汇总报告
│
└── docs/                    # 项目文档
    ├── 项目架构.md
    ├── 开发文档.md
    └── 并发配置说明.md
```

---

## 六、快速启动

### 环境要求

- Python 3.10+
- PostgreSQL 16 + pgvector 扩展
- Ollama（本地大模型）

### 1. 安装依赖

```bash
pip install flask flask-socketio psycopg2-binary requests numpy pandas openpyxl pillow jieba
```

### 2. 下载 Ollama 模型

```bash
ollama pull qwen3.5:9b           # 主视觉识别
ollama pull deepseek-r1:8b       # JSON 修复
ollama pull qwen3-embedding:8b   # 向量嵌入
ollama pull qwen3-embedding:0.6b # 轻量向量（可选）
```

### 3. 初始化数据库

```bash
# CPA 知识库（cpa_knowledge）
psql -U postgres -c "CREATE DATABASE cpa_knowledge;"
psql -U postgres -d cpa_knowledge -f cpazs/schema.sql

# 导入教材
python import_all_cpa_8b.py

# 审计数据库（audit_ocr）和管道数据库（audit_pipeline_db）
# 会自动按需创建，详见各模块文档
```

### 4. 配置模型供应商

编辑 `data/model_config.json`，填入 API Key：

```json
{
  "current_provider": "ollama",
  "providers": {
    "deepseek": {
      "api_key": "sk-xxx",
      "chat_api": "https://api.deepseek.com/v1/chat/completions",
      "models": { "main": "deepseek-chat", "fix": "deepseek-chat" }
    }
  }
}
```

### 5. 启动服务

```bash
# 终端1：审计仪表盘（端口5000）
python app.py

# 终端2：CPA知识库问答（端口5001）
python web_app.py
```

访问 http://localhost:5000 → 审计仪表盘（侧边栏可跳转 CPA 问答）

---

## 七、API 文档

### 审计仪表盘（app.py，端口5000）

| 路由 | 方法 | 用途 |
|------|------|------|
| `/` | GET | 审计仪表盘页面 |
| `/api/audit_data` | GET | 审计数据列表（支持排序、搜索、分页） |
| `/api/audit_record/<id>` | GET | 单条记录详情 |
| `/api/statistics` | GET | 统计数据（总数、风险分布、通过率） |
| `/api/ask_ai` | POST | AI 审计辅导（非流式） |
| `/api/ask_ai_stream` | GET | AI 审计辅导（SSE 流式） |
| `/api/knowledge_base` | GET | 审计知识库列表 |

### CPA 知识库问答（web_app.py，端口5001）

| 路由 | 方法 | 用途 |
|------|------|------|
| `/` | GET | CPA 问答页面 |
| `/api/chat` | POST | 流式问答（Socket.IO） |
| `/api/chat_history` | GET | 历史问答列表 |
| `/api/search` | POST | 知识库搜索（向量/BM25/混合/图谱） |
| `/api/cpa_knowledge/*` | GET/POST | 知识库 CRUD |
| `/api/cpa_knowledge/audit_tutor_list` | GET | 审计辅导记录列表 |
| `/api/cpa_knowledge/audit_tutor_detail/<id>` | GET | 审计辅导详情 |
| `/api/audit_tutor_stream` | GET | 审计辅导流式接口 |
| `/api/audit_chat_history/<id>` | GET | 对话历史加载 |
| `/api/audit_chat_history/<id>/clear` | POST | 对话历史删除 |
| `/api/dream/*` | GET/POST | 做梦机制相关 |
| `/api/agents/*` | GET/POST/PUT/DELETE | Agent 管理 |
| `/api/teams/*` | GET/POST/PUT/DELETE | 团队管理 |
| `/api/team/run` | POST | 团队运行 |
| `/api/team/run_stream` | GET | 团队运行（流式） |
| `/api/config/*` | GET/POST | 系统配置 |

---

## 八、核心工作流

### 8.1 审计 OCR 流程

```
input_pic/ → main.py
  → ocr_engine.audit_ocr_recognize() 调用 Qwen3.5:9b
  → validator 校验（日期/金额/信用代码）
  → 分类保存到 output/分类结果/
  → db_service 写入 audit_results 表
  → 生成 Excel 报告
```

### 8.2 CPA 问答流程 (RAG)

```
用户提问 → web_app.py
  → search_knowledge_base() 向量检索 cpa_embeddings
  → search_qa_history() 向量检索 cpa_qa_history
  → 拼接上下文 → DeepSeek API 流式回答
  → Socket.IO 推送前端渲染
  → 自动保存问答对到 cpa_qa_history
```

### 8.3 审计 AI 辅导（跨系统联动）

```
审计仪表盘点击"问问AI" → app.py 代理 → web_app.py
  → 接收审计风险详情 + 关联知识库规则
  → 检索 CPA 教材知识库
  → DeepSeek 流式生成专业辅导分析
  → SSE 流返回仪表盘渲染
```

### 8.4 Agent 两阶段管道（建设中）

```
pic_claw/downloaded/ 图片批次
  → Agent1：从 10 大类 130 子类中分类
  → Agent2：按类目动态 Prompt 提取字段
  → 审计规则引擎校验 → 写入 audit_results
  → pipeline_logs 全流程追踪
```

---

## 九、高级功能

### 9.1 多模式知识检索

CPA 知识库支持 4 种检索模式：

| 模式 | 原理 | 适用场景 |
|------|------|----------|
| 向量检索 | pgvector 余弦相似度 | 语义匹配 |
| BM25 全文检索 | PostgreSQL tsvector | 关键词精确匹配 |
| 混合检索 | 向量 + BM25 加权融合 | 综合最优 |
| 知识图谱检索 | 知识点关联关系 | 关联推理 |

### 9.2 做梦机制

从历史问答中自动提炼知识点，定期合并到 `cpa_dream_knowledge` 表，作为长期记忆供未来检索使用。支持手动触发和定时自动执行。

### 9.3 Agent 团队协作

支持定义多个 Agent（角色设定 + 模型绑定），组建团队进行多轮对话协作，可用于自动化审计分析、合规检查等场景。

---

## 十、配置说明

### 关键配置项（data/config.json）

```json
{
  "MODEL_PROVIDER": "ollama",
  "OLLAMA_API_URL": "http://localhost:11434/api/chat",
  "MAIN_MODEL": "qwen3.5:latest",
  "FIX_MODEL": "deepseek-r1:8b",
  "EMBED_MODEL": "qwen3-embedding:8b",
  "IMAGE_FOLDER": "./input_pic",
  "EXCEL_OUTPUT": "./output/audit_ocr_result.xlsx",
  "OUTPUT_ROOT_FOLDER": "./output/分类结果",
  "SUPPORTED_FORMATS": [".png", ".jpg", ".jpeg", ".webp", ".gif"],
  "DB_HOST": "localhost",
  "DB_PORT": 5432,
  "DB_NAME": "audit_ocr",
  "DB_USER": "postgres",
  "DB_PASSWORD": "admin"
}
```

---

## 十一、常见问题

**Q: 端口冲突怎么办？**
审计仪表盘占用 5000 端口，CPA 问答占用 5001 端口。编辑对应 .py 文件末尾的 `app.run(port=...)` 修改。

**Q: "问问AI"按钮无响应？**
确保 `web_app.py` 和 `app.py` **都**在运行，且 Ollama 服务已启动（用于向量检索）。检查 terminal 是否有报错日志。

**Q: 如何重新导入 CPA 教材？**
```bash
python clear_embeddings.py   # 清空向量库
python import_all_cpa_8b.py  # 重新导入全部教材
```

**Q: 如何切换向量维度？**
```bash
python change_vector_dimension.py 1024   # 切换到 0.6b 模型
python change_vector_dimension.py 4096   # 切换到 8b 模型
```

**Q: 知识库管理页面弹窗不显示？**
检查是否使用了过新的 Bootstrap 版本（5.3+），`.modal` 类名可能与自定义样式冲突。本项目已改为 `.modal-box` 类名规避冲突。

---

## 十二、许可证

仅供学习和研究使用。
