# ============================================================
# CPA 知识库 - 修复 pgvector 扩展工具
# 功能: 检查并安装 pgvector 扩展，修复向量搜索功能
# 用法: python fix_vector_extension.py
# ============================================================

import psycopg2
from psycopg2 import OperationalError

def create_connection():
    try:
        conn = psycopg2.connect(
            dbname="cpa_knowledge",
            user="postgres",
            password="admin",
            host="localhost",
            port="5432"
        )
        return conn
    except OperationalError as e:
        print(f"连接数据库失败: {e}")
        return None

def install_pgvector():
    conn = create_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # 尝试创建扩展
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.commit()
            print("✅ pgvector 扩展安装成功")
        except Exception as e:
            print(f"安装 pgvector 扩展失败: {e}")
            print("请手动安装 pgvector: https://github.com/pgvector/pgvector")
        
        # 检查 embedding 字段类型
        cur.execute("SELECT data_type FROM information_schema.columns WHERE table_name = 'cpa_embeddings' AND column_name = 'embedding'")
        result = cur.fetchone()
        if result:
            print(f"当前 embedding 字段类型: {result[0]}")
            
            # 如果是 bytea 类型，需要改为 vector 类型
            if result[0] == 'bytea':
                print("需要将 bytea 类型转换为 vector 类型")
                print("注意: 这需要重新导入数据")
                
    except Exception as e:
        print(f"操作失败: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    install_pgvector()