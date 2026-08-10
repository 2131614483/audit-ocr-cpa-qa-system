"""
智谱API全流程测试（集成版）
功能：
1. 使用10大类别专属提示词（category_prompts.py）
2. 自动JSON修复和重试机制（agent_retry.py）
3. 3并发处理
4. 写入数据库（Agent1和Agent2分别写入不同表）
5. 按类别复制图片到文件夹
6. 输出JSON结构结果文件
"""
import os
import re
import json
import shutil
import base64
import time
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import psycopg2, psycopg2.extras

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 切换到智谱API
from config.settings import set_provider
set_provider("zhipu")

# 导入专属提示词和重试机制
from pic_claw.category_prompts import build_classify_prompt, get_category_map, CATEGORY_GROUPS
from pic_claw.agent_retry import classify_with_retry, extract_with_retry

# ===================== 配置 =====================
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "audit_pipeline_db",
    "user": "postgres",
    "password": "admin"
}

# 输出目录
OUTPUT_ROOT = Path(__file__).parent / "分类结果_智谱"
OUTPUT_ROOT.mkdir(exist_ok=True)

# 并发数
MAX_WORKERS = 3

# 反转映射：类型→大类
TYPE_TO_CATEGORY = get_category_map()


def image_to_base64(image_path: str) -> str:
    """图片转base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def write_agent1_result(image_id: int, batch_id: int, cls_result: dict, 
                        real_type: str, real_category: str, 
                        raw_output: str, duration_s: float, 
                        retry_count: int = 0, error_msg: str = None):
    """写入Agent1分类结果到数据库"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            predicted_type = cls_result.get("type_name", "未知") if cls_result else None
            predicted_category = cls_result.get("category_name", "其他类") if cls_result else None
            confidence = cls_result.get("confidence", 0) if cls_result else 0
            reasoning = cls_result.get("reasoning", "") if cls_result else None
            
            is_correct = None
            if cls_result and real_type:
                is_correct = (predicted_type == real_type)
            
            cur.execute("""
                INSERT INTO agent1_classify_results (
                    image_id, batch_id, predicted_type, predicted_category,
                    confidence, reasoning, actual_type, actual_category,
                    is_correct, model_name, raw_output, duration_ms,
                    retry_count, status, error_msg
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                image_id, batch_id, predicted_type, predicted_category,
                confidence, reasoning, real_type, real_category,
                is_correct, "GLM-4.6V-FlashX", raw_output, int(duration_s * 1000),
                retry_count, "done" if cls_result else "failed", error_msg
            ))
            conn.commit()
    finally:
        conn.close()


def write_agent2_result(image_id: int, batch_id: int, category_name: str,
                        doc_type_name: str, ext_result: dict,
                        raw_output: str, duration_s: float,
                        retry_count: int = 0, error_msg: str = None):
    """写入Agent2提取结果到数据库"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            if ext_result:
                ocr_extract = ext_result.get("ocr_extract", {})
                validation = ext_result.get("validation_result", {})
                
                field_count = 0
                for v in ocr_extract.values():
                    if v != "N/A":
                        if isinstance(v, dict):
                            field_count += len([vv for vv in v.values() if vv != "N/A"])
                        else:
                            field_count += 1
                
                cur.execute("""
                    INSERT INTO agent2_extract_results (
                        image_id, batch_id, category_name, doc_type_name,
                        extracted_fields, field_count, validation_result,
                        risk_rating, risk_description, audit_conclusion, audit_reason,
                        summary, summary_confidence, model_name, raw_output,
                        duration_ms, retry_count, status, error_msg
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    image_id, batch_id, category_name, doc_type_name,
                    json.dumps(ocr_extract, ensure_ascii=False), field_count,
                    json.dumps(validation, ensure_ascii=False) if validation else None,
                    ext_result.get("risk_rating"), ext_result.get("risk_description"),
                    ext_result.get("audit_conclusion"), ext_result.get("reason"),
                    ext_result.get("_summary"), ext_result.get("_confidence", 0),
                    "GLM-4.6V-FlashX", raw_output, int(duration_s * 1000),
                    retry_count, "done", error_msg
                ))
            else:
                cur.execute("""
                    INSERT INTO agent2_extract_results (
                        image_id, batch_id, category_name, doc_type_name,
                        status, error_msg, model_name, raw_output, duration_ms, retry_count
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    image_id, batch_id, category_name, doc_type_name,
                    "failed", error_msg, "GLM-4.6V-FlashX", raw_output,
                    int(duration_s * 1000), retry_count
                ))
            conn.commit()
    finally:
        conn.close()


def process_single_image(file_path: str, file_name: str, image_id: int, batch_id: int,
                         real_type: str = None, real_category: str = None) -> dict:
    """
    处理单张图片：分类+提取（带重试）+ 写入数据库
    """
    b64 = image_to_base64(file_path)
    result = {
        "file_name": file_name,
        "file_path": file_path,
        "image_id": image_id,
        "batch_id": batch_id,
        "real_type": real_type,
        "real_category": real_category,
        "process_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # ---- Agent1 分类（带重试） ----
    t1 = time.time()
    classify_prompt = build_classify_prompt()
    cls_result, cls_error = classify_with_retry(classify_prompt, b64, max_retries=3)
    t_cls = time.time() - t1
    
    # 写入Agent1结果
    write_agent1_result(
        image_id, batch_id, cls_result, real_type, real_category,
        cls_error or "success", t_cls
    )
    
    if cls_result:
        type_name = cls_result.get("type_name", "未知")
        category = cls_result.get("category_name", "其他类")
        confidence = cls_result.get("confidence", 0)
        reasoning = cls_result.get("reasoning", "")
        
        result["classify_result"] = {
            "type_name": type_name,
            "category": category,
            "confidence": confidence,
            "reasoning": reasoning,
            "duration_s": round(t_cls, 1),
            "status": "success"
        }
    else:
        result["classify_result"] = {
            "status": "failed",
            "error": cls_error,
            "duration_s": round(t_cls, 1)
        }
        return result
    
    # ---- Agent2 提取（带重试） ----
    t2 = time.time()
    
    extract_prompt = f"""你是一位专业的审计凭证信息提取专家。请从这张图片中提取所有可见的关键字段信息。

凭证类型：{type_name}
所属大类：{category}

请严格按照以下JSON格式输出（只输出JSON，不要包含任何其他文字）：
{{
    "image_type": "{type_name}",
    "ocr_extract": {{
        "invoice_code": "发票代码或N/A",
        "invoice_number": "发票号码或N/A",
        "date": "日期(YYYY-MM-DD)或N/A",
        "total_amount": "金额(纯数字)或N/A",
        "relevant_party": "相关方名称或N/A",
        "tax_rate": "税率或N/A",
        "tax_id": "纳税人识别号或N/A",
        "bank_info": "银行信息或N/A",
        "serial_number": "流水号或N/A",
        "details": "摘要/备注或N/A",
        "seal_info": {{
            "seal_type": "印章类型或N/A",
            "seal_number": "印章编号或N/A",
            "seal_clarity": "印章清晰度(清晰/模糊/无)或N/A",
            "joint_seal": "是否联合盖章(是/否)或N/A"
        }},
        "license_info": {{
            "unified_social_credit_code": "统一社会信用代码或N/A",
            "legal_person": "法定代表人或N/A",
            "valid_period": "有效期限或N/A"
        }},
        "asset_info": {{
            "asset_tag": "资产标签或N/A",
            "asset_name": "资产名称或N/A",
            "location": "位置或N/A",
            "quantity": "数量或N/A",
            "progress": "进度或N/A"
        }},
        "internal_control_info": {{
            "signer": "签字人或N/A",
            "approval_level": "审批级别或N/A",
            "attachment_complete": "附件是否完整(是/否)或N/A"
        }},
        "other_info": "其他信息或N/A"
    }},
    "validation_result": {{
        "date_valid": true,
        "amount_valid": true,
        "code_format_valid": true,
        "no_missing_field": true,
        "image_normal": true,
        "no_duplicate": true,
        "consistent_info": true,
        "compliance": true,
        "no_fraud": true
    }},
    "risk_rating": "高风险/中风险/低风险",
    "risk_description": "风险说明",
    "audit_conclusion": "通过/不通过/人工复核",
    "reason": "审计说明",
    "audit_value": "数字化审计留痕，可核对、可预警",
    "_confidence": 0.95,
    "_summary": "简要描述该凭证的核心内容（20字以内）"
}}

注意：
1. 不存在的字段填"N/A"
2. 金额只填数字，去掉货币符号
3. 日期统一为YYYY-MM-DD格式
4. 布尔值填true或false
5. 仔细阅读图片中的所有文字"""

    ext_result, ext_error = extract_with_retry(extract_prompt, b64, max_retries=3)
    t_ext = time.time() - t2
    
    # 写入Agent2结果
    write_agent2_result(
        image_id, batch_id, category, type_name,
        ext_result, ext_error or "success", t_ext
    )
    
    if ext_result:
        ocr = ext_result.get("ocr_extract", {})
        field_count = len([v for v in ocr.values() if v != "N/A" and not isinstance(v, dict)])
        for k, v in ocr.items():
            if isinstance(v, dict):
                field_count += len([vv for vv in v.values() if vv != "N/A"])
        
        result["extract_result"] = {
            "status": "success",
            "fields_extracted": field_count,
            "data": ext_result,
            "duration_s": round(t_ext, 1)
        }
    else:
        result["extract_result"] = {
            "status": "failed",
            "error": ext_error,
            "duration_s": round(t_ext, 1)
        }
    
    result["total_duration_s"] = round(time.time() - t1, 1)
    return result


def process_and_log(img: dict, index: int, total: int) -> dict:
    """处理单张图片并打印日志"""
    print(f"\n[{index}/{total}] 📄 {img['file_name']}")
    if img.get("doc_type_name"):
        print(f"         真实: {img['doc_type_name']} ({img.get('category_name', '')})")
    
    result = process_single_image(
        img["file_path"], 
        img["file_name"],
        img["id"],
        img.get("batch_id", 4),
        img.get("doc_type_name"),
        img.get("category_name")
    )
    
    cls = result.get("classify_result", {})
    if cls.get("status") == "success":
        ext = result.get("extract_result", {})
        fields = ext.get("fields_extracted", 0) if ext.get("status") == "success" else 0
        print(f"         ✅ {cls['type_name']} ({cls['category']}) | 提取{fields}字段 | {result['total_duration_s']:.1f}s")
    else:
        print(f"         ❌ 分类失败: {cls.get('error', '')[:60]}")
    
    return result


def copy_and_organize(results: list):
    """按类别复制图片到文件夹，并生成JSON结果文件"""
    print(f"\n{'=' * 60}")
    print("📁 整理输出...")
    
    for r in results:
        file_name = r["file_name"]
        src_path = r["file_path"]
        cls = r.get("classify_result", {})
        
        if cls.get("status") != "success":
            print(f"  ⏭️ {file_name} (分类失败，跳过)")
            continue
        
        type_name = cls.get("type_name", "未知")
        category = cls.get("category", "其他类")
        
        # 创建类别文件夹
        type_dir = OUTPUT_ROOT / category / type_name
        type_dir.mkdir(parents=True, exist_ok=True)
        
        # 复制图片
        if Path(src_path).exists():
            dst_path = type_dir / file_name
            shutil.copy2(src_path, str(dst_path))
            r["output_path"] = str(dst_path)
            print(f"  ✓ {category}/{type_name}/{file_name}")
        
        # 保存JSON结果
        json_path = type_dir / f"{Path(file_name).stem}_result.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
    
    # 生成汇总JSON
    summary_path = OUTPUT_ROOT / "汇总结果.json"
    summary = {
        "process_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_images": len(results),
        "success_count": len([r for r in results if r.get("classify_result", {}).get("status") == "success"]),
        "error_count": len([r for r in results if r.get("classify_result", {}).get("status") != "success"]),
        "results": results
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n📊 汇总结果: {summary_path}")
    print(f"📁 输出目录: {OUTPUT_ROOT}")


def main():
    """主函数：从数据库取图片并3并发处理"""
    # 取10张待测试图片
    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT id, batch_id, file_path, file_name, doc_type_name, category_name
            FROM voucher_images
            WHERE batch_id = 4 AND classify_status = 'pending'
            ORDER BY id
            LIMIT 10
        """)
        images = [dict(r) for r in cur.fetchall()]
    conn.close()
    
    if not images:
        print("没有待处理的图片")
        return
    
    print("=" * 60)
    print("🚀 智谱API全流程测试（集成版）")
    print(f"📊 待处理: {len(images)}张图片")
    print(f"🤖 模型: GLM-4.6V-FlashX")
    print(f"🔄 重试: 最多3次")
    print(f"⚡ 并发: {MAX_WORKERS}")
    print(f"📋 提示词: 10大类别专属视觉描述")
    print(f"💾 数据库: Agent1→agent1_classify_results, Agent2→agent2_extract_results")
    print("=" * 60)
    
    # 3并发处理
    results = [None] * len(images)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for i, img in enumerate(images):
            future = executor.submit(process_and_log, img, i + 1, len(images))
            futures[future] = i
        
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = {"file_name": images[idx]["file_name"], "error": str(e)}
    
    # 整理输出
    copy_and_organize(results)
    
    # 打印汇总
    print(f"\n{'=' * 60}")
    print("📊 测试汇总")
    print("=" * 60)
    success = len([r for r in results if r and r.get("classify_result", {}).get("status") == "success"])
    failed = len(results) - success
    print(f"  总数: {len(results)}")
    print(f"  成功: {success}")
    print(f"  失败: {failed}")
    
    # 打印数据库统计
    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM agent1_classify_results WHERE batch_id = 4")
        a1_cnt = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM agent2_extract_results WHERE batch_id = 4")
        a2_cnt = cur.fetchone()["cnt"]
        cur.execute("SELECT is_correct, COUNT(*) as cnt FROM agent1_classify_results WHERE batch_id = 4 GROUP BY is_correct")
        accuracy = cur.fetchall()
    conn.close()
    
    print(f"\n💾 数据库写入:")
    print(f"  Agent1分类结果: {a1_cnt}条")
    print(f"  Agent2提取结果: {a2_cnt}条")
    for row in accuracy:
        if row["is_correct"] is True:
            print(f"  分类正确: {row['cnt']}条")
        elif row["is_correct"] is False:
            print(f"  分类错误: {row['cnt']}条")


if __name__ == "__main__":
    main()