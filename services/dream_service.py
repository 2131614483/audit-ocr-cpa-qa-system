# ============================================================
# 做梦服务 (Dream Service)
# 功能: 1) 每次问答后自动提炼知识点 2) 手动做梦：矛盾检测+去重
# 核心: extract_knowledge() - 提炼知识点
#       run_dream_consolidation() - 做梦合并
#       search_dream_knowledge() - 检索归档知识
# ============================================================

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import json
import time
import requests
import psycopg2
from pathlib import Path

# 从配置文件加载 API 配置
CONFIG_PATH = Path(__file__).parent.parent / "data" / "model_config.json"

def _load_deepseek_config():
    """从配置文件加载DeepSeek配置"""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            provider = config.get("current_provider", "deepseek")
            providers = config.get("providers", {})
            pcfg = providers.get(provider, {})
            return {
                "provider": provider,
                "api_key": pcfg.get("api_key", ""),
                "api_url": pcfg.get("chat_api", "https://api.deepseek.com/v1/chat/completions"),
                "model": pcfg.get("models", {}).get("main", "deepseek-chat"),
            }
    except Exception as e:
        print(f"[dream] 加载配置失败: {e}")
    return {"provider": "deepseek", "api_key": "", "api_url": "https://api.deepseek.com/v1/chat/completions", "model": "deepseek-chat"}

_ds_config = _load_deepseek_config()
DEEPSEEK_API_KEY = _ds_config["api_key"]
DEEPSEEK_API_URL = _ds_config["api_url"]
DEEPSEEK_MODEL = _ds_config["model"]
DEEPSEEK_PROVIDER = _ds_config.get("provider", "deepseek")
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
OLLAMA_EMBED_MODEL = "qwen3-embedding:8b"

DB_CONFIG = {
    "host": "localhost", "port": 5432,
    "dbname": "cpa_knowledge", "user": "postgres", "password": "admin"
}

# ==================== 工具函数 ====================

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def get_embedding(text):
    if not text or not text.strip():
        return None
    try:
        r = requests.post(OLLAMA_EMBED_URL, json={"model": OLLAMA_EMBED_MODEL, "prompt": text.strip()}, timeout=60)
        if r.status_code == 200:
            data = r.json()
            return data.get("embedding") or (data.get("embeddings", [None])[0] if data.get("embeddings") else None)
    except Exception as e:
        print(f"[dream] embedding失败: {e}")
    return None


def _parse_embedding(emb) -> list:
    """把 pgvector 文本向量解析为 list[float]"""
    if emb is None:
        return []
    if isinstance(emb, list):
        return [float(x) for x in emb]
    s = str(emb).strip()
    if s.startswith('[') and s.endswith(']'):
        try:
            return [float(x) for x in s[1:-1].split(',')]
        except Exception:
            return []
    return []


def _embedding_cosine(a, b):
    """两个向量的余弦相似度；任一向量缺失返回 None"""
    va = _parse_embedding(a)
    vb = _parse_embedding(b)
    if not va or not vb or len(va) != len(vb):
        return None
    dot = sum(x * y for x, y in zip(va, vb))
    na = (sum(x * x for x in va) ** 0.5) or 1.0
    nb = (sum(x * x for x in vb) ** 0.5) or 1.0
    return dot / (na * nb)

def call_deepseek(messages, max_tokens=1000):
    try:
        is_ollama = DEEPSEEK_PROVIDER == "ollama"
        r = requests.post(DEEPSEEK_API_URL, json={
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens,
            # Ollama /api/chat 默认流式输出（NDJSON），必须显式关闭才能整包解析
            "stream": False,
        }, headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }, timeout=300 if is_ollama else 60)
        if r.status_code == 200:
            data = r.json()
            if is_ollama:
                return data.get("message", {}).get("content", "")
            return data["choices"][0]["message"]["content"]
        print(f"[dream] API错误: {r.status_code}")
    except requests.Timeout:
        print(f"[dream] API超时")
        return None
    except Exception as e:
        print(f"[dream] API调用失败: {e}")
    return None

# ==================== 核心功能 ====================

EXTRACT_PROMPT = """你是一名CPA知识提炼专家。请分析以下问答对话，提取出3-5条独立、完整的核心知识点。

要求：
1. 每条知识点必须完整、准确，可直接作为CPA备考资料
2. 去除口语化的冗余信息
3. 标注适用的科目（会计/审计/税法/财务成本管理/经济法/公司战略与风险管理）
4. 按重要性排序

对话：
问题：{question}
回答：{answer}

请严格按以下JSON数组格式输出，不要添加其他内容：
[
    {{
        "topic": "知识点主题（简洁，如'收入确认五步法'）",
        "summary": "一句话摘要（20字以内）",
        "content": "精炼后的知识内容（100-300字）",
        "category": "科目分类"
    }}
]"""

def extract_knowledge(question, answer):
    """从单条问答中提炼知识点"""
    if not answer or len(answer) < 50:
        return []

    prompt = EXTRACT_PROMPT.format(question=question[:500], answer=answer[:2000])
    result = call_deepseek([
        {"role": "system", "content": "你是CPA知识提炼专家，请提取核心知识点并输出JSON数组。"},
        {"role": "user", "content": prompt}
    ], max_tokens=2000)

    if not result:
        return []

    try:
        # 尝试从 markdown 代码块中提取
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0].strip()
        elif "```" in result:
            result = result.split("```")[1].split("```")[0].strip()

        items = json.loads(result)
        if isinstance(items, list):
            return items
        return []
    except Exception as e:
        print(f"[dream] 解析提炼结果失败: {e}")
        return []


def save_dream_knowledge(question, answer, session_id, qa_ids=None):
    """保存提炼的知识点到归档库"""
    items = extract_knowledge(question, answer)
    if not items:
        return 0

    conn = get_db()
    cur = conn.cursor()

    # 获取当前最大 batch
    cur.execute("SELECT COALESCE(MAX(dream_batch), 0) FROM cpa_dream_knowledge")
    max_batch = cur.fetchone()[0]

    saved = 0
    for item in items:
        topic = item.get("topic", "")[:200]
        summary = item.get("summary", "")[:500]
        content = item.get("content", "")
        category = item.get("category", "")[:50]

        if not content:
            continue

        combined = f"知识点：{topic}\n摘要：{summary}\n内容：{content}"
        embedding = get_embedding(combined)

        embedding_str = '[' + ','.join(map(str, embedding)) + ']' if embedding else None
        source_ids = qa_ids or []

        # 动态计算可信度：基于内容完整度
        conf = 0.3
        if topic and len(topic) > 5:
            conf += 0.2
        if summary and len(summary) > 10:
            conf += 0.15
        if content and len(content) > 150:
            conf += 0.2
        if qa_ids:
            conf += 0.1
        if category:
            conf += 0.05
        confidence = min(0.95, max(0.15, round(conf, 2)))

        cur.execute("""
            INSERT INTO cpa_dream_knowledge
                (topic, content, summary, category, confidence, source_session_id, source_qa_ids, dream_batch, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (topic, content, summary, category, confidence, session_id, source_ids, max_batch + 1, embedding_str))
        saved += 1

    conn.commit()
    cur.close()
    conn.close()

    # 记录日志
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cpa_dream_log (dream_batch, dream_type, qa_processed, knowledge_created, contradictions_found, status, finished_at)
        VALUES (%s, 'auto', 1, %s, 0, 'done', NOW())
    """, (max_batch + 1, saved))
    conn.commit()
    cur.close()
    conn.close()

    print(f"[dream] ✅ 自动提炼完成: {saved} 条知识点")
    return saved


# ==================== 手动做梦（矛盾检测+去重） ====================

CONTRADICT_PROMPT = """你是一名CPA知识审核专家。以下两条知识卡片来自不同的问答对话，请判断它们是否存在矛盾。

知识A（可信度{conf_a}）：
主题：{topic_a}
内容：{content_a}

知识B（可信度{conf_b}）：
主题：{topic_b}
内容：{content_b}

请严格按以下JSON格式输出：
{{
    "has_contradiction": true或false,
    "description": "如果存在矛盾，描述矛盾的具体内容（否则为空）",
    "resolution": "如果存在矛盾，给出合并或修正建议（否则为空）",
    "merge_content": "如果存在矛盾，合并后的正确知识内容（否则为空）"
}}"""


def detect_contradiction(item_a, item_b):
    """检测两条知识是否矛盾"""
    # 语义预过滤：仅对「双方都有向量且语义相近(≥0.7)」的知识做 LLM 矛盾检测，
    # 其余跳过，避免 O(n²) 全量 LLM 调用导致合并永远跑不完
    _sim = _embedding_cosine(item_a.get("embedding"), item_b.get("embedding"))
    if _sim is None or _sim < 0.7:
        return {"has_contradiction": False}
    prompt = CONTRADICT_PROMPT.format(
        conf_a=item_a.get("confidence", 0.5),
        topic_a=item_a.get("topic", "")[:100],
        content_a=item_a.get("content", "")[:500],
        conf_b=item_b.get("confidence", 0.5),
        topic_b=item_b.get("topic", "")[:100],
        content_b=item_b.get("content", "")[:500]
    )
    result = call_deepseek([
        {"role": "system", "content": "你是CPA知识审核专家，请判断两条知识是否矛盾。"},
        {"role": "user", "content": prompt}
    ], max_tokens=1500)

    if not result:
        return None

    try:
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0].strip()
        elif "```" in result:
            result = result.split("```")[1].split("```")[0].strip()
        return json.loads(result)
    except:
        return None


def run_dream_consolidation(progress_callback=None):
    """手动做梦：读取归档知识，检测矛盾，去重合并"""
    conn = get_db()
    cur = conn.cursor()

    try:
        # 获取当前最大 batch
        cur.execute("SELECT COALESCE(MAX(dream_batch), 0) FROM cpa_dream_knowledge")
        new_batch = cur.fetchone()[0] + 1

        # 记录开始
        cur.execute("""
            INSERT INTO cpa_dream_log (dream_batch, dream_type, status, started_at)
            VALUES (%s, 'manual', 'running', NOW())
        """, (new_batch,))
        conn.commit()

        # 获取所有知识（按可信度排序，高可信度优先）
        cur.execute("""
            SELECT id, topic, content, summary, category, confidence, source_qa_ids, contradictions, embedding
            FROM cpa_dream_knowledge
            ORDER BY confidence DESC, id ASC
        """)
        all_items = cur.fetchall()
        total = len(all_items)

        if total < 2:
            cur.execute("UPDATE cpa_dream_log SET status='done', qa_processed=0, knowledge_created=0, contradictions_found=0, finished_at=NOW() WHERE dream_batch=%s", (new_batch,))
            conn.commit()
            cur.close()
            conn.close()
            if progress_callback:
                progress_callback("done", {"total": 0, "contradictions": 0, "merged": 0})
            return {"total": 0, "contradictions": 0, "merged": 0}

        contradictions_found = 0
        merged = 0
        to_delete = set()
        to_update = []

        # 按 category 分组对比
        categories = {}
        for item in all_items:
            cat = item[4] or "未分类"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)

        compared = 0
        for cat, items in categories.items():
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    compared += 1
                    if progress_callback:
                        progress_callback("comparing", {"total": total, "current": compared, "detail": f"正在对比 {items[i][1][:30]} ↔ {items[j][1][:30]}"})

                    item_a = {"id": items[i][0], "topic": items[i][1], "content": items[i][2], "confidence": items[i][5], "embedding": items[i][8]}
                    item_b = {"id": items[j][0], "topic": items[j][1], "content": items[j][2], "confidence": items[j][5], "embedding": items[j][8]}

                    result = detect_contradiction(item_a, item_b)
                    if result and result.get("has_contradiction"):
                        contradictions_found += 1
                        merge_content = result.get("merge_content", "")
                        if merge_content:
                            if item_a["confidence"] >= item_b["confidence"]:
                                keep_id, remove_id = item_a["id"], item_b["id"]
                                keep_conf = min(1.0, item_a["confidence"] + 0.1)
                            else:
                                keep_id, remove_id = item_b["id"], item_a["id"]
                                keep_conf = min(1.0, item_b["confidence"] + 0.1)

                            to_delete.add(remove_id)
                            combined_ids = f'矛盾解决: {result.get("description", "")}\n合并建议: {result.get("resolution", "")}'
                            to_update.append((merge_content, keep_conf, combined_ids, keep_id))
                            merged += 1

        # 执行更新和删除
        for content, conf, contradictions, item_id in to_update:
            embedding = get_embedding(content[:1000])
            embedding_str = '[' + ','.join(map(str, embedding)) + ']' if embedding else None
            cur.execute("""
                UPDATE cpa_dream_knowledge
                SET content=%s, confidence=%s, contradictions=%s, embedding=%s, dream_batch=%s, updated_at=NOW()
                WHERE id=%s
            """, (content, conf, contradictions, embedding_str, new_batch, item_id))

        for item_id in to_delete:
            cur.execute("DELETE FROM cpa_dream_knowledge WHERE id=%s", (item_id,))

        # 更新日志为done
        cur.execute("""
            UPDATE cpa_dream_log
            SET status='done', qa_processed=%s, knowledge_created=%s, contradictions_found=%s, finished_at=NOW()
            WHERE dream_batch=%s
        """, (total, merged, contradictions_found, new_batch))
        conn.commit()

        print(f"[dream] 🧠 做梦完成! 处理{total}条, 发现{contradictions_found}处矛盾, 合并{merged}条")

        if progress_callback:
            progress_callback("done", {"total": total, "contradictions": contradictions_found, "merged": merged})

        return {"total": total, "contradictions": contradictions_found, "merged": merged}

    except Exception as e:
        print(f"[dream] ❌ 做梦失败: {e}")
        import traceback
        traceback.print_exc()
        try:
            cur.execute("""
                UPDATE cpa_dream_log SET status='failed', finished_at=NOW() WHERE dream_batch=%s
            """, (new_batch,))
            conn.commit()
        except:
            pass
        if progress_callback:
            progress_callback("failed", {"error": str(e)})
        return {"error": str(e)}

    finally:
        cur.close()
        conn.close()


# ==================== 检索归档知识 ====================

def search_dream_knowledge(query, top_k=5):
    """从做梦归档知识库中检索"""
    embedding = get_embedding(query)
    if not embedding:
        return []

    query_vector = '[' + ','.join(map(str, embedding)) + ']'

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, topic, content, summary, category, confidence,
               1 - (embedding <-> %s) as similarity
        FROM cpa_dream_knowledge
        WHERE embedding IS NOT NULL
        ORDER BY embedding <-> %s
        LIMIT %s
    """, (query_vector, query_vector, top_k))

    results = []
    for row in cur.fetchall():
        similarity = float(row[6]) if row[6] else 0
        if similarity > 0.5:
            results.append({
                "content": f"【归档知识】{row[2]}",
                "source_type": "dream_knowledge",
                "source_id": row[0],
                "similarity": similarity,
                "summary": row[4] or row[3],
                "source_label": f"🧠 归档知识: {row[1] or row[3]} ({row[4] or '未分类'})",
                "metadata": {"topic": row[1], "category": row[4], "confidence": row[5]}
            })

    cur.close()
    conn.close()
    return results


def get_dream_stats():
    """获取做梦统计信息"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM cpa_dream_knowledge")
    total_knowledge = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM cpa_dream_knowledge WHERE confidence >= 0.8")
    high_conf = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(MAX(dream_batch), 0) FROM cpa_dream_log
        WHERE dream_type='manual' AND status='done'
    """)
    last_batch = cur.fetchone()[0]

    cur.execute("""
        SELECT finished_at FROM cpa_dream_log
        WHERE dream_type='manual' AND status='done' AND dream_batch=%s
    """, (last_batch,))
    row = cur.fetchone()
    last_dream_time = str(row[0]) if row else None

    cur.execute("""
        SELECT dream_type, COUNT(*) FROM cpa_dream_log GROUP BY dream_type
    """)
    log_stats = {r[0]: r[1] for r in cur.fetchall()}

    cur.close()
    conn.close()

    return {
        "total_knowledge": total_knowledge,
        "high_confidence": high_conf,
        "last_dream_time": last_dream_time,
        "last_batch": last_batch,
        "auto_count": log_stats.get("auto", 0),
        "manual_count": log_stats.get("manual", 0)
    }
