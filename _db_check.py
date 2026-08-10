import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='postgres', user='postgres', password='admin')
cur = conn.cursor()

print('=' * 60)
print('📊 PostgreSQL 服务器检查')
print('=' * 60)

cur.execute("SELECT version()")
print(f'PostgreSQL: {cur.fetchone()[0]}')

cur.execute("SELECT datname FROM pg_database ORDER BY datname")
dbs = cur.fetchall()
print(f'\n📋 所有数据库 ({len(dbs)} 个)：')
for db in dbs:
    print(f'   {db[0]}')

print('\n' + '=' * 60)
print('📊 逐个测试连接')
print('=' * 60)

for db_name in ['cpa_knowledge', 'audit_pipeline_db', 'audit_ocr', 'annual_reports']:
    try:
        conn2 = psycopg2.connect(host='localhost', port=5432, dbname=db_name, user='postgres', password='admin')
        cur2 = conn2.cursor()
        cur2.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
        tbl_count = cur2.fetchone()[0]
        print(f'\n✅ {db_name}: 连接成功 ({tbl_count} 张表)')

        if tbl_count > 0:
            cur2.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name LIMIT 20")
            for t in cur2.fetchall():
                print(f'   - {t[0]}')
        conn2.close()
    except psycopg2.OperationalError as e:
        print(f'\n❌ {db_name}: 连接失败 - {e}')
    except Exception as e:
        print(f'\n⚠️ {db_name}: {e}')

cur.close()
conn.close()
print('\n✅ 检查完成')
