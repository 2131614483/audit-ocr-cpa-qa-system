# CPA 知识库问答系统（端口 5001）

## 系统概述

基于 Flask + Socket.IO 的 CPA（注册会计师）知识库智能问答系统，提供流式回答、多轮对话、知识库管理、知识图谱构建、团队协作Agent等功能。面向 CPA 考生和审计从业人员，支持多种检索模式的知识库查询与 AI 辅导。

**启动入口**：`web_app.py`  
**服务端口**：5001

---

## 页面路由

| 路由 | 模板 | 功能说明 |
|------|------|----------|
| `/` | `index.html` | CPA问答主界面，支持对话交互、流式输出、双知识库展示、思考模式 |
| `/admin` | `admin.html` | 管理后台，整合知识库浏览、问答历史、审计、审计辅导、知识提炼四个标签页 |
| `/kb-browser` | `kb_browser.html` | 知识库浏览器 |
| `/knowledge_base` | `knowledge_base.html` | 知识库管理页面 |
| `/agents` | `agents.html` | Agent（智能体）管理页面 |
| `/teams` | `teams.html` | 团队协作管理页面 |
| `/teams/<id>` | `team_chat.html` | 指定团队的聊天协作界面 |
| `/settings` | `settings.html` | .html` 系统设置页面 |
| `/dashboard` | `dashboard.html` | 审计数据仪表盘（基于Bootstrap） |
| `/images/<path>` | - | 图片资源静态文件服务 |

---

## API 接口

### 知识库相关

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/knowledge_base/list` | POST | 知识库条目列表（支持分页、搜索、来源筛选） |
| `/api/knowledge_base/delete` | POST | 删除知识库条目 |
| `/api/knowledge_base/detail` | POST | 知识库条目详情 |
| `/api/knowledge_base/browse` | POST | 浏览知识库 |
| `/api/knowledge_base/<id>` | GET | 获取指定知识条目 |
| `/api/knowledge_base/batch` | GET | 批量获取知识库条目 |
| `/api/all_knowledge_base` | GET | 获取所有知识库条目 |

### CPA 知识库

| 接口 | 方法 | 说明 |
|------|------|------|
|--|------|
| `/api/cpa_knowledge/search` | POST | 搜索CPA知识库（支持向量/BM25/混合/图谱四种模式） |
| `/api/cpa_knowledge/list` | POST | CPA知识库条目列表 |
| `/api/cpa_knowledge/detail` | POST | CPA知识条目详情 |
| `/api/cpa_knowledge/delete` | POST | 删除CPA知识条目 |
| `/api/cpa_knowledge/stats` | GET | CPA知识库统计 |
| `/api/cpa_knowledge/books` | GET | 获取CPA教材列表 |
| `/api/cpa_knowledge/audit_list` | POST | CPA审计知识列表 |
| `/api/cpa_knowledge/audit_delete` | POST | 删除CPA审计知识 |

### 对话与聊天

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/set_context` | POST | 设置对话上下文 |
| `/api/set_prompt` | POST | 设置提示词 |
| `/api/toggle_skill` | POST | 切换技能开关 |
| `/api/clear_history` | POST | 清空对话历史 |
| `/api/pin_message` | POST | 置顶消息 |
| `/api/unpin_message` | POST | 取消置顶 |
| `/api/unpin_message_by_content` | POST | 按内容取消置顶 |
| `/api/get_pinned_context` | POST | 获取置顶上下文 |
| `/api/get_session` | POST | 获取/创建会话 |

### 审计辅导

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/audit_tutor` | POST | 审计AI辅导（非流式，含知识库检索+CPA专业分析） |
| `/api/audit_tutor_stream` | POST | 审计AI辅导（SSE流式响应） |
| `/api/ask_ai` | POST | 问问AI（非流式） |
| `/api/ask_ai_stream` | POST | 问问AI（SSE流式响应） |
| `/api/audit_chat_history/<id>` | GET | 获取审计辅导聊天历史 |
| `/api/audit_chat_history/<id>/clear` | POST | 清空审计辅导聊天历史 |

### 问答历史

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/qa_history/list` | POST | 问答历史列表 |
| `/api/qa_history/delete` | POST |  | POST | 删除问答历史 |
| `/api/qa_history/detail` | POST | 问答历史详情 |
| `/api/cpa_qa_history/list` | POST | CPA问答历史列表 |
| `/api/cpa_qa_history/detail` | POST | CPA问答历史详情 |
| `/api/cpa_qa_history/delete` | POST | 删除CPA问答历史 |

### 知识图谱

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/graph/build` | POST | 构建知识图谱 |
| `/api/graph/stats` | GET | 知识图谱统计 |

### 知识提炼（Dream）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/dream/start` | POST | 启动知识提炼 |
| `/api/dream/status` | GET | 知识提炼状态 |
| `/api/dream/knowledge/categories` | GET | 提炼知识分类 |
| `/api/dream/knowledge/list` | POST | 提炼知识列表 |
| `/api/dream/knowledge/detail` | POST | 提炼知识详情 |
| `/api/dream/knowledge/delete` | POST | 删除提炼知识 |

### 模型与系统配置

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/config/get` | GET | 获取模型配置 |
| `/api/config/save` | POST | 保存模型配置 |
| `/api/system_config/get` | GET | 获取系统配置 |
| `/api/system_config/save` | POST | 保存系统配置 |
| `/api/prompts/get` | GET | 获取提示词配置 |
| `/api/prompts/save` | POST | 保存提示词配置 |
| `/api/books/list` | GET | 获取教材列表 |

### Agent 与团队

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/agents/list` | GET | 获取Agent列表 |
| `/api/agents/get` | POST | 获取单个Agent |
| `/api/agents/create` | POST | 创建Agent |
| `/api/agents/update` | POST | 更新Agent |
| `/api/agents/delete` | POST | 删除Agent |
| `/api/teams/list` | GET | 获取团队列表 |
| `/api/teams/get` | POST | 获取单个团队 |
| `/api/teams/create` | POST | 创建团队 |
| `/api/teams/update` | POST | 更新团队 |
| `/api/teams/delete` | POST | 删除团队 |
| `/api/teams/run` | POST | 运行团队工作流 |
| `/api/teams/run_stream` | POST | 流式运行团队工作流 |
| `/api/teams/<id>/history` | GET | 团队运行历史 |
| `/api/teams/<id>/clear` | POST | 清空团队历史 |

### 审计数据

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/audit_data` | GET | 获取审计数据 |
| `/api/audit_record/<id>` | GET | 获取审计记录详情 |
| `/api/statistics` | GET | 审计统计信息 |
| `/api/stats` | GET | 系统运行统计 |

### 文件上传

| 接口 | 方法 | 说明 |
|------|------|------|
| `/upload/file` | POST | 上传文件 |
| `/upload/image` | POST | 上传图片 |
| `/uploads/<folder>/<filename>` | GET | 获取上传的文件 |

---

## 核心功能

### 1. CPA 智能问答
- 基于 DeepSeek API 的智能对话引擎
- 支持流式（SSE）和非流式两种响应模式
- 多轮对话上下文管理（最近 20 轮）
- 技能系统（Skills）：可动态启用/禁用专业技能
- 提示词管理：支持自定义系统提示词
- 消息置顶：可将重要消息固定在上下文

### 知识库管理
- 双知识库架构：CPA教材知识库 + 审计知识库
- 四种检索模式：
  - **向量检索**：基于语义相似度搜索
  - **BM25检索**：基于关键词匹配
  - **混合检索**：RRF融合排序
  - **知识图谱**：基于实体关系的检索
- 知识库条目管理（增删改查）
- 知识库来源管理（教材、文档等）
- 知识库统计与可视化

### 知识图谱
- 自动从知识库中提取实体和关系
- 支持图谱构建触发和状态查询
- 为知识检索提供关系推理能力

### 知识提炼（Dream）
- 自动从知识库中提炼核心知识点
- 支持分类查看提炼结果
- 提炼状态监控

### Agent 与团队协作
- Agent（智能体）管理：创建、配置、运行专业Agent
- 团队协作：多Agent协同工作流
- 支持流式和非流式两种运行模式
- 团队运行历史记录

### 审计辅导
- 结合CPA知识库进行专业审计辅导分析
- 支持 SSE 流式输出
- 自动分析风险点、知识链接、审计建议和学习指引
- 多检索模式支持（向量/BM25/混合/图谱）

---

## 后端服务

- **框架**：Flask + Socket.IO
- **数据库**：PostgreSQL（cpa_knowledge 数据库）
- **AI接口**：DeepSeek API
- **分词**：jieba 中文分词（含CPA专业词典）
- **数据存储**：
  - `data/model_config.json`：模型配置
  - `data/prompts_config.json`：提示词与技能配置
  - `data/config.json`：系统全局配置
  - `data/cpa_dict.txt`：CPA专业分词词典
  - `uploads/files/`：上传文件存储
  - `uploads/images/`：上传图片存储

---

## 启动方式

```bash
# 默认端口 5001
python web_app.py
```

服务启动后访问 `http://localhost:5001`