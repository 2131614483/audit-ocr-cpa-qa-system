"""重置batch 4图片状态为pending"""
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "audit_pipeline_db",
    "user": "postgres",
    "password": "admin"
}

conn = psycopg2.connect(**DB_CONFIG)
with conn.cursor() as cur:
    cur.execute("""
        UPDATE voucher_images 
        SET classify_status = 'pending', ocr_status = 'pending', 
            extract_status = 'pending', audit_status = 'pending'
        WHERE batch_id = 4
    """)
    updated = cur.rowcount
    conn.commit()
conn.close()
print(f"✅ 已重置 {updated} 张图片状态为 pending")