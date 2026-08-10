"""重置batch=4的状态为pending，并测试智谱API"""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['PYTHONUNBUFFERED'] = '1'

import psycopg2, psycopg2.extras

conn = psycopg2.connect(host='localhost', port=5432, dbname='audit_pipeline_db', user='postgres', password='admin')

# 1. 重置batch=4所有图片状态为pending
with conn.cursor() as cur:
    cur.execute("""
        UPDATE voucher_images 
        SET classify_status = 'pending', extract_status = 'pending',
            doc_type_name = NULL, category_name = NULL, classify_confidence = NULL,
            updated_at = NOW()
        WHERE batch_id = 4
    """)
    print(f"已重置 {cur.rowcount} 张图片状态为pending")

    # 2. 删除已提取的字段
    cur.execute("""
        DELETE FROM extracted_fields 
        WHERE image_id IN (SELECT id FROM voucher_images WHERE batch_id = 4)
    """)
    print(f"已删除 {cur.rowcount} 条提取字段记录")

    # 3. 删除agent日志
    cur.execute("""
        DELETE FROM agent_logs 
        WHERE image_id IN (SELECT id FROM voucher_images WHERE batch_id = 4)
    """)
    print(f"已删除 {cur.rowcount} 条agent日志")

conn.commit()

# 4. 测试智谱API连接
print("\n测试智谱API连接...")
from config.settings import set_provider
set_provider("zhipu")
from services.ollama_client import call_llm, get_main_model
print(f"当前模型: {get_main_model()}")

# 简单测试
try:
    resp = call_llm("请回复'连接成功'四个字", model_key="main")
    print(f"智谱API测试: {resp[:50]}")
except Exception as e:
    print(f"智谱API测试失败: {e}")

conn.close()
print("\n准备完成！")