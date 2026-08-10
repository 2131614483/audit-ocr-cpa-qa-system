# ============================================================
# CPA 知识库 - 数据库表检查工具
# 功能: 检查 cpa_knowledge 数据库中所有表的记录数和状态
# 用法: python check_all_tables.py
# ============================================================

import psycopg2

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            dbname='cpa_knowledge',
            user='postgres',
            password='admin'
        )
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def check_embedding_tables():
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # 获取所有包含 embedding 字段的表
        cur.execute("""
            SELECT table_name, column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE column_name LIKE '%embedding%'
            ORDER BY table_name, column_name
        """)
        
        results = cur.fetchall()
        
        print("=== 包含 embedding 字段的表 ===")
        print(f"{'表名':<20} {'字段名':<20} {'数据类型':<20} {'UDT类型':<20}")
        print("-" * 80)
        
        for row in results:
            table_name, column_name, data_type, udt_name = row
            status = "✅" if udt_name == 'vector' else "⚠️"
            print(f"{status} {table_name:<20} {column_name:<20} {data_type:<20} {udt_name:<20}")
        
        print("\n=== 各表记录统计 ===")
        cur.execute("""
            SELECT table_name, 
                   (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count,
                   (SELECT reltuples::bigint FROM pg_class WHERE relname = t.table_name) as row_count
            FROM information_schema.tables t
            WHERE table_name LIKE '%embedding%' OR table_name LIKE '%cpa_%'
            ORDER BY table_name
        """)
        
        results = cur.fetchall()
        print(f"{'表名':<20} {'字段数':<10} {'记录数':<10}")
        print("-" * 40)
        
        for row in results:
            table_name, col_count, row_count = row
            print(f"{table_name:<20} {col_count:<10} {row_count:<10}")
        
        # 测试向量查询
        print("\n=== 测试向量查询 ===")
        cur.execute("SELECT COUNT(*) FROM cpa_embeddings WHERE embedding IS NOT NULL")
        count = cur.fetchone()[0]
        
        if count > 0:
            cur.execute("SELECT embedding FROM cpa_embeddings LIMIT 1")
            row = cur.fetchone()
            if row:
                emb = row[0]
                print(f"向量数据类型: {type(emb)}")
                
                try:
                    # 测试向量相似度查询
                    cur.execute("SELECT COUNT(*) FROM cpa_embeddings WHERE embedding <-> %s < 1.0", (emb,))
                    result = cur.fetchone()
                    print(f"✅ 向量相似度查询正常工作")
                except Exception as e:
                    print(f"❌ 向量相似度查询失败: {e}")
        else:
            print("ℹ️  cpa_embeddings 表为空，请先导入数据")
        
    except Exception as e:
        print(f"检查失败: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_embedding_tables()