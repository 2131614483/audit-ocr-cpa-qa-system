"""验证10000条模拟数据"""
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
    # Agent1样本
    cur.execute("SELECT predicted_type, predicted_category, confidence, reasoning FROM agent1_classify_results WHERE batch_id = 4 LIMIT 3")
    print("=" * 60)
    print("Agent1分类结果样本:")
    print("=" * 60)
    for r in cur.fetchall():
        print(f"  {r['predicted_type']} ({r['predicted_category']}) | 置信度:{r['confidence']} | {r['reasoning']}")
    
    # Agent2样本 - 各类别
    print(f"\n{'=' * 60}")
    print("Agent2提取结果样本:")
    print(f"{'=' * 60}")
    
    tables = {
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
    
    for cat, table in tables.items():
        cur.execute(f"""
            SELECT doc_type_name, f_date, f_amount, f_party, f_tax_id, 
                   f_seal_type, f_seal_clarity, f_license_info, f_asset_info,
                   f_internal_control_info, risk_rating, audit_conclusion
            FROM {table} WHERE batch_id = 4 LIMIT 1
        """)
        r = cur.fetchone()
        print(f"\n  【{cat}】{r['doc_type_name']}")
        print(f"    日期:{r['f_date']} | 金额:{r['f_amount']} | 相关方:{r['f_party']}")
        print(f"    税号:{r['f_tax_id']} | 印章:{r['f_seal_type']}({r['f_seal_clarity']})")
        print(f"    证照信息:{r['f_license_info']}")
        print(f"    资产信息:{r['f_asset_info']}")
        print(f"    内控信息:{r['f_internal_control_info']}")
        print(f"    风险:{r['risk_rating']} | 结论:{r['audit_conclusion']}")

conn.close()
