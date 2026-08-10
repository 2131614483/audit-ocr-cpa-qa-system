-- ============================================================
-- 批量审计凭证处理系统 - 数据库建表脚本
-- 数据库: audit_pipeline_db (独立于现有的 cpa_knowledge)
-- ============================================================

-- 1. 批次表
CREATE TABLE IF NOT EXISTS batches (
    id              BIGSERIAL PRIMARY KEY,
    batch_no        VARCHAR(32) NOT NULL UNIQUE,
    batch_name      VARCHAR(200),
    source          VARCHAR(50) DEFAULT 'import',
    total_images    INT DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'pending',
    ocr_progress    INT DEFAULT 0,
    extract_progress INT DEFAULT 0,
    audit_progress  INT DEFAULT 0,
    error_count     INT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    completed_at    TIMESTAMP,
    remark          TEXT
);
CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);
CREATE INDEX IF NOT EXISTS idx_batches_created ON batches(created_at DESC);

-- 2. 大类定义表
CREATE TABLE IF NOT EXISTS document_categories (
    id              SERIAL PRIMARY KEY,
    category_name   VARCHAR(50) NOT NULL UNIQUE,
    sort_order      INT DEFAULT 0,
    description     TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 3. 子类定义表（140+ 种凭证类型）
CREATE TABLE IF NOT EXISTS document_types (
    id              SERIAL PRIMARY KEY,
    category_id     INT NOT NULL REFERENCES document_categories(id),
    type_name       VARCHAR(100) NOT NULL UNIQUE,
    search_keywords JSONB,
    expected_fields JSONB,
    sort_order      INT DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 4. 图片表
CREATE TABLE IF NOT EXISTS voucher_images (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        BIGINT NOT NULL REFERENCES batches(id),
    file_name       VARCHAR(255) NOT NULL,
    file_path       VARCHAR(500) NOT NULL,
    file_md5        VARCHAR(64),
    file_size       BIGINT,
    file_format     VARCHAR(10),
    image_width     INT,
    image_height    INT,
    doc_type_id     INT REFERENCES document_types(id),
    doc_type_name   VARCHAR(100),
    category_name   VARCHAR(50),
    classify_confidence DECIMAL(5,4),
    classify_status VARCHAR(20) DEFAULT 'pending',
    ocr_status      VARCHAR(20) DEFAULT 'pending',
    extract_status  VARCHAR(20) DEFAULT 'pending',
    audit_status    VARCHAR(20) DEFAULT 'pending',
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_vi_batch ON voucher_images(batch_id);
CREATE INDEX IF NOT EXISTS idx_vi_md5 ON voucher_images(file_md5);
CREATE INDEX IF NOT EXISTS idx_vi_ocr_status ON voucher_images(ocr_status);
CREATE INDEX IF NOT EXISTS idx_vi_audit_status ON voucher_images(audit_status);
CREATE INDEX IF NOT EXISTS idx_vi_classify_status ON voucher_images(classify_status);
CREATE INDEX IF NOT EXISTS idx_vi_doc_type ON voucher_images(doc_type_name);
CREATE INDEX IF NOT EXISTS idx_vi_batch_status ON voucher_images(batch_id, ocr_status);

-- 5. Agent 执行日志（分类 + 提取）
CREATE TABLE IF NOT EXISTS agent_logs (
    id              BIGSERIAL PRIMARY KEY,
    image_id        BIGINT REFERENCES voucher_images(id),
    agent_stage     VARCHAR(20) NOT NULL,
    input_summary   TEXT,
    output_json     JSONB,
    llm_model       VARCHAR(50),
    prompt_tokens   INT,
    completion_tokens INT,
    duration_ms     INT,
    status          VARCHAR(20) DEFAULT 'done',
    error_msg       TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_al_image ON agent_logs(image_id);
CREATE INDEX IF NOT EXISTS idx_al_stage ON agent_logs(agent_stage);

-- 6. OCR 识别结果表
CREATE TABLE IF NOT EXISTS ocr_results (
    id              BIGSERIAL PRIMARY KEY,
    image_id        BIGINT NOT NULL REFERENCES voucher_images(id),
    ocr_engine      VARCHAR(32) DEFAULT 'paddle',
    raw_text        TEXT,
    raw_json        JSONB,
    confidence      DECIMAL(5,4),
    text_length     INT,
    processing_time INT,
    status          VARCHAR(20) DEFAULT 'done',
    error_msg       TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ocr_image ON ocr_results(image_id);
CREATE INDEX IF NOT EXISTS idx_ocr_confidence ON ocr_results(confidence DESC);

-- 7. 提取字段表（key-value 动态字段）
CREATE TABLE IF NOT EXISTS extracted_fields (
    id              BIGSERIAL PRIMARY KEY,
    image_id        BIGINT NOT NULL REFERENCES voucher_images(id),
    field_name      VARCHAR(64) NOT NULL,
    field_value     TEXT,
    field_type      VARCHAR(20) DEFAULT 'text',
    confidence      DECIMAL(5,4),
    extract_method  VARCHAR(20) DEFAULT 'llm',
    source_bbox     JSONB,
    source_text     TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ef_image ON extracted_fields(image_id);
CREATE INDEX IF NOT EXISTS idx_ef_name ON extracted_fields(field_name);
CREATE INDEX IF NOT EXISTS idx_ef_name_value ON extracted_fields(field_name, field_value);

-- 8. 审计结果表
CREATE TABLE IF NOT EXISTS audit_results (
    id              BIGSERIAL PRIMARY KEY,
    image_id        BIGINT NOT NULL REFERENCES voucher_images(id),
    batch_id        BIGINT NOT NULL REFERENCES batches(id),
    risk_rating     VARCHAR(10) DEFAULT '低风险',
    audit_conclusion VARCHAR(20) DEFAULT '通过',
    risk_score      DECIMAL(6,4),
    rule_ids        BIGINT[],
    rule_details    JSONB,
    audit_summary   TEXT,
    violation_items JSONB,
    clean_text      TEXT,
    summary_desc    TEXT,
    audit_mode      VARCHAR(20) DEFAULT 'auto',
    auditor         VARCHAR(100),
    audited_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ar_image ON audit_results(image_id);
CREATE INDEX IF NOT EXISTS idx_ar_batch ON audit_results(batch_id);
CREATE INDEX IF NOT EXISTS idx_ar_risk ON audit_results(risk_rating);
CREATE INDEX IF NOT EXISTS idx_ar_conclusion ON audit_results(audit_conclusion);
CREATE INDEX IF NOT EXISTS idx_ar_batch_risk ON audit_results(batch_id, risk_rating);

-- 9. 审计规则表
CREATE TABLE IF NOT EXISTS audit_rules (
    id              SERIAL PRIMARY KEY,
    rule_name       VARCHAR(200) NOT NULL,
    rule_type       VARCHAR(50),
    doc_type_ids    INT[],
    condition_expr  TEXT NOT NULL,
    risk_rating     VARCHAR(10) DEFAULT '中风险',
    audit_conclusion VARCHAR(20) DEFAULT '不通过',
    description     TEXT,
    priority        INT DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ar_rules_active ON audit_rules(is_active);
CREATE INDEX IF NOT EXISTS idx_ar_rules_type ON audit_rules(rule_type);

-- 10. 管道追踪日志表
CREATE TABLE IF NOT EXISTS pipeline_logs (
    id              BIGSERIAL PRIMARY KEY,
    image_id        BIGINT REFERENCES voucher_images(id),
    batch_id        BIGINT REFERENCES batches(id),
    stage           VARCHAR(20) NOT NULL,
    status          VARCHAR(20) NOT NULL,
    message         TEXT,
    duration_ms     INT,
    extra_data      JSONB,
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pl_image ON pipeline_logs(image_id);
CREATE INDEX IF NOT EXISTS idx_pl_batch ON pipeline_logs(batch_id);
CREATE INDEX IF NOT EXISTS idx_pl_stage ON pipeline_logs(stage);
CREATE INDEX IF NOT EXISTS idx_pl_created ON pipeline_logs(created_at DESC);
