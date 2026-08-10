"""
创建Agent1和Agent2结果表
"""
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "audit_pipeline_db",
    "user": "postgres",
    "password": "admin"
}

sql = """
-- Agent1 分类结果表
CREATE TABLE IF NOT EXISTS agent1_classify_results (
    id                  BIGSERIAL PRIMARY KEY,
    image_id            BIGINT NOT NULL REFERENCES voucher_images(id),
    batch_id            BIGINT NOT NULL REFERENCES batches(id),
    
    -- 分类结果
    predicted_type      VARCHAR(100),
    predicted_category  VARCHAR(50),
    confidence          DECIMAL(5,4),
    reasoning           TEXT,
    
    -- 真实值（用于评估）
    actual_type         VARCHAR(100),
    actual_category     VARCHAR(50),
    
    -- 是否匹配
    is_correct          BOOLEAN,
    
    -- 模型信息
    model_name          VARCHAR(50),
    prompt_text         TEXT,
    raw_output          TEXT,
    duration_ms         INT,
    retry_count         INT DEFAULT 0,
    
    -- 状态
    status              VARCHAR(20) DEFAULT 'done',
    error_msg           TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_a1cr_image ON agent1_classify_results(image_id);
CREATE INDEX IF NOT EXISTS idx_a1cr_batch ON agent1_classify_results(batch_id);
CREATE INDEX IF NOT EXISTS idx_a1cr_correct ON agent1_classify_results(is_correct);
CREATE INDEX IF NOT EXISTS idx_a1cr_type ON agent1_classify_results(predicted_type);

-- Agent2 提取结果表（按10大类统一管理）
CREATE TABLE IF NOT EXISTS agent2_extract_results (
    id                  BIGSERIAL PRIMARY KEY,
    image_id            BIGINT NOT NULL REFERENCES voucher_images(id),
    batch_id            BIGINT NOT NULL REFERENCES batches(id),
    
    -- 所属大类（10大类之一）
    category_name       VARCHAR(50) NOT NULL,
    doc_type_name       VARCHAR(100),
    
    -- 提取的字段（JSONB存储完整提取结果）
    extracted_fields    JSONB,
    field_count         INT DEFAULT 0,
    
    -- 验证结果
    validation_result   JSONB,
    
    -- 风险评估
    risk_rating         VARCHAR(10),
    risk_description    TEXT,
    audit_conclusion    VARCHAR(20),
    audit_reason        TEXT,
    
    -- 摘要
    summary             TEXT,
    summary_confidence  DECIMAL(5,4),
    
    -- 模型信息
    model_name          VARCHAR(50),
    prompt_text         TEXT,
    raw_output          TEXT,
    duration_ms         INT,
    retry_count         INT DEFAULT 0,
    
    -- 状态
    status              VARCHAR(20) DEFAULT 'done',
    error_msg           TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_a2er_image ON agent2_extract_results(image_id);
CREATE INDEX IF NOT EXISTS idx_a2er_batch ON agent2_extract_results(batch_id);
CREATE INDEX IF NOT EXISTS idx_a2er_category ON agent2_extract_results(category_name);
CREATE INDEX IF NOT EXISTS idx_a2er_risk ON agent2_extract_results(risk_rating);
CREATE INDEX IF NOT EXISTS idx_a2er_conclusion ON agent2_extract_results(audit_conclusion);

-- 10大类统计视图
CREATE OR REPLACE VIEW v_category_extract_stats AS
SELECT 
    category_name,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE status = 'done') as success_count,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
    AVG(field_count) as avg_fields,
    COUNT(*) FILTER (WHERE risk_rating = '高风险') as high_risk_count,
    COUNT(*) FILTER (WHERE risk_rating = '中风险') as medium_risk_count,
    COUNT(*) FILTER (WHERE risk_rating = '低风险') as low_risk_count,
    COUNT(*) FILTER (WHERE audit_conclusion = '通过') as pass_count,
    COUNT(*) FILTER (WHERE audit_conclusion = '不通过') as fail_count,
    COUNT(*) FILTER (WHERE audit_conclusion = '人工复核') as review_count
FROM agent2_extract_results
GROUP BY category_name
ORDER BY category_name;

-- 分类准确率统计视图
CREATE OR REPLACE VIEW v_classify_accuracy_stats AS
SELECT 
    batch_id,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE is_correct = true) as correct_count,
    COUNT(*) FILTER (WHERE is_correct = false) as incorrect_count,
    ROUND(COUNT(*) FILTER (WHERE is_correct = true)::numeric / NULLIF(COUNT(*), 0) * 100, 2) as accuracy_pct,
    AVG(confidence) as avg_confidence
FROM agent1_classify_results
GROUP BY batch_id
ORDER BY batch_id;
"""

conn = psycopg2.connect(**DB_CONFIG)
with conn.cursor() as cur:
    cur.execute(sql)
    conn.commit()
conn.close()
print("✅ Agent1和Agent2结果表创建成功")