# ============================================================
# 审计知识库 - 表结构检查工具
# 功能: 检查 knowledge_base 表的字段定义和索引状态
# 用法: python knowledge/check_schema.py
# ============================================================

import psycopg2
conn = psycopg2.connect(host="localhost", port=5432, dbname="audit_ocr", user="postgres", password="admin")
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name='knowledge_base' ORDER BY ordinal_position")
for c in cur.fetchall():
    print(f"{c[0]:30s} nullable={c[1]}")
cur.close()
conn.close()
