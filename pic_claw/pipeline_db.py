import psycopg2
import psycopg2.extras
from datetime import datetime
from pathlib import Path

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "audit_pipeline_db",
    "user": "postgres",
    "password": "admin",
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def create_batch(batch_no: str, batch_name: str = "", source: str = "import", total_images: int = 0) -> int:
    sql = """
        INSERT INTO batches (batch_no, batch_name, source, total_images, status)
        VALUES (%s, %s, %s, %s, 'pending')
        RETURNING id
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (batch_no, batch_name, source, total_images))
            return cur.fetchone()[0]


def update_batch_progress(batch_id: int, **kwargs):
    fields = []
    values = []
    for k, v in kwargs.items():
        fields.append(f"{k} = %s")
        values.append(v)
    values.append(batch_id)
    sql = f"UPDATE batches SET {', '.join(fields)}, updated_at = NOW() WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, values)


def get_batch(batch_id: int) -> dict:
    sql = "SELECT * FROM batches WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (batch_id,))
            return cur.fetchone()


def insert_voucher_image(batch_id: int, file_name: str, file_path: str,
                         file_md5: str = None, file_size: int = None,
                         file_format: str = None, doc_type_name: str = None,
                         category_name: str = None) -> int:
    sql = """
        INSERT INTO voucher_images
            (batch_id, file_name, file_path, file_md5, file_size, file_format,
             doc_type_name, category_name, classify_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        RETURNING id
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (batch_id, file_name, file_path, file_md5,
                              file_size, file_format, doc_type_name, category_name))
            return cur.fetchone()[0]


def get_pending_classify_images(batch_id: int = None, limit: int = 50) -> list:
    sql = """
        SELECT id, file_path, file_name, doc_type_name, category_name
        FROM voucher_images
        WHERE classify_status = 'pending'
    """
    params = []
    if batch_id:
        sql += " AND batch_id = %s"
        params.append(batch_id)
    sql += " ORDER BY id LIMIT %s"
    params.append(limit)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def update_classify_result(image_id: int, doc_type_name: str, category_name: str,
                           confidence: float, status: str = "done"):
    sql = """
        UPDATE voucher_images
        SET doc_type_name = %s, category_name = %s, classify_confidence = %s,
            classify_status = %s, updated_at = NOW()
        WHERE id = %s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (doc_type_name, category_name, confidence, status, image_id))


def insert_agent_log(image_id: int, agent_stage: str, input_summary: str,
                     output_json: dict, llm_model: str, duration_ms: int,
                     status: str = "done", error_msg: str = None):
    sql = """
        INSERT INTO agent_logs
            (image_id, agent_stage, input_summary, output_json, llm_model,
             duration_ms, status, error_msg)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (image_id, agent_stage, input_summary,
                              psycopg2.extras.Json(output_json), llm_model,
                              duration_ms, status, error_msg))


def insert_pipeline_log(image_id: int, batch_id: int, stage: str, status: str,
                        message: str = None, duration_ms: int = None):
    sql = """
        INSERT INTO pipeline_logs (image_id, batch_id, stage, status, message, duration_ms)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (image_id, batch_id, stage, status, message, duration_ms))


def get_all_document_types() -> list:
    sql = """
        SELECT dt.id, dt.type_name, dt.category_id, dc.category_name
        FROM document_types dt
        JOIN document_categories dc ON dc.id = dt.category_id
        WHERE dt.is_active = TRUE
        ORDER BY dc.sort_order, dt.sort_order
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]


def get_classify_stats(batch_id: int = None) -> dict:
    sql = """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE classify_status = 'pending') AS pending,
            COUNT(*) FILTER (WHERE classify_status = 'done') AS done,
            COUNT(*) FILTER (WHERE classify_status = 'failed') AS failed
        FROM voucher_images
    """
    params = []
    if batch_id:
        sql += " WHERE batch_id = %s"
        params.append(batch_id)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return dict(cur.fetchone())


# ============================================================
# Agent2 提取阶段 - 数据库操作
# ============================================================

def get_pending_extract_images(batch_id: int = None, limit: int = 50) -> list:
    sql = """
        SELECT id, file_path, file_name, doc_type_name, category_name
        FROM voucher_images
        WHERE classify_status = 'done'
          AND extract_status = 'pending'
    """
    params = []
    if batch_id:
        sql += " AND batch_id = %s"
        params.append(batch_id)
    sql += " ORDER BY id LIMIT %s"
    params.append(limit)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def update_extract_status(image_id: int, status: str = "done"):
    sql = """
        UPDATE voucher_images
        SET extract_status = %s, updated_at = NOW()
        WHERE id = %s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (status, image_id))


def insert_extracted_field(image_id: int, field_name: str, field_value: str,
                           field_type: str = "text", confidence: float = None,
                           extract_method: str = "llm", source_text: str = None):
    sql = """
        INSERT INTO extracted_fields
            (image_id, field_name, field_value, field_type, confidence,
             extract_method, source_text)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (image_id, field_name, field_value, field_type,
                              confidence, extract_method, source_text))


def get_extracted_fields(image_id: int) -> list:
    sql = """
        SELECT field_name, field_value, field_type, confidence, extract_method
        FROM extracted_fields
        WHERE image_id = %s
        ORDER BY id
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (image_id,))
            return [dict(r) for r in cur.fetchall()]


def get_expected_fields(doc_type_name: str) -> list:
    sql = """
        SELECT dt.expected_fields
        FROM document_types dt
        WHERE dt.type_name = %s AND dt.is_active = TRUE
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (doc_type_name,))
            row = cur.fetchone()
            if row and row["expected_fields"]:
                return row["expected_fields"]
    return []


def get_extract_stats(batch_id: int = None) -> dict:
    sql = """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE extract_status = 'pending') AS pending,
            COUNT(*) FILTER (WHERE extract_status = 'done') AS done,
            COUNT(*) FILTER (WHERE extract_status = 'failed') AS failed
        FROM voucher_images
        WHERE classify_status = 'done'
    """
    params = []
    if batch_id:
        sql += " AND batch_id = %s"
        params.append(batch_id)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return dict(cur.fetchone())