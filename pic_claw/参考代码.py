import os
import re
import requests
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
import base64
import time
import json
from datetime import datetime
import shutil
import traceback

# ===================== 审计配置项（按需修改） =====================
OLLAMA_API_URL = "http://localhost:11434/api/chat"
# 主识别模型 + 错误修复模型配置
MAIN_MODEL = "qwen3.5:latest"  # 第一次调用的主模型
FIX_MODEL = "deepseek-r1:8b"  # 出错时用于修复的模型
IMAGE_FOLDER = r"C:\Backup\Pictures\测试"
EXCEL_OUTPUT = r"C:\Backup\Pictures\测试\audit_ocr_result1.xlsx"
OUTPUT_ROOT_FOLDER = r"C:\Backup\Pictures\测试\分类结果"
ERROR_LOG_SIMPLE = r"C:\Backup\Pictures\测试\ocr_error_simple.log"
RETRY_TASK_LOG = r"C:\Backup\Pictures\测试\ocr_retry_tasks.log"
SUPPORTED_FORMATS = [".png", ".jpg", ".jpeg", ".webp", ".gif"]
RETRY_TIMES = 5  # 主模型重试次数
FIX_RETRY_TIMES = 3  # 修复模型重试次数
PROCESS_RETRY_TIMES = 5
TIMEOUT = 300

IMAGE_TYPES = [
    # 增值税发票相关
    "增值税专用发票", "增值税普通发票", "电子增值税普通发票", "增值税电子普通发票", "增值税发票电子化",
    "机动车销售统一发票",

    # 交通票据
    "出租车票", "火车票", "飞机票", "多张飞机票", "轮船票", "长途客运票", "地铁票", "公交票", "停车费发票",
    "过路费发票",

    # 银行金融票据
    "银行回单", "电子回单", "银行对账单", "银行承兑汇票", "商业承兑汇票", "银行承兑汇票复印件", "商业承兑汇票复印件",
    "现金支票", "转账支票", "银行存款凭证", "现金日记账", "银行存款日记账",

    # 收据类
    "收据", "小票", "发票清单", "费用明细表", "报销单", "差旅费报销单", "会议费发票", "培训费发票", "办公用品发票",

    # 合同协议类
    "合同", "协议", "租赁合同", "采购合同", "销售合同", "服务合同", "技术合同", "劳务合同", "劳动合同", "保密协议",
    "战略合作协议", "技术开发合同", "技术转让合同", "技术咨询合同", "技术服务合同", "建设工程合同", "承揽合同",

    # 财务报表类
    "财务报表", "现金流量表", "资产负债表", "利润表", "所有者权益变动表", "利润分配表", "财务报表附注",
    "审计报告", "审计报告附注", "资产评估报告", "资产评估报告附注", "财务分析报告",

    # 资产管理类
    "固定资产照片", "存货照片", "在建工程现场照片", "设备验收单", "资产盘点表", "资产转移单", "资产报废单",
    "固定资产明细账", "无形资产明细账", "长期待摊费用明细账", "预付账款明细账", "预收账款明细账",

    # 印章类
    "公章", "财务章", "法人章", "合同章", "发票专用章", "业务专用章", "法定代表人章",

    # 证照类
    "营业执照", "开户许可证", "资质证书", "安全生产许可证", "卫生许可证", "食品经营许可证", "道路运输许可证",
    "税务登记证", "组织机构代码证", "社会保险登记证", "外汇登记证", "进出口许可证",

    # 审批类
    "审批单", "签字页", "申请表", "请示报告", "批复文件", "会议纪要", "决策文件", "立项审批表",

    # 会议活动类
    "会议照片", "现场检查照片", "活动签到表", "培训签到表", "会议通知", "会议邀请函", "活动总结报告",

    # 海外票据
    "海外票据", "境外发票", "外汇兑换凭证", "国际运输发票", "海外服务发票", "跨境交易凭证",

    # 海关税务类
    "海关单据", "报关单", "报关单复印件", "进口关税缴款书", "出口退税单据", "海关缴款书", "海关专用缴款书",
    "完税证明", "税收缴款书", "印花税票", "土地使用税完税证明", "房产税完税证明", "车船税完税证明",

    # 保险类
    "保险单据", "保险费收据", "理赔通知书", "保险合同", "保险单", "保险发票", "保险费发票",

    # 政府公共事业类
    "水费发票", "电费发票", "燃气费发票", "物业费收据", "停车费收据", "交通违章罚款单", "社保缴费凭证",
    "医保缴费凭证", "公积金缴费凭证", "电话费发票", "网络费发票", "宽带费发票", "有线电视费",

    # 教育培训类
    "学费收据", "培训费发票", "考试费收据", "教材费发票", "住宿费发票", "餐费发票", "学杂费收据",

    # 医疗类
    "医疗费用发票", "药品费收据", "检查费单据", "治疗费发票", "住院费发票", "手术费发票", "化验费发票",

    # 金融投资类
    "股票交易凭证", "基金交易单据", "债券凭证", "理财产品购买凭证", "投资协议", "投资收益凭证",

    # 其他特殊票据
    "捐赠收据", "赞助费发票", "会费收据", "押金收据", "违约金收据", "赔偿金收据", "退款凭证",
    "结算单", "结算凭证", "结算清单", "结算报告", "结算确认书", "结算协议", "结算申请表",
    "其他"
]


# ===================== 新增：大写金额转数字工具函数（兼容繁体） =====================
def chinese_to_number(chinese_amount: str | float | int | None) -> float | None:
    """
    中文大写金额转阿拉伯数字（兼容简体/繁体）
    支持：
    简体：壹贰叁肆伍陆柒捌玖拾佰仟万亿 元角分
    繁体：壹貳參肆伍陸柒捌玖拾佰仟萬億 圓角分
    """
    # 核心修复：处理非字符串类型输入和None值
    if chinese_amount is None or pd.isna(chinese_amount) or chinese_amount == "N/A":
        return None

    # 强制转换为字符串，避免float/int/None类型调用strip()报错
    s = str(chinese_amount).strip()

    # 如果是纯数字字符串，直接转换
    if re.match(r'^\d+(\.\d{1,2})?$', s):
        try:
            return round(float(s), 2)
        except:
            return None

    # 基础映射（包含简体+繁体）
    digit_map = {
        # 简体
        '零': 0, '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5,
        '陆': 6, '柒': 7, '捌': 8, '玖': 9,
        '拾': 10, '佰': 100, '仟': 1000, '万': 10000, '亿': 100000000,
        # 繁体
        '零': 0, '壹': 1, '貳': 2, '參': 3, '肆': 4, '伍': 5,
        '陸': 6, '柒': 7, '捌': 8, '玖': 9,
        '拾': 10, '佰': 100, '仟': 1000, '萬': 10000, '億': 100000000
    }
    unit_map = {
        '元': 1.0, '圆': 1.0, '圓': 1.0,  # 元的不同写法
        '角': 0.1,
        '分': 0.01
    }

    total = 0
    has_yuan = False

    try:
        # 处理元/圆/圓、角、分
        if any(unit in s for unit in ['元', '圆', '圓']):
            # 找到第一个出现的元/圆/圓
            yuan_pos = min([s.find(unit) for unit in ['元', '圆', '圓'] if s.find(unit) != -1])
            yuan_part = s[:yuan_pos]
            rest = s[yuan_pos + 1:]
            has_yuan = True
        else:
            yuan_part = s
            rest = ''

        # 处理整数部分
        temp = 0
        for c in yuan_part:
            if c in digit_map:
                val = digit_map[c]
                if val >= 10:
                    if temp == 0:
                        temp = 1 * val
                    else:
                        temp *= val
                else:
                    temp += val
            elif c in ['整', '正']:  # 兼容繁体的"正"
                pass
        total += temp

        # 处理角分
        if '角' in rest:
            jiao_idx = rest.index('角')
            if jiao_idx > 0:
                jiao = rest[jiao_idx - 1]
                total += digit_map.get(jiao, 0) * 0.1
        if '分' in rest:
            fen_idx = rest.index('分')
            if fen_idx > 0:
                fen = rest[fen_idx - 1]
                total += digit_map.get(fen, 0) * 0.01

        return round(total, 2) if total > 0 else None
    except:
        return None


# ===================== 工具函数：日志处理 =====================
def init_log_files():
    """初始化日志文件（清空旧内容）"""
    # 初始化简洁错误日志
    with open(ERROR_LOG_SIMPLE, "w", encoding="utf-8") as f:
        f.write("=== OCR审计错误日志 ===\n")
        f.write(f"初始化时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("格式：[时间] | 错误类型 | 文件路径 | 核心原因\n")
        f.write("-" * 120 + "\n")

    # 初始化重跑任务日志（JSON数组格式）
    with open(RETRY_TASK_LOG, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)


def write_simple_error_log(error_type: str, image_path: str, reason: str):
    """写入简洁错误日志（可追溯）"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_content = f"[{timestamp}] | {error_type} | {image_path} | {reason}\n"
    with open(ERROR_LOG_SIMPLE, "a", encoding="utf-8") as f:
        f.write(log_content)


def add_retry_task(task_type: str, image_path: str, raw_content: str = ""):
    """添加重跑任务到日志（支持两类任务：model_fail/json_error）"""
    # 读取现有任务
    try:
        with open(RETRY_TASK_LOG, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    except:
        tasks = []

    # 去重：避免重复添加同一文件的同一类型任务
    task_exists = any(
        t["image_path"] == image_path and t["task_type"] == task_type
        for t in tasks
    )
    if task_exists:
        return

    # 添加新任务
    new_task = {
        "task_type": task_type,  # model_fail:模型调用失败; json_error:JSON格式错误
        "image_path": image_path,
        "raw_content": raw_content,  # JSON错误时保存原始内容
        "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "retry_status": "pending"  # pending:待重跑; success:重跑成功; fail:重跑失败
    }
    tasks.append(new_task)

    # 写入日志
    with open(RETRY_TASK_LOG, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def update_retry_task_status(image_path: str, task_type: str, status: str):
    """更新重跑任务状态"""
    try:
        with open(RETRY_TASK_LOG, "r", encoding="utf-8") as f:
            tasks = json.load(f)

        for task in tasks:
            if task["image_path"] == image_path and task["task_type"] == task_type:
                task["retry_status"] = status
                task["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break

        with open(RETRY_TASK_LOG, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
    except Exception as e:
        write_simple_error_log("log_update_fail", image_path, f"更新重跑任务状态失败：{str(e)}")


# ===================== 核心函数：自定义JSON序列化器（修复Match对象问题） =====================
class CustomJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理非序列化类型"""

    def default(self, obj):
        # 处理正则Match对象
        if isinstance(obj, re.Match):
            return obj.group()  # 返回匹配的字符串内容
        # 处理datetime对象
        elif isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        # 处理None值和其他不可序列化对象
        elif obj is None:
            return "N/A"
        else:
            return str(obj)


# ===================== 核心函数：调用指定Ollama模型（主动清空上下文） =====================
def call_ollama_model(model_name: str, prompt: str, image_base64: str = "") -> str:
    """
    强制清空上下文调用Ollama模型：
    1. 每次调用前主动重置对话上下文（通过Ollama API的特殊参数）
    2. 仅传递当前请求，无任何历史对话
    """
    # ========== 核心：主动清空Ollama侧的对话上下文 ==========
    reset_payload = {
        "model": model_name,
        "messages": [{"role": "system", "content": "清空所有对话历史，重置上下文"}],
        "options": {"num_ctx": 0},  # 强制重置上下文窗口
        "stream": False
    }
    try:
        # 先发送重置请求，确保上下文清空
        requests.post(OLLAMA_API_URL, json=reset_payload, timeout=TIMEOUT)
        # 仅首次启动时记录上下文重置日志，避免冗余
        if not hasattr(call_ollama_model, "context_reset_logged"):
            write_simple_error_log("context_reset_success", "", f"成功清空{model_name}的上下文")
            call_ollama_model.context_reset_logged = True
    except Exception as e:
        # 重置失败不影响主请求，但记录日志
        write_simple_error_log("context_reset_fail", "", f"清空上下文失败：{str(e)}")

    # ========== 构造全新的无上下文请求 ==========
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt}  # 永远只有这一条，全新上下文
        ],
        "temperature": 0.0,
        "stream": False,
        "max_tokens": 16384
    }

    # 附加图片（如果有）
    if image_base64:
        payload["messages"][0]["images"] = [image_base64]

    # 执行主请求
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        result = response.json()
        return result["message"]["content"].strip()
    except Exception as e:
        raise Exception(f"模型{model_name}调用失败：{str(e)}")


# ===================== 核心函数：使用DeepSeek修复JSON =====================
def fix_json_with_deepseek(raw_content: str, image_path: str) -> Dict[str, Any]:
    """使用DeepSeek模型修复JSON格式错误"""
    fix_prompt = f"""请修复以下JSON内容，要求：
    1. 严格按照指定结构输出完整、合法的JSON（无需任何解释、无需额外文字）；
    2. 修正格式错误（如缺少逗号、引号不闭合、字段类型错误等）；
    3. 补充缺失的字段（无值填"N/A"，禁止使用null/None）；
    4. 基于图片审计场景，合理规整内容（如日期格式统一为YYYY-MM-DD）；
    5. 金额识别需兼容简体/繁体汉字数字（壹贰叁/壹貳參、万元/萬元、元/圓等）；
    6. 识别到的繁体汉字金额需转换为标准阿拉伯数字（保留2位小数）；
    7. 所有字段值必须是字符串/布尔值/数字，禁止使用null/None；

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

    # 调用DeepSeek模型进行修复（带重试）
    for retry in range(FIX_RETRY_TIMES):
        try:
            fix_content = call_ollama_model(FIX_MODEL, fix_prompt)

            # 提取JSON内容（增强容错：去除更多干扰字符）
            fix_content_clean = fix_content.strip().replace("```json", "").replace("```", "").replace("\\n", "\n")
            json_match = re.search(r"\{[\s\S]*\}", fix_content_clean)
            if not json_match:
                raise ValueError("修复后仍未识别到有效JSON")

            fix_json_str = json_match.group()
            fixed_result = json.loads(fix_json_str)

            # 强制补充image_type字段，避免缺失
            fixed_result["image_type"] = fixed_result.get("image_type", "其他")
            write_simple_error_log("json_fix_success", image_path, f"DeepSeek修复JSON成功（重试{retry}次）")
            return fixed_result
        except Exception as e:
            error_msg = f"DeepSeek修复失败（重试{retry + 1}/{FIX_RETRY_TIMES}）：{str(e)}"
            write_simple_error_log("json_fix_fail", image_path, error_msg)
            if retry < FIX_RETRY_TIMES - 1:
                time.sleep(5)  # 修复：重试等待5秒
                continue
            else:
                # 最终修复失败，返回兜底JSON
                return {
                    "image_type": "其他",
                    "ocr_extract": {
                        "invoice_code": "N/A", "invoice_number": "N/A", "date": "N/A", "total_amount": "N/A",
                        "relevant_party": "N/A", "tax_rate": "N/A", "tax_id": "N/A", "bank_info": "N/A",
                        "serial_number": "N/A", "details": "N/A",
                        "seal_info": {"seal_type": "N/A", "seal_number": "N/A", "seal_clarity": "N/A",
                                      "joint_seal": "N/A"},
                        "license_info": {"unified_social_credit_code": "N/A", "legal_person": "N/A",
                                         "valid_period": "N/A"},
                        "asset_info": {"asset_tag": "N/A", "asset_name": "N/A", "location": "N/A", "quantity": "N/A",
                                       "progress": "N/A"},
                        "internal_control_info": {"signer": "N/A", "approval_level": "N/A",
                                                  "attachment_complete": "N/A"},
                        "other_info": f"JSON修复失败：{str(e)}"
                    },
                    "validation_result": {
                        "date_valid": False, "amount_valid": False, "code_format_valid": False,
                        "no_missing_field": False, "image_normal": False, "no_duplicate": True,
                        "consistent_info": True, "compliance": False, "no_fraud": True
                    },
                    "risk_rating": "高风险",
                    "risk_description": f"JSON格式错误且DeepSeek修复失败：{str(e)}",
                    "audit_conclusion": "不通过",
                    "reason": f"JSON格式错误且DeepSeek修复失败：{str(e)}",
                    "audit_value": "数字化审计留痕，可核对、可预警"
                }


# ===================== 工具函数：数据校验 =====================
def is_valid_date(date_str: str | None) -> bool:
    """修复：处理None值的日期校验"""
    if date_str is None or date_str == "N/A":
        return True
    try:
        date = datetime.strptime(str(date_str), "%Y-%m-%d")
        return date <= datetime.now()
    except:
        return False


def is_valid_amount(amount_str: str | float | int | None) -> bool:
    """修复：支持数字类型和None值输入的金额校验"""
    if amount_str is None or amount_str == "N/A":
        return True

    # 强制转换为字符串
    amount_str = str(amount_str).strip()

    try:
        # 先尝试直接转数字
        amount = float(amount_str)
        return amount >= 0 and len(str(amount).split(".")[-1]) <= 2
    except:
        # 失败 → 尝试【大写金额转换（兼容繁体）】
        converted = chinese_to_number(amount_str)
        if converted is not None:
            return True
        return False


def is_valid_credit_code(code: str | None) -> bool:
    """核心修复：处理None值的统一社会信用代码校验"""
    if code is None or code == "N/A":
        return True
    # 强制转换为字符串并去除空白
    code_str = str(code).strip()
    # 校验长度和格式
    return len(code_str) == 18 and re.match(r"^[0-9A-Z]{18}$", code_str)


# ===================== 核心函数：审计级OCR识别（主模型+修复模型） =====================
def audit_ocr_recognize(image_path: str) -> Dict[str, Any]:
    """完整审计流程：先调用qwen3.5，出错则用deepseek修复"""
    # 兜底错误JSON（确保包含所有必要字段）
    error_json = {
        "image_type": "其他",
        "ocr_extract": {
            "invoice_code": "N/A", "invoice_number": "N/A", "date": "N/A", "total_amount": "N/A",
            "relevant_party": "N/A", "tax_rate": "N/A", "tax_id": "N/A", "bank_info": "N/A",
            "serial_number": "N/A", "details": "N/A",
            "seal_info": {"seal_type": "N/A", "seal_number": "N/A", "seal_clarity": "N/A", "joint_seal": "N/A"},
            "license_info": {"unified_social_credit_code": "N/A", "legal_person": "N/A", "valid_period": "N/A"},
            "asset_info": {"asset_tag": "N/A", "asset_name": "N/A", "location": "N/A", "quantity": "N/A",
                           "progress": "N/A"},
            "internal_control_info": {"signer": "N/A", "approval_level": "N/A", "attachment_complete": "N/A"},
            "other_info": "N/A"
        },
        "validation_result": {
            "date_valid": False, "amount_valid": False, "code_format_valid": False,
            "no_missing_field": False, "image_normal": False, "no_duplicate": True,
            "consistent_info": True, "compliance": False, "no_fraud": True
        },
        "risk_rating": "高风险",
        "risk_description": "默认错误：未识别",
        "audit_conclusion": "不通过",
        "reason": "默认错误：未识别",
        "audit_value": "数字化审计留痕，可核对、可预警"
    }

    # 构造更严格的审计指令（新增繁体金额识别要求）
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

    # 读取图片
    try:
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        error_reason = f"图片读取失败：{str(e)}"
        write_simple_error_log("image_read_fail", image_path, error_reason)
        add_retry_task("model_fail", image_path)
        error_json["ocr_extract"]["other_info"] = error_reason
        error_json["risk_description"] = error_reason
        error_json["reason"] = error_reason
        return error_json

    # ========== 第一步：调用主模型 qwen3.5 ==========
    raw_content = ""
    main_model_success = False

    for retry in range(RETRY_TIMES):
        try:
            raw_content = call_ollama_model(MAIN_MODEL, prompt, image_base64)

            # 提取并解析JSON（增强容错）
            raw_content_clean = raw_content.strip().replace("```json", "").replace("```", "").replace("\\n", "\n")
            json_match = re.search(r"\{[\s\S]*\}", raw_content_clean)

            if not json_match:
                # 第一次无有效JSON：直接调用DeepSeek修复，不再重试
                if retry == 0:
                    error_reason = f"主模型返回无有效JSON，直接调用DeepSeek修复"
                    write_simple_error_log("json_no_match", image_path, error_reason)
                    add_retry_task("json_error", image_path, raw_content)
                    audit_result = fix_json_with_deepseek(raw_content, image_path)
                    main_model_success = True
                    break
                # 多次无有效JSON：抛出异常
                else:
                    raise ValueError(f"主模型第{retry + 1}次仍未返回有效JSON内容")

            json_str = json_match.group()
            audit_result = json.loads(json_str)
            main_model_success = True
            break  # 主模型调用成功，跳出重试

        except json.JSONDecodeError as e:
            # JSON格式错误：记录并调用DeepSeek修复
            error_reason = f"主模型JSON格式错误：{str(e)}"
            write_simple_error_log("json_format_error", image_path, error_reason)
            add_retry_task("json_error", image_path, raw_content)

            # 调用DeepSeek修复JSON
            audit_result = fix_json_with_deepseek(raw_content, image_path)
            main_model_success = True
            break

        except Exception as e:
            error_reason = f"主模型调用失败（重试{retry + 1}/{RETRY_TIMES}）：{str(e)}"
            write_simple_error_log("model_call_fail", image_path, error_reason)
            if retry < RETRY_TIMES - 1:
                print(f"⚠️ {image_path} 主模型识别失败（重试{retry + 1}/{RETRY_TIMES}）：{str(e)}")
                time.sleep(5)  # 重试等待5秒
            else:
                # 主模型多次调用失败：返回兜底JSON
                add_retry_task("model_fail", image_path)
                error_json["risk_description"] = f"主模型识别失败（已重试{RETRY_TIMES}次）：{str(e)}"
                error_json["reason"] = error_json["risk_description"]
                return error_json

    # ========== 数据校验和补充默认值 ==========
    if main_model_success:
        # 强制补充顶层字段，避免缺失
        audit_result["image_type"] = audit_result.get("image_type", "其他")
        audit_result["risk_rating"] = audit_result.get("risk_rating", "高风险")
        audit_result["audit_conclusion"] = audit_result.get("audit_conclusion", "不通过")
        audit_result["risk_description"] = audit_result.get("risk_description", "未识别")
        audit_result["reason"] = audit_result.get("reason", "未识别")

        # 补充嵌套字段默认值（强制替换None为"N/A"）
        default_ocr = {
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
        default_validation = {
            "date_valid": True, "amount_valid": True, "code_format_valid": True,
            "no_missing_field": True, "image_normal": True, "no_duplicate": True,
            "consistent_info": True, "compliance": True, "no_fraud": True
        }

        def deep_merge(default: dict, target: dict) -> dict:
            """深度合并，强制替换None为"N/A"，增加类型校验"""
            # 先校验target是否为字典，不是则直接返回default
            if not isinstance(target, dict):
                return default.copy()

            # 创建target的副本，避免修改原字典
            merged = target.copy()

            for key, value in default.items():
                if key not in merged or merged[key] is None:
                    merged[key] = value
                elif isinstance(value, dict) and isinstance(merged[key], dict):
                    # 递归合并嵌套字典
                    merged[key] = deep_merge(value, merged[key])
                elif isinstance(value, dict) and not isinstance(merged[key], dict):
                    # 如果目标值不是字典，但默认值是字典，用默认值替换
                    merged[key] = value.copy()
            return merged

        # 安全合并字典，避免类型错误
        audit_result["ocr_extract"] = deep_merge(default_ocr, audit_result.get("ocr_extract", {}))
        audit_result["validation_result"] = deep_merge(default_validation, audit_result.get("validation_result", {}))
        audit_result["audit_value"] = audit_result.get("audit_value", "数字化审计留痕，可核对、可预警")

        # ========== 新增：自动转换大写金额为数字（兼容繁体） ==========
        raw_amount = audit_result["ocr_extract"]["total_amount"]
        converted_amount = chinese_to_number(raw_amount)
        if converted_amount is not None:
            audit_result["ocr_extract"]["total_amount"] = str(converted_amount)

        # 二次校验（使用修复后的校验函数）
        audit_result["validation_result"]["date_valid"] = is_valid_date(audit_result["ocr_extract"]["date"])
        audit_result["validation_result"]["amount_valid"] = is_valid_amount(audit_result["ocr_extract"]["total_amount"])
        audit_result["validation_result"]["code_format_valid"] = is_valid_credit_code(
            audit_result["ocr_extract"]["license_info"]["unified_social_credit_code"])

        return audit_result

    return error_json


# ===================== 工具函数：图片分类与信息保存 =====================
def sanitize_filename(filename: str | None) -> str:
    """修复：处理None值的文件名清理"""
    if filename is None:
        return "unknown_file"
    illegal_chars = r'[\/:*?"<>|]'
    return re.sub(illegal_chars, "_", str(filename))


def save_image_and_info(image_path: Path, audit_result: Dict[str, Any], index: int):
    """修复：增加所有嵌套字段的类型校验，避免字符串索引错误"""
    for retry in range(PROCESS_RETRY_TIMES + 1):
        try:
            # 核心修复：容错获取image_type，避免KeyError和None值
            image_type = audit_result.get("image_type", "其他")
            if image_type is None or str(image_type).strip() == "":
                image_type = "其他"

            type_folder = Path(OUTPUT_ROOT_FOLDER) / sanitize_filename(image_type)
            type_folder.mkdir(parents=True, exist_ok=True)

            original_name = image_path.name
            new_filename = f"{index:04d}_{sanitize_filename(image_type)}_{sanitize_filename(original_name)}"
            new_image_path = type_folder / new_filename

            shutil.copy2(str(image_path), str(new_image_path))
            print(f"✅ 图片已复制到：{new_image_path}")

            txt_path = new_image_path.with_suffix(".txt")

            # 核心修复：安全获取嵌套字段，增加类型校验
            ocr_extract = audit_result.get("ocr_extract", {})
            if not isinstance(ocr_extract, dict):
                ocr_extract = {}

            # 安全获取各级嵌套字段
            seal_info = ocr_extract.get("seal_info", {})
            if not isinstance(seal_info, dict):
                seal_info = {}

            license_info = ocr_extract.get("license_info", {})
            if not isinstance(license_info, dict):
                license_info = {}

            asset_info = ocr_extract.get("asset_info", {})
            if not isinstance(asset_info, dict):
                asset_info = {}

            internal_control_info = ocr_extract.get("internal_control_info", {})
            if not isinstance(internal_control_info, dict):
                internal_control_info = {}

            # 记录审计时间
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            key_info = {
                "审计时间": current_time,
                "图片类型": str(image_type),  # 强制转换为字符串
                "核心信息": {
                    "日期": ocr_extract.get("date", "N/A"),
                    "总金额": ocr_extract.get("total_amount", "N/A"),
                    "相关方": ocr_extract.get("relevant_party", "N/A"),
                    "统一社会信用代码": license_info.get("unified_social_credit_code", "N/A"),
                    "资产名称": asset_info.get("asset_name", "N/A"),
                    "签字人": internal_control_info.get("signer", "N/A")
                },
                "风险评级": audit_result.get("risk_rating", "高风险"),
                "审计结论": audit_result.get("audit_conclusion", "不通过"),
                "风险说明": audit_result.get("risk_description", "未识别")
            }

            txt_content = f"=== 图片关键信息 ===\n"
            for key, value in key_info.items():
                if isinstance(value, dict):
                    txt_content += f"{key}：\n"
                    for sub_key, sub_value in value.items():
                        # 处理None值
                        sub_value_str = "N/A" if sub_value is None else str(sub_value)
                        txt_content += f"  - {sub_key}：{sub_value_str}\n"
                else:
                    # 处理None值
                    value_str = "N/A" if value is None else str(value)
                    txt_content += f"{key}：{value_str}\n"

            txt_content += "\n=== 完整识别内容 ===\n"
            # 使用自定义JSON编码器处理非序列化类型和None值
            txt_content += json.dumps(audit_result, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(txt_content)
            print(f"✅ 信息文件已保存到：{txt_path}")
            return

        except Exception as e:
            error_reason = f"保存文件失败（重试{retry + 1}/{PROCESS_RETRY_TIMES}）：{str(e)}"
            write_simple_error_log("file_save_fail", str(image_path), error_reason)
            if retry < PROCESS_RETRY_TIMES:
                print(f"⚠️ 保存文件失败（重试{retry + 1}/{PROCESS_RETRY_TIMES}）：{str(e)}")
                time.sleep(5)  # 重试等待5秒
            else:
                print(f"❌ 保存文件最终失败 {image_path}：{str(e)}")
                return


# ===================== 核心新增：重跑失败任务函数 =====================
def retry_failed_tasks() -> None:
    """重跑失败任务（model_fail/json_error）"""
    print("\n🚀 开始重跑失败任务...")
    print(f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)

    # 读取重跑任务
    try:
        with open(RETRY_TASK_LOG, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    except Exception as e:
        print(f"❌ 读取重跑任务日志失败：{str(e)}")
        write_simple_error_log("retry_log_read_fail", "", f"读取重跑任务日志失败：{str(e)}")
        return

    if not tasks:
        print("✅ 无待重跑任务")
        return

    # 筛选待重跑任务
    pending_tasks = [t for t in tasks if t["retry_status"] == "pending"]
    if not pending_tasks:
        print("✅ 无待重跑任务（所有任务已处理）")
        return

    print(f"📋 待重跑任务数：{len(pending_tasks)}")
    success_count = 0
    fail_count = 0

    # 处理每个待重跑任务
    for idx, task in enumerate(pending_tasks, 1):
        task_type = task["task_type"]
        image_path = task["image_path"]
        raw_content = task.get("raw_content", "")
        print(f"\n[{idx}/{len(pending_tasks)}] 处理任务：{task_type} | {image_path}")

        try:
            if task_type == "model_fail":
                # 模型调用失败：重新执行完整识别
                audit_result = audit_ocr_recognize(image_path)
                # 保存结果（使用大索引避免重复）
                img_path = Path(image_path)
                save_image_and_info(img_path, audit_result, idx + 10000)
                # 更新任务状态
                update_retry_task_status(image_path, task_type, "success")
                success_count += 1
                print(f"✅ 重跑成功：{image_path}")

            elif task_type == "json_error":
                # JSON格式错误：直接调用DeepSeek修复
                fixed_result = fix_json_with_deepseek(raw_content, image_path)
                img_path = Path(image_path)
                save_image_and_info(img_path, fixed_result, idx + 20000)
                update_retry_task_status(image_path, task_type, "success")
                success_count += 1
                print(f"✅ JSON修复成功：{image_path}")

        except Exception as e:
            error_reason = f"重跑失败：{str(e)}"
            write_simple_error_log("retry_fail", image_path, error_reason)
            update_retry_task_status(image_path, task_type, "fail")
            fail_count += 1
            print(f"❌ 重跑失败：{image_path} | {str(e)}")

    # 输出重跑统计
    print("-" * 80)
    print(f"📊 重跑结果统计：")
    print(f"✅ 成功：{success_count} 个")
    print(f"❌ 失败：{fail_count} 个")
    print(f"📋 重跑日志已更新：{RETRY_TASK_LOG}")


# ===================== 批量审计处理函数 =====================
def batch_audit_process() -> None:
    """主批量处理函数"""
    # 初始化日志
    init_log_files()

    # 检查Ollama服务
    try:
        requests.get("http://localhost:11434/api/tags", timeout=10)
    except Exception as e:
        error_reason = f"无法连接Ollama服务：{str(e)}"
        write_simple_error_log("ollama_connect_fail", "", error_reason)
        print("❌ 无法连接Ollama服务！请先启动Ollama并下载模型")
        return

    # 检查模型是否存在（仅提示，不中断）
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=10)
        models = [m["name"].split(":")[0] for m in response.json()["models"]]
        main_model_base = MAIN_MODEL.split(":")[0]
        if main_model_base not in models:
            print(f"⚠️ 主模型 {MAIN_MODEL} 未下载，请先执行：ollama pull {MAIN_MODEL}")
        if FIX_MODEL not in models:
            print(f"⚠️ 修复模型 {FIX_MODEL} 未下载，请先执行：ollama pull {FIX_MODEL}")
    except Exception as e:
        write_simple_error_log("model_check_fail", "", f"检查模型失败：{str(e)}")

    # 检查图片文件夹
    image_dir = Path(IMAGE_FOLDER)
    if not image_dir.exists():
        error_reason = f"图片文件夹不存在：{IMAGE_FOLDER}"
        write_simple_error_log("folder_not_exist", "", error_reason)
        print(f"❌ 图片文件夹不存在：{IMAGE_FOLDER}")
        return

    # 收集图片文件（去重）
    image_files = []
    processed_paths = set()
    for file in image_dir.iterdir():
        if file.is_file() and file.suffix.lower() in SUPPORTED_FORMATS:
            file_path = str(file.absolute())
            if file_path not in processed_paths:
                processed_paths.add(file_path)
                image_files.append(file)

    if not image_files:
        error_reason = f"无支持的图片文件：{IMAGE_FOLDER}"
        write_simple_error_log("no_image_files", "", error_reason)
        print(f"⚠️ 无支持的图片文件：{IMAGE_FOLDER}")
        return

    # 批量处理
    results = []
    failed_files = []
    total = len(image_files)
    print(f"\n🚀 开始审计处理 {total} 张图片...（当前系统时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
    print(f"🔧 主识别模型：{MAIN_MODEL} | 错误修复模型：{FIX_MODEL}")
    print("🔧 已启用繁体汉字金额识别功能")
    print("🔧 已修复None值处理逻辑")
    print("🔧 已修复字符串索引错误")
    print("-" * 80)

    for idx, img_path in enumerate(image_files, 1):
        img_name = img_path.name
        print(f"\n[{idx}/{total}] 审计中：{img_name}")

        try:
            audit_result = audit_ocr_recognize(str(img_path))
            save_image_and_info(img_path, audit_result, idx)

            # 整理Excel数据（处理None值，增加类型校验）
            # 核心修复：安全获取嵌套字段，避免字符串索引错误
            ocr_extract = audit_result.get("ocr_extract", {})
            if not isinstance(ocr_extract, dict):
                ocr_extract = {}

            seal_info = ocr_extract.get("seal_info", {})
            if not isinstance(seal_info, dict):
                seal_info = {}

            license_info = ocr_extract.get("license_info", {})
            if not isinstance(license_info, dict):
                license_info = {}

            asset_info = ocr_extract.get("asset_info", {})
            if not isinstance(asset_info, dict):
                asset_info = {}

            internal_control_info = ocr_extract.get("internal_control_info", {})
            if not isinstance(internal_control_info, dict):
                internal_control_info = {}

            validation_result = audit_result.get("validation_result", {})
            if not isinstance(validation_result, dict):
                validation_result = {}

            # 统一处理None值为"N/A"
            def get_safe_value(d: dict, key: str, default: str = "N/A") -> str:
                """安全获取字典值，增加类型校验"""
                if not isinstance(d, dict):
                    return default
                value = d.get(key, default)
                return "N/A" if value is None else str(value)

            row = {
                "图片名称": img_name,
                "图片路径": str(img_path.absolute()),
                "分类保存路径": str(
                    Path(OUTPUT_ROOT_FOLDER) / sanitize_filename(audit_result.get("image_type", "其他")) /
                    f"{idx:04d}_{sanitize_filename(audit_result.get('image_type', '其他'))}_{img_name}"),
                "审计时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "图像类型": get_safe_value(audit_result, "image_type"),
                "票据代码": get_safe_value(ocr_extract, "invoice_code"),
                "票据号码": get_safe_value(ocr_extract, "invoice_number"),
                "日期": get_safe_value(ocr_extract, "date"),
                "总金额": get_safe_value(ocr_extract, "total_amount"),
                "相关方": get_safe_value(ocr_extract, "relevant_party"),
                "税率": get_safe_value(ocr_extract, "tax_rate"),
                "税号": get_safe_value(ocr_extract, "tax_id"),
                "开户行/账号": get_safe_value(ocr_extract, "bank_info"),
                "流水号": get_safe_value(ocr_extract, "serial_number"),
                "详情": get_safe_value(ocr_extract, "details"),
                "印章类型": get_safe_value(seal_info, "seal_type"),
                "印章编号": get_safe_value(seal_info, "seal_number"),
                "印章清晰度": get_safe_value(seal_info, "seal_clarity"),
                "骑缝章完整性": get_safe_value(seal_info, "joint_seal"),
                "统一社会信用代码": get_safe_value(license_info, "unified_social_credit_code"),
                "法人": get_safe_value(license_info, "legal_person"),
                "证照有效期": get_safe_value(license_info, "valid_period"),
                "资产标签": get_safe_value(asset_info, "asset_tag"),
                "资产名称": get_safe_value(asset_info, "asset_name"),
                "存放位置": get_safe_value(asset_info, "location"),
                "资产数量": get_safe_value(asset_info, "quantity"),
                "工程进度": get_safe_value(asset_info, "progress"),
                "签字人": get_safe_value(internal_control_info, "signer"),
                "审批层级": get_safe_value(internal_control_info, "approval_level"),
                "附件完整性": get_safe_value(internal_control_info, "attachment_complete"),
                "其他信息": get_safe_value(ocr_extract, "other_info"),
                "日期有效性": validation_result.get("date_valid", False),
                "金额有效性": validation_result.get("amount_valid", False),
                "编码格式有效性": validation_result.get("code_format_valid", False),
                "无缺项": validation_result.get("no_missing_field", False),
                "图片正常": validation_result.get("image_normal", False),
                "无重复报销": validation_result.get("no_duplicate", True),
                "信息一致性": validation_result.get("consistent_info", True),
                "合规性": validation_result.get("compliance", False),
                "无舞弊": validation_result.get("no_fraud", True),
                "风险评级": get_safe_value(audit_result, "risk_rating"),
                "风险说明": get_safe_value(audit_result, "risk_description"),
                "审计结论": get_safe_value(audit_result, "audit_conclusion"),
                "审计说明": get_safe_value(audit_result, "reason")
            }
            results.append(row)

        except Exception as e:
            error_reason = f"文件处理失败：{str(e)}"
            write_simple_error_log("file_process_fail", str(img_path), error_reason)
            failed_files.append(str(img_path))
            print(f"❌ {img_name} 处理失败，已跳过！错误：{str(e)}")
            continue

    # 写入Excel
    try:
        Path(EXCEL_OUTPUT).parent.mkdir(exist_ok=True)
        df = pd.DataFrame(results)
        df.to_excel(EXCEL_OUTPUT, index=False, engine="openpyxl")

        # 统计风险
        high_risk = sum(1 for r in results if r["风险评级"] == "高风险")
        mid_risk = sum(1 for r in results if r["风险评级"] == "中风险")
        low_risk = sum(1 for r in results if r["风险评级"] == "低风险")

        print("-" * 80)
        print(f"✅ 审计完成！（完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
        print(f"📊 Excel结果保存至：{EXCEL_OUTPUT}")
        print(f"📁 分类图片保存至：{OUTPUT_ROOT_FOLDER}")
        print(f"📋 简洁错误日志：{ERROR_LOG_SIMPLE}")
        print(f"📋 重跑任务日志：{RETRY_TASK_LOG}")
        print(f"📊 风险统计：高风险{high_risk}张 | 中风险{mid_risk}张 | 低风险{low_risk}张")
        print(f"❌ 处理失败文件数：{len(failed_files)} 个")
        if failed_files:
            print(f"📝 失败文件列表：{failed_files}")
    except Exception as e:
        error_reason = f"写入Excel失败：{str(e)}"
        write_simple_error_log("excel_write_fail", "", error_reason)
        print(f"❌ 写入Excel失败：{str(e)}")


# ===================== 运行入口（支持主处理/重跑模式） =====================
if __name__ == "__main__":
    print("📢 审计OCR工具（Qwen3.5主识别 + DeepSeek错误修复 + 简/繁体金额转换）")
    print("🔧 已修复float和None值处理错误")
    print("🔧 已修复字符串索引错误（string indices must be integers）")
    print("=" * 80)
    print("模式选择：")
    print("1. 执行完整审计（默认）")
    print("2. 重跑失败任务")
    print("=" * 80)

    choice = input("请输入模式编号（1/2，默认1）：").strip() or "1"

    if choice == "1":
        print("\n📢 执行完整审计流程...")
        print("前置准备：")
        print(f"1. 安装依赖：pip install requests pandas openpyxl")
        print(f"2. 下载主模型：ollama pull {MAIN_MODEL}")
        print(f"3. 下载修复模型：ollama pull {FIX_MODEL}")
        print("4. 启动Ollama服务（ollama serve）")
        print(f"当前系统时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🔧 已启用繁体汉字金额识别功能")
        print("🔧 已修复None值和float类型处理逻辑")
        print("🔧 已修复字符串索引错误")
        print("-" * 80)

        try:
            batch_audit_process()
        except Exception as e:
            error_reason = f"程序全局异常：{str(e)}\n{traceback.format_exc()}"
            write_simple_error_log("global_exception", "", error_reason)
            print(f"❌ 程序运行出错：{str(e)}")
            print(f"📋 详细错误信息已保存至：{ERROR_LOG_SIMPLE}")

    elif choice == "2":
        print("\n📢 执行失败任务重跑流程...")
        print(f"当前系统时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🔧 已启用繁体汉字金额识别功能")
        print("🔧 已修复None值和float类型处理逻辑")
        print("🔧 已修复字符串索引错误")
        print("-" * 80)

        try:
            retry_failed_tasks()
        except Exception as e:
            error_reason = f"重跑程序异常：{str(e)}\n{traceback.format_exc()}"
            write_simple_error_log("retry_global_exception", "", error_reason)
            print(f"❌ 重跑程序出错：{str(e)}")
            print(f"📋 详细错误信息已保存至：{ERROR_LOG_SIMPLE}")

    else:
        print("❌ 无效选择，退出程序")

    input("\n按Enter键退出...")