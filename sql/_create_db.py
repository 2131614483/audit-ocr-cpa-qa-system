"""创建 audit_pipeline_db 数据库"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='postgres', user='postgres', password='admin')
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT 1 FROM pg_database WHERE datname = 'audit_pipeline_db'")
exists = cur.fetchone()
if not exists:
    cur.execute('CREATE DATABASE audit_pipeline_db ENCODING "UTF8"')
    print('数据库 audit_pipeline_db 创建成功')
else:
    print('数据库 audit_pipeline_db 已存在')

cur.close()
conn.close()
