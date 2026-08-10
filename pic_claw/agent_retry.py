"""
Agent重试工具
功能：为Agent1分类和Agent2提取提供统一的重试机制
- API调用失败自动重试
- JSON格式错误自动修复重试
- 可配置重试次数和等待时间
"""
# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import time
import json
import re
from config.settings import set_provider
from services.ollama_client import call_llm


def extract_json(raw_text: str) -> dict:
    """从模型响应中提取JSON"""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def retry_with_fix(prompt: str, expected_structure: str, 
                   image_base64: str = None, 
                   max_retries: int = 3, 
                   retry_delay: int = 2,
                   task_name: str = "任务") -> tuple:
    """
    带重试和自动修复的模型调用
    
    参数:
        prompt: 发送给模型的提示词
        expected_structure: 期望的JSON结构描述（用于修复时参考）
        image_base64: 图片base64编码（可选）
        max_retries: 最大重试次数（默认3次）
        retry_delay: 重试等待秒数（默认2秒）
        task_name: 任务名称（用于日志输出）
    
    返回:
        (result_dict, error_message)
        - result_dict: 解析后的JSON字典，成功时返回，失败时返回None
        - error_message: 错误信息，成功时返回None，失败时返回错误描述
    """
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            # 调用模型
            if image_base64:
                raw_text = call_llm(prompt, model_key="main", image_base64=image_base64)
            else:
                raw_text = call_llm(prompt, model_key="main")
            
            # 尝试解析JSON
            result = extract_json(raw_text)
            if result is not None:
                return result, None
            
            # JSON解析失败，尝试修复
            if attempt < max_retries:
                print(f"  ⚠️ [{task_name}] JSON格式错误，尝试修复（第{attempt}次）...")
                fix_prompt = f"""请修复以下JSON格式错误。

## 期望的JSON结构
{expected_structure}

## 需要修复的原始内容
{raw_text[:2000]}

## 要求
1. 严格按照期望结构输出完整合法的JSON
2. 修正所有格式错误
3. 只输出JSON，不要包含任何其他文字

请输出修复后的JSON："""
                
                if image_base64:
                    fixed_text = call_llm(fix_prompt, model_key="main", image_base64=image_base64)
                else:
                    fixed_text = call_llm(fix_prompt, model_key="main")
                
                result = extract_json(fixed_text)
                if result is not None:
                    print(f"  ✅ [{task_name}] JSON修复成功")
                    return result, None
                
                print(f"  ⚠️ [{task_name}] JSON修复失败，继续重试...")
                time.sleep(retry_delay)
            else:
                last_error = f"JSON格式错误且修复失败"
                return None, last_error
                
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                print(f"  ⚠️ [{task_name}] 调用失败: {str(e)[:80]}，{retry_delay}秒后重试（第{attempt}次）...")
                time.sleep(retry_delay)
            else:
                print(f"  ❌ [{task_name}] 最终失败: {str(e)[:80]}")
    
    return None, last_error


def classify_with_retry(prompt: str, image_base64: str, max_retries: int = 3) -> tuple:
    """
    Agent1分类专用重试
    
    返回:
        (result_dict, error_message)
    """
    expected = """{
    "type_name": "凭证类型名称（字符串）",
    "category_name": "所属大类名称（字符串）",
    "confidence": 0.95,
    "reasoning": "分类依据（字符串，20字以内）"
}"""
    return retry_with_fix(prompt, expected, image_base64, max_retries, task_name="Agent1分类")


def extract_with_retry(prompt: str, image_base64: str, max_retries: int = 3) -> tuple:
    """
    Agent2提取专用重试
    
    返回:
        (result_dict, error_message)
    """
    expected = """{
    "image_type": "凭证类型（字符串）",
    "ocr_extract": {
        "invoice_code": "发票代码或N/A",
        "invoice_number": "发票号码或N/A",
        "date": "日期YYYY-MM-DD或N/A",
        "total_amount": "金额纯数字或N/A",
        "relevant_party": "相关方或N/A",
        "seal_info": {"seal_type": "...", "seal_number": "...", "seal_clarity": "...", "joint_seal": "..."},
        "license_info": {"unified_social_credit_code": "...", "legal_person": "...", "valid_period": "..."},
        "asset_info": {"asset_tag": "...", "asset_name": "...", "location": "...", "quantity": "...", "progress": "..."},
        "internal_control_info": {"signer": "...", "approval_level": "...", "attachment_complete": "..."},
        "other_info": "其他信息或N/A"
    },
    "validation_result": {
        "date_valid": true, "amount_valid": true, "code_format_valid": true,
        "no_missing_field": true, "image_normal": true, "no_duplicate": true,
        "consistent_info": true, "compliance": true, "no_fraud": true
    },
    "risk_rating": "高风险/中风险/低风险",
    "risk_description": "风险说明",
    "audit_conclusion": "通过/不通过/人工复核",
    "reason": "审计说明",
    "audit_value": "数字化审计留痕，可核对、可预警",
    "_confidence": 0.95,
    "_summary": "凭证摘要（20字以内）"
}"""
    return retry_with_fix(prompt, expected, image_base64, max_retries, task_name="Agent2提取")