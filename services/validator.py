# ============================================================
# 数据校验服务
# 功能: 校验 OCR 识别结果中的日期、金额、信用代码等字段
# 核心: is_valid_date() - 日期校验（YYYY-MM-DD，不超当前时间）
#       is_valid_amount() - 金额校验（非负，最多2位小数）
#       is_valid_credit_code() - 统一社会信用代码格式校验
# ============================================================

import re
from datetime import datetime

from utils.converter import chinese_to_number


def is_valid_date(date_str: str | None) -> bool:
    if date_str is None or date_str == "N/A":
        return True
    try:
        date = datetime.strptime(str(date_str), "%Y-%m-%d")
        return date <= datetime.now()
    except:
        return False


def is_valid_amount(amount_str: str | float | int | None) -> bool:
    if amount_str is None or amount_str == "N/A":
        return True

    amount_str = str(amount_str).strip()

    try:
        amount = float(amount_str)
        return amount >= 0 and len(str(amount).split(".")[-1]) <= 2
    except:
        converted = chinese_to_number(amount_str)
        if converted is not None:
            return True
        return False


def is_valid_credit_code(code: str | None) -> bool:
    if code is None or code == "N/A":
        return True
    code_str = str(code).strip()
    return len(code_str) == 18 and re.match(r"^[0-9A-Z]{18}$", code_str)
