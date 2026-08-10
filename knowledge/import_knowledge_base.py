# ============================================================
# 审计知识库 - JSON 知识库入库工具
# 功能: 将 audit_knowledge_base.json 中的规则数据
#       导入到 knowledge_base 表，并生成向量
# 用法: python knowledge/import_knowledge_base.py
# ============================================================

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from datetime import datetime
from services.embedding_service import get_embedding

DB = {"host": "localhost", "port": 5432, "dbname": "audit_ocr", "user": "postgres", "password": "admin"}
KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_knowledge_base.json")

conn = psycopg2.connect(**DB)
cur = conn.cursor()

with open(KB_PATH, "r", encoding="utf-8") as f:
    kb_data = json.load(f)

print(f"知识库版本: {kb_data.get('version', 'N/A')}")
print(f"包含分类数: {len(kb_data['categories'])}")

total = 0
success = 0
fail = 0

for cat in kb_data["categories"]:
    category = cat["category"]
    rules = cat["rules"]
    print(f"\n{'='*60}")
    print(f"分类: {category} ({len(rules)} 条规则)")
    print(f"{'='*60}")

    for rule in rules:
        total += 1
        rule_id = rule["id"]
        rule_name = rule["name"]
        content = rule["content"]
        risk_level = rule.get("risk_level", "中")

        # 生成嵌入向量
        embed_text = f"审计规则 - {category} - {rule_name}: {content}"
        print(f"  [{total}] {rule_id} {rule_name} ... ", end="", flush=True)

        embedding = get_embedding(embed_text)

        if embedding:
            # 储存到数据库
            embedding_str = "{" + ",".join(str(x) for x in embedding) + "}"
            cur.execute("""
                INSERT INTO knowledge_base (category, rule_id, rule_name, content, risk_level, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::double precision[])
            """, (category, rule_id, rule_name, content, risk_level, embedding_str))
            success += 1
            print("✅")
        else:
            # 不存向量，只存文本
            cur.execute("""
                INSERT INTO knowledge_base (category, rule_id, rule_name, content, risk_level)
                VALUES (%s, %s, %s, %s, %s)
            """, (category, rule_id, rule_name, content, risk_level))
            fail += 1
            print("⚠️ 无向量(已存文本)")

conn.commit()

print(f"\n{'='*60}")
print(f"✅ 入库完成!")
print(f"   总计: {total} 条")
print(f"   成功(含向量): {success} 条")
print(f"   仅文本: {fail} 条")

cur.close()
conn.close()
