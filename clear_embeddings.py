# ============================================================
# CPA 知识库 - 清空向量数据工具
# 功能: 清空 cpa_embeddings 和 cpa_qa_history 表的所有数据
# 用法: python clear_embeddings.py
# 注意: 清空后需重新运行 import_all_cpa_8b.py 导入教材
# ============================================================

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
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

def clear_all_embeddings():
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # 统计当前数据
        cur.execute("SELECT COUNT(*) FROM cpa_embeddings")
        count = cur.fetchone()[0]
        print(f"当前 cpa_embeddings 表中有 {count} 条记录")
        
        # 清空表
        print("正在清空 cpa_embeddings 表...")
        cur.execute("TRUNCATE TABLE cpa_embeddings RESTART IDENTITY")
        conn.commit()
        
        # 验证
        cur.execute("SELECT COUNT(*) FROM cpa_embeddings")
        count = cur.fetchone()[0]
        print(f"✅ 清空完成！当前记录数: {count}")
        
    except Exception as e:
        print(f"❌ 清空失败: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    clear_all_embeddings()