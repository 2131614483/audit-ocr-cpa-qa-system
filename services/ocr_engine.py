# ============================================================
# OCR 识别引擎
# 功能: 调用大模型视觉识别票据图片，提取结构化 JSON 数据，
#       失败时调用 DeepSeek 修复 JSON，结合知识库检索优化结果
# 核心: audit_ocr_recognize() - 主识别函数
#       fix_json_with_deepseek() - JSON 修复
# ============================================================

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import json
import re
import time
import base64
from datetime import datetime
from pathlib import Path

from config.settings import cfg
from config.constants import IMAGE_TYPES
from models.schemas import FALLBACK_RESULT, deep_merge, DEFAULT_OCR, DEFAULT_VALIDATION
from services.ollama_client import call_ollama_model, get_main_model, get_fix_model
from services.validator import is_valid_date, is_valid_amount, is_valid_credit_code
from services.knowledge_retriever import retrieve_relevant_rules, format_rules_for_prompt
from utils.json_handler import safe_json_loads
from utils.logger import write_simple_error_log, add_retry_task
from utils.converter import chinese_to_number


def fix_json_with_deepseek(raw_content: str, image_path: str, rules_text: str = "") -> dict:
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fix_prompt = f"""请修复以下JSON内容，要求：
1. 严格按照指定结构输出完整、合法的JSON（无需任何解释、无需额外文字）；
2. 修正格式错误（如缺少逗号、引号不闭合、字段类型错误等）；
3. 补充缺失的字段（无值填"N/A"，禁止使用null/None）；
4. 基于图片审计场景，合理规整内容（如日期格式统一为YYYY-MM-DD）；
5. 金额识别需兼容简体/繁体汉字数字（壹贰叁/壹貳參、万元/萬元、元/圓等）；
6. 识别到的繁体汉字金额需转换为标准阿拉伯数字（保留2位小数）；
7. 所有字段值必须是字符串/布尔值/数字，禁止使用null/None；
8. 当前系统时间为 {current_time_str}，基于此时间校验日期有效性；
{rules_text}

标准JSON结构：
{{
    "image_type": "图像类型（从列表选：{','.join(IMAGE_TYPES)}）",
    "ocr_extract": {{
        "invoice_code": "N/A", "invoice_number": "N/A", "date": "N/A", "total_amount": "N/A",
        "relevant_party": "N/A", "tax_rate": "N/A", "tax_id": "N/A", "bank_info": "N/A",
        "serial_number": "N/A", "details": "N/A",
        "seal_info": {{"seal_type": "N/A", "seal_number": "N/A", "seal_clarity": "N/A", "joint_seal": "N/A"}},
        "license_info": {{"unified_social_credit_code": "N/A", "legal_person": "N/A", "valid_period": "N/A"}},
        "asset_info": {{"asset_tag": "N/A", "asset_name": "N/A", "location": "N/A", "quantity": "N/A", "progress": "N/A"}},
        "internal_control_info": {{"signer": "N/A", "approval_level": "N/A", "attachment_complete": "N/A"}},
        "other_info": "N/A"
    }},
    "validation_result": {{
        "date_valid": true/false, "amount_valid": true/false, "code_format_valid": true/false,
        "no_missing_field": true/false, "image_normal": true/false, "no_duplicate": true/false,
        "consistent_info": true/false, "compliance": true/false, "no_fraud": true/false
    }},
    "risk_rating": "高风险/中风险/低风险",
    "risk_description": "风险说明",
    "audit_conclusion": "通过/不通过/人工复核",
    "reason": "审计说明",
    "audit_value": "数字化审计留痕，可核对、可预警"
}}

需要修复的原始内容：
{raw_content}
"""

    for retry in range(cfg.FIX_RETRY_TIMES):
        try:
            fix_content = call_ollama_model(get_fix_model(), fix_prompt)
            fix_content_clean = fix_content.strip().replace("```json", "").replace("```", "").replace("\\n", "\n")
            json_match = re.search(r"\{[\s\S]*\}", fix_content_clean)
            if not json_match:
                raise ValueError("修复后仍未识别到有效JSON")

            fix_json_str = json_match.group()
            fixed_result = json.loads(fix_json_str)
            fixed_result["image_type"] = fixed_result.get("image_type", "其他")
            write_simple_error_log("json_fix_success", image_path, f"DeepSeek修复JSON成功（重试{retry}次）")
            return fixed_result
        except Exception as e:
            error_msg = f"DeepSeek修复失败（重试{retry + 1}/{cfg.FIX_RETRY_TIMES}）：{str(e)}"
            write_simple_error_log("json_fix_fail", image_path, error_msg)
            if retry < cfg.FIX_RETRY_TIMES - 1:
                time.sleep(5)
                continue
            else:
                fallback = dict(FALLBACK_RESULT)
                fallback["ocr_extract"]["other_info"] = f"JSON修复失败：{str(e)}"
                fallback["risk_description"] = f"JSON格式错误且DeepSeek修复失败：{str(e)}"
                fallback["reason"] = f"JSON格式错误且DeepSeek修复失败：{str(e)}"
                return fallback


def audit_ocr_recognize(image_path: str, db_enabled: bool = None) -> dict:
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 从知识库检索相关审计规则
    img_name = Path(image_path).name
    rules_text = ""
    kb_rule_ids = ""
    _db = db_enabled if db_enabled is not None else getattr(cfg, "DB_ENABLED", False)
    if _db:
        try:
            query = f"审计凭证OCR识别 {img_name}"
            rules = retrieve_relevant_rules(query, top_k=5)
            if rules:
                rules_text = format_rules_for_prompt(rules)
                kb_rule_ids = ",".join(str(r["id"]) for r in rules)
                write_simple_error_log("kb_retrieve_success", image_path, f"检索到{len(rules)}条规则: {kb_rule_ids}")
        except Exception as e:
            write_simple_error_log("kb_retrieve_error", image_path, f"知识库检索异常: {str(e)}")

    prompt = f"""### 强制要求 ###
1. 必须输出完整、合法的JSON格式内容，不允许任何多余文字、解释、说明、备注；
2. JSON结构必须严格匹配下方的"标准JSON结构"，字段名、层级、数据类型完全一致；
3. 所有字段值不能为空，无对应信息时统一填"N/A"，禁止使用null/None；
4. 布尔值必须是true/false（小写），不能是"是/否""True/False"；
5. 日期格式统一为YYYY-MM-DD，金额保留2位小数，无值填"N/A"；
6. **金额识别强制要求**：
   - 必须识别并转换所有中文数字金额（包括简体和繁体）
   - 简体示例：壹仟贰佰叁拾肆元伍角陆分 → 1234.56
   - 繁体示例：壹仟貳佰參拾肆圓伍角陸分 → 1234.56
   - 支持的繁体字符：壹貳參肆伍陸柒捌玖拾佰仟萬億圓
   - 识别到的中文金额必须转换为阿拉伯数字（保留2位小数）填入total_amount字段

### 当前系统时间 ###
{current_time_str}
{rules_text}

### 处理步骤 ###
步骤1：识别图像类型，只能从以下列表选其一返回：{','.join(IMAGE_TYPES)}
步骤2：根据图像类型提取关键信息，重点识别所有金额字段（兼容简体/繁体汉字数字）；
步骤3：将识别到的中文大写金额（无论简体/繁体）转换为阿拉伯数字；
步骤4：基于当前时间验证信息有效性；
步骤5：风险评级并说明风险点；
步骤6：按指定JSON结构输出（无则填"N/A"，禁止使用null/None）。

### 标准JSON结构 ###
{{
    "image_type": "图像类型",
    "ocr_extract": {{
        "invoice_code": "N/A", "invoice_number": "N/A", "date": "N/A", "total_amount": "N/A",
        "relevant_party": "N/A", "tax_rate": "N/A", "tax_id": "N/A", "bank_info": "N/A",
        "serial_number": "N/A", "details": "N/A",
        "seal_info": {{"seal_type": "N/A", "seal_number": "N/A", "seal_clarity": "N/A", "joint_seal": "N/A"}},
        "license_info": {{"unified_social_credit_code": "N/A", "legal_person": "N/A", "valid_period": "N/A"}},
        "asset_info": {{"asset_tag": "N/A", "asset_name": "N/A", "location": "N/A", "quantity": "N/A", "progress": "N/A"}},
        "internal_control_info": {{"signer": "N/A", "approval_level": "N/A", "attachment_complete": "N/A"}},
        "other_info": "N/A"
    }},
    "validation_result": {{
        "date_valid": true/false, "amount_valid": true/false, "code_format_valid": true/false,
        "no_missing_field": true/false, "image_normal": true/false, "no_duplicate": true/false,
        "consistent_info": true/false, "compliance": true/false, "no_fraud": true/false
    }},
    "risk_rating": "高风险/中风险/低风险",
    "risk_description": "风险说明",
    "audit_conclusion": "通过/不通过/人工复核",
    "reason": "审计说明",
    "audit_value": "数字化审计留痕，可核对、可预警"
}}

### 输出要求 ###
只输出JSON内容，无任何其他文字！"""

    try:
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        error_reason = f"图片读取失败：{str(e)}"
        write_simple_error_log("image_read_fail", image_path, error_reason)
        add_retry_task("model_fail", image_path)
        fallback = dict(FALLBACK_RESULT)
        fallback["ocr_extract"]["other_info"] = error_reason
        fallback["risk_description"] = error_reason
        fallback["reason"] = error_reason
        return fallback

    raw_content = ""
    main_model_success = False

    for retry in range(cfg.RETRY_TIMES):
        try:
            raw_content = call_ollama_model(get_main_model(), prompt, image_base64)
            raw_content_clean = raw_content.strip().replace("```json", "").replace("```", "").replace("\\n", "\n")
            json_match = re.search(r"\{[\s\S]*\}", raw_content_clean)
            if not json_match:
                if retry == 0:
                    error_reason = f"主模型返回无有效JSON，直接调用DeepSeek修复"
                    write_simple_error_log("json_no_match", image_path, error_reason)
                    add_retry_task("json_error", image_path, raw_content)
                    audit_result = fix_json_with_deepseek(raw_content, image_path, rules_text)
                    main_model_success = True
                    break
                else:
                    raise ValueError(f"主模型第{retry + 1}次仍未返回有效JSON内容")

            json_str = json_match.group()
            audit_result = json.loads(json_str)
            main_model_success = True
            break

        except json.JSONDecodeError as e:
            error_reason = f"主模型JSON格式错误：{str(e)}"
            write_simple_error_log("json_format_error", image_path, error_reason)
            add_retry_task("json_error", image_path, raw_content)
            audit_result = fix_json_with_deepseek(raw_content, image_path, rules_text)
            main_model_success = True
            break

        except Exception as e:
            error_reason = f"主模型调用失败（重试{retry + 1}/{cfg.RETRY_TIMES}）：{str(e)}"
            write_simple_error_log("model_call_fail", image_path, error_reason)
            if retry < cfg.RETRY_TIMES - 1:
                print(f"⚠️ {image_path} 主模型识别失败（重试{retry + 1}/{cfg.RETRY_TIMES}）：{str(e)}")
                time.sleep(5)
            else:
                add_retry_task("model_fail", image_path)
                fallback = dict(FALLBACK_RESULT)
                fallback["risk_description"] = f"主模型识别失败（已重试{cfg.RETRY_TIMES}次）：{str(e)}"
                fallback["reason"] = fallback["risk_description"]
                return fallback

    if main_model_success:
        audit_result["image_type"] = audit_result.get("image_type", "其他")
        audit_result["risk_rating"] = audit_result.get("risk_rating", "高风险")
        audit_result["audit_conclusion"] = audit_result.get("audit_conclusion", "不通过")
        audit_result["risk_description"] = audit_result.get("risk_description", "未识别")
        audit_result["reason"] = audit_result.get("reason", "未识别")

        audit_result["ocr_extract"] = deep_merge(DEFAULT_OCR, audit_result.get("ocr_extract", {}))
        audit_result["validation_result"] = deep_merge(DEFAULT_VALIDATION, audit_result.get("validation_result", {}))
        audit_result["audit_value"] = audit_result.get("audit_value", "数字化审计留痕，可核对、可预警")
        audit_result["kb_rule_ids"] = kb_rule_ids

        raw_amount = audit_result["ocr_extract"]["total_amount"]
        converted_amount = chinese_to_number(raw_amount)
        if converted_amount is not None:
            audit_result["ocr_extract"]["total_amount"] = str(converted_amount)

        audit_result["validation_result"]["date_valid"] = is_valid_date(audit_result["ocr_extract"]["date"])
        audit_result["validation_result"]["amount_valid"] = is_valid_amount(audit_result["ocr_extract"]["total_amount"])
        audit_result["validation_result"]["code_format_valid"] = is_valid_credit_code(
            audit_result["ocr_extract"]["license_info"]["unified_social_credit_code"])

        return audit_result

    return dict(FALLBACK_RESULT)
