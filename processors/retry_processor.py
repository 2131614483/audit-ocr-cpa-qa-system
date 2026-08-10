# ============================================================
# 失败任务重跑处理器
# 功能: 读取重跑任务日志，逐个重新执行 OCR 识别，
#       更新任务状态（完成/失败）
# 核心: retry_failed_tasks() - 重跑所有待处理任务
# ============================================================

import json
from pathlib import Path
from datetime import datetime

from config.settings import cfg
from services.ocr_engine import audit_ocr_recognize, fix_json_with_deepseek
from utils.file_ops import save_image_and_info
from utils.logger import write_simple_error_log, update_retry_task_status


def retry_failed_tasks():
    print("\n🚀 开始重跑失败任务...")
    print(f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)

    try:
        with open(cfg.RETRY_TASK_LOG, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    except Exception as e:
        print(f"❌ 读取重跑任务日志失败：{str(e)}")
        write_simple_error_log("retry_log_read_fail", "", f"读取重跑任务日志失败：{str(e)}")
        return

    if not tasks:
        print("✅ 无待重跑任务")
        return

    pending_tasks = [t for t in tasks if t["retry_status"] == "pending"]
    if not pending_tasks:
        print("✅ 无待重跑任务（所有任务已处理）")
        return

    print(f"📋 待重跑任务数：{len(pending_tasks)}")
    success_count = 0
    fail_count = 0

    for idx, task in enumerate(pending_tasks, 1):
        task_type = task["task_type"]
        image_path = task["image_path"]
        raw_content = task.get("raw_content", "")
        print(f"\n[{idx}/{len(pending_tasks)}] 处理任务：{task_type} | {image_path}")

        try:
            if task_type == "model_fail":
                audit_result = audit_ocr_recognize(image_path)
                img_path = Path(image_path)
                save_image_and_info(img_path, audit_result, idx + 10000)
                update_retry_task_status(image_path, task_type, "success")
                success_count += 1
                print(f"✅ 重跑成功：{image_path}")

            elif task_type == "json_error":
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

    print("-" * 80)
    print(f"📊 重跑结果统计：")
    print(f"✅ 成功：{success_count} 个")
    print(f"❌ 失败：{fail_count} 个")
    print(f"📋 重跑日志已更新：{cfg.RETRY_TASK_LOG}")
