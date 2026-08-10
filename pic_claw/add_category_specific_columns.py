"""
为10大类Agent2提取表添加专属独立字段
每个大类根据其特有JSON结构添加专属字段
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

conn = psycopg2.connect(**DB_CONFIG)
with conn.cursor() as cur:
    
    # 1. 发票类 - 专属字段
    cur.execute("""
        ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_license_info JSONB;
        ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_asset_info JSONB;
        ALTER TABLE agent2_extract_发票类 ADD COLUMN IF NOT EXISTS f_internal_control_info JSONB;
    """)
    cur.execute("""
        UPDATE agent2_extract_发票类 SET
            f_license_info = extracted_fields->'license_info',
            f_asset_info = extracted_fields->'asset_info',
            f_internal_control_info = extracted_fields->'internal_control_info'
        WHERE f_license_info IS NULL;
    """)
    print("✅ 发票类: 添加3个专属字段 (license_info, asset_info, internal_control_info)")
    
    # 2. 差旅票据类 - 专属字段
    cur.execute("""
        ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_license_info JSONB;
        ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_asset_info JSONB;
        ALTER TABLE agent2_extract_差旅票据类 ADD COLUMN IF NOT EXISTS f_internal_control_info JSONB;
    """)
    cur.execute("""
        UPDATE agent2_extract_差旅票据类 SET
            f_license_info = extracted_fields->'license_info',
            f_asset_info = extracted_fields->'asset_info',
            f_internal_control_info = extracted_fields->'internal_control_info'
        WHERE f_license_info IS NULL;
    """)
    print("✅ 差旅票据类: 添加3个专属字段")
    
    # 3. 银行/资金类 - 专属字段
    cur.execute("""
        ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_license_info JSONB;
        ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_asset_info JSONB;
        ALTER TABLE agent2_extract_银行资金类 ADD COLUMN IF NOT EXISTS f_internal_control_info JSONB;
    """)
    cur.execute("""
        UPDATE agent2_extract_银行资金类 SET
            f_license_info = extracted_fields->'license_info',
            f_asset_info = extracted_fields->'asset_info',
            f_internal_control_info = extracted_fields->'internal_control_info'
        WHERE f_license_info IS NULL;
    """)
    print("✅ 银行/资金类: 添加3个专属字段")
    
    # 4. 企业内部管理类 - 专属字段
    cur.execute("""
        ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_license_info JSONB;
        ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_asset_info JSONB;
        ALTER TABLE agent2_extract_企业内部管理类 ADD COLUMN IF NOT EXISTS f_internal_control_info JSONB;
    """)
    cur.execute("""
        UPDATE agent2_extract_企业内部管理类 SET
            f_license_info = extracted_fields->'license_info',
            f_asset_info = extracted_fields->'asset_info',
            f_internal_control_info = extracted_fields->'internal_control_info'
        WHERE f_license_info IS NULL;
    """)
    print("✅ 企业内部管理类: 添加3个专属字段")
    
    # 5. 税务类 - 专属字段
    cur.execute("""
        ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_license_info JSONB;
        ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_asset_info JSONB;
        ALTER TABLE agent2_extract_税务类 ADD COLUMN IF NOT EXISTS f_internal_control_info JSONB;
    """)
    cur.execute("""
        UPDATE agent2_extract_税务类 SET
            f_license_info = extracted_fields->'license_info',
            f_asset_info = extracted_fields->'asset_info',
            f_internal_control_info = extracted_fields->'internal_control_info'
        WHERE f_license_info IS NULL;
    """)
    print("✅ 税务类: 添加3个专属字段")
    
    # 6. 资产类 - 专属字段
    cur.execute("""
        ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_license_info JSONB;
        ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_asset_info JSONB;
        ALTER TABLE agent2_extract_资产类 ADD COLUMN IF NOT EXISTS f_internal_control_info JSONB;
    """)
    cur.execute("""
        UPDATE agent2_extract_资产类 SET
            f_license_info = extracted_fields->'license_info',
            f_asset_info = extracted_fields->'asset_info',
            f_internal_control_info = extracted_fields->'internal_control_info'
        WHERE f_license_info IS NULL;
    """)
    print("✅ 资产类: 添加3个专属字段")
    
    # 7. 合同/协议类 - 专属字段
    cur.execute("""
        ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_license_info JSONB;
        ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_asset_info JSONB;
        ALTER TABLE agent2_extract_合同协议类 ADD COLUMN IF NOT EXISTS f_internal_control_info JSONB;
    """)
    cur.execute("""
        UPDATE agent2_extract_合同协议类 SET
            f_license_info = extracted_fields->'license_info',
            f_asset_info = extracted_fields->'asset_info',
            f_internal_control_info = extracted_fields->'internal_control_info'
        WHERE f_license_info IS NULL;
    """)
    print("✅ 合同/协议类: 添加3个专属字段")
    
    # 8. 函证/审计类 - 专属字段
    cur.execute("""
        ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_license_info JSONB;
        ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_asset_info JSONB;
        ALTER TABLE agent2_extract_函证审计类 ADD COLUMN IF NOT EXISTS f_internal_control_info JSONB;
    """)
    cur.execute("""
        UPDATE agent2_extract_函证审计类 SET
            f_license_info = extracted_fields->'license_info',
            f_asset_info = extracted_fields->'asset_info',
            f_internal_control_info = extracted_fields->'internal_control_info'
        WHERE f_license_info IS NULL;
    """)
    print("✅ 函证/审计类: 添加3个专属字段")
    
    # 9. 证照/资质类 - 专属字段
    cur.execute("""
        ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_license_info JSONB;
        ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_asset_info JSONB;
        ALTER TABLE agent2_extract_证照资质类 ADD COLUMN IF NOT EXISTS f_internal_control_info JSONB;
    """)
    cur.execute("""
        UPDATE agent2_extract_证照资质类 SET
            f_license_info = extracted_fields->'license_info',
            f_asset_info = extracted_fields->'asset_info',
            f_internal_control_info = extracted_fields->'internal_control_info'
        WHERE f_license_info IS NULL;
    """)
    print("✅ 证照/资质类: 添加3个专属字段")
    
    # 10. 人事/薪酬类 - 专属字段
    cur.execute("""
        ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_license_info JSONB;
        ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_asset_info JSONB;
        ALTER TABLE agent2_extract_人事薪酬类 ADD COLUMN IF NOT EXISTS f_internal_control_info JSONB;
    """)
    cur.execute("""
        UPDATE agent2_extract_人事薪酬类 SET
            f_license_info = extracted_fields->'license_info',
            f_asset_info = extracted_fields->'asset_info',
            f_internal_control_info = extracted_fields->'internal_control_info'
        WHERE f_license_info IS NULL;
    """)
    print("✅ 人事/薪酬类: 添加3个专属字段")
    
    conn.commit()
conn.close()

print("\n✅ 完成！10大类表均已添加专属JSON字段")
print("\n 字段说明:")
print("  f_license_info (JSONB) - 证照信息 {unified_social_credit_code, legal_person, valid_period}")
print("  f_asset_info (JSONB)   - 资产信息 {asset_tag, asset_name, location, quantity, progress}")
print("  f_internal_control_info (JSONB) - 内控信息 {signer, approval_level, attachment_complete}")
