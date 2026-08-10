# 审计OCR+CPA问答综合系统（端口 5005）

## 系统概述

集成 CPA 知识库问答与审计 OCR 数据仪表盘的综合系统。基于 Flask + Socket.IO，提供 CPA 智能问答、审计数据统计可视化、凭证记录管理、AI 审计辅导四大核心功能。连接 `audit_pipeline_db`（审计流水线数据库）和 `cpa_knowledge`（CPA知识库）两个 PostgreSQL 数据库。

**启动入口**：`web_app_5005.py`  
**服务端口**：5005

---

## 页面路由

| 路由 | 模板 | 功能说明 |
|------|------|----------|
| `/` | `index.html` | CPA问答主界面（与5001共用模板） |
| `/dashboard` | `audit_dashboard.html` | **审计OCR仪表盘**：综合概览、统计卡片、类别分布、风险分布、每日金额趋势、凭证记录列表与AI辅导 |
| `/admin` | `admin.html` | 管理后台：知识库浏览、问答历史、审计辅导、知识提炼 |
| `/kb-browser` | `kb_browser.html` | 知识库浏览器 |
| `/knowledge_base` | `knowledge_base.html` | 知识库管理 |
| `/agents` | `agents.html` | Agent管理页面 |
| `/teams` | `teams.html` | 团队协作管理 |
| `/teams/<id>` | `team_chat.html` | 团队聊天协作界面 |
| `/settings` | `settings.html` | 系统设置 |
| `/images/<path>` | - | 图片静态资源 |

---

## API 接口

### 审计仪表盘（本系统独有）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/audit/stats` | GET | 审计统计：凭证总数、10大类别数量、风险分布、审计结论分布、30天每日金额趋势 |
| `/api/audit/list` | POST | 审计记录列表（支持分类/风险/日期区间筛选、分页、全量数据） |
| `/api/audit/detail` | POST | 审计记录详情（含全部字段，联动AI辅导） |
| `/api/audit_data` | GET | 审计数据全量 |
| `/api/audit_record/<id>` | GET | 单条审计记录详情 |

### CPA 知识库

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/cpa_knowledge/search` | POST | CPA知识库搜索（向量/BM25/混合/图谱） |
| `/api/cpa_knowledge/list` | POST | CPA知识库条目列表 |
| `/api/cpa_knowledge/detail` | POST | CPA知识条目详情 |
| `/api/cpa_knowledge/delete` | POST | 删除CPA知识条目 |
| `/api/cpa_knowledge/stats` | POST | 删除CPA知识条目 _knowledge/stats` | GET | CPA知识库统计 |
| `/api/cpa_knowledge/books` | GET | 获取CPA教材列表 |
| `/api/cpa_knowledge/audit_list` | POST | CPA审计知识列表 |
| `/api/cpa_knowledge/audit_delete` | POST | 删除审计知识 |

### 审计AI辅导（本系统独有）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/audit_tutor` | POST | 审计AI辅导（非流式）：结合须知库和专业CPA知识库生成辅导分析 |
| `/api/audit_tutor_stream` | POST | 审计AI辅导（SSE流式）：支持检索模式选择（向量/BM25/混合/图谱）、AI模型选择（默认/推理）、追问对话历史 |
| `/api/ask_ai` | POST | 问问AI（非流式，同audit_tutor） |
| `/api/ask_ai_stream` | POST | 问问AI（流式） |
| `/api/audit_chat_history/<id>` | GET | 获取审计辅导历史 |
| `/api/audit_chat_history/<id>/clear` | POST | 清空审计辅导历史 |

### 知识库管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/knowledge_base/list` | POST | 知识库条目列表 |
| `/api/knowledge_base/delete` | POST | 删除知识条目 |
| `/api/knowledge_base/detail` | POST | 知识条目详情 |
| `/api/knowledge_base/<id>` | GET | 获取指定知识条目 |
| `/api/knowledge_base/batch` | GET | 批量获取知识条目 |
| `/api/all_knowledge_base` | GET | 所有知识条目 |

### 对话管理

| 接口 | 方法 | 说明 | 说明 |
|------|------|------|
| `/api/set_context` | POST | 设置上下文 |
| `/api/set_prompt` | POST | 设置提示词 |
| `/api/toggle_skill` | POST | 切换技能 |
| `/api/clear_history` | POST | 清空历史 |
| `/api/pin_message` | POST | 置顶消息 |
| `/api/unpin_message` | POST | 取消置顶 |
| `/api/get_pinned_context` | POST | 获取置顶上下文 |
| `/api/get_session` | POST | 获取/创建会话 |

### 问答历史

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/qa_history/list` | POST | 问答历史列表 |
| `/api/qa_history/delete` | POST | 删除问答历史 |
| `/api/qa_history/detail` | POST | 问答历史详情 |
| `/api/cpa_qa_history/list` | POST | CPA问答历史 |
| `/api/cpa_qa_history/detail` | POST | CPA问答历史详情 |
| `/api/cpa_qa_history/delete` | POST | 删除CPA问答历史 |
| `/api/stats` | GET | 系统运行统计 |

### 知识图谱与提炼

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/graph/build` | POST | 构建知识图谱 |
| `/api/graph/stats` | GET | 图谱统计 |
| `/api/dream/start` | POST | 启动知识提炼 |
| `/api/dream/status` | GET | 提炼状态 |
| `/api/dream/knowledge/categories` | GET | 提炼分类 |
| `/api/dream/knowledge/list` | POST | 提炼列表 |
| `/api/dream/knowledge/detail` | POST | 提炼详情 |
| `/api/dream/knowledge/delete` | POST | 删除提炼 |

### Agent 与团队

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/agents/list` | GET | Agent列表 |
| `/api/agents/get` | POST | 获取Agent |
| `/api/agents/create` | POST | 创建Agent |
| `/api/agents/update` | POST | 更新Agent |
| `/api/agents/delete` | POST | 删除Agent |
| `/api/teams/list` | GET | 团队列表 |
| `/api/teams/get` | POST | 获取团队 |
| `/api/teams/create` | POST | 创建团队 |
| `/api/teams/update` | POST | 更新团队 |
| `/api/teams/delete` | POST | 删除团队 |
| `/api/teams/run` | POST | 运行团队 |
| `/api/teams/run_stream` | POST | 流式运行团队 |
| `/api/teams/<id>/history` | GET | 运行历史 |
| `/api/teams/<id>/clear` | POST | 清空历史 |

### 模型与系统配置

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/config/get` | GET | 获取模型配置 |
| `/api/config/save` | POST | 保存模型配置 |
| `/api/system_config/get` | GET | 系统配置 |
| `/api/system_config/save` | POST | 保存系统配置 |
| `/api/prompts/get` | GET | 提示词配置 |
| `/api/prompts/save` | POST | 提示词配置 |
| `/api/books/list` | GET | 教材列表 |
| `/api/statistics` | GET | 审计统计 |

### 文件上传

| 接口 | 方法 | 说明 |
|------|------|------|
| `/upload/file` | POST | 文件上传 |
| `/upload/image` | POST | 图片上传 |
| `/uploads/<folder>/<filename>` | GET | 获取上传文件 |

---

## 核心功能

### 1. 审计OCR仪表盘
- **综合概览**：凭证总数、通过率、需关注数、有数据天数
- **统计卡片**：凭证总数、类别数、高风险/中风险/低风险数量、总金额
- **10大类别卡片**：按发票类、差旅票据类、银行/资金类等10大类别展示数量
- **类别分布图**：水平条形图展示各类别数量
- **风险分布图**：水平条形图展示高/中/低风险数量与占比
- **每日金额趋势图**：近30天每日金额柱状图，支持鼠标悬停查看数值和日期
- **审计结论分布**：通过/不通过/需人工/未知的占比展示

### 2. 凭证记录管理
- **多条件筛选**：按分类、风险等级、日期区间筛选
- **全量分页**：无限制全量数据查询，支持首页/尾页/省略号/跳页
- **记录详情弹窗**：展示全部字段，含票据类型、金额、相关方、风险评级、审计结论、风险说明、审计说明、摘要等
- **详情内嵌AI辅导**：在详情弹窗中直接启动审计辅导

### 3. CPA智能审计辅导
- **智能审计辅导分析**：结合CPA知识库进行专业辅导
- **四种检索模式**：
  - 向量检索（语义）
  - BM25（关键词）
  - 混合检索（RRF融合）
  - 知识图谱
- **AI模型选择**：默认模型 / 推理模型
- **SSE流式输出**：实时显示AI生成内容，含来源参考
- **追问功能**：支持多轮对话追问
- **自动分析**：留空自动生成风险点、知识链接、审计建议和学习指引

### 4. CPA知识库问答
- 基于DeepSeek API的智能问答
- 多科目录提示词（会计、审计、税法、经济法、财管、战略、综合）
- 双知识库检索：CPA教材知识库 + 审计知识库
- 消息置顶与上下文管理

### 5. 知识管理与提炼
- 知识库条目管理（增删改查）
- 知识图谱自动构建
- Dream知识提炼与分类

### 6. Agent与团队协作
- Agent智能体管理
- 多Agent团队协作工作流
- 流式与非流式运行

---

## 数据库架构

### audit_pipeline_db（审计流水线数据库）
- `agent1_classify_results`：Agent1分类结果表
- `agent2_extract_*`：按类别拆分的10张提取结果表：
  - `agent2_extract_发票类`
  - `agent2_extract_差旅票据类`
  - `agent2_extract_银行资金类`
  - `agent2_extract_企业内部管理类`
  - `agent2_extract_税务类`
  - `agent2_extract_资产类`
  - `agent2_extract_合同协议类`
  - `agent2_extract_函证审计类`
  - `agent2_extract_证照资质类`
  - `agent2_extract_人事薪酬类`

### cpa_knowledge（CPA知识库数据库）
- `cpa_embeddings`：CPA教材向量化存储
- 存储CPA各科目教材知识的向量嵌入

---

## 后端服务

- **框架**：Flask + Socket.IO
- **数据库**：PostgreSQL × 2（audit_pipeline_db + cpa_knowledge）
- **AI接口**：DeepSeek API（支持多供应商配置）
- **分词**：jieba 中文分词 + CPA专业词典
- **数据存储**：
  - `data/model_config.json`：AI模型配置
  - `data/prompts_config.json`：提示词配置
  - `data/config.json`：系统全局配置
  - `data/cpa_dict.txt`：CPA分词词典
  - `uploads/`：上传文件存储
- **服务模块**：
  - `services/dream_service.py`：知识提炼
  - `services/agent_service.py`：Agent管理
  - `services/team_service.py`：团队管理
  - `services/orchestrator.py`：工作流编排
  - `services/ollama_client.py`：Ollama模型调用

---

## 启动方式

```bash
# 默认端口 5005
python web_app_5005.py
```

服务启动后访问 `http://localhost:5005`，审计仪表盘访问 `http://localhost:5005/dashboard`

---

## 与端口5001的差异

| 对比项 | 5001（web_app.py） | 5005（web_app_5005.py） |
|--------|-------------------|------------------------|
| 端口 | 5001 | 5005 |
| Socket.IO | 完整Socket.IO会话管理 | Socket.IO基础集成 |
| 审计仪表盘 | `dashboard.html`（Bootstrap） | `audit_dashboard.html`（自研UI） |
| 审计数据库 | 连接 `audit_ocr` | 连接 `audit_pipeline_db` |
| 审计API | 基础审计数据接口 | 完整审计仪表盘API（stats/list/detail） |
| 审计辅导 | 基础版 | 完整版（检索模式+模型选择+追问） |
| 首页模板 | `index.html`（含skills技能系统） | `index.html`（skills=[]） |
| 技能系统 | 支持Skills动态启用 | 未启用Skills |