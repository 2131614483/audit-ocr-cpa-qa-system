import psycopg2
from cpazs.config_cpa import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

print("正在清空旧数据（TRUNCATE CASCADE 自动处理外键 + 重置ID）...")

# 先断开依赖关系：清空有外键引用的表
cur.execute("TRUNCATE TABLE cpa_knowledge_points CASCADE")
print(f"  ✅ cpa_knowledge_points 已清空")
cur.execute("TRUNCATE TABLE cpa_qa_pairs CASCADE")
print(f"  ✅ cpa_qa_pairs 已清空")

# 再清空核心表，RESTART IDENTITY 自动重置序列
cur.execute("TRUNCATE TABLE cpa_embeddings RESTART IDENTITY CASCADE")
print(f"  ✅ cpa_embeddings 已清空，ID已重置")
cur.execute("TRUNCATE TABLE cpa_chapters RESTART IDENTITY CASCADE")
print(f"  ✅ cpa_chapters 已清空，ID已重置")
cur.execute("TRUNCATE TABLE cpa_books RESTART IDENTITY CASCADE")
print(f"  ✅ cpa_books 已清空，ID已重置")

conn.commit()
cur.close()
conn.close()
print("\n🎉 全部清空，id从1开始。可以运行导入：")
print("  python json_import_cpa.py --all")
