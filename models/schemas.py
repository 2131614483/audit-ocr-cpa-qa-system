# ============================================================
# 数据模型定义
# 功能: 定义 OCR 识别的默认 JSON 结构和验证结果结构，
#       提供深度合并工具（默认值 + 识别结果）
# 核心: DEFAULT_OCR - 默认 OCR 字段
#       DEFAULT_VALIDATION - 默认验证字段
#       deep_merge() - 深度合并
# ============================================================

DEFAULT_OCR = {
    "invoice_code": "N/A", "invoice_number": "N/A", "date": "N/A", "total_amount": "N/A",
    "relevant_party": "N/A", "tax_rate": "N/A", "tax_id": "N/A", "bank_info": "N/A",
    "serial_number": "N/A", "details": "N/A",
    "seal_info": {"seal_type": "N/A", "seal_number": "N/A", "seal_clarity": "N/A", "joint_seal": "N/A"},
    "license_info": {"unified_social_credit_code": "N/A", "legal_person": "N/A", "valid_period": "N/A"},
    "asset_info": {"asset_tag": "N/A", "asset_name": "N/A", "location": "N/A", "quantity": "N/A",
                   "progress": "N/A"},
    "internal_control_info": {"signer": "N/A", "approval_level": "N/A", "attachment_complete": "N/A"},
    "other_info": "N/A"
}

DEFAULT_VALIDATION = {
    "date_valid": True, "amount_valid": True, "code_format_valid": True,
    "no_missing_field": True, "image_normal": True, "no_duplicate": True,
    "consistent_info": True, "compliance": True, "no_fraud": True
}

FALLBACK_RESULT = {
    "image_type": "其他",
    "ocr_extract": dict(DEFAULT_OCR),
    "validation_result": dict(DEFAULT_VALIDATION),
    "risk_rating": "高风险",
    "risk_description": "默认错误：未识别",
    "audit_conclusion": "不通过",
    "reason": "默认错误：未识别",
    "audit_value": "数字化审计留痕，可核对、可预警"
}


def deep_merge(default: dict, target: dict) -> dict:
    if not isinstance(target, dict):
        return default.copy()

    merged = target.copy()

    for key, value in default.items():
        if key not in merged or merged[key] is None:
            merged[key] = value
        elif isinstance(value, dict) and isinstance(merged[key], dict):
            merged[key] = deep_merge(value, merged[key])
        elif isinstance(value, dict) and not isinstance(merged[key], dict):
            merged[key] = value.copy()
    return merged
