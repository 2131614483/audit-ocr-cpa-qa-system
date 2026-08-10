"""清空batch 4的Agent1和Agent2数据"""
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "audit_pipeline_db",
    "user": "postgres",
    "password": "admin"
}

CATEGORY_TABLES = [
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

conn = psycopg2.connect(**DB_CONFIG)
with conn.cursor() as cur:
    cur.execute("DELETE FROM agent1_classify_results WHERE batch_id = 4")
    a1_cnt = cur.rowcount
    conn.commit()
    print(f"✅ Agent1清空: {a1_cnt}条")
    
    for table in CATEGORY_TABLES:
        cur.execute(f"DELETE FROM {table} WHERE batch_id = 4")
        cnt = cur.rowcount
        conn.commit()
        print(f"✅ {table}清空: {cnt}条")

conn.close()
print("\n✅ 完成！batch 4数据已清空")
