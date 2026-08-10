"""
为10大类Agent2提取表添加独立字段列，并从JSONB解析填充
"""
# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "audit_pipeline_db",
    "user": "postgres",
    "password": "admin"
}

tables = [
    "agent2_extract_发票类",
    "agent2_extract_差旅票据类",
    "agent2_extract_银行资金类",
    "agent2_extract_企业内部管理类",
    "agent2_extract_税务类",
    "agent2_extract_资产类",
    "agent2_extract_合同协议类",
    "agent2_extract_函证审计类",
    "agent2_extract_证照资质类",
    "agent2_extract_人事薪酬类",
]

columns_sql = """
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_date DATE;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_amount NUMERIC(15,2);
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_party VARCHAR(200);
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_tax_id VARCHAR(50);
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_serial_no VARCHAR(100);
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_details TEXT;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_bank_info VARCHAR(200);
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_tax_rate VARCHAR(20);
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_invoice_code VARCHAR(50);
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_invoice_no VARCHAR(50);
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_seal_type VARCHAR(50);
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_seal_clarity VARCHAR(20);
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_joint_seal VARCHAR(10);
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS f_other TEXT;
"""

fill_sql = """
UPDATE {table} SET
    f_date = NULLIF(extracted_fields->>'date', 'N/A')::DATE,
    f_amount = NULLIF(extracted_fields->>'total_amount', 'N/A')::NUMERIC,
    f_party = NULLIF(extracted_fields->>'relevant_party', 'N/A'),
    f_tax_id = NULLIF(extracted_fields->>'tax_id', 'N/A'),
    f_serial_no = NULLIF(extracted_fields->>'serial_number', 'N/A'),
    f_details = NULLIF(extracted_fields->>'details', 'N/A'),
    f_bank_info = NULLIF(extracted_fields->>'bank_info', 'N/A'),
    f_tax_rate = NULLIF(extracted_fields->>'tax_rate', 'N/A'),
    f_invoice_code = NULLIF(extracted_fields->>'invoice_code', 'N/A'),
    f_invoice_no = NULLIF(extracted_fields->>'invoice_number', 'N/A'),
    f_seal_type = NULLIF(extracted_fields->'seal_info'->>'seal_type', 'N/A'),
    f_seal_clarity = NULLIF(extracted_fields->'seal_info'->>'seal_clarity', 'N/A'),
    f_joint_seal = NULLIF(extracted_fields->'seal_info'->>'joint_seal', 'N/A'),
    f_other = NULLIF(extracted_fields->>'other_info', 'N/A')
WHERE f_date IS NULL;
"""

conn = psycopg2.connect(**DB_CONFIG)
with conn.cursor() as cur:
    for table in tables:
        cur.execute(columns_sql.format(table=table))
        cur.execute(fill_sql.format(table=table))
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        cnt = cur.fetchone()[0]
        print(f"  ✅ {table}: 添加14个独立字段，{cnt}条数据已解析")
    conn.commit()

    # 创建统一视图
    cur.execute("""
        CREATE OR REPLACE VIEW v_all_extract_fields AS
        SELECT '发票类' as category, doc_type_name, f_date, f_amount, f_party, f_tax_id, f_serial_no, f_details, f_bank_info, f_tax_rate, f_invoice_code, f_invoice_no, f_seal_type, f_seal_clarity, f_joint_seal, f_other, risk_rating, audit_conclusion, summary, image_id, batch_id FROM agent2_extract_发票类
        UNION ALL SELECT '差旅票据类', doc_type_name, f_date, f_amount, f_party, f_tax_id, f_serial_no, f_details, f_bank_info, f_tax_rate, f_invoice_code, f_invoice_no, f_seal_type, f_seal_clarity, f_joint_seal, f_other, risk_rating, audit_conclusion, summary, image_id, batch_id FROM agent2_extract_差旅票据类
        UNION ALL SELECT '银行/资金类', doc_type_name, f_date, f_amount, f_party, f_tax_id, f_serial_no, f_details, f_bank_info, f_tax_rate, f_invoice_code, f_invoice_no, f_seal_type, f_seal_clarity, f_joint_seal, f_other, risk_rating, audit_conclusion, summary, image_id, batch_id FROM agent2_extract_银行资金类
        UNION ALL SELECT '企业内部管理类', doc_type_name, f_date, f_amount, f_party, f_tax_id, f_serial_no, f_details, f_bank_info, f_tax_rate, f_invoice_code, f_invoice_no, f_seal_type, f_seal_clarity, f_joint_seal, f_other, risk_rating, audit_conclusion, summary, image_id, batch_id FROM agent2_extract_企业内部管理类
        UNION ALL SELECT '税务类', doc_type_name, f_date, f_amount, f_party, f_tax_id, f_serial_no, f_details, f_bank_info, f_tax_rate, f_invoice_code, f_invoice_no, f_seal_type, f_seal_clarity, f_joint_seal, f_other, risk_rating, audit_conclusion, summary, image_id, batch_id FROM agent2_extract_税务类
        UNION ALL SELECT '资产类', doc_type_name, f_date, f_amount, f_party, f_tax_id, f_serial_no, f_details, f_bank_info, f_tax_rate, f_invoice_code, f_invoice_no, f_seal_type, f_seal_clarity, f_joint_seal, f_other, risk_rating, audit_conclusion, summary, image_id, batch_id FROM agent2_extract_资产类
        UNION ALL SELECT '合同/协议类', doc_type_name, f_date, f_amount, f_party, f_tax_id, f_serial_no, f_details, f_bank_info, f_tax_rate, f_invoice_code, f_invoice_no, f_seal_type, f_seal_clarity, f_joint_seal, f_other, risk_rating, audit_conclusion, summary, image_id, batch_id FROM agent2_extract_合同协议类
        UNION ALL SELECT '函证/审计类', doc_type_name, f_date, f_amount, f_party, f_tax_id, f_serial_no, f_details, f_bank_info, f_tax_rate, f_invoice_code, f_invoice_no, f_seal_type, f_seal_clarity, f_joint_seal, f_other, risk_rating, audit_conclusion, summary, image_id, batch_id FROM agent2_extract_函证审计类
        UNION ALL SELECT '证照/资质类', doc_type_name, f_date, f_amount, f_party, f_tax_id, f_serial_no, f_details, f_bank_info, f_tax_rate, f_invoice_code, f_invoice_no, f_seal_type, f_seal_clarity, f_joint_seal, f_other, risk_rating, audit_conclusion, summary, image_id, batch_id FROM agent2_extract_证照资质类
        UNION ALL SELECT '人事/薪酬类', doc_type_name, f_date, f_amount, f_party, f_tax_id, f_serial_no, f_details, f_bank_info, f_tax_rate, f_invoice_code, f_invoice_no, f_seal_type, f_seal_clarity, f_joint_seal, f_other, risk_rating, audit_conclusion, summary, image_id, batch_id FROM agent2_extract_人事薪酬类;
    """)
    conn.commit()

conn.close()
print("\n✅ 完成！10大类表均已添加独立字段并解析填充")
print("📊 统一查询视图: v_all_extract_fields")
