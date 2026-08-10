# ============================================================
# 审计知识库 - 表结构修复工具
# 功能: 修复 knowledge_base 表的字段类型和约束问题
# 用法: python knowledge/fix_schema.py
# ============================================================

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import psycopg2
conn = psycopg2.connect(host="localhost", port=5432, dbname="audit_ocr", user="postgres", password="admin")
conn.autocommit = True
cur = conn.cursor()

# 先删旧数据
cur.execute("DELETE FROM knowledge_base")

# 修改 NOT NULL 约束
cur.execute("ALTER TABLE knowledge_base ALTER COLUMN rule_id DROP NOT NULL")
cur.execute("ALTER TABLE knowledge_base ALTER COLUMN rule_name DROP NOT NULL")

print("✅ 约束已修改，旧数据已清空")
cur.close()
conn.close()
