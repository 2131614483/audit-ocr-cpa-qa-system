# ============================================================
# CPA 知识点辅导服务
# 功能: 连接 cpa_knowledge 数据库检索 CPA 教材知识库，
#       生成辅导评语，支持单张凭证辅导和全局汇总
# 核心: search_cpa_knowledge() - 检索教材知识库
#       format_single_tutoring() - 单张凭证辅导
#       format_global_tutoring() - 全局汇总辅导
# ============================================================

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import json
import os
from collections import Counter
import requests as _requests
import psycopg2
from pathlib import Path
from utils.logger import write_simple_error_log

CPA_DB = {
    "host": "localhost", "port": 5432,
    "dbname": "cpa_knowledge", "user": "postgres", "password": "admin"
}
CPA_EMBED_URL = "http://localhost:11434/api/embeddings"
CPA_EMBED_MODEL = "qwen3-embedding:8b"


def _get_embedding(text: str) -> list | None:
    try:
        r = _requests.post(CPA_EMBED_URL, json={"model": CPA_EMBED_MODEL, "prompt": text.strip()}, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data.get("embedding", data.get("embeddings", [None])[0])
    except Exception:
        return None


def _retrieve_cpa(query_text: str, top_k: int = 5) -> list[dict]:
    if not query_text or not query_text.strip():
        return []
    vec = _get_embedding(query_text)
    if not vec:
        return []
    vec_str = "[" + ",".join(str(x) for x in vec) + "]"
    conn = psycopg2.connect(**CPA_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT chunk_content, metadata, 1 - (embedding <-> %s) as similarity
        FROM cpa_embeddings
        WHERE embedding IS NOT NULL
        ORDER BY embedding <-> %s
        LIMIT %s
    """, (vec_str, vec_str, top_k))
    results = []
    for row in cur.fetchall():
        meta = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or {})
        results.append({
            "content": row[0][:600],
            "course": meta.get("course", ""),
            "book": meta.get("book", ""),
            "heading_path": meta.get("heading_path", ""),
            "similarity": round(row[2], 4) if row[2] else 0
        })
    cur.close()
    conn.close()
    return results


def format_single_tutoring(audit_result: dict, image_name: str) -> str:
    ocr = audit_result.get("ocr_extract", {}) or {}
    query_parts = []
    img_type = audit_result.get("image_type", "")
    risk = audit_result.get("risk_rating", "")
    reason = audit_result.get("reason", "") or audit_result.get("risk_description", "")
    if img_type:
        query_parts.append(f"类型：{img_type}")
    if risk:
        query_parts.append(f"风险：{risk}")
    if reason:
        query_parts.append(f"说明：{reason}")
    if ocr.get("date"):
        query_parts.append(f"日期：{ocr['date']}")
    if ocr.get("total_amount") and ocr["total_amount"] not in ("N/A", ""):
        query_parts.append(f"金额：{ocr['total_amount']}")
    if ocr.get("relevant_party") and ocr["relevant_party"] not in ("N/A", ""):
        query_parts.append(f"相关方：{ocr['relevant_party']}")
    query = " ".join(query_parts) if query_parts else f"审计凭证 {image_name}"
    cpa_results = _retrieve_cpa(query, top_k=5)
    if not cpa_results:
        return ""
    lines = [
        "",
        "━" * 60,
        "  📚 CPA 知识点辅导 —— 单张凭证",
        "━" * 60,
        f"  📄 凭证：{image_name}",
        f"  🏷️  类型：{img_type}",
        f"  ⚠️  风险：{risk}",
        f"  💡 说明：{reason}",
        "",
        "  【相关CPA教材知识点】",
    ]
    for i, r in enumerate(cpa_results, 1):
        heading = r["heading_path"] or f"{r['course']} > {r['book']}"
        lines.append(f"")
        lines.append(f"  ── {i}. {heading}（相关度{r['similarity']:.0%}）")
        lines.append(f"     {r['content'][:200]}")
    lines.append("")
    lines.append("━" * 60)
    return "\n".join(lines)


def format_global_tutoring(results: list[dict]) -> str:
    if not results:
        return ""
    total = len(results)
    high = sum(1 for r in results if r.get("风险评级") == "高风险")
    mid = sum(1 for r in results if r.get("风险评级") == "中风险")
    low = sum(1 for r in results if r.get("风险评级") == "低风险")
    problem_types = []
    for r in results:
        reason = r.get("审计说明", "") or r.get("风险说明", "")
        if "日期" in reason or "过期" in reason or "date" in reason.lower():
            problem_types.append("日期异常")
        elif "金额" in reason or "amount" in reason.lower():
            problem_types.append("金额异常")
        elif "章" in reason or "seal" in reason.lower() or "印" in reason:
            problem_types.append("印章问题")
        elif "缺失" in reason or "missing" in reason.lower():
            problem_types.append("信息缺失")
    problem_stats = Counter(problem_types)
    type_counts = Counter(r.get("图像类型", "其他") for r in results)
    query_parts = [
        f"本次审计共处理了{total}张凭证，其中高风险{high}张、中风险{mid}张、低风险{low}张。",
        "主要问题包括：" + "、".join(f"{k}({v}次)" for k, v in problem_stats.most_common(5)) if problem_stats else "无明显集中问题。",
    ]
    query = " ".join(query_parts)
    cpa_results = _retrieve_cpa(query, top_k=8)
    if not cpa_results:
        return ""
    lines = [
        "",
        "█" * 60,
        "  ██  CPA 综合辅导报告 —— 全局汇总",
        "█" * 60,
        "",
        f"  📊 本次审计概况",
        f"  ───────────────────────",
        f"  处理凭证：{total} 张",
        f"  高风险：{high} 张 ({high*100//max(total,1)}%)",
        f"  中风险：{mid} 张 ({mid*100//max(total,1)}%)",
        f"  低风险：{low} 张 ({low*100//max(total,1)}%)",
        "",
        f"  📋 主要问题分布",
        f"  ───────────────────────",
    ]
    for problem, cnt in problem_stats.most_common(5):
        pct = cnt * 100 // max(total, 1)
        bar = "█" * (pct // 5)
        lines.append(f"  {problem}：{cnt}次 ({pct}%) {bar}")
    lines.append("")
    lines.append(f"  🏷️  凭证类型分布")
    lines.append(f"  ───────────────────────")
    for t, cnt in type_counts.most_common(5):
        lines.append(f"  {t}：{cnt}张")
    lines.append("")
    lines.append(f"  📖 CPA教材知识点建议")
    lines.append(f"  ───────────────────────")
    lines.append(f"  针对本次审计中出现的共性问题，建议复习以下CPA教材内容：")
    for i, r in enumerate(cpa_results, 1):
        heading = r["heading_path"] or f"{r['course']} > {r['book']}"
        lines.append(f"")
        lines.append(f"  {i}. {heading}（相关度{r['similarity']:.0%}）")
        lines.append(f"     {r['content'][:250]}")
    lines.append("")
    lines.append("█" * 60)
    return "\n".join(lines)


def append_tutoring_to_info(txt_path: str | Path, tutoring_text: str):
    if not tutoring_text:
        return
    try:
        with open(txt_path, "a", encoding="utf-8") as f:
            f.write("\n\n" + tutoring_text)
    except Exception as e:
        write_simple_error_log("cpa_tutoring_write_fail", str(txt_path), str(e))


def save_global_tutoring(tutoring_text: str, output_root: str = ""):
    if not tutoring_text:
        return
    output_dir = output_root or "./output"
    save_path = Path(output_dir) / "cpa_tutoring_summary.txt"
    try:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(tutoring_text)
        print(f"  📚 CPA综合辅导报告已保存：{save_path}")
    except Exception as e:
        write_simple_error_log("cpa_tutoring_save_fail", "", str(e))
