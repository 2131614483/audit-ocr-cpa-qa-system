"""在 audit_pipeline_db 中执行建表脚本"""
import psycopg2
from pathlib import Path

sql_path = Path(__file__).parent / '01_create_audit_pipeline.sql'
sql = sql_path.read_text(encoding='utf-8')

conn = psycopg2.connect(host='localhost', port=5432, dbname='audit_pipeline_db', user='postgres', password='admin')
cur = conn.cursor()
try:
    cur.execute(sql)
    conn.commit()
    print('所有表创建成功')
    
    # 列出创建的表
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
    tables = cur.fetchall()
    for t in tables:
        print(f'  ✓ {t[0]}')
except Exception as e:
    print(f'建表失败: {e}')
    conn.rollback()
finally:
    cur.close()
    conn.close()
