-- ============================================================
-- Agent2提取表 - 添加独立字段列（从JSONB解析）
-- 方便SQL直接运算和查询
-- ============================================================

-- 通用字段（所有类别都有）
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_date DATE;
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_amount NUMERIC(15,2);
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_party VARCHAR(200);
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_tax_id VARCHAR(50);
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_serial_no VARCHAR(100);
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_details TEXT;
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_bank_info VARCHAR(200);
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_tax_rate VARCHAR(20);
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_invoice_code VARCHAR(50);
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_invoice_no VARCHAR(50);
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_seal_type VARCHAR(50);
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_seal_clarity VARCHAR(20);
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_joint_seal VARCHAR(10);
ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_other TEXT;

ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_date DATE;
ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_amount NUMERIC(15,2);
ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_party VARCHAR(200);
ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_tax_id VARCHAR(50);
ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_serial_no VARCHAR(100);
ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_details TEXT;
ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_bank_info VARCHAR(200);
ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_tax_rate VARCHAR(20);
ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_invoice_code VARCHAR(50);
ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_invoice_no VARCHAR(50);
ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_seal_type VARCHAR(50);
ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_seal_clarity VARCHAR(20);
ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_joint_seal VARCHAR(10);
ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_other TEXT;

ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_date DATE;
ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_amount NUMERIC(15,2);
ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_party VARCHAR(200);
ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_tax_id VARCHAR(50);
ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_serial_no VARCHAR(100);
ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_details TEXT;
ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_bank_info VARCHAR(200);
ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_tax_rate VARCHAR(20);
ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_invoice_code VARCHAR(50);
ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_invoice_no VARCHAR(50);
ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_seal_type VARCHAR(50);
ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_seal_clarity VARCHAR(20);
ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_joint_seal VARCHAR(10);
ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_other TEXT;

ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_date DATE;
ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_amount NUMERIC(15,2);
ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_party VARCHAR(200);
ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_tax_id VARCHAR(50);
ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_serial_no VARCHAR(100);
ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_details TEXT;
ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_bank_info VARCHAR(200);
ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_tax_rate VARCHAR(20);
ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_invoice_code VARCHAR(50);
ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_invoice_no VARCHAR(50);
ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_seal_type VARCHAR(50);
ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_seal_clarity VARCHAR(20);
ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_joint_seal VARCHAR(10);
ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_other TEXT;

ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_date DATE;
ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_amount NUMERIC(15,2);
ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_party VARCHAR(200);
ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_tax_id VARCHAR(50);
ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_serial_no VARCHAR(100);
ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_details TEXT;
ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_bank_info VARCHAR(200);
ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_tax_rate VARCHAR(20);
ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_invoice_code VARCHAR(50);
ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_invoice_no VARCHAR(50);
ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_seal_type VARCHAR(50);
ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_seal_clarity VARCHAR(20);
ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_joint_seal VARCHAR(10);
ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_other TEXT;

ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_date DATE;
ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_amount NUMERIC(15,2);
ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_party VARCHAR(200);
ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_tax_id VARCHAR(50);
ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_serial_no VARCHAR(100);
ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_details TEXT;
ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_bank_info VARCHAR(200);
ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_tax_rate VARCHAR(20);
ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_invoice_code VARCHAR(50);
ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_invoice_no VARCHAR(50);
ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_seal_type VARCHAR(50);
ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_seal_clarity VARCHAR(20);
ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_joint_seal VARCHAR(10);
ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_other TEXT;

ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_date DATE;
ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_amount NUMERIC(15,2);
ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_party VARCHAR(200);
ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_tax_id VARCHAR(50);
ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_serial_no VARCHAR(100);
ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_details TEXT;
ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_bank_info VARCHAR(200);
ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_tax_rate VARCHAR(20);
ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_invoice_code VARCHAR(50);
ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_invoice_no VARCHAR(50);
ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_seal_type VARCHAR(50);
ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_seal_clarity VARCHAR(20);
ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_joint_seal VARCHAR(10);
ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_other TEXT;

ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_date DATE;
ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_amount NUMERIC(15,2);
ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_party VARCHAR(200);
ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_tax_id VARCHAR(50);
ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_serial_no VARCHAR(100);
ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_details TEXT;
ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_bank_info VARCHAR(200);
ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_tax_rate VARCHAR(20);
ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_invoice_code VARCHAR(50);
ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_invoice_no VARCHAR(50);
ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_seal_type VARCHAR(50);
ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_seal_clarity VARCHAR(20);
ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_joint_seal VARCHAR(10);
ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_other TEXT;

ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_date DATE;
ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_amount NUMERIC(15,2);
ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_party VARCHAR(200);
ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_tax_id VARCHAR(50);
ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_serial_no VARCHAR(100);
ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_details TEXT;
ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_bank_info VARCHAR(200);
ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_tax_rate VARCHAR(20);
ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_invoice_code VARCHAR(50);
ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_invoice_no VARCHAR(50);
ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_seal_type VARCHAR(50);
ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_seal_clarity VARCHAR(20);
ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_joint_seal VARCHAR(10);
ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_other TEXT;

ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_date DATE;
ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_amount NUMERIC(15,2);
ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_party VARCHAR(200);
ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_tax_id VARCHAR(50);
ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_serial_no VARCHAR(100);
ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_details TEXT;
ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_bank_info VARCHAR(200);
ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_tax_rate VARCHAR(20);
ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_invoice_code VARCHAR(50);
ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_invoice_no VARCHAR(50);
ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_seal_type VARCHAR(50);
ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_seal_clarity VARCHAR(20);
ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_joint_seal VARCHAR(10);
ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_other TEXT;

-- 从JSONB解析填充独立字段（发票类示例）
UPDATE agent2_extract_发票类 SET
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

UPDATE agent2_extract_差旅票据类 SET
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

UPDATE agent2_extract_银行资金类 SET
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

UPDATE agent2_extract_企业内部管理类 SET
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

UPDATE agent2_extract_税务类 SET
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

UPDATE agent2_extract_资产类 SET
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

UPDATE agent2_extract_合同协议类 SET
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

UPDATE agent2_extract_函证审计类 SET
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

UPDATE agent2_extract_证照资质类 SET
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

UPDATE agent2_extract_人事薪酬类 SET
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

-- 创建统一查询视图（10大类合并）
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
