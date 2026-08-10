"""
创建Agent2按10大类拆分的独立表 + 模拟写入测试数据
不调用图像识别，直接模拟写入
"""
import psycopg2
import json
from datetime import datetime

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "audit_pipeline_db",
    "user": "postgres",
    "password": "admin"
}

sql = """
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
"""

conn = psycopg2.connect(**DB_CONFIG)
with conn.cursor() as cur:
    cur.execute(sql)
    conn.commit()
conn.close()
print("✅ 10大类Agent2提取表创建成功")

# 类别→表名映射
CATEGORY_TABLE_MAP = {
    "发票类": "agent2_extract_发票类",
    "差旅票据类": "agent2_extract_差旅票据类",
    "银行/资金类": "agent2_extract_银行资金类",
    "企业内部管理类": "agent2_extract_企业内部管理类",
    "税务类": "agent2_extract_税务类",
    "资产类": "agent2_extract_资产类",
    "合同/协议类": "agent2_extract_合同协议类",
    "函证/审计类": "agent2_extract_函证审计类",
    "证照/资质类": "agent2_extract_证照资质类",
    "人事/薪酬类": "agent2_extract_人事薪酬类",
}

# 模拟数据
MOCK_DATA = [
    {
        "category": "发票类",
        "doc_type": "增值税专用发票",
        "fields": {
            "invoice_code": "011002300111",
            "invoice_number": "12345678",
            "date": "2024-03-15",
            "total_amount": 11300.00,
            "relevant_party": "北京某某科技有限公司",
            "tax_rate": "13%",
            "tax_id": "91110108MA01XXXXX",
            "bank_info": "中国银行北京分行",
            "serial_number": "SN20240315001",
            "details": "购买办公用品一批",
            "seal_info": {"seal_type": "发票专用章", "seal_number": "110108XXXX", "seal_clarity": "清晰", "joint_seal": "否"},
            "other_info": "N/A"
        },
        "validation": {"date_valid": True, "amount_valid": True, "code_format_valid": True, "no_missing_field": True, "image_normal": True, "no_duplicate": True, "consistent_info": True, "compliance": True, "no_fraud": True},
        "risk_rating": "低风险",
        "risk_description": "发票信息完整，格式规范",
        "audit_conclusion": "通过",
        "audit_reason": "发票要素齐全，金额计算正确",
        "summary": "增值税专用发票，金额11300元",
        "confidence": 0.96
    },
    {
        "category": "差旅票据类",
        "doc_type": "航空运输电子客票行程单",
        "fields": {
            "date": "2024-05-20",
            "total_amount": 1280.00,
            "relevant_party": "张三",
            "serial_number": "ETKT-9991234567890",
            "details": "北京-上海 航班CA1234",
            "other_info": "民航发展基金50元"
        },
        "validation": {"date_valid": True, "amount_valid": True, "code_format_valid": True, "no_missing_field": True, "image_normal": True, "no_duplicate": True, "consistent_info": True, "compliance": True, "no_fraud": True},
        "risk_rating": "低风险",
        "risk_description": "行程单信息完整",
        "audit_conclusion": "通过",
        "audit_reason": "差旅票据合规",
        "summary": "机票行程单，北京至上海",
        "confidence": 0.92
    },
    {
        "category": "银行/资金类",
        "doc_type": "银行回单",
        "fields": {
            "date": "2024-04-10",
            "total_amount": 50000.00,
            "relevant_party": "某某供应商有限公司",
            "bank_info": "工商银行北京中关村支行",
            "serial_number": "2024041000012345",
            "details": "支付货款",
            "seal_info": {"seal_type": "业务专用章", "seal_number": "N/A", "seal_clarity": "清晰", "joint_seal": "否"},
            "other_info": "N/A"
        },
        "validation": {"date_valid": True, "amount_valid": True, "code_format_valid": True, "no_missing_field": True, "image_normal": True, "no_duplicate": True, "consistent_info": True, "compliance": True, "no_fraud": True},
        "risk_rating": "中风险",
        "risk_description": "大额转账需关注",
        "audit_conclusion": "人工复核",
        "audit_reason": "金额较大，建议核实交易背景",
        "summary": "银行回单，支付货款5万元",
        "confidence": 0.88
    },
    {
        "category": "企业内部管理类",
        "doc_type": "付款申请单",
        "fields": {
            "date": "2024-06-01",
            "total_amount": 8500.00,
            "relevant_party": "行政部",
            "details": "6月份办公用品采购付款申请",
            "internal_control_info": {"signer": "李四", "approval_level": "部门经理审批", "attachment_complete": "是"},
            "other_info": "附发票3张"
        },
        "validation": {"date_valid": True, "amount_valid": True, "code_format_valid": True, "no_missing_field": True, "image_normal": True, "no_duplicate": True, "consistent_info": True, "compliance": True, "no_fraud": True},
        "risk_rating": "低风险",
        "risk_description": "内部审批流程完整",
        "audit_conclusion": "通过",
        "audit_reason": "审批手续齐全",
        "summary": "付款申请单，办公用品采购",
        "confidence": 0.94
    },
    {
        "category": "税务类",
        "doc_type": "完税凭证",
        "fields": {
            "date": "2024-04-15",
            "total_amount": 125000.00,
            "relevant_party": "某某科技有限公司",
            "tax_id": "91110108MA01XXXXX",
            "serial_number": "TAX202404150001",
            "details": "2024年Q1企业所得税",
            "other_info": "N/A"
        },
        "validation": {"date_valid": True, "amount_valid": True, "code_format_valid": True, "no_missing_field": True, "image_normal": True, "no_duplicate": True, "consistent_info": True, "compliance": True, "no_fraud": True},
        "risk_rating": "低风险",
        "risk_description": "完税凭证信息完整",
        "audit_conclusion": "通过",
        "audit_reason": "按期缴纳税款",
        "summary": "完税凭证，Q1企业所得税",
        "confidence": 0.91
    },
    {
        "category": "资产类",
        "doc_type": "固定资产盘点表",
        "fields": {
            "date": "2024-03-31",
            "details": "2024年Q1固定资产盘点",
            "asset_info": {"asset_tag": "FA-2024-001", "asset_name": "笔记本电脑", "location": "3楼办公室", "quantity": "50台", "progress": "已盘点"},
            "internal_control_info": {"signer": "王五", "approval_level": "资产管理员", "attachment_complete": "是"},
            "other_info": "盘点差异：无"
        },
        "validation": {"date_valid": True, "amount_valid": True, "code_format_valid": True, "no_missing_field": True, "image_normal": True, "no_duplicate": True, "consistent_info": True, "compliance": True, "no_fraud": True},
        "risk_rating": "低风险",
        "risk_description": "资产盘点记录完整",
        "audit_conclusion": "通过",
        "audit_reason": "账实相符",
        "summary": "固定资产盘点表，Q1盘点",
        "confidence": 0.89
    },
    {
        "category": "合同/协议类",
        "doc_type": "采购合同",
        "fields": {
            "date": "2024-02-20",
            "total_amount": 200000.00,
            "relevant_party": "某某供应商有限公司",
            "details": "年度办公用品采购合同",
            "seal_info": {"seal_type": "合同专用章", "seal_number": "N/A", "seal_clarity": "清晰", "joint_seal": "是"},
            "other_info": "合同期限：2024.02.20-2025.02.19"
        },
        "validation": {"date_valid": True, "amount_valid": True, "code_format_valid": True, "no_missing_field": True, "image_normal": True, "no_duplicate": True, "consistent_info": True, "compliance": True, "no_fraud": True},
        "risk_rating": "中风险",
        "risk_description": "大额合同需关注履约情况",
        "audit_conclusion": "通过",
        "audit_reason": "合同要素齐全，双方签章完整",
        "summary": "采购合同，年度办公用品",
        "confidence": 0.87
    },
    {
        "category": "函证/审计类",
        "doc_type": "银行询证函",
        "fields": {
            "date": "2024-03-31",
            "relevant_party": "工商银行北京中关村支行",
            "details": "2023年度银行存款余额询证",
            "serial_number": "HZ-2024-001",
            "other_info": "回函日期：2024-04-15"
        },
        "validation": {"date_valid": True, "amount_valid": True, "code_format_valid": True, "no_missing_field": True, "image_normal": True, "no_duplicate": True, "consistent_info": True, "compliance": True, "no_fraud": True},
        "risk_rating": "低风险",
        "risk_description": "银行回函确认",
        "audit_conclusion": "通过",
        "audit_reason": "银行回函已确认",
        "summary": "银行询证函，存款余额确认",
        "confidence": 0.93
    },
    {
        "category": "证照/资质类",
        "doc_type": "营业执照",
        "fields": {
            "date": "2023-06-15",
            "relevant_party": "某某科技有限公司",
            "license_info": {"unified_social_credit_code": "91110108MA01XXXXX", "legal_person": "赵六", "valid_period": "2023-06-15至长期"},
            "other_info": "注册资本：1000万元"
        },
        "validation": {"date_valid": True, "amount_valid": True, "code_format_valid": True, "no_missing_field": True, "image_normal": True, "no_duplicate": True, "consistent_info": True, "compliance": True, "no_fraud": True},
        "risk_rating": "低风险",
        "risk_description": "营业执照有效",
        "audit_conclusion": "通过",
        "audit_reason": "证照在有效期内",
        "summary": "营业执照，统一社会信用代码",
        "confidence": 0.95
    },
    {
        "category": "人事/薪酬类",
        "doc_type": "工资表",
        "fields": {
            "date": "2024-05-31",
            "total_amount": 350000.00,
            "relevant_party": "全体员工",
            "details": "2024年5月工资发放表",
            "internal_control_info": {"signer": "人力资源部", "approval_level": "总经理审批", "attachment_complete": "是"},
            "other_info": "人数：45人"
        },
        "validation": {"date_valid": True, "amount_valid": True, "code_format_valid": True, "no_missing_field": True, "image_normal": True, "no_duplicate": True, "consistent_info": True, "compliance": True, "no_fraud": True},
        "risk_rating": "低风险",
        "risk_description": "工资表信息完整",
        "audit_conclusion": "通过",
        "audit_reason": "工资发放合规",
        "summary": "5月工资表，45人合计35万",
        "confidence": 0.90
    },
]

# 写入模拟数据
conn = psycopg2.connect(**DB_CONFIG)
with conn.cursor() as cur:
    # 先获取batch 4的image_id列表
    cur.execute("SELECT id, doc_type_name, category_name FROM voucher_images WHERE batch_id = 4 LIMIT 20")
    images = cur.fetchall()
    
    for i, mock in enumerate(MOCK_DATA):
        if i >= len(images):
            break
        
        image_id = images[i][0]
        table_name = CATEGORY_TABLE_MAP.get(mock["category"])
        
        if not table_name:
            print(f"⚠️ 未知类别: {mock['category']}")
            continue
        
        sql_insert = f"""
            INSERT INTO {table_name} (
                image_id, batch_id, doc_type_name, extracted_fields, field_count,
                validation_result, risk_rating, risk_description, audit_conclusion,
                audit_reason, summary, summary_confidence, model_name, duration_ms,
                retry_count, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        field_count = len([v for v in mock["fields"].values() if v != "N/A" and not isinstance(v, dict)])
        for v in mock["fields"].values():
            if isinstance(v, dict):
                field_count += len([vv for vv in v.values() if vv != "N/A"])
        
        cur.execute(sql_insert, (
            image_id, 4, mock["doc_type"],
            json.dumps(mock["fields"], ensure_ascii=False), field_count,
            json.dumps(mock["validation"], ensure_ascii=False),
            mock["risk_rating"], mock["risk_description"],
            mock["audit_conclusion"], mock["audit_reason"],
            mock["summary"], mock["confidence"],
            "GLM-4.6V-FlashX", 5000, 0, "done"
        ))
    
    conn.commit()
conn.close()
print(f"✅ 模拟写入 {len(MOCK_DATA)} 条Agent2提取数据到10大类表")

# 打印统计
conn = psycopg2.connect(**DB_CONFIG)
with conn.cursor() as cur:
    for cat, table in CATEGORY_TABLE_MAP.items():
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE batch_id = 4")
        cnt = cur.fetchone()[0]
        print(f"  {cat}: {cnt}条")
conn.close()