# ============================================================
# 审计知识库 - 表结构修改工具
# 功能: 修改知识库表的字段定义（添加/修改列）
# 用法: python knowledge/alter_kb_table.py
# ============================================================

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import psycopg2

DB = {"host": "localhost", "port": 5432, "dbname": "audit_ocr", "user": "postgres", "password": "admin"}

conn = psycopg2.connect(**DB)
conn.autocommit = True
cur = conn.cursor()

# 新增字段
for col, dtype in [("source", "VARCHAR(500)"), ("section_title", "VARCHAR(500)")]:
    cur.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='knowledge_base' AND column_name='{col}'
            ) THEN
                ALTER TABLE knowledge_base ADD COLUMN {col} {dtype};
            END IF;
        END $$;
    """)

print("✅ 表结构更新完成（已加 source, section_title 字段）")
cur.close()
conn.close()
