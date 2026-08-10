"""
一键创建知识图谱独立数据库
用法: python knowledge/setup_kg_db.py
"""
# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import sys
import os
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
from pathlib import Path

# 数据库配置（与现有系统一致）
DB_HOST = "localhost"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASSWORD = "admin"
DB_NAME = "cpa_knowledge_graph"

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def create_database():
    """创建数据库（如果不存在）"""
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD,
        dbname="postgres"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
    if cur.fetchone():
        print(f"✅ 数据库 {DB_NAME} 已存在，跳过创建")
    else:
        cur.execute(f"CREATE DATABASE {DB_NAME} WITH ENCODING 'UTF8' OWNER {DB_USER}")
        print(f"✅ 数据库 {DB_NAME} 创建成功")

    cur.close()
    conn.close()


def create_tables():
    """执行建表SQL"""
    schema_file = SQL_DIR / "kg_schema.sql"
    if not schema_file.exists():
        print(f"❌ 找不到 {schema_file}")
        sys.exit(1)

    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD,
        dbname=DB_NAME
    )
    cur = conn.cursor()

    sql = schema_file.read_text(encoding="utf-8")
    cur.execute(sql)
    conn.commit()
    print(f"✅ 表创建完成 (已执行 {schema_file.name})")

    cur.close()
    conn.close()


def verify():
    """验证表已创建"""
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD,
        dbname=DB_NAME
    )
    cur = conn.cursor()

    tables = [
        "kg_entities", "kg_relationships", "kg_formulas",
        "kg_confusion_pairs", "kg_communities", "kg_build_log"
    ]

    print("\n📋 验证结果:")
    for tbl in tables:
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema='public' AND table_name=%s
        """, (tbl,))
        exists = cur.fetchone()[0] > 0
        status = "✅" if exists else "❌"
        print(f"  {status} {tbl}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("   CPA 知识图谱独立数据库 — 初始化")
    print(f"   目标数据库: {DB_NAME}")
    print("=" * 60)

    create_database()
    create_tables()
    verify()

    print(f"\n🎉 初始化完成！数据库 {DB_NAME} 已就绪。")
    print(f"   下一步: python knowledge/build_kg.py --book \"会计\" --limit 100")
