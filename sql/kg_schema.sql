-- ============================================
-- 知识图谱 Schema
-- 数据库: cpa_knowledge_graph
-- 所有表以 kg_ 前缀命名，与 cpa_knowledge 的 cpa_* 表隔离
-- ============================================

-- 启用必要扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================
-- 1. 实体表
-- ============================================
CREATE TABLE IF NOT EXISTS kg_entities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    entity_type VARCHAR(30) NOT NULL
        CHECK (entity_type IN ('Concept','Standard','Formula','TaxItem','Question','Chapter','Section')),
    category VARCHAR(50),           -- 会计科目/审计程序/税目税率/财管公式/经济法条/战略框架
    definition TEXT,                -- 定义
    chapter_ref VARCHAR(500),       -- 所属章节引用（如"会计 > 第5章 长期股权投资"）
    source_chunk_ids INT[],         -- 来源chunk ID (对应 cpa_knowledge.cpa_embeddings.id)
    embedding VECTOR(4096),         -- 实体名向量，用于实体链接
    aliases TEXT[],                 -- 别名列表（实体对齐去重用）
    importance VARCHAR(10) DEFAULT '中'
        CHECK (importance IN ('高','中','低')),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, entity_type)
);

-- ============================================
-- 2. 关系表
-- ============================================
CREATE TABLE IF NOT EXISTS kg_relationships (
    id SERIAL PRIMARY KEY,
    source_entity_id INT NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
    target_entity_id INT NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
    relation_type VARCHAR(30) NOT NULL
        CHECK (relation_type IN (
            'derives_from',      -- A的计算依赖B
            'references',        -- A引用准则B
            'contrasts_with',    -- A与B容易混淆
            'prerequisite_of',   -- 学B之前必须先懂A
            'composes',          -- A由B1,B2组成
            'leads_to',          -- A的变动会导致B变动
            'belongs_to',        -- A属于章节B
            'tested_by',         -- A被考题B测试
            'similar_to'         -- A与B相似（跨章节同类概念）
        )),
    description TEXT,             -- 关系说明
    formula TEXT,                 -- 如果是推导关系，存公式
    weight FLOAT DEFAULT 1.0,     -- 关系权重
    confidence FLOAT DEFAULT 0.5, -- LLM抽取置信度
    source_chunk_ids INT[],
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_entity_id, target_entity_id, relation_type)
);

-- ============================================
-- 3. 公式表
-- ============================================
CREATE TABLE IF NOT EXISTS kg_formulas (
    id SERIAL PRIMARY KEY,
    entity_id INT REFERENCES kg_entities(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    expression TEXT NOT NULL,       -- 公式表达式
    inputs JSONB,                   -- ["营业收入", "营业成本"]
    output VARCHAR(200),            -- "毛利润"
    conditions TEXT,                -- 适用条件
    example TEXT,                   -- 计算示例
    source_chunk_ids INT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 4. 易混概念对表
-- ============================================
CREATE TABLE IF NOT EXISTS kg_confusion_pairs (
    id SERIAL PRIMARY KEY,
    entity_a_id INT NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
    entity_b_id INT NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
    distinction TEXT NOT NULL,      -- 区分要点
    typical_question TEXT,          -- 典型考题
    scenario_a TEXT,                -- 概念A的典型使用场景
    scenario_b TEXT,                -- 概念B的典型使用场景
    chapter_ids INT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_a_id, entity_b_id)
);

-- ============================================
-- 5. 社区检测结果表
-- ============================================
CREATE TABLE IF NOT EXISTS kg_communities (
    id SERIAL PRIMARY KEY,
    community_label VARCHAR(100),   -- 社区标签（LLM生成）
    entity_ids INT[],
    summary TEXT,                   -- 社区主题摘要（LLM生成）
    topic_keywords TEXT[],
    modularity_score FLOAT,         -- 模块度得分
    embedding VECTOR(4096),         -- 摘要向量，用于检索
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 6. 图谱构建日志表
-- ============================================
CREATE TABLE IF NOT EXISTS kg_build_log (
    id SERIAL PRIMARY KEY,
    build_type VARCHAR(30) NOT NULL,  -- entity_extraction/relation_extraction/community_detection
    status VARCHAR(20) DEFAULT 'running'
        CHECK (status IN ('running','completed','failed')),
    book_filter VARCHAR(200),         -- 处理的教材范围
    chunks_processed INT DEFAULT 0,
    entities_created INT DEFAULT 0,
    entities_updated INT DEFAULT 0,
    relations_created INT DEFAULT 0,
    formulas_created INT DEFAULT 0,
    confusion_pairs_created INT DEFAULT 0,
    communities_detected INT DEFAULT 0,
    errors JSONB,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP
);

-- ============================================
-- 索引
-- ============================================

-- 实体索引
CREATE INDEX IF NOT EXISTS idx_kg_entities_type ON kg_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_kg_entities_category ON kg_entities(category);
CREATE INDEX IF NOT EXISTS idx_kg_entities_importance ON kg_entities(importance);
CREATE INDEX IF NOT EXISTS idx_kg_entities_name_trgm ON kg_entities USING gin(name gin_trgm_ops);
-- 向量索引（等数据够多后再建，初始可跳过）
-- CREATE INDEX IF NOT EXISTS idx_kg_entities_embedding ON kg_entities USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 关系索引
CREATE INDEX IF NOT EXISTS idx_kg_rel_source ON kg_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_target ON kg_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_type ON kg_relationships(relation_type);
CREATE INDEX IF NOT EXISTS idx_kg_rel_confidence ON kg_relationships(confidence DESC);

-- 公式索引
CREATE INDEX IF NOT EXISTS idx_kg_formulas_entity ON kg_formulas(entity_id);

-- 易混概念索引
CREATE INDEX IF NOT EXISTS idx_kg_confusion_a ON kg_confusion_pairs(entity_a_id);
CREATE INDEX IF NOT EXISTS idx_kg_confusion_b ON kg_confusion_pairs(entity_b_id);

-- 社区索引
-- CREATE INDEX IF NOT EXISTS idx_kg_communities_embedding ON kg_communities USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- 构建日志索引
CREATE INDEX IF NOT EXISTS idx_kg_build_type ON kg_build_log(build_type);
CREATE INDEX IF NOT EXISTS idx_kg_build_status ON kg_build_log(status);
