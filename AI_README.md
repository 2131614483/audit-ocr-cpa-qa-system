# AI_README: 审计OCR+CPA问答综合系统

This document is optimized for LLM/AI consumption. It contains complete file structure, function signatures, database schemas, API routes, data flows, and inter-module dependency mappings for the entire project.

---

## [SYSTEM_IDENTITY]
name="审计OCR+CPA问答综合系统"
version="20260516"
language="Python 3.10+"
framework="Flask 3.x"
database="PostgreSQL 16 + pgvector"
llm_orchestration="Ollama + DeepSeek API + multi-provider"

---

## [FILE_TREE]

```
proj_root: d:\pythonpro\ollama项目\审计OCR+CPA问答综合系统

## Web Services (2 servers)
app.py          # Flask server @5000 - 审计仪表盘 (audit dashboard)
web_app.py      # Flask+SocketIO server @5001 - CPA问答 (CPA Q&A RAG)

## CLI entrypoints
main.py         # CLI menu: audit OCR recognition pipeline
cpa_qa.py       # CLI: CPA Q&A interactive session

## Config Module
config/
  __init__.py
  settings.py       # AppConfig singleton: load config.json + model_config.json
  constants.py      # 186 audit document type constants

## Data/Config Files (runtime editable)
data/
  config.json              # app config: DB, Ollama, paths
  model_config.json        # 6 providers: Ollama/DeepSeek/智谱/通义千问/OpenAI/豆包
  prompts_config.json      # system prompt templates
  cpa_dict.txt             # jieba custom dictionary (CPA terms)

## Core Services
services/
  __init__.py
  ollama_client.py         # unified LLM caller: supports 6 providers
  ocr_engine.py            # OCR recognition engine (vision model)
  embedding_service.py     # text -> vector embedding
  knowledge_retriever.py   # audit knowledge base retrieval + vector search
  validator.py             # data validation: date/amount/tax_id
  db_service.py            # DB write operations
  cpa_tutor.py             # CPA tutoring logic
  dream_service.py         # dream mechanism: knowledge extraction + consolidation
  agent_service.py         # Agent CRUD (name/role/model bindings)
  team_service.py          # Team CRUD (agent groups)
  orchestrator.py          # multi-agent orchestration runner

## Data Models
models/
  __init__.py
  schemas.py               # default JSON structures + deep_merge utility

## Frontend Templates (Jinja2 + Bootstrap5)
templates/
  dashboard.html           # audit dashboard main page (table/sort/filter/AI tutor)
  index.html               # CPA Q&A page (chat interface)
  admin.html               # knowledge base admin (5 tabs: overview/textbook/history/audit/dream)
  kb_browser.html          # knowledge base browser
  knowledge_base.html      # audit knowledge base page
  agents.html              # agent management UI
  teams.html               # team management UI
  team_chat.html           # team conversation UI
  settings.html            # system settings page

## CPA Textbook Knowledge Base
cpazs/
  config_cpa.py            # 23 textbooks configuration
  schema.sql               # cpa_knowledge DB schema
  md格式/                  # textbook markdown files (6 subjects, 23 books)
  json格式/                # textbook json format (partial)

## Audit Knowledge Base
knowledge/
  audit_knowledge_base.json        # audit rules KB (JSON)
  setup_kb_table.py                # KB table creation script
  凭证类型识别指南.md               # document type recognition guide
  发票校验规则库.md                  # invoice validation rules
  审计OCR识别与知识库匹配优化方案.md  # OCR+KB matching optimization
  审计凭证OCR——全类别凭证风险评估手册.md # risk assessment manual
  金额转换规则库.md                  # amount conversion rules

## Batch Document Pipeline (under development)
pic_claw/
  picclaw.py               # Baidu image crawler + CATEGORIES (130 types)
  downloaded/              # ~140K images, 130 category subdirs

## Pipeline DB scripts
sql/
  01_create_audit_pipeline.sql    # CREATE TABLE for audit_pipeline_db
  _create_db.py                   # CREATE DATABASE audit_pipeline_db
  _run_create_tables.py           # execute SQL script
  _import_categories.py           # import 10 categories + 130 subtypes

## Input/Output
input_pic/                 # images to be OCR-recognized
output/
  分类结果/                # classified output (images + .txt)
  audit_ocr_result.xlsx    # Excel summary report

## Utility Scripts
import_all_cpa_8b.py       # vectorize all 23 textbooks -> cpa_embeddings
create_cpa_db.py           # create CPA DB
clear_embeddings.py        # truncate cpa_embeddings table
change_vector_dimension.py # switch vector dimension (1024/4096)
check_all_tables.py        # verify all tables exist
fix_vector_extension.py    # fix pgvector extension
json_import_cpa.py         # import JSON textbook
```

---

## [DATABASE_SCHEMAS]

### DB1: cpa_knowledge (CPA knowledge base)

```sql
-- 1. cpa_courses: 6 CPA subjects
CREATE TABLE cpa_courses (
    id SERIAL PRIMARY KEY,
    course_name VARCHAR(100) NOT NULL UNIQUE,  -- 会计/审计/税法/经济法/财管/战略
    course_code VARCHAR(20),
    description TEXT
);

-- 2. cpa_books: 23 textbooks
CREATE TABLE cpa_books (
    id SERIAL PRIMARY KEY,
    course_id INT REFERENCES cpa_courses(id),
    book_name VARCHAR(200) NOT NULL,
    book_type VARCHAR(20),        -- 'official' or 'qingyi'
    total_chunks INT DEFAULT 0,
    UNIQUE(course_id, book_name)
);

-- 3. cpa_chapters: chapter tree
CREATE TABLE cpa_chapters (
    id SERIAL PRIMARY KEY,
    book_id INT REFERENCES cpa_books(id),
    parent_id INT REFERENCES cpa_chapters(id),
    chapter_title VARCHAR(500) NOT NULL,
    chapter_level INT DEFAULT 1,
    sort_order INT
);

-- 4. cpa_embeddings: vector knowledge base (core RAG table)
CREATE TABLE cpa_embeddings (
    id BIGSERIAL PRIMARY KEY,
    chunk_content TEXT NOT NULL,
    chunk_embedding vector(4096),
    source_type VARCHAR(20) CHECK(source_type IN ('knowledge_point','qa_pair','chapter_chunk','book_content')),
    source_id INT,
    book_name VARCHAR(200),
    chapter_title VARCHAR(500),
    page_ref VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_cpa_embeddings_vector ON cpa_embeddings USING ivfflat (chunk_embedding vector_cosine_ops);
CREATE INDEX idx_cpa_embeddings_source_type ON cpa_embeddings(source_type);
CREATE INDEX idx_cpa_embeddings_book ON cpa_embeddings(book_name);

-- 5. cpa_qa_history: question-answer history
CREATE TABLE cpa_qa_history (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(64),
    question TEXT NOT NULL,
    answer TEXT,
    prompt_key VARCHAR(50) DEFAULT 'general',
    referenced_sources JSONB,
    q_embedding vector(4096),
    a_embedding vector(4096),
    source_type VARCHAR(20) DEFAULT 'general',
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_qa_session ON cpa_qa_history(session_id);
CREATE INDEX idx_qa_vector ON cpa_qa_history USING ivfflat (q_embedding vector_cosine_ops);

-- 6. cpa_dream_knowledge: dream-extracted knowledge
CREATE TABLE cpa_dream_knowledge (
    id BIGSERIAL PRIMARY KEY,
    knowledge TEXT NOT NULL,
    source_qa_ids JSONB,
    tags JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### DB2: audit_ocr (audit results)

```sql
-- Main audit results table
CREATE TABLE audit_results (
    id SERIAL PRIMARY KEY,
    image_name VARCHAR(255),
    image_path TEXT,
    doc_type VARCHAR(100),
    ocr_text TEXT,
    extracted_fields JSONB,
    risk_rating VARCHAR(20),
    risk_score DECIMAL(6,4),
    audit_conclusion VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- knowledge base table
CREATE TABLE knowledge_base (
    id SERIAL PRIMARY KEY,
    kb_type VARCHAR(50),
    kb_title TEXT,
    kb_content TEXT,
    kb_embedding vector(4096),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### DB3: audit_pipeline_db (batch pipeline, under construction)

```sql
-- 10 tables, see sql/01_create_audit_pipeline.sql for full DDL

-- document_categories: 10 parent categories
CREATE TABLE document_categories (
    id SERIAL PRIMARY KEY,
    category_name VARCHAR(50) UNIQUE,   -- 发票类/差旅票据类/银行/资金类/...
    sort_order INT,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

-- document_types: 130 subtypes with extraction field templates
CREATE TABLE document_types (
    id SERIAL PRIMARY KEY,
    category_id INT REFERENCES document_categories(id),
    type_name VARCHAR(100) UNIQUE,      -- 增值税专用发票/银行回单/...
    search_keywords JSONB,              -- ["关键词1","关键词2",...]
    expected_fields JSONB,              -- [{"name":"invoice_code","type":"text","label":"发票代码"},...]
    sort_order INT
);

-- batches: job batch tracking
CREATE TABLE batches (
    id BIGSERIAL PRIMARY KEY,
    batch_no VARCHAR(32) UNIQUE,
    batch_name VARCHAR(200),
    total_images INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending', -- pending/running/done/failed
    ocr_progress INT DEFAULT 0,
    extract_progress INT DEFAULT 0,
    audit_progress INT DEFAULT 0
);

-- voucher_images: image metadata + state machine
CREATE TABLE voucher_images (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT REFERENCES batches(id),
    file_name VARCHAR(255),
    file_path VARCHAR(500),
    file_md5 VARCHAR(64),
    doc_type_id INT REFERENCES document_types(id),
    doc_type_name VARCHAR(100),
    category_name VARCHAR(50),
    classify_confidence DECIMAL(5,4),
    classify_status VARCHAR(20) DEFAULT 'pending', -- pending/done/failed
    ocr_status VARCHAR(20) DEFAULT 'pending',
    extract_status VARCHAR(20) DEFAULT 'pending',
    audit_status VARCHAR(20) DEFAULT 'pending'
);

-- agent_logs: agent1 (classify) + agent2 (extract) execution logs
CREATE TABLE agent_logs (
    id BIGSERIAL PRIMARY KEY,
    image_id BIGINT REFERENCES voucher_images(id),
    agent_stage VARCHAR(20),             -- 'classify' or 'extract'
    input_summary TEXT,
    output_json JSONB,
    llm_model VARCHAR(50),
    prompt_tokens INT,
    completion_tokens INT,
    duration_ms INT,
    status VARCHAR(20) DEFAULT 'done'
);

-- extracted_fields: dynamic key-value storage
CREATE TABLE extracted_fields (
    id BIGSERIAL PRIMARY KEY,
    image_id BIGINT REFERENCES voucher_images(id),
    field_name VARCHAR(64) NOT NULL,
    field_value TEXT,
    field_type VARCHAR(20) DEFAULT 'text',
    confidence DECIMAL(5,4)
);

-- audit_results: audit conclusions per image
CREATE TABLE audit_results (
    id BIGSERIAL PRIMARY KEY,
    image_id BIGINT REFERENCES voucher_images(id),
    batch_id BIGINT REFERENCES batches(id),
    risk_rating VARCHAR(10) DEFAULT '低风险',
    audit_conclusion VARCHAR(20) DEFAULT '通过',
    risk_score DECIMAL(6,4),
    rule_details JSONB,
    audit_summary TEXT,
    violation_items JSONB
);

-- audit_rules: configurable audit rule engine
CREATE TABLE audit_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(200),
    rule_type VARCHAR(50),
    condition_expr TEXT NOT NULL,
    risk_rating VARCHAR(10),
    audit_conclusion VARCHAR(20)
);

-- pipeline_logs: full pipeline trace
CREATE TABLE pipeline_logs (
    id BIGSERIAL PRIMARY KEY,
    image_id BIGINT REFERENCES voucher_images(id),
    batch_id BIGINT REFERENCES batches(id),
    stage VARCHAR(20),
    status VARCHAR(20),
    message TEXT,
    duration_ms INT
);
```

---

## [API_ENDPOINTS]

### Server1: app.py @:5000

```
GET  /                                     → dashboard.html
GET  /api/audit_data?sort=&order=&search=  → JSON[audit_records]  (with sort & filter)
GET  /api/audit_record/<int:id>            → JSON{single_record_detail}
GET  /api/statistics                       → JSON{total, risk_distribution, pass_rate}
POST /api/ask_ai                           → JSON{answer}  (non-streaming audit tutor)
GET  /api/ask_ai_stream?record_id=&mode=   → SSE stream  (streaming audit tutor)
GET  /api/knowledge_base                   → JSON[kb_rules]
```

### Server2: web_app.py @:5001

```
GET  /                                     → index.html (CPA Q&A)
GET  /admin                                → admin.html (knowledge base admin)
GET  /kb_browser                           → kb_browser.html
GET  /agents                               → agents.html
GET  /teams                                → teams.html
GET  /team_chat                            → team_chat.html
GET  /knowledge_base                       → knowledge_base.html
GET  /settings                             → settings.html

POST /api/chat                             → Socket.IO stream  (CPA Q&A)
GET  /api/chat_history                     → JSON[qa_records]
POST /api/search                           → JSON[search_results]  (mode: vector/bm25/hybrid/graph)

GET  /api/config                           → JSON{model_config}
POST /api/config/save                      → save model_config.json

GET  /api/cpa_knowledge/list               → JSON[paginated knowledge]
GET  /api/cpa_knowledge/detail/<id>        → JSON{knowledge_detail}
POST /api/cpa_knowledge/delete             → delete knowledge entry
GET  /api/cpa_knowledge/stats              → JSON{knowledge_stats}
GET  /api/cpa_knowledge/audit_list         → JSON[audit_tutor_records]
POST /api/cpa_knowledge/audit_delete       → delete audit record

GET  /api/cpa_knowledge/audit_tutor_list   → JSON[audit_tutor_records]
GET  /api/cpa_knowledge/audit_tutor_detail/<id> → JSON{audit_record_detail}

GET  /api/audit_tutor_stream?record_id=&question=&history= → SSE stream
GET  /api/audit_chat_history/<int:record_id>             → JSON[chat_history]
POST /api/audit_chat_history/<int:record_id>/clear       → delete history

GET  /api/dream/list                       → JSON[dream_knowledge]
POST /api/dream/save                       → save dream knowledge
POST /api/dream/consolidate                → run consolidation
GET  /api/dream/stats                      → JSON{dream_stats}

GET/POST/PUT/DELETE /api/agents/<id>       → Agent CRUD
GET/POST/PUT/DELETE /api/teams/<id>        → Team CRUD
POST /api/team/run                         → JSON{team_run_result}
GET  /api/team/run_stream                  → SSE stream (team run)

Static: /images/<path:filename>            → serve uploaded images
```

---

## [KEY_FUNCTION_SIGNATURES]

### web_app.py (CPA Q&A Server)

```python
# Database
def get_db_connection() -> psycopg2.connection  # cpa_knowledge DB
def get_audit_connection() -> psycopg2.connection | None  # audit_ocr DB

# Config
def load_model_config() -> dict
def get_deepseek_config() -> dict[api_key, api_url, model, reason_model]

# Embedding
def get_ollama_embedding(text: str) -> list[float] | None  # 4096d vector

# Knowledge search (4 modes)
def search_knowledge_base(query: str, mode: str='vector', top_k: int=10, ...) -> list[dict]
  # mode in {'vector','bm25','hybrid','graph'}
  # hybrid = 0.7*vector_score + 0.3*bm25_score

# LLM calls
def call_deepseek_stream(prompt: str, question: str, context: str='', use_reason: bool=False, history: list|None=None) -> Generator[str]
def call_deepseek_api(prompt: str, question: str, context: str='', use_reason: bool=False, history: list|None=None) -> str

# QA history
def save_qa_history(session_id: str, question: str, answer: str, prompt_key: str='general', referenced_sources: list|None=None) -> int|None
  # returns qa_id (int) or None

def _update_qa_answer(qa_id: int, question: str, answer: str) -> None
  # called after streaming completes to fill in the full answer

# Dream mechanism
from services.dream_service import save_dream_knowledge, search_dream_knowledge, run_dream_consolidation, get_dream_stats
```

### app.py (Audit Dashboard Server)

```python
def get_db_config() -> dict  # audit_ocr DB config
def get_connection() -> psycopg2.connection | None  # audit_ocr
def get_cpa_connection() -> psycopg2.connection | None  # cpa_knowledge
def get_ollama_embedding(text: str) -> list[float] | None
def get_deepseek_config() -> dict

# Proxies to web_app.py
def stream_audit_tutor(record_id: int, question: str, search_mode: str='vector', history: list|None=None) -> Generator[str]
  # calls http://localhost:5001/api/audit_tutor_stream
```

### services/ollama_client.py

```python
def call_model(prompt: str, model: str, provider: str='ollama', ...) -> str
  # routes to correct provider: ollama/deepseek/zhipu/qwen/openai/doubao

def call_model_stream(prompt: str, model: str, provider: str='ollama', ...) -> Generator[str]
def get_available_providers() -> list[str]
```

### services/ocr_engine.py

```python
def audit_ocr_recognize(image_path: str, provider: str='ollama', model: str='qwen3.5:latest', retry_count: int=3) -> dict
  # Returns: {status, doc_type, ocr_text, extracted_fields, json_data, raw_response}
  # On failure: calls deepseek-r1:8b for JSON repair

def ocr_single_image(image_path: str, config: dict) -> dict
```

### services/embedding_service.py

```python
def generate_embedding(text: str, model: str='qwen3-embedding:8b') -> list[float]
def batch_generate_embeddings(texts: list[str]) -> list[list[float]]
```

### services/knowledge_retriever.py

```python
def retrieve_knowledge(query: str, top_k: int=5) -> list[dict]
def vector_search(query_embedding: list[float], top_k: int=5) -> list[dict]
def bm25_search(query: str, top_k: int=5) -> list[dict]
```

### services/validator.py

```python
def validate_date(date_str: str) -> tuple[bool, str]
def validate_amount(amount_str: str) -> tuple[bool, float]
def validate_tax_id(tax_id: str) -> bool
def validate_invoice(data: dict) -> list[str]  # returns list of error messages
```

### services/dream_service.py

```python
def save_dream_knowledge(knowledge: str, source_qa_ids: list[int], tags: list[str]=None) -> int
def search_dream_knowledge(query: str, top_k: int=5) -> list[dict]
def run_dream_consolidation(threshold: float=0.85) -> dict  # merge similar knowledge
def get_dream_stats() -> dict
```

### services/agent_service.py

```python
def list_agents() -> list[dict]
def get_agent(agent_id: int) -> dict
def create_agent(data: dict) -> dict  # {name, role_description, model, provider, ...}
def update_agent(agent_id: int, data: dict) -> dict
def delete_agent(agent_id: int) -> bool
```

### services/team_service.py

```python
def list_teams() -> list[dict]
def get_team(team_id: int) -> dict
def create_team(data: dict) -> dict  # {name, description, agent_ids: [...]}
def update_team(team_id: int, data: dict) -> dict
def delete_team(team_id: int) -> bool
```

### services/orchestrator.py

```python
def run_team(team_id: int, user_input: str) -> dict
def run_team_stream(team_id: int, user_input: str) -> Generator[str]
```

---

## [CONFIGURATION_STRUCTURE]

### data/config.json
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
  "RETRY_TIMES": 5,
  "TIMEOUT": 300,
  "DB_HOST": "localhost",
  "DB_PORT": 5432,
  "DB_NAME": "audit_ocr",
  "DB_USER": "postgres",
  "DB_PASSWORD": "admin"
}
```

### data/model_config.json
```json
{
  "current_provider": "ollama",
  "providers": {
    "ollama": { "chat_api": "http://localhost:11434/api/chat", "models": {...} },
    "deepseek": { "api_key": "sk-...", "chat_api": "https://api.deepseek.com/v1/chat/completions", "models": {...} },
    "zhipu": { ... },
    "qwen": { ... },
    "openai": { ... },
    "doubao": { ... }
  }
}
```

### config/settings.py (AppConfig singleton)
```python
class AppConfig:
    # Loads config.json + model_config.json
    # Provides: cfg.MODEL_PROVIDER, cfg.OLLAMA_API_URL, cfg.MAIN_MODEL, ...
    # Functions: set_provider(name) -> switches current provider at runtime
    #            get_provider_config(name) -> returns provider-specific config
```

---

## [DATA_FLOWS]

### Flow 1: Audit OCR Recognition
```
main.py menu
  → batch_processor.scan_images(input_pic/)
  → for each image:
      → ocr_engine.audit_ocr_recognize(image_path)
          → call_model(provider, vision_model, prompt) -> JSON
          → if JSON invalid: call_model(deepseek, fix_model, prompt) -> repaired JSON
          → validator.validate_invoice(extracted_data)
          → return {status, doc_type, ocr_text, fields, confidence}
      → file_ops: save image + txt to output/分类结果/{doc_type}/
      → db_service: INSERT INTO audit_results
      → if error: log to error log + retry queue
  → generate Excel: output/audit_ocr_result.xlsx
```

### Flow 2: CPA RAG Q&A
```
user types question in index.html
  → Socket.IO emit('ask_question', {question, mode})
  → web_app.py receive:
      1. embed question: get_ollama_embedding(question) -> 4096d vector
      2. search cpa_embeddings: pgvector cosine similarity -> top 10 chunks
      3. search cpa_qa_history: pgvector cosine similarity -> top 5 Q&A
      4. search cpa_dream_knowledge: text similarity -> top 3 dream knowledge
      5. build context: combine chunks + QA + dream + book/chapter metadata
      6. call_deepseek_stream(prompt, question, context)
      7. Socket.IO emit('token', chunk) for each token
      8. on stream complete: save_qa_history(question, full_answer)
```

### Flow 3: Audit AI Tutor (cross-server)
```
dashboard.html: user clicks "问问AI" on a audit record
  → app.py GET /api/ask_ai_stream?record_id=&question=
  → app.py proxies to: web_app.py GET /api/audit_tutor_stream?record_id=&question=
  → web_app.py:
      1. load audit record from audit_ocr.audit_results (via get_audit_connection())
      2. retrieve associated KB rules from knowledge_base
      3. search CPA textbooks: search_knowledge_base(question)
      4. build audit-specific prompt: [audit context] + [KB rules] + [CPA knowledge]
      5. call_deepseek_stream(audit_prompt, question, context)
  → SSE stream: data: {"type":"meta","sources":[...]}\n\ndata: {"type":"content","text":"..."}\n\ndata: {"type":"done"}\n
  → on stream complete: save_qa_history(source_type='audit_tutor')
```

### Flow 4: Agent Two-Stage Pipeline (under construction)
```
batch start:
  → create batch in batches table
  → for each image in pic_claw/downloaded/{type}/:
      → INSERT INTO voucher_images (batch_id, file_path, ...)

Stage 1 - Classify (Agent 1):
  → for each image with classify_status='pending':
      → OCR image -> raw text
      → Agent1 prompt: "Classify this document into one of 130 types from document_types"
      → update voucher_images: doc_type_name, category_name, classify_confidence, classify_status='done'
      → INSERT INTO agent_logs (agent_stage='classify', ...)

Stage 2 - Extract (Agent 2):
  → for each image with classify_status='done' AND extract_status='pending':
      → Load document_types.expected_fields for this doc_type
      → Agent2 prompt: prompt template from document_types + expected_fields
      → INSERT INTO extracted_fields (image_id, field_name, field_value, ...)
      → INSERT INTO agent_logs (agent_stage='extract', ...)
      → update voucher_images: extract_status='done'

Stage 3 - Audit:
  → Load audit_rules matching this doc_type
  → Evaluate extracted fields against rules
  → INSERT INTO audit_results (risk_rating, conclusion, ...)
  → update voucher_images: audit_status='done'
```

### Flow 5: Dream Mechanism
```
cron or manual trigger:
  → load recent cpa_qa_history entries (last N days)
  → for each QA pair:
      → call LLM: "Extract key knowledge points from this Q&A"
      → INSERT INTO cpa_dream_knowledge (knowledge, source_qa_ids, tags)
  → run_dream_consolidation():
      → group similar dream knowledge by embedding similarity > 0.85
      → merge: combine text, union source IDs, union tags
      → delete originals, insert merged
```

---

## [IMPORT_RELATIONSHIPS]

```
app.py
  ├── flask, flask_socketio
  ├── psycopg2
  ├── requests
  ├── jieba, re
  ├── config/settings → cfg
  └── services/dream_service → save_dream_knowledge, etc.

web_app.py
  ├── flask, flask_socketio
  ├── psycopg2, numpy
  ├── requests
  ├── jieba, re, uuid
  ├── config/settings → cfg
  ├── services/dream_service → save_dream_knowledge, search_dream_knowledge, run_dream_consolidation, get_dream_stats
  ├── services/agent_service → list_agents, get_agent, create_agent, update_agent, delete_agent
  ├── services/team_service → list_teams, get_team, create_team, update_team, delete_team
  └── services/orchestrator → run_team, run_team_stream

main.py
  ├── config/settings → cfg
  ├── services/ollama_client → call_model
  ├── services/ocr_engine → audit_ocr_recognize
  ├── services/validator → validate_*
  ├── services/db_service → save_*
  └── models/schemas → default_json, deep_merge
```

---

## [PICCLAW.PY CATEGORIES - THE 130 DOCUMENT TYPES]

Located in `pic_claw/picclaw.py`, the CATEGORIES list defines 130 document types across 10 parent categories:

| # | Category | Count | Types |
|---|----------|:-----:|-------|
| 1 | 发票类 | 20 | 增值税专用发票, 增值税普通发票, 增值税电子普通发票, 增值税电子专用发票, 全电发票, 定额发票, 通用机打发票, 红字发票, 机动车销售发票, 二手车销售发票, 农产品收购发票, 服务业发票, 建筑安装业发票, 交通运输业发票, 餐饮发票, 住宿发票, 物业费发票, 水电费发票, 通信费发票, 保险费发票 |
| 2 | 差旅票据类 | 8 | 航空运输电子客票, 铁路车票, 出租车发票, 过路费发票, 停车费发票, 航空运输货运单, 船票, 汽车客运票 |
| 3 | 银行/资金类 | 18 | 银行回单, 银行对账单, 银行进账单, 电汇凭证, 银行承兑汇票, 商业承兑汇票, 转账支票, 现金支票, 利息单, 手续费回单, 信用证, 保函, 贴现凭证, 贷款借据, 还款凭证, 结汇水单, 国际汇款申请书, 现金缴款单 |
| 4 | 函证/审计类 | 14 | 银行询证函, 企业询证函, 应收账款询证函, 应付账款询证函, 存货询证函, 对账函, 催款函, 审计报告, 验资报告, 审计工作底稿, 审计业务约定书, 管理层声明书, 专项审计报告, 内部控制审计报告 |
| 5 | 税务类 | 14 | 完税凭证, 海关进口增值税缴款书, 非税收入票据, 税收缴款书, 纳税申报表, 个人所得税纳税记录, 增值税发票汇总表, 出口退税申报表, 税务登记证, 税务事项通知书, 企业所得税汇算清缴, 印花税票, 房产税申报表, 车辆购置税发票 |
| 6 | 企业内部管理类 | 16 | 费用报销单, 差旅费报销单, 付款申请单, 借款单, 入库单, 出库单, 调拨单, 盘点表, 现金盘点表, 银行存款余额调节表, 内部转账单, 出差申请单, 采购申请单, 验收单, 送货单, 比价单 |
| 7 | 薪酬/人事/合同类 | 10 | 工资单, 劳务费发放表, 社保缴费凭证, 公积金缴存凭证, 考勤表, 年终奖金表, 加班工资表, 劳动合同, 劳务合同, 福利费发放表 |
| 8 | 账簿/分录/报表类 | 12 | 记账凭证, 原始凭证, 收款凭证, 付款凭证, 转账凭证, 总账, 明细账, 日记账, 资产负债表, 利润表, 现金流量表, 所有者权益变动表 |
| 9 | 固定资产/成本类 | 8 | 固定资产卡片, 固定资产报废单, 折旧计算表, 成本计算单, 材料领用单, 固定资产调拨单, 固定资产增加单, 无形资产台账 |
| 10 | 收据/合同/资质类 | 10 | 收据, 捐赠收据, 会费收据, 购销合同, 租赁合同, 营业执照, 开户许可证, 组织机构代码证, 医疗收费票据, 诉讼费票据 |

Each subtype entry format: `("type_name", ["search_keyword1", "search_keyword2", "search_keyword3"])`

---

## [FRONTEND_BINDINGS]

| Template | Route | Server | JS Functions (key) |
|----------|-------|--------|---------------------|
| dashboard.html | `/` | app.py:5000 | renderTable(), getFilteredData(), sortBy(), showRecordDetail(), sendChatMessage(), clearChat(), restoreLastSession() |
| index.html | `/` | web_app.py:5001 | sendMessage(), loadChatHistory(), searchKnowledge(), switchMode(), renderMarkdown() |
| admin.html | `/admin` | web_app.py:5001 | loadKnowledge(), loadAudit(), loadDream(), showDetail(), toggleItem() |
| agents.html | `/agents` | web_app.py:5001 | loadAgents(), createAgent(), editAgent(), deleteAgent() |
| teams.html | `/teams` | web_app.py:5001 | loadTeams(), createTeam(), editTeam(), deleteTeam() |
| team_chat.html | `/team_chat` | web_app.py:5001 | sendTeamMessage(), renderTeamStream() |
| settings.html | `/settings` | web_app.py:5001 | loadConfig(), saveConfig(), testConnection() |

---

## [SSE_STREAM_PROTOCOL]

Used by `/api/ask_ai_stream` and `/api/audit_tutor_stream`

```
event: message
data: {"type":"meta","sources":[{"title":"...","content":"...","relevance":0.95}]}

event: message
data: {"type":"content","text":"审计人员需要关注..."}

event: message
data: {"type":"content","text":"以下是具体分析步骤..."}

event: message
data: {"type":"done"}
```

Client-side parsing (JavaScript):
```javascript
const reader = response.body.getReader();
const decoder = new TextDecoder();
while (true) {
    const { done, value } = await reader.read();
    const text = decoder.decode(value);
    const lines = text.split('\n').filter(l => l.startsWith('data: '));
    for (const line of lines) {
        const data = JSON.parse(line.slice(6));
        if (data.type === 'content') output += data.text;
        if (data.type === 'done') break;
    }
}
```

---

## [SOCKETIO_EVENTS]

Used by CPA Q&A page (index.html <-> web_app.py)

```
Client -> Server:
  emit('ask_question', {question, mode, search_mode, history})

Server -> Client:
  emit('token', {text: "..."})         # streaming token
  emit('source', {title, content})     # referenced source
  emit('done', {})                     # stream complete
  emit('error', {message: "..."})      # error
```

---

## [ERROR_HANDLING_PATTERNS]

```python
# Pattern 1: Database connection with fallback
try:
    conn = psycopg2.connect(...)
except Exception as e:
    print(f"DB error: {e}")
    return None  # caller checks for None

# Pattern 2: OCR retry with JSON repair
for attempt in range(RETRY_TIMES):
    result = call_vision_model(image)
    if is_valid_json(result):
        break
    result = call_fix_model(result)  # deepseek repair
    time.sleep(1)

# Pattern 3: Streaming error handling
try:
    for chunk in call_deepseek_stream(prompt):
        yield chunk
except Exception as e:
    yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"
```

---

## [CONSTANTS]

```python
# From config/constants.py
DOCUMENT_TYPES = [186 types]  # full list of audit document types

# From services/ocr_engine.py (embedded)
RETRY_TIMES = 5
FIX_RETRY_TIMES = 3
PROCESS_RETRY_TIMES = 5
TIMEOUT = 300  # seconds

# From pic_claw/picclaw.py
CATEGORIES = [130 subtypes, each: (name, [keywords])]

# From config/settings.py (defaults)
SUPPORTED_FORMATS = [".png", ".jpg", ".jpeg", ".webp", ".gif"]

# Database connection defaults
DB_HOST = "localhost"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASSWORD = "admin"
```

---

*Generated: 2026-05-16. For AI-assisted development and maintenance of this project.*
