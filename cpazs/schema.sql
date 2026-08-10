-- CPA知识库数据库 Schema
-- 数据库名称：cpa_knowledge

-- ============================================
-- 表1：科目表 (cpa_courses)
-- ============================================
CREATE TABLE IF NOT EXISTS cpa_courses (
    id SERIAL PRIMARY KEY,
    course_code VARCHAR(10) NOT NULL UNIQUE,
    course_name VARCHAR(50) NOT NULL,
    course_name_en VARCHAR(100),
    description TEXT,
    exam_weight VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入CPA考试6个科目
INSERT INTO cpa_courses (course_code, course_name, course_name_en, description, exam_weight) VALUES
('KJ', '会计', 'Accounting', '主要测试考生是否具备注册会计师执业所需要的会计专业知识', '最高'),
('SJ', '审计', 'Auditing', '主要测试考生是否具备注册会计师执业所需要的审计专业知识', '较高'),
('SF', '税法', 'Tax Law', '主要测试考生是否具备注册会计师执业所需要的税法专业知识', '中等'),
('CW', '财务成本管理', 'Financial Management', '主要测试考生是否具备注册会计师执业所需要的财务管理专业知识', '中等'),
('JJ', '经济法', 'Economic Law', '主要测试考生是否具备注册会计师执业所需要的经济法专业知识', '较低'),
('ZZ', '公司战略与风险管理', 'Business Strategy', '主要测试考生是否具备注册会计师执业所需要的战略管理专业知识', '较低');

-- ============================================
-- 表2：教材表 (cpa_books)
-- ============================================
CREATE TABLE IF NOT EXISTS cpa_books (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES cpa_courses(id),
    book_name VARCHAR(200) NOT NULL,
    book_type VARCHAR(20) NOT NULL CHECK (book_type IN ('官方教材', '轻一', '法规汇编', '其他')),
    publisher VARCHAR(100),
    publish_year INTEGER,
    md_file_path VARCHAR(500),
    json_file_path VARCHAR(500),
    total_pages INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_books_course ON cpa_books(course_id);
CREATE INDEX IF NOT EXISTS idx_books_type ON cpa_books(book_type);

-- ============================================
-- 表3：章节表 (cpa_chapters)
-- ============================================
CREATE TABLE IF NOT EXISTS cpa_chapters (
    id SERIAL PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES cpa_books(id),
    chapter_number VARCHAR(20) NOT NULL,
    chapter_title VARCHAR(200) NOT NULL,
    parent_id INTEGER REFERENCES cpa_chapters(id),
    page_start INTEGER,
    page_end INTEGER,
    md_content TEXT,
    content_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(book_id, chapter_number)
);

CREATE INDEX IF NOT EXISTS idx_chapters_book ON cpa_chapters(book_id);
CREATE INDEX IF NOT EXISTS idx_chapters_parent ON cpa_chapters(parent_id);
CREATE INDEX IF NOT EXISTS idx_chapters_number ON cpa_chapters(chapter_number);

-- ============================================
-- 表4：知识点表 (cpa_knowledge_points)
-- ============================================
CREATE TABLE IF NOT EXISTS cpa_knowledge_points (
    id SERIAL PRIMARY KEY,
    chapter_id INTEGER NOT NULL REFERENCES cpa_chapters(id),
    point_code VARCHAR(50),
    point_title VARCHAR(200) NOT NULL,
    point_content TEXT,
    importance_level VARCHAR(10) CHECK (importance_level IN ('高', '中', '低')),
    exam_frequency VARCHAR(20) CHECK (exam_frequency IN ('常考', '偶尔', '罕见')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kp_chapter ON cpa_knowledge_points(chapter_id);
CREATE INDEX IF NOT EXISTS idx_kp_importance ON cpa_knowledge_points(importance_level);

-- ============================================
-- 表5：问答对表 (cpa_qa_pairs)
-- ============================================
CREATE TABLE IF NOT EXISTS cpa_qa_pairs (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES cpa_courses(id),
    knowledge_point_id INTEGER REFERENCES cpa_knowledge_points(id),
    question TEXT NOT NULL,
    question_type VARCHAR(20) CHECK (question_type IN ('选择题', '判断题', '简答题', '计算题', '综合题')),
    answer TEXT NOT NULL,
    answer_explain TEXT,
    difficulty_level VARCHAR(10) CHECK (difficulty_level IN ('易', '中', '难')),
    source VARCHAR(100),
    exam_year INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_qa_course ON cpa_qa_pairs(course_id);
CREATE INDEX IF NOT EXISTS idx_qa_knowledge ON cpa_qa_pairs(knowledge_point_id);
CREATE INDEX IF NOT EXISTS idx_qa_difficulty ON cpa_qa_pairs(difficulty_level);
CREATE INDEX IF NOT EXISTS idx_qa_type ON cpa_qa_pairs(question_type);

-- ============================================
-- 表6：向量索引表 (cpa_embeddings)
-- ============================================
CREATE TABLE IF NOT EXISTS cpa_embeddings (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('knowledge_point', 'qa_pair', 'chapter_chunk', 'book_content')),
    source_id INTEGER NOT NULL,
    chunk_content TEXT NOT NULL,
    chunk_summary TEXT,
    embedding BYTEA,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_emb_source ON cpa_embeddings(source_type, source_id);

-- ============================================
-- 表7：用户问答历史表 (cpa_chat_history)
-- ============================================
CREATE TABLE IF NOT EXISTS cpa_chat_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    user_question TEXT NOT NULL,
    bot_answer TEXT,
    referenced_chunks JSONB,
    feedback VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_history_session ON cpa_chat_history(session_id);
CREATE INDEX IF NOT EXISTS idx_history_created ON cpa_chat_history(created_at);

-- ============================================
-- 表8：做梦知识归档表 (cpa_dream_knowledge)
-- ============================================
CREATE TABLE IF NOT EXISTS cpa_dream_knowledge (
    id SERIAL PRIMARY KEY,
    topic VARCHAR(200),
    content TEXT NOT NULL,
    summary VARCHAR(500),
    category VARCHAR(50),
    confidence FLOAT DEFAULT 0.5,
    source_session_id VARCHAR(100),
    source_qa_ids INTEGER[],
    contradictions TEXT,
    dream_batch INTEGER DEFAULT 0,
    embedding VECTOR(4096),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dream_category ON cpa_dream_knowledge(category);
CREATE INDEX IF NOT EXISTS idx_dream_confidence ON cpa_dream_knowledge(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_dream_batch ON cpa_dream_knowledge(dream_batch);

-- ============================================
-- 表9：做梦日志表 (cpa_dream_log)
-- ============================================
CREATE TABLE IF NOT EXISTS cpa_dream_log (
    id SERIAL PRIMARY KEY,
    dream_batch INTEGER,
    dream_type VARCHAR(20) CHECK (dream_type IN ('auto', 'manual')),
    qa_processed INTEGER DEFAULT 0,
    knowledge_created INTEGER DEFAULT 0,
    contradictions_found INTEGER DEFAULT 0,
    status VARCHAR(20) CHECK (status IN ('running', 'done', 'failed')),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP
);

-- ============================================
-- 表10：Agent 配置表 (cpa_agent_configs)
-- ============================================
CREATE TABLE IF NOT EXISTS cpa_agent_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL,
    display_name VARCHAR(100),
    description TEXT,
    prompt_template TEXT NOT NULL,
    model VARCHAR(100) DEFAULT 'deepseek-chat',
    temperature FLOAT DEFAULT 0.3,
    max_tokens INTEGER DEFAULT 2000,
    style VARCHAR(50) DEFAULT 'text',
    skills TEXT[],
    capabilities TEXT,
    decision_rules TEXT,
    icon VARCHAR(20) DEFAULT '🤖',
    is_builtin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 表11：团队配置表 (cpa_team_configs)
-- ============================================
CREATE TABLE IF NOT EXISTS cpa_team_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    workflow_type VARCHAR(30) NOT NULL CHECK (workflow_type IN ('sequential', 'parallel', 'debate', 'pipeline', 'custom')),
    max_rounds INTEGER DEFAULT 3,
    decision_mode VARCHAR(30) DEFAULT 'consensus' CHECK (decision_mode IN ('consensus', 'majority', 'autocratic')),
    is_builtin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 表12：团队成员表 (cpa_team_members)
-- ============================================
CREATE TABLE IF NOT EXISTS cpa_team_members (
    id SERIAL PRIMARY KEY,
    team_id INTEGER REFERENCES cpa_team_configs(id) ON DELETE CASCADE,
    agent_id INTEGER REFERENCES cpa_agent_configs(id) ON DELETE CASCADE,
    role_in_team VARCHAR(100),
    task_rules TEXT,
    priority INTEGER DEFAULT 0,
    input_from TEXT[],
    output_to TEXT[]
);

-- ============================================
-- 表13：工作流运行记录 (cpa_workflow_runs)
-- ============================================
CREATE TABLE IF NOT EXISTS cpa_workflow_runs (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100),
    team_id INTEGER REFERENCES cpa_team_configs(id),
    question TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'running' CHECK (status IN ('running', 'done', 'failed')),
    final_answer TEXT,
    total_cost FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cpa_workflow_steps (
    id SERIAL PRIMARY KEY,
    workflow_id INTEGER REFERENCES cpa_workflow_runs(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    agent_id INTEGER REFERENCES cpa_agent_configs(id),
    agent_name VARCHAR(100),
    input_text TEXT,
    output_text TEXT,
    token_used INTEGER DEFAULT 0,
    duration_sec FLOAT,
    decision TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入内置 Agent
INSERT INTO cpa_agent_configs (name, role, display_name, description, prompt_template, model, temperature, skills, icon, is_builtin) VALUES
('会计专家', 'accounting', '会计专家', '专业会计知识解答',
 '你是一名专业的注册会计师考试辅导专家，请根据提供的知识库内容回答问题。回答要准确、详细，并引用相关知识点。',
 'deepseek-chat', 0.3, ARRAY['knowledge_search', 'qa_history_search'], '📊', TRUE),
('审计专家', 'auditing', '审计专家', '精通审计准则和实务操作',
 '你是一名专业的审计师，精通审计准则和实务操作。请根据知识库内容提供专业的审计相关回答。',
 'deepseek-chat', 0.3, ARRAY['knowledge_search', 'qa_history_search'], '🔍', TRUE),
('税法专家', 'tax', '税法专家', '熟悉中国税法法规',
 '你是一名税务专家，熟悉中国税法法规。请提供准确的税务咨询和法规解释。',
 'deepseek-chat', 0.3, ARRAY['knowledge_search', 'qa_history_search'], '💰', TRUE),
('综合顾问', 'general', '综合顾问', '综合性 CPA 考试辅导',
 '你是一名综合性的CPA考试辅导专家，擅长解答各类会计、审计、税法、财务管理等问题。',
 'deepseek-chat', 0.3, ARRAY['knowledge_search', 'qa_history_search', 'calculator'], '🎯', TRUE),
('财务管理专家', 'finance', '财务管理专家', '精通财务管理和成本分析',
 '你是一名专业的注册会计师考试《财务成本管理》科目辅导专家。精通财务分析、资本预算、成本计算、本量利分析等专业知识。请根据知识库内容提供准确的财务管理和成本分析解答。',
 'deepseek-chat', 0.3, ARRAY['knowledge_search', 'qa_history_search', 'calculator'], '💰', TRUE),
('裁判', 'arbitrator', '裁判', '辩论裁决专家，主持多专家讨论并做出最终裁决',
 '你是一名公正的辩论裁决专家。你的职责是：\n1. 认真听取各方的观点和论据\n2. 指出各方论据的强弱之处\n3. 基于事实和专业知识做出公正裁决\n4. 给出清晰、有依据的最终结论\n\n请保持中立客观，不偏袒任何一方。',
 'deepseek-chat', 0.3, ARRAY['knowledge_search', 'qa_history_search'], '⚖️', TRUE)
ON CONFLICT DO NOTHING;

-- 插入内置团队
INSERT INTO cpa_team_configs (name, description, workflow_type, max_rounds, decision_mode, is_builtin) VALUES
('完整审计工作流', '从审计风险识别到报告输出的完整审计分析流程', 'sequential', 3, 'consensus', TRUE),
('多角度分析', '多个专家同时分析同一问题，汇总不同角度观点', 'parallel', 3, 'consensus', TRUE),
('辩论式审查', '会计与审计专家辩论，综合顾问裁决', 'debate', 3, 'consensus', TRUE)
ON CONFLICT DO NOTHING;