# ============================================================
# 中文金额转换工具
# 功能: 将中文大写金额（如"壹仟贰佰叁拾肆元伍角陆分"）
#       转换为阿拉伯数字（1234.56）
# 核心: chinese_to_number() - 主转换函数
# ============================================================

import re
import pandas as pd


def chinese_to_number(chinese_amount: str | float | int | None) -> float | None:
    if chinese_amount is None or pd.isna(chinese_amount) or chinese_amount == "N/A":
        return None

    s = str(chinese_amount).strip()

    if re.match(r'^\d+(\.\d{1,2})?$', s):
        try:
            return round(float(s), 2)
        except:
            return None

    digit_map = {
        '零': 0, '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5,
        '陆': 6, '柒': 7, '捌': 8, '玖': 9,
        '拾': 10, '佰': 100, '仟': 1000, '万': 10000, '亿': 100000000,
        '貳': 2, '參': 3, '陸': 6,
        '萬': 10000, '億': 100000000,
    }
    unit_map = {
        '元': 1.0, '圆': 1.0, '圓': 1.0,
        '角': 0.1,
        '分': 0.01
    }

    total = 0

    try:
        if any(unit in s for unit in ['元', '圆', '圓']):
            yuan_pos = min([s.find(unit) for unit in ['元', '圆', '圓'] if s.find(unit) != -1])
            yuan_part = s[:yuan_pos]
            rest = s[yuan_pos + 1:]
        else:
            yuan_part = s
            rest = ''

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
            elif c in ['整', '正']:
                pass
        total += temp

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
