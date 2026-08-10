"""验证独立字段解析结果"""
import psycopg2
import psycopg2.extras

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "audit_pipeline_db",
    "user": "postgres",
    "password": "admin"
}

conn = psycopg2.connect(**DB_CONFIG)
with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
    # 查询统一视图
    cur.execute("""
        SELECT category, doc_type_name, f_date, f_amount, f_party, f_tax_id, 
               f_serial_no, f_details, f_seal_type, f_seal_clarity,
               risk_rating, audit_conclusion, summary
        FROM v_all_extract_fields
        ORDER BY category
    """)
    rows = cur.fetchall()
    
    print("=" * 80)
    print("📊 10大类独立字段解析结果")
    print("=" * 80)
    for r in rows:
        print(f"\n【{r['category']}】{r['doc_type_name']}")
        print(f"  日期: {r['f_date']}")
        print(f"  金额: {r['f_amount']}")
        print(f"  相关方: {r['f_party']}")
        print(f"  税号: {r['f_tax_id']}")
        print(f"  流水号: {r['f_serial_no']}")
        print(f"  摘要: {r['f_details']}")
        print(f"  印章: {r['f_seal_type']} ({r['f_seal_clarity']})")
        print(f"  风险: {r['risk_rating']} | 结论: {r['audit_conclusion']}")
        print(f"  总结: {r['summary']}")

conn.close()
