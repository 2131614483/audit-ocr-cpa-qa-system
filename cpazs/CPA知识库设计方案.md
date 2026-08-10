# CPA知识库问答系统 - 数据库设计方案

## 一、数据源分析

### 1.1 现有文件结构

```
cpazs/
├── 2026年注册会计师（会计）官方教材/
│   └── auto/
│       ├── 2026年注册会计师（会计）官方教材.md        # 教材正文
│       ├── 2026年注册会计师（会计）官方教材_model.json   # 布局检测结果
│       ├── 2026年注册会计师（会计）官方教材_content_list.json  # 结构化内容列表
│       └── ...（PDF相关文件）
├── 2026年注册会计师（审计）/
├── 2026年注册会计师（税法）/
├── 2026年注册会计师（经济法）/
├── 2026年注册会计师（财务成本管理）/
├── 2026年注册会计师（公司战略与风险管理）/
├── 会计轻一（上/中/下册） (OCR)/
├── 审计轻一（上/中/下册） (OCR)/
└── 战略轻一（上册）（OCR)/
```

### 1.2 教材分类

| 科目编号 | 科目名称 | 教材类型 |
|---------|---------|---------|
| 1 | 会计 | 官方教材 + 轻一 |
| 2 | 审计 | 官方教材 + 轻一 |
| 3 | 税法 | 官方教材 |
| 4 | 财务成本管理 | 官方教材 |
| 5 | 经济法 | 官方教材 |
| 6 | 公司战略与风险管理 | 官方教材 |
| 7 | 经济法规汇编 | 选编教材 |

---

## 二、数据库设计

### 2.1 数据库名称

```sql
CREATE DATABASE cpa_knowledge;
```

### 2.2 表结构设计

#### 表1：cpa_courses（科目表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PRIMARY KEY | 科目ID |
| course_code | VARCHAR(10) | 科目编码，如"KJ"、"SJ" |
| course_name | VARCHAR(50) | 科目名称 |
| course_name_en | VARCHAR(100) | 英文名称 |
| description | TEXT | 科目描述 |
| exam_weight | VARCHAR(20) | 考试权重 |
| created_at | TIMESTAMP | 创建时间 |

#### 表2：cpa_books（教材表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PRIMARY KEY | 教材ID |
| course_id | INTEGER | 所属科目ID |
| book_name | VARCHAR(200) | 教材名称 |
| book_type | VARCHAR(20) | 教材类型：官方教材/轻一/法规汇编 |
| publisher | VARCHAR(100) | 出版社 |
| publish_year | INTEGER | 出版年份 |
| md_file_path | VARCHAR(500) | MD文件路径 |
| json_file_path | VARCHAR(500) | JSON文件路径 |
| total_pages | INTEGER | 总页数 |
| created_at | TIMESTAMP | 创建时间 |

#### 表3：cpa_chapters（章节表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PRIMARY KEY | 章节ID |
| book_id | INTEGER | 所属教材ID |
| chapter_number | VARCHAR(20) | 章节编号，如"1"、"2.1" |
| chapter_title | VARCHAR(200) | 章节标题 |
| parent_id | INTEGER | 父章节ID（用于多级目录） |
| page_start | INTEGER | 起始页码 |
| page_end | INTEGER | 结束页码 |
| md_content | TEXT | MD格式内容 |
| content_hash | VARCHAR(64) | 内容哈希值 |
| created_at | TIMESTAMP | 创建时间 |

#### 表4：cpa_knowledge_points（知识点表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PRIMARY KEY | 知识点ID |
| chapter_id | INTEGER | 所属章节ID |
| point_code | VARCHAR(50) | 知识点编码 |
| point_title | VARCHAR(200) | 知识点标题 |
| point_content | TEXT | 知识点内容 |
| importance_level | VARCHAR(10) | 重要程度：高/中/低 |
| exam_frequency | VARCHAR(20) | 考试频率：常考/偶尔/罕见 |
| embedding | VECTOR(2048) | 向量（可选） |
| created_at | TIMESTAMP | 创建时间 |

#### 表5：cpa_qa_pairs（问答对表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PRIMARY KEY | 问答对ID |
| course_id | INTEGER | 所属科目ID |
| knowledge_point_id | INTEGER | 关联知识点ID |
| question | TEXT | 问题 |
| question_type | VARCHAR(20) | 问题类型：选择/判断/简答/计算 |
| answer | TEXT | 答案 |
| answer_explain | TEXT | 答案解析 |
| difficulty_level | VARCHAR(10) | 难度：易/中/难 |
| source | VARCHAR(100) | 来源：真题/模拟题/练习 |
| year | INTEGER | 所属年份 |
| created_at | TIMESTAMP | 创建时间 |

#### 表6：cpa_embeddings（向量索引表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PRIMARY KEY | 记录ID |
| source_type | VARCHAR(20) | 来源类型：knowledge_point/qa_pair/chunk |
| source_id | INTEGER | 来源记录ID |
| chunk_content | TEXT | 文本块内容 |
| chunk_summary | TEXT | 块摘要 |
| embedding | VECTOR(2048) | 向量嵌入 |
| metadata | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |

---

## 三、向量化方案

### 3.1 文本分块策略

```
分块大小：500-800字符
分块重叠：50-100字符
```

### 3.2 Chunk元数据结构

```json
{
    "course": "会计",
    "book": "2026年注册会计师（会计）官方教材",
    "chapter": "第一章 总论",
    "section": "第一节 会计概述",
    "chunk_index": 3,
    "heading_path": "第一章 总论 > 第一节 会计概述",
    "page_number": 5,
    "source_file": "2026年注册会计师（会计）官方教材.md"
}
```

---

## 四、导入脚本设计

### 4.1 文件清单

```
cpazs/
├── import_cpa_knowledge.py      # 主导入脚本
├── parse_md_chunks.py           # MD分块解析
├── config_cpa.py                # CPA知识库配置
└── requirements.txt              # 依赖
```

### 4.2 导入流程

```
1. 扫描cpazs目录下的所有MD文件
   ↓
2. 解析MD文件结构（章节、标题、段落）
   ↓
3. 按章节分块存储到cpa_chapters表
   ↓
4. 从MD中提取知识点（标题、正文）
   ↓
5. 分块处理并生成向量
   ↓
6. 存储到cpa_embeddings表
```

### 4.3 MD解析规则

```python
# 标题识别
# 一级标题 → 章节（#）
# 二级标题 → 小节（##）
# 三级标题 → 知识点（###）

# 内容提取
# 段落内容 → 知识点内容
# 公式块 → 特殊处理
# 表格 → JSON格式存储
```

---

## 五、使用示例

### 5.1 问答查询流程

```
用户问题 → 向量化 → 相似度检索 → 返回知识点 → 生成回答
```

### 5.2 SQL查询示例

```sql
-- 按科目查询章节
SELECT c.chapter_number, c.chapter_title, b.book_name
FROM cpa_chapters c
JOIN cpa_books b ON c.book_id = b.id
JOIN cpa_courses co ON b.course_id = co.id
WHERE co.course_code = 'KJ'
ORDER BY c.chapter_number;

-- 查询相关知识点
SELECT kp.point_title, kp.point_content
FROM cpa_knowledge_points kp
JOIN cpa_chapters c ON kp.chapter_id = c.id
WHERE c.chapter_number LIKE '1.%';

-- 检索问答对
SELECT q.question, q.answer, q.answer_explain
FROM cpa_qa_pairs q
WHERE q.course_id = 1 AND q.difficulty_level = '中';
```

---

## 六、实施计划

### 阶段一：数据库搭建（1天）
- [ ] 创建数据库和表
- [ ] 编写导入脚本框架

### 阶段二：数据导入（2-3天）
- [ ] 解析MD文件
- [ ] 提取章节和知识点
- [ ] 生成向量嵌入

### 阶段三：API开发（2天）
- [ ] 问答检索API
- [ ] 知识库管理API

### 阶段四：集成测试（1天）
- [ ] 与现有系统集成
- [ ] 功能测试

---

## 七、文件结构

```
cpazs/
├── README.md                    # 本文档
├── config_cpa.py                # 配置文件
├── import_cpa_knowledge.py       # 导入脚本
├── schema.sql                   # 数据库Schema
├── test_query.py                # 测试脚本
└── requirements.txt             # Python依赖
```