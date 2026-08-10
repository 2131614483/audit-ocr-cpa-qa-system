-- ============================================================
-- Agent2提取结果表 - 按10大类拆分（10个独立表）
-- ============================================================

-- 1. 发票类
CREATE TABLE IF NOT EXISTS agent2_extract_发票类 (
    id                  BIGSERIAL PRIMARY KEY,
    image_id            BIGINT NOT NULL REFERENCES voucher_images(id),
    batch_id            BIGINT NOT NULL REFERENCES batches(id),
    doc_type_name       VARCHAR(100),
    extracted_fields    JSONB,
    field_count         INT DEFAULT 0,
    validation_result   JSONB,
    risk_rating         VARCHAR(10),
    risk_description    TEXT,
    audit_conclusion    VARCHAR(20),
    audit_reason        TEXT,
    summary             TEXT,
    summary_confidence  DECIMAL(5,4),
    model_name          VARCHAR(50),
    raw_output          TEXT,
    duration_ms         INT,
    retry_count         INT DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'done',
    error_msg           TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_a2_fp_image ON agent2_extract_发票类(image_id);
CREATE INDEX IF NOT EXISTS idx_a2_fp_batch ON agent2_extract_发票类(batch_id);
CREATE INDEX IF NOT EXISTS idx_a2_fp_risk ON agent2_extract_发票类(risk_rating);

-- 2. 差旅票据类
CREATE TABLE IF NOT EXISTS agent2_extract_差旅票据类 (
    id                  BIGSERIAL PRIMARY KEY,
    image_id            BIGINT NOT NULL REFERENCES voucher_images(id),
    batch_id            BIGINT NOT NULL REFERENCES batches(id),
    doc_type_name       VARCHAR(100),
    extracted_fields    JSONB,
    field_count         INT DEFAULT 0,
    validation_result   JSONB,
    risk_rating         VARCHAR(10),
    risk_description    TEXT,
    audit_conclusion    VARCHAR(20),
    audit_reason        TEXT,
    summary             TEXT,
    summary_confidence  DECIMAL(5,4),
    model_name          VARCHAR(50),
    raw_output          TEXT,
    duration_ms         INT,
    retry_count         INT DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'done',
    error_msg           TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_a2_cl_image ON agent2_extract_差旅票据类(image_id);
CREATE INDEX IF NOT EXISTS idx_a2_cl_batch ON agent2_extract_差旅票据类(batch_id);
CREATE INDEX IF NOT EXISTS idx_a2_cl_risk ON agent2_extract_差旅票据类(risk_rating);

-- 3. 银行/资金类
CREATE TABLE IF NOT EXISTS agent2_extract_银行资金类 (
    id                  BIGSERIAL PRIMARY KEY,
    image_id            BIGINT NOT NULL REFERENCES voucher_images(id),
    batch_id            BIGINT NOT NULL REFERENCES batches(id),
    doc_type_name       VARCHAR(100),
    extracted_fields    JSONB,
    field_count         INT DEFAULT 0,
    validation_result   JSONB,
    risk_rating         VARCHAR(10),
    risk_description    TEXT,
    audit_conclusion    VARCHAR(20),
    audit_reason        TEXT,
    summary             TEXT,
    summary_confidence  DECIMAL(5,4),
    model_name          VARCHAR(50),
    raw_output          TEXT,
    duration_ms         INT,
    retry_count         INT DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'done',
    error_msg           TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_a2_yh_image ON agent2_extract_银行资金类(image_id);
CREATE INDEX IF NOT EXISTS idx_a2_yh_batch ON agent2_extract_银行资金类(batch_id);
CREATE INDEX IF NOT EXISTS idx_a2_yh_risk ON agent2_extract_银行资金类(risk_rating);

-- 4. 企业内部管理类
CREATE TABLE IF NOT EXISTS agent2_extract_企业内部管理类 (
    id                  BIGSERIAL PRIMARY KEY,
    image_id            BIGINT NOT NULL REFERENCES voucher_images(id),
    batch_id            BIGINT NOT NULL REFERENCES batches(id),
    doc_type_name       VARCHAR(100),
    extracted_fields    JSONB,
    field_count         INT DEFAULT 0,
    validation_result   JSONB,
    risk_rating         VARCHAR(10),
    risk_description    TEXT,
    audit_conclusion    VARCHAR(20),
    audit_reason        TEXT,
    summary             TEXT,
    summary_confidence  DECIMAL(5,4),
    model_name          VARCHAR(50),
    raw_output          TEXT,
    duration_ms         INT,
    retry_count         INT DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'done',
    error_msg           TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_a2_qy_image ON agent2_extract_企业内部管理类(image_id);
CREATE INDEX IF NOT EXISTS idx_a2_qy_batch ON agent2_extract_企业内部管理类(batch_id);
CREATE INDEX IF NOT EXISTS idx_a2_qy_risk ON agent2_extract_企业内部管理类(risk_rating);

-- 5. 税务类
CREATE TABLE IF NOT EXISTS agent2_extract_税务类 (
    id                  BIGSERIAL PRIMARY KEY,
    image_id            BIGINT NOT NULL REFERENCES voucher_images(id),
    batch_id            BIGINT NOT NULL REFERENCES batches(id),
    doc_type_name       VARCHAR(100),
    extracted_fields    JSONB,
    field_count         INT DEFAULT 0,
    validation_result   JSONB,
    risk_rating         VARCHAR(10),
    risk_description    TEXT,
    audit_conclusion    VARCHAR(20),
    audit_reason        TEXT,
    summary             TEXT,
    summary_confidence  DECIMAL(5,4),
    model_name          VARCHAR(50),
    raw_output          TEXT,
    duration_ms         INT,
    retry_count         INT DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'done',
    error_msg           TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_a2_sw_image ON agent2_extract_税务类(image_id);
CREATE INDEX IF NOT EXISTS idx_a2_sw_batch ON agent2_extract_税务类(batch_id);
CREATE INDEX IF NOT EXISTS idx_a2_sw_risk ON agent2_extract_税务类(risk_rating);

-- 6. 资产类
CREATE TABLE IF NOT EXISTS agent2_extract_资产类 (
    id                  BIGSERIAL PRIMARY KEY,
    image_id            BIGINT NOT NULL REFERENCES voucher_images(id),
    batch_id            BIGINT NOT NULL REFERENCES batches(id),
    doc_type_name       VARCHAR(100),
    extracted_fields    JSONB,
    field_count         INT DEFAULT 0,
    validation_result   JSONB,
    risk_rating         VARCHAR(10),
    risk_description    TEXT,
    audit_conclusion    VARCHAR(20),
    audit_reason        TEXT,
    summary             TEXT,
    summary_confidence  DECIMAL(5,4),
    model_name          VARCHAR(50),
    raw_output          TEXT,
    duration_ms         INT,
    retry_count         INT DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'done',
    error_msg           TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_a2_zc_image ON agent2_extract_资产类(image_id);
CREATE INDEX IF NOT EXISTS idx_a2_zc_batch ON agent2_extract_资产类(batch_id);
CREATE INDEX IF NOT EXISTS idx_a2_zc_risk ON agent2_extract_资产类(risk_rating);

-- 7. 合同/协议类
CREATE TABLE IF NOT EXISTS agent2_extract_合同协议类 (
    id                  BIGSERIAL PRIMARY KEY,
    image_id            BIGINT NOT NULL REFERENCES voucher_images(id),
    batch_id            BIGINT NOT NULL REFERENCES batches(id),
    doc_type_name       VARCHAR(100),
    extracted_fields    JSONB,
    field_count         INT DEFAULT 0,
    validation_result   JSONB,
    risk_rating         VARCHAR(10),
    risk_description    TEXT,
    audit_conclusion    VARCHAR(20),
    audit_reason        TEXT,
    summary             TEXT,
    summary_confidence  DECIMAL(5,4),
    model_name          VARCHAR(50),
    raw_output          TEXT,
    duration_ms         INT,
    retry_count         INT DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'done',
    error_msg           TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_a2_ht_image ON agent2_extract_合同协议类(image_id);
CREATE INDEX IF NOT EXISTS idx_a2_ht_batch ON agent2_extract_合同协议类(batch_id);
CREATE INDEX IF NOT EXISTS idx_a2_ht_risk ON agent2_extract_合同协议类(risk_rating);

-- 8. 函证/审计类
CREATE TABLE IF NOT EXISTS agent2_extract_函证审计类 (
    id                  BIGSERIAL PRIMARY KEY,
    image_id            BIGINT NOT NULL REFERENCES voucher_images(id),
    batch_id            BIGINT NOT NULL REFERENCES batches(id),
    doc_type_name       VARCHAR(100),
    extracted_fields    JSONB,
    field_count         INT DEFAULT 0,
    validation_result   JSONB,
    risk_rating         VARCHAR(10),
    risk_description    TEXT,
    audit_conclusion    VARCHAR(20),
    audit_reason        TEXT,
    summary             TEXT,
    summary_confidence  DECIMAL(5,4),
    model_name          VARCHAR(50),
    raw_output          TEXT,
    duration_ms         INT,
    retry_count         INT DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'done',
    error_msg           TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_a2_hz_image ON agent2_extract_函证审计类(image_id);
CREATE INDEX IF NOT EXISTS idx_a2_hz_batch ON agent2_extract_函证审计类(batch_id);
CREATE INDEX IF NOT EXISTS idx_a2_hz_risk ON agent2_extract_函证审计类(risk_rating);

-- 9. 证照/资质类
CREATE TABLE IF NOT EXISTS agent2_extract_证照资质类 (
    id                  BIGSERIAL PRIMARY KEY,
    image_id            BIGINT NOT NULL REFERENCES voucher_images(id),
    batch_id            BIGINT NOT NULL REFERENCES batches(id),
    doc_type_name       VARCHAR(100),
    extracted_fields    JSONB,
    field_count         INT DEFAULT 0,
    validation_result   JSONB,
    risk_rating         VARCHAR(10),
    risk_description    TEXT,
    audit_conclusion    VARCHAR(20),
    audit_reason        TEXT,
    summary             TEXT,
    summary_confidence  DECIMAL(5,4),
    model_name          VARCHAR(50),
    raw_output          TEXT,
    duration_ms         INT,
    retry_count         INT DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'done',
    error_msg           TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_a2_zz_image ON agent2_extract_证照资质类(image_id);
CREATE INDEX IF NOT EXISTS idx_a2_zz_batch ON agent2_extract_证照资质类(batch_id);
CREATE INDEX IF NOT EXISTS idx_a2_zz_risk ON agent2_extract_证照资质类(risk_rating);

-- 10. 人事/薪酬类
CREATE TABLE IF NOT EXISTS agent2_extract_人事薪酬类 (
    id                  BIGSERIAL PRIMARY KEY,
    image_id            BIGINT NOT NULL REFERENCES voucher_images(id),
    batch_id            BIGINT NOT NULL REFERENCES batches(id),
    doc_type_name       VARCHAR(100),
    extracted_fields    JSONB,
    field_count         INT DEFAULT 0,
    validation_result   JSONB,
    risk_rating         VARCHAR(10),
    risk_description    TEXT,
    audit_conclusion    VARCHAR(20),
    audit_reason        TEXT,
    summary             TEXT,
    summary_confidence  DECIMAL(5,4),
    model_name          VARCHAR(50),
    raw_output          TEXT,
    duration_ms         INT,
    retry_count         INT DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'done',
    error_msg           TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_a2_rs_image ON agent2_extract_人事薪酬类(image_id);
CREATE INDEX IF NOT EXISTS idx_a2_rs_batch ON agent2_extract_人事薪酬类(batch_id);
CREATE INDEX IF NOT EXISTS idx_a2_rs_risk ON agent2_extract_人事薪酬类(risk_rating);

-- 10大类统计视图
CREATE OR REPLACE VIEW v_category_extract_stats AS
SELECT '发票类' as category_name, COUNT(*) as total_count FROM agent2_extract_发票类 WHERE batch_id = 4
UNION ALL SELECT '差旅票据类', COUNT(*) FROM agent2_extract_差旅票据类 WHERE batch_id = 4
UNION ALL SELECT '银行/资金类', COUNT(*) FROM agent2_extract_银行资金类 WHERE batch_id = 4
UNION ALL SELECT '企业内部管理类', COUNT(*) FROM agent2_extract_企业内部管理类 WHERE batch_id = 4
UNION ALL SELECT '税务类', COUNT(*) FROM agent2_extract_税务类 WHERE batch_id = 4
UNION ALL SELECT '资产类', COUNT(*) FROM agent2_extract_资产类 WHERE batch_id = 4
UNION ALL SELECT '合同/协议类', COUNT(*) FROM agent2_extract_合同协议类 WHERE batch_id = 4
UNION ALL SELECT '函证/审计类', COUNT(*) FROM agent2_extract_函证审计类 WHERE batch_id = 4
UNION ALL SELECT '证照/资质类', COUNT(*) FROM agent2_extract_证照资质类 WHERE batch_id = 4
UNION ALL SELECT '人事/薪酬类', COUNT(*) FROM agent2_extract_人事薪酬类 WHERE batch_id = 4;
