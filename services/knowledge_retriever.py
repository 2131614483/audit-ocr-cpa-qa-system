# ============================================================
# 审计知识库检索服务
# 功能: 从 knowledge_base 表检索相关审计规则，
#       使用向量余弦相似度匹配，返回 top-k 规则
# 核心: retrieve_relevant_rules() - 检索相关规则
#       format_rules_for_prompt() - 格式化规则文本
# ============================================================

import psycopg2
import psycopg2.extras
from datetime import datetime

from config.settings import cfg
from services.embedding_service import get_embedding, cosine_similarity
from utils.logger import write_simple_error_log


def get_db_config():
    return {
        "host": getattr(cfg, "DB_HOST", "localhost"),
        "port": getattr(cfg, "DB_PORT", 5432),
        "dbname": getattr(cfg, "DB_NAME", "audit_ocr"),
        "user": getattr(cfg, "DB_USER", "postgres"),
        "password": getattr(cfg, "DB_PASSWORD", "admin"),
    }


def retrieve_relevant_rules(query_text: str, top_k: int = 5) -> list[dict]:
    if not query_text or not query_text.strip():
        return []

    query_vec = get_embedding(query_text[:2000])
    if not query_vec:
        return []

    conn = None
    try:
        conn = psycopg2.connect(**get_db_config())
        cur = conn.cursor()
        cur.execute("SELECT id, category, rule_id, rule_name, content, risk_level, embedding FROM knowledge_base WHERE embedding IS NOT NULL")

        scored = []
        for row in cur.fetchall():
            db_embedding = row[6]
            db_list = list(db_embedding) if db_embedding else []
            if db_list:
                sim = cosine_similarity(query_vec, db_list)
                scored.append((sim, {
                    "id": row[0],
                    "category": row[1],
                    "rule_id": row[2],
                    "rule_name": row[3],
                    "content": row[4],
                    "risk_level": row[5],
                }))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        results = []
        for sim, rule in top:
            rule["similarity"] = round(sim, 4)
            results.append(rule)

        return results

    except Exception as e:
        write_simple_error_log("kb_retrieve_fail", "", f"知识库检索失败: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()


def format_rules_for_prompt(rules: list[dict]) -> str:
    if not rules:
        return ""

    lines = ["\n### 相关审计规则参考 ###"]
    lines.append("以下是与当前图片相关的审计规则，请参考这些规则进行风险判断：")

    for i, rule in enumerate(rules, 1):
        lines.append(f"\n规则{i}（相关度{rule['similarity']:.2%}）：")
        lines.append(f"  [{rule['rule_id']}] {rule['rule_name']}")
        lines.append(f"  分类：{rule['category']}（风险等级：{rule['risk_level']}）")
        lines.append(f"  内容：{rule['content']}")

    lines.append("\n请结合上述规则，仔细分析图片内容，给出准确的风险评级和审计结论。")
    return "\n".join(lines)
