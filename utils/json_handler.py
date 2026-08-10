# ============================================================
# JSON 安全解析工具
# 功能: 自定义 JSON 编码器（处理 datetime/re.Match/None），
#       从 LLM 输出中安全提取并解析 JSON 字符串
# 核心: CustomJSONEncoder - 自定义编码器
#       safe_json_loads() - 安全解析 JSON
# ============================================================

import json
import re
from datetime import datetime


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, re.Match):
            return obj.group()
        elif isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        elif obj is None:
            return "N/A"
        else:
            return str(obj)


def safe_json_loads(text: str) -> dict | None:
    text_clean = text.strip().replace("```json", "").replace("```", "").replace("\\n", "\n")
    json_match = re.search(r"\{[\s\S]*\}", text_clean)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            return None
    return None
