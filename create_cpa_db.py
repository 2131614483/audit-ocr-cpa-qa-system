# ============================================================
# CPA 知识库 - 创建数据库工具
# 功能: 创建 cpa_knowledge 数据库（在 postgres 数据库中执行）
# 用法: python create_cpa_db.py
# 注意: 会先删除已存在的 cpa_knowledge 数据库
# ============================================================

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

conn = psycopg2.connect(host='localhost', port=5432, dbname='postgres', user='postgres', password='admin')
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()

cur.execute("DROP DATABASE IF EXISTS cpa_knowledge")
cur.execute('CREATE DATABASE cpa_knowledge')
print('Database cpa_knowledge recreated')

conn.close()