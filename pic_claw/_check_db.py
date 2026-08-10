"""检查batch=4的图片数据"""
import sys, os, psycopg2, psycopg2.extras
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

conn = psycopg2.connect(host='localhost', port=5432, dbname='audit_pipeline_db', user='postgres', password='admin')
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute("SELECT id, file_name, doc_type_name, category_name, classify_status FROM voucher_images WHERE batch_id=4 ORDER BY id LIMIT 10")
for r in cur.fetchall():
    print(f'ID={r["id"]} name={r["file_name"]} type={r["doc_type_name"]} cat={r["category_name"]} status={r["classify_status"]}')
conn.close()