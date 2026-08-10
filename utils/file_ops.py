# ============================================================
# 文件操作工具
# 功能: 按票据类型分类保存图片和信息文件到输出目录，
#       生成分类目录结构，写入识别结果到 .txt 文件
# 核心: save_image_and_info() - 保存图片和信息文件
# ============================================================

import re
import json
import time
import shutil
from pathlib import Path
from datetime import datetime

from config.settings import cfg
from models.schemas import deep_merge, DEFAULT_OCR, DEFAULT_VALIDATION
from utils.json_handler import CustomJSONEncoder
from utils.logger import write_simple_error_log


def sanitize_filename(filename: str | None) -> str:
    if filename is None:
        return "unknown_file"
    illegal_chars = r'[\/:*?"<>|]'
    return re.sub(illegal_chars, "_", str(filename))


def get_safe_value(d: dict, key: str, default: str = "N/A") -> str:
    if not isinstance(d, dict):
        return default
    value = d.get(key, default)
    return "N/A" if value is None else str(value)


def save_image_and_info(image_path: Path, audit_result: dict, index: int, output_root: str = ""):
    root = output_root or cfg.OUTPUT_ROOT_FOLDER
    for retry in range(cfg.PROCESS_RETRY_TIMES + 1):
        try:
            image_type = audit_result.get("image_type", "其他")
            if image_type is None or str(image_type).strip() == "":
                image_type = "其他"

            type_folder = root / sanitize_filename(image_type) if isinstance(root, Path) else Path(root) / sanitize_filename(image_type)
            type_folder.mkdir(parents=True, exist_ok=True)

            original_name = image_path.name
            new_filename = f"{index:04d}_{sanitize_filename(image_type)}_{sanitize_filename(original_name)}"
            new_image_path = type_folder / new_filename

            shutil.copy2(str(image_path), str(new_image_path))
            print(f"✅ 图片已复制到：{new_image_path}")

            txt_path = new_image_path.with_suffix(".txt")

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

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            key_info = {
                "审计时间": current_time,
                "图片类型": str(image_type),
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

            txt_content = "=== 图片关键信息 ===\n"
            for key, value in key_info.items():
                if isinstance(value, dict):
                    txt_content += f"{key}：\n"
                    for sub_key, sub_value in value.items():
                        sub_value_str = "N/A" if sub_value is None else str(sub_value)
                        txt_content += f"  - {sub_key}：{sub_value_str}\n"
                else:
                    value_str = "N/A" if value is None else str(value)
                    txt_content += f"{key}：{value_str}\n"

            txt_content += "\n=== 完整识别内容 ===\n"
            txt_content += json.dumps(audit_result, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(txt_content)
            print(f"✅ 信息文件已保存到：{txt_path}")
            return

        except Exception as e:
            error_reason = f"保存文件失败（重试{retry + 1}/{cfg.PROCESS_RETRY_TIMES}）：{str(e)}"
            write_simple_error_log("file_save_fail", str(image_path), error_reason)
            if retry < cfg.PROCESS_RETRY_TIMES:
                print(f"⚠️ 保存文件失败（重试{retry + 1}/{cfg.PROCESS_RETRY_TIMES}）：{str(e)}")
                time.sleep(5)
            else:
                print(f"❌ 保存文件最终失败 {image_path}：{str(e)}")
                return
