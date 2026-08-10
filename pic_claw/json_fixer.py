"""
JSON修复工具
功能：当模型输出的JSON格式不标准时，自动调用模型修复
适用于Agent1分类和Agent2提取
"""
import re
import json
import time
from config.settings import set_provider, get_provider_config
from services.ollama_client import call_llm, call_ollama_model


def extract_json_from_response(raw_text: str) -> dict:
    """从模型响应中提取JSON（基础版）"""
    text = raw_text.strip()
    # 去除markdown代码块
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取第一个{到最后一个}之间的内容
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def fix_json_with_model(raw_text: str, expected_structure: str, max_retries: int = 2, has_image: bool = False, image_base64: str = None) -> dict:
    """
    当JSON解析失败时，调用模型修复
    
    参数:
        raw_text: 模型原始输出（无法解析的JSON）
        expected_structure: 期望的JSON结构描述
        max_retries: 最大重试次数
        has_image: 是否需要附带图片（Agent1/2分类提取时需要）
        image_base64: 图片base64编码
    
    返回:
        修复后的JSON字典，如果修复失败返回None
    """
    fix_prompt = f"""你是一位JSON格式修复专家。请修复以下JSON内容。

## 期望的JSON结构
{expected_structure}

## 需要修复的原始内容（格式有误）
{raw_text[:2000]}

## 修复要求
1. 严格按照期望结构输出完整、合法的JSON
2. 修正所有格式错误（缺少逗号、引号不闭合、字段类型错误等）
3. 补充缺失的字段（无值填"N/A"或null）
4. 只输出JSON，不要包含任何其他文字
5. 确保JSON可以被json.loads()直接解析

请输出修复后的JSON："""

    for retry in range(max_retries):
        try:
            if has_image and image_base64:
                fixed_text = call_llm(fix_prompt, model_key="main", image_base64=image_base64)
            else:
                fixed_text = call_llm(fix_prompt, model_key="main")
            
            result = extract_json_from_response(fixed_text)
            if result is not None:
                return result
            
            print(f"  ⚠️ JSON修复第{retry+1}次失败，继续重试...")
            time.sleep(2)
        except Exception as e:
            print(f"  ⚠️ JSON修复调用失败: {e}")
            time.sleep(2)
    
    return None


def call_with_json_retry(prompt: str, expected_structure: str, max_retries: int = 2, has_image: bool = False, image_base64: str = None) -> dict:
    """
    调用模型并自动修复JSON格式错误
    
    参数:
        prompt: 发送给模型的提示词
        expected_structure: 期望的JSON结构描述（用于修复时参考）
        max_retries: JSON修复最大重试次数
        has_image: 是否需要附带图片
        image_base64: 图片base64编码
    
    返回:
        (result_dict, raw_text, is_fixed)
        - result_dict: 解析后的JSON字典
        - raw_text: 模型原始输出
        - is_fixed: 是否经过修复
    """
    # 第一次调用
    try:
        if has_image and image_base64:
            raw_text = call_llm(prompt, model_key="main", image_base64=image_base64)
        else:
            raw_text = call_llm(prompt, model_key="main")
    except Exception as e:
        return None, str(e), False
    
    # 尝试解析
    result = extract_json_from_response(raw_text)
    if result is not None:
        return result, raw_text, False
    
    # 解析失败，尝试修复
    print(f"  ⚠️ JSON解析失败，尝试自动修复...")
    fixed_result = fix_json_with_model(raw_text, expected_structure, max_retries, has_image, image_base64)
    
    if fixed_result is not None:
        return fixed_result, raw_text, True
    
    return None, raw_text, False


def get_expected_structure_description(task_type: str) -> str:
    """获取不同任务的期望JSON结构描述"""
    if task_type == "classify":
        return """{
    "type_name": "凭证类型名称（字符串）",
    "category_name": "所属大类名称（字符串）",
    "confidence": 0.95,
    "reasoning": "分类依据（字符串，20字以内）"
}"""
    elif task_type == "extract":
        return """{
    "image_type": "凭证类型（字符串）",
    "ocr_extract": {
        "invoice_code": "发票代码（字符串或N/A）",
        "invoice_number": "发票号码（字符串或N/A）",
        "date": "日期YYYY-MM-DD（字符串或N/A）",
        "total_amount": "金额纯数字（数字或N/A）",
        "relevant_party": "相关方（字符串或N/A）",
        "tax_rate": "税率（字符串或N/A）",
        "tax_id": "纳税人识别号（字符串或N/A）",
        "bank_info": "银行信息（字符串或N/A）",
        "serial_number": "流水号（字符串或N/A）",
        "details": "摘要（字符串或N/A）",
        "seal_info": {"seal_type": "...", "seal_number": "...", "seal_clarity": "...", "joint_seal": "..."},
        "license_info": {"unified_social_credit_code": "...", "legal_person": "...", "valid_period": "..."},
        "asset_info": {"asset_tag": "...", "asset_name": "...", "location": "...", "quantity": "...", "progress": "..."},
        "internal_control_info": {"signer": "...", "approval_level": "...", "attachment_complete": "..."},
        "other_info": "其他信息（字符串或N/A）"
    },
    "validation_result": {
        "date_valid": true, "amount_valid": true, "code_format_valid": true,
        "no_missing_field": true, "image_normal": true, "no_duplicate": true,
        "consistent_info": true, "compliance": true, "no_fraud": true
    },
    "risk_rating": "高风险/中风险/低风险",
    "risk_description": "风险说明（字符串）",
    "audit_conclusion": "通过/不通过/人工复核",
    "reason": "审计说明（字符串）",
    "audit_value": "数字化审计留痕，可核对、可预警",
    "_confidence": 0.95,
    "_summary": "凭证摘要（字符串，20字以内）"
}"""
    return "未知任务类型"