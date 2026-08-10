import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, dbname='cpa_knowledge', user='postgres', password='admin')
cur = conn.cursor()

# 把卡住的 running 状态改为 failed
cur.execute("UPDATE cpa_dream_log SET status='failed', finished_at=NOW() WHERE status='running'")
affected = cur.rowcount
conn.commit()
print(f"✅ 已重置 {affected} 条卡住的做梦记录")

cur.execute("SELECT id, status, started_at, finished_at FROM cpa_dream_log ORDER BY id DESC")
print("\n当前做梦日志:")
for r in cur.fetchall():
    print(f"  id={r[0]}, status={r[1]}, started={r[2]}, finished={r[3]}")

cur.close()
conn.close()
