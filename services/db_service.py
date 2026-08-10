# ============================================================
# 数据库写入服务
# 功能: 连接 PostgreSQL，将 OCR 识别结果写入 audit_results 表，
#       提供字段映射和批量写入支持
# 核心: save_single_result() - 单条写入
#       get_db_config() / get_connection() - 连接管理
# ============================================================

import json
import psycopg2
import psycopg2.extras
from datetime import datetime

from config.settings import cfg
from utils.logger import write_simple_error_log


def get_db_config():
    return {
        "host": getattr(cfg, "DB_HOST", "localhost"),
        "port": getattr(cfg, "DB_PORT", 5432),
        "dbname": getattr(cfg, "DB_NAME", "audit_ocr"),
        "user": getattr(cfg, "DB_USER", "postgres"),
        "password": getattr(cfg, "DB_PASSWORD", "admin"),
    }


def get_connection():
    try:
        return psycopg2.connect(**get_db_config())
    except Exception as e:
        write_simple_error_log("db_connect_fail", "", f"数据库连接失败: {str(e)}")
        return None


def test_connection():
    conn = get_connection()
    if conn:
        conn.close()
        return True
    return False


def to_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes")
    return False


def to_str(v):
    if v is None:
        return ""
    return str(v)


COLUMN_MAP = [
    ("图片名称", "image_name"),
    ("图片路径", "image_path"),
    ("分类保存路径", "classified_save_path"),
    ("图像类型", "image_type"),
    ("票据代码", "invoice_code"),
    ("票据号码", "invoice_number"),
    ("日期", "date"),
    ("总金额", "total_amount"),
    ("相关方", "relevant_party"),
    ("税率", "tax_rate"),
    ("税号", "tax_id"),
    ("开户行/账号", "bank_info"),
    ("流水号", "serial_number"),
    ("详情", "details"),
    ("印章类型", "seal_type"),
    ("印章编号", "seal_number"),
    ("印章清晰度", "seal_clarity"),
    ("骑缝章完整性", "joint_seal"),
    ("统一社会信用代码", "unified_social_credit_code"),
    ("法人", "legal_person"),
    ("证照有效期", "valid_period"),
    ("资产标签", "asset_tag"),
    ("资产名称", "asset_name"),
    ("存放位置", "location"),
    ("资产数量", "quantity"),
    ("工程进度", "progress"),
    ("签字人", "signer"),
    ("审批层级", "approval_level"),
    ("附件完整性", "attachment_complete"),
    ("其他信息", "other_info"),
    ("日期有效性", "date_valid", "bool"),
    ("金额有效性", "amount_valid", "bool"),
    ("编码格式有效性", "code_format_valid", "bool"),
    ("无缺项", "no_missing_field", "bool"),
    ("图片正常", "image_normal", "bool"),
    ("无重复报销", "no_duplicate", "bool"),
    ("信息一致性", "consistent_info", "bool"),
    ("合规性", "compliance", "bool"),
    ("无舞弊", "no_fraud", "bool"),
    ("风险评级", "risk_rating"),
    ("风险说明", "risk_description"),
    ("审计结论", "audit_conclusion"),
    ("审计说明", "audit_reason"),
    ("匹配知识库规则", "kb_rule_ids"),
    ("CPA知识辅导", "cpa_tutoring"),
]


def row_to_db_values(row):
    """将中文key的字典转为(列名列表, 值列表, jsonb值, batch_id)"""
    str_cols = []
    str_vals = []
    bool_cols = []
    bool_vals = []

    for mapping in COLUMN_MAP:
        cn_key = mapping[0]
        db_col = mapping[1]
        is_bool = len(mapping) > 2 and mapping[2] == "bool"

        val = row.get(cn_key)
        if is_bool:
            bool_cols.append(db_col)
            bool_vals.append(to_bool(val))
        else:
            str_cols.append(db_col)
            str_vals.append(to_str(val))

    return str_cols, str_vals, bool_cols, bool_vals


def save_batch_results(results: list, batch_id: str = None):
    if not batch_id:
        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    conn = get_connection()
    if not conn:
        return 0, len(results)

    success_count = 0
    fail_count = 0

    try:
        with conn:
            for row in results:
                try:
                    str_cols, str_vals, bool_cols, bool_vals = row_to_db_values(row)

                    all_cols = str_cols + bool_cols + [
                        "full_json", "batch_id", "audit_time"
                    ]
                    placeholders = ", ".join([f"%s"] * (len(str_vals) + len(bool_vals) + 3))
                    cols_str = ", ".join(all_cols)
                    sql = f"INSERT INTO audit_results ({cols_str}) VALUES ({placeholders})"

                    audit_time_str = row.get("审计时间")
                    if audit_time_str:
                        try:
                            audit_time = datetime.strptime(str(audit_time_str), "%Y-%m-%d %H:%M:%S")
                        except:
                            audit_time = datetime.now()
                    else:
                        audit_time = datetime.now()

                    full_json = row.get("_full_json", {})
                    if isinstance(full_json, dict):
                        full_json_str = json.dumps(full_json, ensure_ascii=False)
                    else:
                        full_json_str = "{}"

                    all_vals = str_vals + bool_vals + [full_json_str, batch_id, audit_time]

                    with conn.cursor() as cur:
                        cur.execute(sql, all_vals)
                    success_count += 1

                except Exception as e:
                    write_simple_error_log("db_insert_fail", to_str(row.get("图片名称")),
                                           f"数据库写入失败: {str(e)}")
                    fail_count += 1
                    continue

    except Exception as e:
        write_simple_error_log("db_batch_insert_fail", "", f"批量数据库写入失败: {str(e)}")
        return success_count, fail_count


def save_single_result(row: dict, batch_id: str):
    """单条写入数据库，失败时记录日志但不抛异常"""
    conn = get_connection()
    if not conn:
        return False

    try:
        with conn:
            str_cols, str_vals, bool_cols, bool_vals = row_to_db_values(row)

            all_cols = str_cols + bool_cols + [
                "full_json", "batch_id", "audit_time"
            ]
            placeholders = ", ".join([f"%s"] * (len(str_vals) + len(bool_vals) + 3))
            cols_str = ", ".join(all_cols)
            sql = f"INSERT INTO audit_results ({cols_str}) VALUES ({placeholders})"

            audit_time_str = row.get("审计时间")
            if audit_time_str:
                try:
                    audit_time = datetime.strptime(str(audit_time_str), "%Y-%m-%d %H:%M:%S")
                except:
                    audit_time = datetime.now()
            else:
                audit_time = datetime.now()

            full_json = row.get("_full_json", {})
            if isinstance(full_json, dict):
                full_json_str = json.dumps(full_json, ensure_ascii=False)
            else:
                full_json_str = "{}"

            all_vals = str_vals + bool_vals + [full_json_str, batch_id, audit_time]

            with conn.cursor() as cur:
                cur.execute(sql, all_vals)

        write_simple_error_log("db_insert_ok", to_str(row.get("图片名称")), f"成功写入 batch={batch_id}")
        return True

    except Exception as e:
        write_simple_error_log("db_insert_fail", to_str(row.get("图片名称")),
                               f"数据库写入失败: {str(e)}")
        return False
