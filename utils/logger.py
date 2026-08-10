# ============================================================
# 日志系统
# 功能: 初始化错误日志和重跑任务队列，
#       记录 OCR 识别错误和待重跑的任务
# 核心: init_log_files() - 初始化日志文件
#       write_simple_error_log() - 写入错误日志
#       add_retry_task() - 添加重跑任务
# ============================================================

import json
import os
from datetime import datetime
from pathlib import Path

from config.settings import cfg


def _ensure_dir(filepath: str):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)


def init_log_files():
    _ensure_dir(cfg.ERROR_LOG_SIMPLE)
    _ensure_dir(cfg.RETRY_TASK_LOG)
    with open(cfg.ERROR_LOG_SIMPLE, "w", encoding="utf-8") as f:
        f.write("=== OCR审计错误日志 ===\n")
        f.write(f"初始化时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("格式：[时间] | 错误类型 | 文件路径 | 核心原因\n")
        f.write("-" * 120 + "\n")

    with open(cfg.RETRY_TASK_LOG, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)


def write_simple_error_log(error_type: str, image_path: str, reason: str):
    _ensure_dir(cfg.ERROR_LOG_SIMPLE)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_content = f"[{timestamp}] | {error_type} | {image_path} | {reason}\n"
    with open(cfg.ERROR_LOG_SIMPLE, "a", encoding="utf-8") as f:
        f.write(log_content)


def add_retry_task(task_type: str, image_path: str, raw_content: str = ""):
    _ensure_dir(cfg.RETRY_TASK_LOG)
    try:
        with open(cfg.RETRY_TASK_LOG, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    except:
        tasks = []

    task_exists = any(
        t["image_path"] == image_path and t["task_type"] == task_type
        for t in tasks
    )
    if task_exists:
        return

    new_task = {
        "task_type": task_type,
        "image_path": image_path,
        "raw_content": raw_content,
        "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "retry_status": "pending"
    }
    tasks.append(new_task)

    with open(cfg.RETRY_TASK_LOG, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def update_retry_task_status(image_path: str, task_type: str, status: str):
    _ensure_dir(cfg.RETRY_TASK_LOG)
    try:
        with open(cfg.RETRY_TASK_LOG, "r", encoding="utf-8") as f:
            tasks = json.load(f)

        for task in tasks:
            if task["image_path"] == image_path and task["task_type"] == task_type:
                task["retry_status"] = status
                task["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break

        with open(cfg.RETRY_TASK_LOG, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
    except Exception as e:
        write_simple_error_log("log_update_fail", image_path, f"更新重跑任务状态失败：{str(e)}")
