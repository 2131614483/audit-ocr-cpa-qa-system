# ============================================================
# 批量处理主逻辑
# 功能: 遍历图片文件夹，逐张调用 OCR 识别管线，
#       支持单线程/多线程/多模型并发三种模式，
#       写入数据库、分类保存文件、生成 Excel
# 核心: batch_audit_process() - 标准批量处理
#       batch_audit_process_multithread() - 多线程处理
#       batch_audit_process_multimodel() - 多模型并发
# ============================================================

import pandas as pd
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from config.settings import cfg, get_provider_config
from services.ollama_client import check_ollama_service, check_models_available, get_main_model, get_fix_model
from services.ocr_engine import audit_ocr_recognize
from services.db_service import save_single_result
from services.cpa_tutor import format_single_tutoring, format_global_tutoring, append_tutoring_to_info, save_global_tutoring
from utils.file_ops import save_image_and_info, sanitize_filename, get_safe_value
from utils.logger import init_log_files, write_simple_error_log

_results_lock = threading.Lock()
_db_lock = threading.Lock()


def batch_audit_process(image_folder: str = "", excel_output: str = "",
                        output_root: str = "", db_enabled: bool = None,
                        max_images: int = 0):
    _img_folder = image_folder or cfg.IMAGE_FOLDER
    _excel_out = excel_output or cfg.EXCEL_OUTPUT
    _out_root = output_root or cfg.OUTPUT_ROOT_FOLDER
    _db = db_enabled if db_enabled is not None else getattr(cfg, "DB_ENABLED", False)

    init_log_files()

    if not check_ollama_service():
        error_reason = "无法连接Ollama服务"
        write_simple_error_log("ollama_connect_fail", "", error_reason)
        print("❌ 无法连接Ollama服务！请先启动Ollama并下载模型")
        return

    available_models = check_models_available()
    main_model = get_main_model()
    fix_model = get_fix_model()
    if available_models:
        if main_model not in available_models and get_provider_config()["name"] == "ollama":
            print(f"⚠️ 主模型 {main_model} 未下载，请先执行：ollama pull {main_model}")
        if fix_model not in available_models and get_provider_config()["name"] == "ollama":
            print(f"⚠️ 修复模型 {fix_model} 未下载，请先执行：ollama pull {fix_model}")

    image_dir = Path(_img_folder)
    if not image_dir.exists():
        error_reason = f"图片文件夹不存在：{_img_folder}"
        write_simple_error_log("folder_not_exist", "", error_reason)
        print(f"❌ 图片文件夹不存在：{_img_folder}")
        return

    image_files = []
    processed_paths = set()
    for file in image_dir.iterdir():
        if file.is_file() and file.suffix.lower() in cfg.SUPPORTED_FORMATS:
            file_path = str(file.absolute())
            if file_path not in processed_paths:
                processed_paths.add(file_path)
                image_files.append(file)

    if not image_files:
        error_reason = f"无支持的图片文件：{_img_folder}"
        write_simple_error_log("no_image_files", "", error_reason)
        print(f"⚠️ 无支持的图片文件：{_img_folder}")
        return

    if max_images > 0 and len(image_files) > max_images:
        image_files = image_files[:max_images]
        print(f"🔢 限制处理 {max_images} 张（共 {total} 张）")

    results = []
    failed_files = []
    db_ok = 0
    db_fail = 0
    total = len(image_files)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n🚀 开始审计处理 {total} 张图片...（当前系统时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
    print(f"🔧 主识别模型：{get_main_model()} | 错误修复模型：{get_fix_model()}")
    print(f"🔧 模型供应商：{get_provider_config()['config'].get('name', 'Ollama')}")
    print("🔧 已启用繁体汉字金额识别功能")
    print("-" * 80)

    for idx, img_path in enumerate(image_files, 1):
        img_name = img_path.name
        print(f"\n[{idx}/{total}] 审计中：{img_name}")

        try:
            audit_result = audit_ocr_recognize(str(img_path), db_enabled=_db)
            save_image_and_info(img_path, audit_result, idx, output_root=_out_root)

            # CPA知识点辅导（单张）
            cpa_tutoring_text = ""
            try:
                cpa_tutoring_text = format_single_tutoring(audit_result, img_name)
                if cpa_tutoring_text:
                    txt_path = (Path(_out_root) / sanitize_filename(audit_result.get("image_type", "其他")) /
                                f"{idx:04d}_{sanitize_filename(audit_result.get('image_type', '其他'))}_{sanitize_filename(img_name)}").with_suffix(".txt")
                    append_tutoring_to_info(txt_path, cpa_tutoring_text)
                    print(f"  📚 CPA辅导已生成")
            except Exception as e:
                write_simple_error_log("cpa_tutoring_error", str(img_path), str(e))

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

            row = {
                "图片名称": img_name,
                "图片路径": str(img_path.absolute()),
                "分类保存路径": str(
                    Path(_out_root) / sanitize_filename(audit_result.get("image_type", "其他")) /
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
                "审计说明": get_safe_value(audit_result, "reason"),
                "匹配知识库规则": audit_result.get("kb_rule_ids", ""),
                "CPA知识辅导": cpa_tutoring_text,
                "_full_json": audit_result
            }
            results.append(row)

            # 立即写入数据库（增量写入，避免中途崩溃丢失）
            if _db:
                if save_single_result(row, batch_id):
                    db_ok += 1
                else:
                    db_fail += 1

            # 进度提示
            elapsed = (datetime.now() - datetime.strptime(
                batch_id, "%Y%m%d_%H%M%S")).total_seconds()
            avg_time = elapsed / idx
            remaining = avg_time * (total - idx)
            print(f"  ✅ 完成 | 用时{elapsed:.0f}s | 估算剩余{remaining:.0f}s "
                  f"| DB成功{db_ok} 失败{db_fail}")

        except Exception as e:
            error_reason = f"文件处理失败：{str(e)}"
            write_simple_error_log("file_process_fail", str(img_path), error_reason)
            failed_files.append(str(img_path))
            print(f"❌ {img_name} 处理失败，已跳过！错误：{str(e)}")
            continue

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        Path(_excel_out).parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(results)
        df.to_excel(_excel_out, index=False, engine="openpyxl")
        print(f"📊 Excel结果保存至：{_excel_out}")
    except Exception as e:
        error_reason = f"写入Excel失败：{str(e)}"
        write_simple_error_log("excel_write_fail", "", error_reason)
        print(f"❌ 写入Excel失败：{str(e)}")

    # CPA综合辅导（全局）
    try:
        global_tutoring = format_global_tutoring(results)
        if global_tutoring:
            save_global_tutoring(global_tutoring, output_root=_out_root)
            print(global_tutoring)
    except Exception as e:
        write_simple_error_log("cpa_global_tutoring_error", "", str(e))

    try:
        high_risk = sum(1 for r in results if r["风险评级"] == "高风险")
        mid_risk = sum(1 for r in results if r["风险评级"] == "中风险")
        low_risk = sum(1 for r in results if r["风险评级"] == "低风险")

        print("-" * 80)
        print(f"✅ 审计完成！（完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
        print(f"📁 分类图片保存至：{_out_root}")
        print(f"📋 错误日志：{cfg.ERROR_LOG_SIMPLE}")
        print(f"📋 重跑任务日志：{cfg.RETRY_TASK_LOG}")
        print(f"📊 风险统计：高风险{high_risk}张 | 中风险{mid_risk}张 | 低风险{low_risk}张")
        if _db:
            print(f"💾 数据库写入：成功 {db_ok} 条 | 失败 {db_fail} 条")
        print(f"❌ 处理失败文件数：{len(failed_files)} 个")
        if failed_files:
            print(f"📝 失败文件列表：{failed_files}")
    except Exception as e:
        write_simple_error_log("stats_print_fail", "", f"统计数据打印失败: {str(e)}")


def _score_result_quality(result: dict) -> float:
    """评估OCR识别结果的质量分数"""
    score = 0.0

    ocr_extract = result.get("ocr_extract", {})
    if not isinstance(ocr_extract, dict):
        return 0.0

    total_amount = ocr_extract.get("total_amount", "")
    if total_amount and total_amount not in ("N/A", "", "无"):
        score += 40

    invoice_code = ocr_extract.get("invoice_code", "")
    if invoice_code and invoice_code not in ("N/A", "", "无"):
        score += 20

    date = ocr_extract.get("date", "")
    if date and date not in ("N/A", "", "无"):
        score += 15

    image_type = result.get("image_type", "")
    if image_type and image_type not in ("N/A", "", "无", "其他"):
        score += 15

    relevant_party = ocr_extract.get("relevant_party", "")
    if relevant_party and relevant_party not in ("N/A", "", "无"):
        score += 10

    return score


def _process_single_image_multimodel(args: tuple) -> tuple:
    """多模型并发处理单张图片"""
    img_path, idx, output_root, db_enabled, providers, max_workers = args
    img_name = Path(img_path).name
    results_by_provider = {}

    def _recognize_with_provider(provider_key: str, img_path: str) -> dict:
        set_provider(provider_key)
        try:
            return audit_ocr_recognize(img_path, db_enabled=False)
        except Exception as e:
            return {"error": str(e), "provider": provider_key}

    with ThreadPoolExecutor(max_workers=len(providers)) as executor:
        futures = {
            executor.submit(_recognize_with_provider, p, img_path): p
            for p in providers
        }
        for future in as_completed(futures):
            provider_key = futures[future]
            try:
                result = future.result()
                results_by_provider[provider_key] = result
            except Exception as e:
                results_by_provider[provider_key] = {"error": str(e)}

    best_result = None
    best_score = -1
    best_provider = None

    for provider_key, result in results_by_provider.items():
        if "error" in result:
            continue
        score = _score_result_quality(result)
        if score > best_score:
            best_score = score
            best_result = result
            best_provider = provider_key

    if best_result is None:
        return None, img_path, img_name, "所有模型均失败"

    best_result["_multi_model_provider"] = best_provider
    best_result["_all_providers_tried"] = list(results_by_provider.keys())

    return best_result, img_path, img_name, None


def batch_audit_process_multimodel(image_folder: str = "", excel_output: str = "",
                                   output_root: str = "", db_enabled: bool = None,
                                   max_images: int = 0, max_workers: int = 4,
                                   providers: list = None):
    """
    多模型并发审计处理 - 多个模型同时识别，结果对比选择

    参数:
        image_folder: 图片文件夹路径
        excel_output: Excel输出路径
        output_root: 分类图片保存根目录
        db_enabled: 是否启用数据库写入
        max_images: 最大处理图片数，0=不限制
        max_workers: 每个模型的并发数
        providers: 供应商列表，如 ["zhipu", "deepseek", "qwen"]
    """
    _img_folder = image_folder or cfg.IMAGE_FOLDER
    _excel_out = excel_output or cfg.EXCEL_OUTPUT
    _out_root = output_root or cfg.OUTPUT_ROOT_FOLDER
    _db = db_enabled if db_enabled is not None else getattr(cfg, "DB_ENABLED", False)

    if not providers or len(providers) < 2:
        raise ValueError("多模型并发模式需要至少2个供应商")

    init_log_files()

    provider_names = []
    for p in providers:
        set_provider(p)
        pname = get_provider_config()["config"].get("name", p)
        provider_names.append(pname)

    image_dir = Path(_img_folder)
    if not image_dir.exists():
        print(f"❌ 图片文件夹不存在：{_img_folder}")
        return

    image_files = []
    for file in image_dir.iterdir():
        if file.is_file() and file.suffix.lower() in cfg.SUPPORTED_FORMATS:
            image_files.append(file)

    if not image_files:
        print(f"⚠️ 无支持的图片文件：{_img_folder}")
        return

    if max_images > 0 and len(image_files) > max_images:
        image_files = image_files[:max_images]

    results = []
    failed_files = []
    db_ok = 0
    db_fail = 0
    total = len(image_files)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n🚀 开始多模型并发审计（{len(providers)}个模型）...")
    print(f"   模型列表：{provider_names}")
    print(f"   每模型并发数：{max_workers}")
    print(f"🔧 已启用繁体汉字金额识别功能")
    print("-" * 80)

    start_time = datetime.now()

    def task_args_generator():
        for idx, img_path in enumerate(image_files, 1):
            yield (str(img_path), idx, _out_root, _db, providers, max_workers)

    total_workers = len(providers) * max_workers

    with ThreadPoolExecutor(max_workers=total_workers) as executor:
        future_to_args = {
            executor.submit(_process_single_image_multimodel, args): args
            for args in task_args_generator()
        }

        completed = 0
        for future in as_completed(future_to_args):
            completed += 1
            try:
                result, img_path, fname, error = future.result()
                if error:
                    failed_files.append(img_path)
                    print(f"[{completed}/{total}] ❌ {fname} | 错误：{error}")
                else:
                    save_image_and_info(Path(img_path), result, completed, output_root=_out_root)

                    ocr_extract = result.get("ocr_extract", {})
                    if not isinstance(ocr_extract, dict):
                        ocr_extract = {}

                    seal_info = ocr_extract.get("seal_info", {})
                    if not isinstance(seal_info, dict):
                        seal_info = {}

                    license_info = ocr_extract.get("license_info", {})
                    if not isinstance(license_info, dict):
                        license_info = {}

                    row = {
                        "序号": completed,
                        "文件名": fname,
                        "图片路径": img_path,
                        "凭证类型": get_safe_value(result, "image_type"),
                        "金额": get_safe_value(ocr_extract, "total_amount"),
                        "日期": get_safe_value(ocr_extract, "date"),
                        "开票方": get_safe_value(ocr_extract, "relevant_party"),
                        "风险评级": get_safe_value(result, "risk_level"),
                        "风险描述": get_safe_value(result, "risk_description"),
                        "知识库规则ID": get_safe_value(result, "kb_rule_ids"),
                        "知识库规则名称": get_safe_value(result, "kb_rule_names"),
                        "详细JSON": str(result.get("full_json", {})),
                        "最佳模型": result.get("_multi_model_provider", ""),
                        "已试模型": ",".join(result.get("_all_providers_tried", [])),
                    }

                    if _db:
                        if save_single_result(row, batch_id):
                            db_ok += 1
                        else:
                            db_fail += 1

                    results.append(row)

                    elapsed = (datetime.now() - start_time).total_seconds()
                    avg_time = elapsed / completed
                    remaining = avg_time * (total - completed)
                    best_model = result.get("_multi_model_provider", "")
                    print(f"[{completed}/{total}] ✅ {fname} | 最佳模型:{best_model} | 用时{elapsed:.0f}s | 估算剩余{remaining:.0f}s")

            except Exception as e:
                completed += 1
                error_reason = f"多模型线程异常：{str(e)}"
                write_simple_error_log("multimodel_thread_fail", str(future_to_args[future][0]), error_reason)
                failed_files.append(str(future_to_args[future][0]))
                print(f"[{completed}/{total}] ❌ 线程异常：{str(e)}")

    try:
        Path(_excel_out).parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(results)
        df.to_excel(_excel_out, index=False, engine="openpyxl")
        print(f"📊 Excel结果保存至：{_excel_out}")
    except Exception as e:
        print(f"❌ 写入Excel失败：{str(e)}")

    try:
        high_risk = sum(1 for r in results if r.get("风险评级") == "高风险")
        mid_risk = sum(1 for r in results if r.get("风险评级") == "中风险")
        low_risk = sum(1 for r in results if r.get("风险评级") == "低风险")

        total_time = (datetime.now() - start_time).total_seconds()

        print("-" * 80)
        print(f"✅ 多模型并发审计完成！（完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
        print(f"⏱️ 总耗时：{total_time:.1f}秒 | 平均每张：{total_time/total:.1f}秒")
        print(f"📁 分类图片保存至：{_out_root}")
        print(f"📊 风险统计：高风险{high_risk}张 | 中风险{mid_risk}张 | 低风险{low_risk}张")
        if _db:
            print(f"💾 数据库写入：成功 {db_ok} 条 | 失败 {db_fail} 条")
        print(f"❌ 处理失败文件数：{len(failed_files)} 个")
    except Exception as e:
        write_simple_error_log("multimodel_stats_fail", "", f"统计数据打印失败: {str(e)}")


def _process_single_image_mt(args):
    """多线程处理单张图片（线程安全）"""
    img_path, idx, total, batch_id, _out_root, _db = args
    
    img_name = Path(img_path).name
    local_result = None
    local_error = None
    
    try:
        audit_result = audit_ocr_recognize(img_path, db_enabled=_db)
        save_image_and_info(Path(img_path), audit_result, idx, output_root=_out_root)
        
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
        
        row = {
            "图片名称": img_name,
            "图片路径": str(Path(img_path).absolute()),
            "分类保存路径": str(
                Path(_out_root) / sanitize_filename(audit_result.get("image_type", "其他")) /
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
            "审计说明": get_safe_value(audit_result, "reason"),
            "匹配知识库规则": audit_result.get("kb_rule_ids", ""),
            "CPA知识辅导": audit_result.get("cpa_tutoring", ""),
            "_full_json": audit_result,
            "_db_save_needed": _db,
            "_db_save_success": False
        }
        local_result = (row, idx, img_name, img_path)
        
    except Exception as e:
        local_error = (str(e), img_path, img_name)
    
    return (local_result, local_error)


def batch_audit_process_multithread(image_folder: str = "", excel_output: str = "",
                                   output_root: str = "", db_enabled: bool = None,
                                   max_images: int = 0, max_workers: int = 4):
    """多线程版本的批量审计处理"""
    _img_folder = image_folder or cfg.IMAGE_FOLDER
    _excel_out = excel_output or cfg.EXCEL_OUTPUT
    _out_root = output_root or cfg.OUTPUT_ROOT_FOLDER
    _db = db_enabled if db_enabled is not None else getattr(cfg, "DB_ENABLED", False)
    
    init_log_files()
    
    provider_info = get_provider_config()
    pname = provider_info["name"]
    is_cloud_api = pname != "ollama"
    
    if is_cloud_api:
        print(f"☁️ 检测到云端API模式 ({pname})，启用多线程加速")
        print(f"⚡ 并发线程数: {max_workers}")
    else:
        print("⚠️ Ollama本地模式不支持多线程加速，将使用单线程处理")
        return batch_audit_process(image_folder, excel_output, output_root, db_enabled, max_images)
    
    if not check_ollama_service():
        error_reason = "无法连接模型服务"
        write_simple_error_log("service_connect_fail", "", error_reason)
        print(f"❌ 无法连接模型服务！请检查网络和API配置")
        return
    
    image_dir = Path(_img_folder)
    if not image_dir.exists():
        error_reason = f"图片文件夹不存在：{_img_folder}"
        write_simple_error_log("folder_not_exist", "", error_reason)
        print(f"❌ 图片文件夹不存在：{_img_folder}")
        return
    
    image_files = []
    processed_paths = set()
    for file in image_dir.iterdir():
        if file.is_file() and file.suffix.lower() in cfg.SUPPORTED_FORMATS:
            file_path = str(file.absolute())
            if file_path not in processed_paths:
                processed_paths.add(file_path)
                image_files.append(file)
    
    if not image_files:
        error_reason = f"无支持的图片文件：{_img_folder}"
        write_simple_error_log("no_image_files", "", error_reason)
        print(f"⚠️ 无支持的图片文件：{_img_folder}")
        return
    
    total = len(image_files)
    if max_images > 0 and total > max_images:
        image_files = image_files[:max_images]
        total = len(image_files)
    
    results = []
    failed_files = []
    db_ok = 0
    db_fail = 0
    completed = 0
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\n🚀 多线程审计处理 {total} 张图片...（当前系统时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
    print(f"🔧 主识别模型：{get_main_model()} | 修复模型：{get_fix_model()}")
    print(f"🔧 模型供应商：{provider_info['config'].get('name', 'Unknown')}")
    print(f"🔧 已启用繁体汉字金额识别功能")
    print("-" * 80)
    
    start_time = datetime.now()
    
    task_args = [(str(img_path), idx, total, batch_id, _out_root, _db) 
                 for idx, img_path in enumerate(image_files, 1)]
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_args = {executor.submit(_process_single_image_mt, args): args for args in task_args}
        
        for future in as_completed(future_to_args):
            args = future_to_args[future]
            idx = args[1]
            img_name = args[3]
            
            try:
                local_result, local_error = future.result()
                completed += 1
                
                if local_error:
                    _, img_path, fname = local_error
                    error_reason = f"文件处理失败：{local_error[0]}"
                    write_simple_error_log("file_process_fail", img_path, error_reason)
                    failed_files.append(img_path)
                    print(f"[{completed}/{total}] ❌ {fname} 处理失败：{local_error[0]}")
                else:
                    row, _, fname, img_path = local_result
                    
                    if _db:
                        with _db_lock:
                            if save_single_result(row, batch_id):
                                row["_db_save_success"] = True
                                db_ok += 1
                            else:
                                db_fail += 1
                    
                    with _results_lock:
                        results.append(row)
                    
                    elapsed = (datetime.now() - start_time).total_seconds()
                    avg_time = elapsed / completed
                    remaining = avg_time * (total - completed)
                    print(f"[{completed}/{total}] ✅ {fname} | 用时{elapsed:.0f}s | 估算剩余{remaining:.0f}s | DB成功{db_ok} 失败{db_fail}")
            
            except Exception as e:
                completed += 1
                error_reason = f"线程执行异常：{str(e)}"
                write_simple_error_log("thread_execute_fail", str(args[0]), error_reason)
                failed_files.append(str(args[0]))
                print(f"[{completed}/{total}] ❌ 线程异常：{str(e)}")
    
    try:
        Path(_excel_out).parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(results)
        df.to_excel(_excel_out, index=False, engine="openpyxl")
        print(f"📊 Excel结果保存至：{_excel_out}")
    except Exception as e:
        error_reason = f"写入Excel失败：{str(e)}"
        write_simple_error_log("excel_write_fail", "", error_reason)
        print(f"❌ 写入Excel失败：{str(e)}")
    
    try:
        high_risk = sum(1 for r in results if r["风险评级"] == "高风险")
        mid_risk = sum(1 for r in results if r["风险评级"] == "中风险")
        low_risk = sum(1 for r in results if r["风险评级"] == "低风险")
        
        total_time = (datetime.now() - start_time).total_seconds()
        
        print("-" * 80)
        print(f"✅ 多线程审计完成！（完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
        print(f"⏱️ 总耗时：{total_time:.1f}秒 | 平均每张：{total_time/total:.1f}秒")
        print(f"📁 分类图片保存至：{_out_root}")
        print(f"📋 错误日志：{cfg.ERROR_LOG_SIMPLE}")
        print(f"📋 重跑任务日志：{cfg.RETRY_TASK_LOG}")
        print(f"📊 风险统计：高风险{high_risk}张 | 中风险{mid_risk}张 | 低风险{low_risk}张")
        if _db:
            print(f"💾 数据库写入：成功 {db_ok} 条 | 失败 {db_fail} 条")
        print(f"❌ 处理失败文件数：{len(failed_files)} 个")
        if failed_files:
            print(f"📝 失败文件列表：{failed_files[:10]}{'...' if len(failed_files) > 10 else ''}")
    except Exception as e:
        write_simple_error_log("stats_print_fail", "", f"统计数据打印失败: {str(e)}")
