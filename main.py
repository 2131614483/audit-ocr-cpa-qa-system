# ============================================================
# 审计OCR工具 - CLI 主入口
# 功能: 交互式菜单，选择模型供应商（Ollama/智谱/DeepSeek/阿里/OpenAI/豆包），
#       选择处理模式（完整审计/多模型并发/失败重跑），批量识别票据图片
# 调用: processors/batch_processor.py → services/ocr_engine.py
# ============================================================

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import traceback
from datetime import datetime
from pathlib import Path

from config.settings import cfg, get_provider_config, set_provider, load_model_config
from utils.logger import write_simple_error_log
from processors.batch_processor import batch_audit_process, batch_audit_process_multithread
from processors.retry_processor import retry_failed_tasks
from services.ollama_client import get_main_model, get_fix_model


_PROVIDERS_MENU = [
    ("ollama", "Ollama 本地模型"),
    ("zhipu", "智谱AI (GLM-4.6V-FlashX)"),
    ("deepseek", "DeepSeek API"),
    ("qwen", "阿里通义千问 API"),
    ("openai", "OpenAI API"),
    ("doubao", "火山引擎豆包 API"),
]


def choose_provider():
    """交互式选择模型供应商"""
    print("=" * 80)
    print("📢 审计OCR工具 - 模型供应商选择")
    print("=" * 80)
    print("请选择模型供应商：")
    for i, (_, name) in enumerate(_PROVIDERS_MENU, 1):
        default = " [默认]" if i == 1 else ""
        print(f"  {i}. {name}{default}")
    print("=" * 80)

    choice = input(f"请输入编号（1-{len(_PROVIDERS_MENU)}，默认1）：").strip()
    if not choice:
        choice = "1"

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(_PROVIDERS_MENU):
            key, display = _PROVIDERS_MENU[idx]
            set_provider(key)
            provider_info = get_provider_config()
            pname = provider_info["config"].get("name", display)
            print(f"  ✅ 已选择：{pname}")
            print(f"  🔧 主识别：{get_main_model()} | 修复：{get_fix_model()}")
            return key
    except (ValueError, IndexError):
        pass

    set_provider("ollama")
    print("  ✅ 已选择：Ollama 本地模型（默认）")
    return "ollama"


def choose_multi_providers():
    """交互式选择多个模型供应商（多模型并发模式）"""
    print("=" * 80)
    print("📢 审计OCR工具 - 多模型并发模式")
    print("=" * 80)
    print("请选择要使用的模型供应商（可多选，用逗号分隔，如 2,3,4）：")
    for i, (_, name) in enumerate(_PROVIDERS_MENU, 1):
        api_key_status = ""
        if i > 1:
            key = _PROVIDERS_MENU[i-1][0]
            model_config = load_model_config()
            provider_info = model_config["providers"].get(key, {})
            api_key = provider_info.get("api_key", "")
            if not api_key or "在此填入" in api_key:
                api_key_status = " [未配置API密钥]"
            else:
                api_key_status = " [已配置]"
        print(f"  {i}. {name}{api_key_status}")
    print("=" * 80)

    choices = input(f"请输入编号（多个用逗号分隔，默认2）：").strip()
    if not choices:
        choices = "2"

    selected = []
    for c in choices.split(","):
        try:
            idx = int(c.strip()) - 1
            if 0 <= idx < len(_PROVIDERS_MENU):
                key, display = _PROVIDERS_MENU[idx]
                model_config = load_model_config()
                if key == "ollama":
                    selected.append(key)
                    continue
                provider_info = model_config["providers"].get(key, {})
                api_key = provider_info.get("api_key", "")
                if not api_key or "在此填入" in api_key:
                    print(f"  ⚠️ {display} 的API密钥未配置，跳过")
                    continue
                selected.append(key)
        except (ValueError, IndexError):
            pass

    if not selected:
        print("  ⚠️ 未选择有效供应商，默认为智谱AI")
        selected = ["zhipu"]

    print(f"  ✅ 已选择 {len(selected)} 个供应商：{selected}")
    return selected


def main(mode: str = "", image_folder: str = "", excel_output: str = "",
         output_root: str = "", db_enabled: bool = None, max_images: int = 0):
    """
    审计OCR工具主入口

    参数:
        mode: 模式 "1"=完整审计 "2"=重跑失败任务，空字符串则交互式输入
        image_folder: 图片来源目录，覆盖 config.json 配置
        excel_output: Excel 输出路径，覆盖 config.json 配置
        output_root: 分类图片保存根目录，覆盖 config.json 配置
        db_enabled: 是否启用数据库写入，覆盖 config.json 配置
        max_images: 最大处理图片数，0=不限制
    """
    print("=" * 80)
    print("📢 审计OCR工具（多模型支持：本地Ollama / 云端API）")
    print("=" * 80)

    if not mode:
        choose_provider()
        print()
        print("模式选择：")
        print("1. 执行完整审计（默认）")
        print("2. 重跑失败任务")
        print("3. 多线程加速（仅支持云端API如智谱/DeepSeek等）")
        print("4. 多模型并发（多个模型同时识别，结果对比选择）")
        print("=" * 80)
        mode = input("请输入模式编号（1/2/3/4，默认1）：").strip() or "1"

    if mode == "1":
        print("\n📢 执行完整审计流程...")
        provider_info = get_provider_config()
        pname = provider_info["config"].get("name", "未知")
        is_local = provider_info["name"] == "ollama"

        if is_local:
            print("前置准备：")
            print(f"1. 安装依赖：pip install requests pandas openpyxl")
            print(f"2. 下载主模型：ollama pull {get_main_model()}")
            print(f"3. 下载修复模型：ollama pull {get_fix_model()}")
            print("4. 启动Ollama服务（ollama serve）")
        else:
            print("前置准备：")
            print(f"1. 安装依赖：pip install requests pandas openpyxl")
            print(f"2. 在 data/model_config.json 中配置 {pname} 的 API 密钥")
            print(f"3. 确认 model_config.json 中 {pname} 的模型名称正确")
        print(f"当前系统时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        _img = image_folder or cfg.IMAGE_FOLDER
        _excel = excel_output or cfg.EXCEL_OUTPUT
        _output = output_root or cfg.OUTPUT_ROOT_FOLDER
        _db = db_enabled if db_enabled is not None else getattr(cfg, "DB_ENABLED", False)

        provider_info = get_provider_config()
        pname = provider_info["config"].get("name", "未知")
        print(f"🔧 当前模型供应商：{pname}")
        print(f"🔧 主识别模型：{get_main_model()} | 修复模型：{get_fix_model()}")
        print(f"📂 图片来源：{_img}")
        print(f"📊 Excel结果：{_excel}")
        print(f"📁 分类图片：{_output}")
        db_status = "启用" if _db else "关闭"
        kb_status = "已加载" if _db else "未启用"
        print(f"💾 数据库写入：{db_status}")
        print(f"📖 知识库检索：{kb_status}")
        if max_images > 0:
            print(f"🔢 最大处理：{max_images} 张")
        print("-" * 80)

        try:
            batch_audit_process(
                image_folder=_img,
                excel_output=_excel,
                output_root=_output,
                db_enabled=_db,
                max_images=max_images
            )
        except Exception as e:
            error_reason = f"程序全局异常：{str(e)}\n{traceback.format_exc()}"
            write_simple_error_log("global_exception", "", error_reason)
            print(f"❌ 程序运行出错：{str(e)}")
            print(f"📋 详细错误信息已保存至：{cfg.ERROR_LOG_SIMPLE}")

    elif mode == "2":
        print("\n📢 执行失败任务重跑流程...")
        print(f"当前系统时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 80)

        try:
            retry_failed_tasks()
        except Exception as e:
            error_reason = f"重跑程序异常：{str(e)}\n{traceback.format_exc()}"
            write_simple_error_log("retry_global_exception", "", error_reason)
            print(f"❌ 重跑程序出错：{str(e)}")
            print(f"📋 详细错误信息已保存至：{cfg.ERROR_LOG_SIMPLE}")

    elif mode == "3":
        print("\n📢 执行多线程加速审计流程...")
        provider_info = get_provider_config()
        pname = provider_info["name"]
        
        if pname == "ollama":
            print("⚠️ Ollama本地模式不支持多线程加速，请选择其他供应商或使用模式1")
            return
        
        print(f"☁️ 当前供应商：{provider_info['config'].get('name', '未知')}")
        print(f"🔧 主识别模型：{get_main_model()} | 修复模型：{get_fix_model()}")
        print(f"当前系统时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("并发线程数选择（根据API配额调整）：")
        print("1. 4并发（保守）")
        print("2. 8并发（推荐）")
        print("3. 16并发（较高）")
        print("4. 30并发（极高）")
        print("5. 64并发（最大）")
        print("=" * 80)
        workers_choice = input("请输入并发数（1-5，默认2）：").strip() or "2"
        
        workers_map = {"1": 4, "2": 8, "3": 16, "4": 30, "5": 64}
        max_workers = workers_map.get(workers_choice, 8)
        print(f"⚡ 已设置并发数：{max_workers}")
        print("-" * 80)

        _img = image_folder or cfg.IMAGE_FOLDER
        _excel = excel_output or cfg.EXCEL_OUTPUT
        _output = output_root or cfg.OUTPUT_ROOT_FOLDER
        _db = db_enabled if db_enabled is not None else getattr(cfg, "DB_ENABLED", False)

        print(f"🔧 当前模型供应商：{provider_info['config'].get('name', '未知')}")
        print(f"📂 图片来源：{_img}")
        print(f"📊 Excel结果：{_excel}")
        print(f"📁 分类图片：{_output}")
        db_status = "启用" if _db else "关闭"
        print(f"💾 数据库写入：{db_status}")
        if max_images > 0:
            print(f"🔢 最大处理：{max_images} 张")
        print("-" * 80)

        try:
            batch_audit_process_multithread(
                image_folder=_img,
                excel_output=_excel,
                output_root=_output,
                db_enabled=_db,
                max_images=max_images,
                max_workers=max_workers
            )
        except Exception as e:
            error_reason = f"多线程程序异常：{str(e)}\n{traceback.format_exc()}"
            write_simple_error_log("multithread_exception", "", error_reason)
            print(f"❌ 多线程程序出错：{str(e)}")
            print(f"📋 详细错误信息已保存至：{cfg.ERROR_LOG_SIMPLE}")

    elif mode == "4":
        print("\n📢 执行多模型并发审计流程...")
        selected_providers = choose_multi_providers()

        if not selected_providers:
            print("❌ 未选择有效供应商，退出")
            return

        print(f"☁️ 已选择 {len(selected_providers)} 个供应商：{selected_providers}")
        print(f"当前系统时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("并发线程数选择（每个模型的并发数）：")
        print("1. 2并发/模型（保守）")
        print("2. 4并发/模型（推荐）")
        print("3. 8并发/模型（较高）")
        print("=" * 80)
        workers_choice = input("请输入并发数（1-3，默认2）：").strip() or "2"

        workers_map = {"1": 2, "2": 4, "3": 8}
        max_workers = workers_map.get(workers_choice, 4)
        print(f"⚡ 已设置每模型并发数：{max_workers}")
        print("-" * 80)

        _img = image_folder or cfg.IMAGE_FOLDER
        _excel = excel_output or cfg.EXCEL_OUTPUT
        _output = output_root or cfg.OUTPUT_ROOT_FOLDER
        _db = db_enabled if db_enabled is not None else getattr(cfg, "DB_ENABLED", False)

        print(f"📂 图片来源：{_img}")
        print(f"📊 Excel结果：{_excel}")
        print(f"📁 分类图片：{_output}")
        db_status = "启用" if _db else "关闭"
        print(f"💾 数据库写入：{db_status}")
        if max_images > 0:
            print(f"🔢 最大处理：{max_images} 张")
        print("-" * 80)

        try:
            from processors.batch_processor import batch_audit_process_multimodel
            batch_audit_process_multimodel(
                image_folder=_img,
                excel_output=_excel,
                output_root=_output,
                db_enabled=_db,
                max_images=max_images,
                max_workers=max_workers,
                providers=selected_providers
            )
        except Exception as e:
            error_reason = f"多模型并发程序异常：{str(e)}\n{traceback.format_exc()}"
            write_simple_error_log("multimodel_exception", "", error_reason)
            print(f"❌ 多模型并发程序出错：{str(e)}")
            print(f"📋 详细错误信息已保存至：{cfg.ERROR_LOG_SIMPLE}")

    else:
        print("❌ 无效选择，退出程序")

    if not mode:
        input("\n按Enter键退出...")


if __name__ == "__main__":
    main()
