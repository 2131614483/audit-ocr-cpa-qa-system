# ============================================================
# 审计知识库 - 创建知识库表工具
# 功能: 创建 knowledge_base 表及其索引，
#       用于存储审计知识库规则和向量数据
# 用法: python knowledge/setup_kb_table.py
# ============================================================

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import psycopg2
import json

DB = {"host": "localhost", "port": 5432, "dbname": "audit_ocr", "user": "postgres", "password": "admin"}

conn = psycopg2.connect(**DB)
conn.autocommit = True
cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS knowledge_base (
        id SERIAL PRIMARY KEY,
        category VARCHAR(200) NOT NULL,
        rule_id VARCHAR(50) NOT NULL,
        rule_name VARCHAR(500) NOT NULL,
        content TEXT NOT NULL,
        risk_level VARCHAR(20),
        embedding double precision[],
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

cur.execute("CREATE INDEX IF NOT EXISTS idx_kb_rule_id ON knowledge_base(rule_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_kb_category ON knowledge_base(category);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_kb_risk_level ON knowledge_base(risk_level);")

print("✅ 表 knowledge_base 创建成功!")
print("   字段: id, category, rule_id, rule_name, content, risk_level, embedding(4096维), created_at")

cur.close()
conn.close()
