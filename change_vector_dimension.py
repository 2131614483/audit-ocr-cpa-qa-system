# ============================================================
# CPA 知识库 - 向量维度切换工具
# 功能: 切换 cpa_embeddings 和 cpa_qa_history 表的向量维度（1024/4096）
# 用法: python change_vector_dimension.py <dimension>
# 注意: 切换后需重新导入教材
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

def change_vector_dimension(dimension: int = 1024):
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # ===== cpa_embeddings =====
        print(f"\n📦 处理 cpa_embeddings 表...")
        
        print(f"1. 删除旧的索引...")
        cur.execute("DROP INDEX IF EXISTS idx_cpa_embeddings")
        conn.commit()
        print("✅ 索引删除成功")
        
        print(f"\n2. 删除旧的向量字段...")
        cur.execute("ALTER TABLE cpa_embeddings DROP COLUMN IF EXISTS embedding")
        conn.commit()
        print("✅ 字段删除成功")
        
        print(f"\n3. 创建新的 {dimension} 维向量字段...")
        cur.execute(f"ALTER TABLE cpa_embeddings ADD COLUMN embedding vector({dimension})")
        conn.commit()
        print("✅ 字段创建成功")
        
        if dimension <= 2000:
            print(f"\n4. 创建新索引 (ivfflat)...")
            cur.execute("CREATE INDEX idx_cpa_embeddings ON cpa_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
            conn.commit()
            print("✅ 索引创建成功")
        else:
            print(f"\n4. ⚠️  跳过索引创建：ivfflat 索引不支持 {dimension} 维向量（上限 2000 维）")
            print("   查询时将使用全表扫描，数据量增大后建议升级 pgvector 或使用其他索引方案")
        
        # ===== cpa_qa_history =====
        print(f"\n📦 处理 cpa_qa_history 表...")
        
        print(f"1. 删除旧的向量字段...")
        cur.execute("ALTER TABLE cpa_qa_history DROP COLUMN IF EXISTS embedding")
        conn.commit()
        print("✅ 字段删除成功")
        
        print(f"2. 创建新的 {dimension} 维向量字段...")
        cur.execute(f"ALTER TABLE cpa_qa_history ADD COLUMN embedding vector({dimension})")
        conn.commit()
        print("✅ 字段创建成功")
        
        print(f"\n🎉 所有表的向量维度已更改为 {dimension}！")
        
    except Exception as e:
        print(f"\n❌ 操作失败: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    dim = int(sys.argv[1]) if len(sys.argv) > 1 else 1024
    change_vector_dimension(dim)