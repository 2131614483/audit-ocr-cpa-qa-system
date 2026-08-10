# ============================================================
# 审计数据仪表盘 - Web 服务
# 端口: 5000
# 功能: 审计记录可视化看板，数据统计，风险分析，记录详情查询，
#       关联知识库展示，AI 审计辅导，CPA知识库多模式检索
# API: /api/audit_data, /api/audit_record, /api/statistics,
#      /api/knowledge_base, /api/ask_ai, /api/ask_ai_stream,
#      /api/cpa_knowledge/*, /api/dream/*, /api/config/*
# ============================================================

from flask import Flask, render_template, jsonify, request, send_from_directory, Response, stream_with_context
import psycopg2
import json
import os
import requests
import jieba
import re
import uuid
import time
from datetime import datetime
from pathlib import Path
from config.settings import cfg

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _sys
if hasattr(_sys.stdout, 'reconfigure'):
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    _sys.stderr.reconfigure(encoding='utf-8', errors='replace')

app = Flask(__name__)

# 加载 jieba 中文分词词典
_dict_path = os.path.join(os.path.dirname(__file__), 'data', 'cpa_dict.txt')
if os.path.exists(_dict_path):
    jieba.load_userdict(_dict_path)
    print(f"已加载 CPA 分词词典 ({os.path.getsize(_dict_path)//1024}KB)")

# DeepSeek API配置
CONFIG_PATH = Path(__file__).parent / "data" / "model_config.json"

def load_model_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"current_provider": "deepseek", "providers": {}}

def get_deepseek_config():
    config = load_model_config()
    provider = config.get("current_provider", "deepseek")
    providers = config.get("providers", {})
    pcfg = providers.get(provider, {})
    return {
        "api_key": pcfg.get("api_key", ""),
        "api_url": pcfg.get("chat_api", "https://api.deepseek.com/v1/chat/completions"),
        "model": pcfg.get("models", {}).get("main", "deepseek-chat"),
        "reason_model": pcfg.get("models", {}).get("fix", "deepseek-chat"),
    }

DEEPSEEK_API_KEY = get_deepseek_config()["api_key"]
DEEPSEEK_API_URL = get_deepseek_config()["api_url"]
DEEPSEEK_MODEL = get_deepseek_config()["model"]

@app.route('/images/<path:filename>')
def serve_image(filename):
    image_dirs = ['input_pic', 'output']
    for dir_name in image_dirs:
        full_path = os.path.join(app.root_path, dir_name, filename)
        if os.path.exists(full_path):
            return send_from_directory(os.path.join(app.root_path, dir_name), filename)
    return "图片未找到", 404

def get_db_config():
    return {
        "host": getattr(cfg, "DB_HOST", "localhost"),
        "port": getattr(cfg, "DB_PORT", 5432),
        "dbname": getattr(cfg, "DB_NAME", "audit_ocr"),
        "user": getattr(cfg, "DB_USER", "postgres"),
        "password": getattr(cfg, "DB_PASSWORD", "admin"),
    }

def get_connection():
    try:
        return psycopg2.connect(**get_db_config())
    except Exception as e:
        print(f"数据库连接失败: {str(e)}")
        return None

def get_cpa_connection():
    try:
        return psycopg2.connect(
            host='localhost', port=5432,
            dbname='cpa_knowledge', user='postgres', password='admin'
        )
    except Exception as e:
        print(f"CPA数据库连接失败: {e}")
        return None

def get_ollama_embedding(text):
    try:
        payload = {"model": "qwen3-embedding:8b", "prompt": text.strip()}
        response = requests.post("http://localhost:11434/api/embeddings", json=payload)
        if response.status_code == 200:
            result = response.json()
            return result.get("embedding", result.get("embeddings", [None])[0])
        return None
    except Exception as e:
        print(f"获取向量失败: {e}")
        return None

def call_deepseek_api(system_prompt, user_message, context=""):
    ds = get_deepseek_config()
    api_key = ds["api_key"]
    api_url = ds["api_url"]
    model = ds["model"]
    if not api_key:
        return None
    full_context = context + "\n\n" + user_message if context else user_message
    try:
        resp = requests.post(api_url, json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_context}
            ],
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 2048
        }, headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        return None
    except Exception as e:
        print(f"DeepSeek API调用失败: {e}")
        return None

def call_deepseek_stream(system_prompt, user_message, context="", provider=None):
    if provider:
        config = load_model_config()
        providers = config.get("providers", {})
        pcfg = providers.get(provider, {})
        api_key = pcfg.get("api_key", "")
        api_url = pcfg.get("chat_api", "https://api.deepseek.com/v1/chat/completions")
        model = pcfg.get("models", {}).get("main", "deepseek-chat")
    else:
        ds = get_deepseek_config()
        api_key = ds["api_key"]
        api_url = ds["api_url"]
        model = ds["model"]
    if not api_key:
        yield f"data: {json.dumps({'type': 'error', 'content': 'API Key 未配置'})}\n\n"
        return
    full_context = context + "\n\n" + user_message if context else user_message
    try:
        resp = requests.post(api_url, json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_context}
            ],
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 2048
        }, headers={"Authorization": f"Bearer {api_key}"}, stream=True, timeout=60)
        for line in resp.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith('data: '):
                    data_str = decoded[6:]
                    if data_str == '[DONE]':
                        continue
                    try:
                        d = json.loads(data_str)
                        if 'choices' in d and len(d['choices']) > 0:
                            delta = d['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

# ============================================================
# CPA 知识库检索函数
# ============================================================

def search_knowledge_base(query, top_k=5, books=None):
    conn = get_cpa_connection()
    if not conn:
        return []
    try:
        query_embedding = get_ollama_embedding(query)
        if not query_embedding:
            return []
        query_vector_str = '[' + ','.join(map(str, query_embedding)) + ']'
        cur = conn.cursor()
        if books and len(books) > 0:
            placeholders = ','.join(['%s'] * len(books))
            sql = f"""
                SELECT e.id, e.chunk_content, e.source_type, e.source_id,
                       1 - (e.embedding <-> %s) as similarity,
                       e.chunk_summary, e.metadata
                FROM cpa_embeddings e
                WHERE e.metadata->>'book' IN ({placeholders})
                ORDER BY e.embedding <-> %s
                LIMIT %s
            """
            params = [query_vector_str] + books + [query_vector_str, top_k]
            cur.execute(sql, params)
        else:
            cur.execute("""
                SELECT e.id, e.chunk_content, e.source_type, e.source_id,
                       1 - (e.embedding <-> %s) as similarity,
                       e.chunk_summary, e.metadata
                FROM cpa_embeddings e
                ORDER BY e.embedding <-> %s
                LIMIT %s
            """, (query_vector_str, query_vector_str, top_k))
        results = []
        for row in cur.fetchall():
            meta = None
            try:
                if row[6]:
                    meta = json.loads(row[6])
            except Exception:
                pass
            source_label = ""
            if meta:
                parts = []
                if meta.get("course"): parts.append(meta["course"])
                if meta.get("book"): parts.append(meta["book"])
                if meta.get("heading_path"): parts.append(meta["heading_path"])
                source_label = " > ".join(parts)
            results.append({
                "id": row[0], "content": row[1], "source_type": row[2], "source_id": row[3],
                "similarity": float(row[4]) if row[4] else 0,
                "summary": row[5], "metadata": meta,
                "source_label": source_label or f"教材 #{row[3]}"
            })
        cur.close()
        conn.close()
        return results
    except Exception as e:
        print(f"知识库检索失败: {e}")
        if conn: conn.close()
        return []

def search_knowledge_base_bm25(query, top_k=5, books=None):
    conn = get_cpa_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        query_words = jieba.cut(query, cut_all=False)
        keywords = [w.strip() for w in query_words
                    if w.strip() and len(w.strip()) >= 2
                    and not re.match(r'^[的了吗是啥我问你给在还有就这对吧呢啊哦嗯哈呀么个只被把被让叫从到向往关于对于按照根据通过经过除了包括以及或者或者还是如果那么虽然但是因为所以然而不过却可可能可以能够会要应该必须需要]$', w.strip())]
        keywords = list(set(keywords))[:10]
        if not keywords:
            cur.close(); conn.close()
            return []
        like_clauses = " OR ".join(["e.chunk_content ILIKE %s" for _ in range(len(keywords))])
        like_params = [f"%{kw}%" for kw in keywords]
        if books and len(books) > 0:
            book_clauses = " OR ".join(["e.metadata->>'book' ILIKE %s" for _ in range(len(books))])
            book_params = [f"%{b}%" for b in books]
            cur.execute(f"""
                SELECT e.id, e.chunk_content, e.source_type, e.source_id,
                       e.chunk_summary, e.metadata
                FROM cpa_embeddings e
                WHERE ({like_clauses}) AND ({book_clauses})
                LIMIT %s
            """, like_params + book_params + [top_k * 5])
        else:
            cur.execute(f"""
                SELECT e.id, e.chunk_content, e.source_type, e.source_id,
                       e.chunk_summary, e.metadata
                FROM cpa_embeddings e
                WHERE {like_clauses}
                LIMIT %s
            """, like_params + [top_k * 5])
        rows = cur.fetchall()
        scored = []
        for row in rows:
            content = row[1] or ""
            match_count = sum(1 for kw in keywords if kw in content)
            score = match_count / len(keywords)
            scored.append((score, row))
        scored.sort(key=lambda x: -x[0])
        results = []
        for score, row in scored[:top_k]:
            meta = None
            try:
                if row[5]: meta = json.loads(row[5])
            except Exception: pass
            source_label = ""
            if meta:
                parts = []
                if meta.get("course"): parts.append(meta["course"])
                if meta.get("book"): parts.append(meta["book"])
                if meta.get("heading_path"): parts.append(meta["heading_path"])
                source_label = " > ".join(parts)
            results.append({
                "id": row[0], "content": row[1], "source_type": row[2], "source_id": row[3],
                "similarity": round(score, 4),
                "summary": row[4], "metadata": meta,
                "source_label": source_label or f"教材 #{row[3]}"
            })
        cur.close(); conn.close()
        return results
    except Exception as e:
        print(f"BM25检索失败: {e}")
        if conn: conn.close()
        return []

def search_knowledge_base_hybrid(query, top_k=5, books=None):
    vector_results = search_knowledge_base(query, top_k=top_k*2, books=books)
    bm25_results = search_knowledge_base_bm25(query, top_k=top_k*2, books=books)
    if not vector_results and not bm25_results: return []
    if not vector_results: return bm25_results[:top_k]
    if not bm25_results: return vector_results[:top_k]
    k = 60
    scores = {}
    details = {}
    for rank, r in enumerate(vector_results):
        cid = str(r.get("source_id", 0)) + r.get("content", "")[:50]
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
        details[cid] = r
    for rank, r in enumerate(bm25_results):
        cid = str(r.get("source_id", 0)) + r.get("content", "")[:50]
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
        if cid not in details: details[cid] = r
    sorted_items = sorted(scores.items(), key=lambda x: -x[1])
    results = []
    for cid, score in sorted_items[:top_k]:
        item = dict(details[cid])
        item["similarity"] = round(min(score * 30, 0.99), 4)
        results.append(item)
    return results

def search_knowledge_base_graph(query, top_k=5, books=None):
    conn = get_cpa_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        query_words = jieba.cut(query, cut_all=False)
        keywords = [w.strip() for w in query_words
                    if w.strip() and len(w.strip()) >= 2
                    and not re.match(r'^[的了吗是啥我问你]$', w.strip())]
        keywords = list(set(keywords))[:10]
        if not keywords:
            cur.close(); conn.close()
            return search_knowledge_base(query, top_k=top_k, books=books)
        like_clauses = " OR ".join(["e.name LIKE %s" for _ in range(len(keywords))])
        like_params = [f"%{kw}%" for kw in keywords]
        if books and len(books) > 0:
            book_clauses = " OR ".join(["e.description LIKE %s" for _ in range(len(books))])
            book_params = [f"%{b}%" for b in books]
            cur.execute(f"""
                SELECT e.id, e.name, e.category, e.source_chunk_ids
                FROM cpa_entities e WHERE ({like_clauses}) AND ({book_clauses})
                ORDER BY CASE e.category WHEN '章' THEN 1 WHEN '节' THEN 2 WHEN '编' THEN 3 ELSE 4 END
                LIMIT 20
            """, like_params + book_params)
        else:
            cur.execute(f"""
                SELECT e.id, e.name, e.category, e.source_chunk_ids
                FROM cpa_entities e WHERE {like_clauses}
                ORDER BY CASE e.category WHEN '章' THEN 1 WHEN '节' THEN 2 WHEN '编' THEN 3 ELSE 4 END
                LIMIT 20
            """, like_params)
        entities = cur.fetchall()
        related_chunk_ids = set()
        matched_entity_ids = set()
        for e in entities:
            eid = e[0]; matched_entity_ids.add(eid)
            if e[3]:
                for cid in e[3]: related_chunk_ids.add(cid)
        if matched_entity_ids:
            id_placeholders = ','.join(['%s'] * len(matched_entity_ids))
            cur.execute(f"""
                SELECT DISTINCT r.target_entity_id, e2.source_chunk_ids
                FROM cpa_relationships r JOIN cpa_entities e2 ON e2.id = r.target_entity_id
                WHERE r.source_entity_id IN ({id_placeholders}) LIMIT 30
            """, list(matched_entity_ids))
            for r in cur.fetchall():
                if r[1]:
                    for cid in r[1]: related_chunk_ids.add(cid)
            cur.execute(f"""
                SELECT DISTINCT r.source_entity_id, e2.source_chunk_ids
                FROM cpa_relationships r JOIN cpa_entities e2 ON e2.id = r.source_entity_id
                WHERE r.target_entity_id IN ({id_placeholders}) LIMIT 30
            """, list(matched_entity_ids))
            for r in cur.fetchall():
                if r[1]:
                    for cid in r[1]: related_chunk_ids.add(cid)
        if related_chunk_ids:
            id_list = list(related_chunk_ids)[:top_k * 3]
            id_placeholders = ','.join(['%s'] * len(id_list))
            cur.execute(f"""
                SELECT e.id, e.chunk_content, e.source_type, e.source_id,
                       0.85 as similarity, e.chunk_summary, e.metadata
                FROM cpa_embeddings e WHERE e.id IN ({id_placeholders}) LIMIT %s
            """, id_list + [top_k])
            graph_rows = cur.fetchall()
        else:
            graph_rows = []
        cur.close(); conn.close()
        if not graph_rows:
            return search_knowledge_base(query, top_k=top_k, books=books)
        results = []
        for row in graph_rows:
            meta = None
            try:
                if row[6]: meta = json.loads(row[6])
            except Exception: pass
            source_label = ""
            if meta:
                parts = []
                if meta.get("course"): parts.append(meta["course"])
                if meta.get("book"): parts.append(meta["book"])
                if meta.get("heading_path"): parts.append(meta["heading_path"])
                source_label = " > ".join(parts)
            results.append({
                "id": row[0], "content": row[1], "source_type": row[2], "source_id": row[3],
                "similarity": float(row[4]) if row[4] else 0,
                "summary": row[5], "metadata": meta,
                "source_label": source_label or f"教材 #{row[3]}"
            })
        return results[:top_k]
    except Exception as e:
        print(f"GraphRAG检索失败: {e}")
        if conn: conn.close()
        return search_knowledge_base(query, top_k=top_k, books=books)

def save_qa_history(session_id, question, answer, prompt_key="general", referenced_sources=None):
    conn = get_cpa_connection()
    if not conn:
        return False
    try:
        combined = f"问题：{question}\n答案：{answer[:500]}"
        embedding = get_ollama_embedding(combined)
        if not embedding:
            conn.close(); return False
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        ref_list = []
        if referenced_sources:
            for src in referenced_sources:
                ref_list.append({
                    "type": "textbook" if src.get("source_type") != "qa_history" else "qa_history",
                    "source_id": src.get("source_id", 0),
                    "similarity": round(src.get("similarity", 0), 4),
                    "source_label": src.get("source_label", "")
                })
        metadata = json.dumps({
            "source": "qa_history", "prompt": prompt_key,
            "question_len": len(question), "answer_len": len(answer),
            "referenced_sources": ref_list
        }, ensure_ascii=False)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO cpa_qa_history (session_id, question, answer, combined_content, embedding, metadata)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (session_id, question, answer, combined[:1000], embedding_str, metadata))
        conn.commit(); cur.close(); conn.close()
        return True
    except Exception as e:
        print(f"保存问答历史失败: {e}")
        if conn: conn.close()
        return False

def search_qa_history(query, top_k=5):
    conn = get_cpa_connection()
    if not conn:
        return []
    try:
        query_embedding = get_ollama_embedding(query)
        if not query_embedding:
            return []
        query_vector_str = '[' + ','.join(map(str, query_embedding)) + ']'
        cur = conn.cursor()
        cur.execute("""
            SELECT question, answer, combined_content,
                   1 - (embedding <-> %s) as similarity, metadata
            FROM cpa_qa_history
            ORDER BY embedding <-> %s LIMIT %s
        """, (query_vector_str, query_vector_str, top_k))
        results = []
        for row in cur.fetchall():
            meta = None
            try:
                if row[4]: meta = json.loads(row[4])
            except Exception: pass
            results.append({
                "question": row[0], "answer": row[1],
                "combined": row[2], "similarity": float(row[3]) if row[3] else 0,
                "metadata": meta
            })
        cur.close(); conn.close()
        return results
    except Exception as e:
        print(f"历史问答检索失败: {e}")
        if conn: conn.close()
        return []

# ============================================================
# 审计OCR - 原始路由
# ============================================================

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/audit_data')
def get_audit_data():
    conn = get_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, image_name, image_type, date, total_amount, relevant_party,
                   risk_rating, audit_conclusion, kb_rule_ids, audit_time,
                   invoice_code, invoice_number, tax_id, image_path, classified_save_path
            FROM audit_results ORDER BY audit_time DESC
        """)
        rows = cur.fetchall()
        data = []
        for row in rows:
            data.append({
                "id": row[0], "image_name": row[1], "image_type": row[2],
                "date": row[3], "total_amount": row[4], "relevant_party": row[5],
                "risk_rating": row[6], "audit_conclusion": row[7], "kb_rule_ids": row[8],
                "audit_time": row[9].strftime("%Y-%m-%d %H:%M:%S") if row[9] else None,
                "invoice_code": row[10], "invoice_number": row[11], "tax_id": row[12],
                "image_path": row[13], "classified_save_path": row[14]
            })
        cur.close(); conn.close()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/audit_record/<int:record_id>')
def get_audit_record(record_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, image_name, image_type, date, total_amount, relevant_party,
                   risk_rating, audit_conclusion, kb_rule_ids, audit_time,
                   invoice_code, invoice_number, tax_id, image_path, classified_save_path,
                   seal_type, seal_number, seal_clarity, joint_seal,
                   unified_social_credit_code, legal_person, valid_period,
                   asset_tag, asset_name, location, quantity, progress,
                   signer, approval_level, attachment_complete, other_info,
                   date_valid, amount_valid, code_format_valid, no_missing_field,
                   image_normal, no_duplicate, consistent_info, compliance, no_fraud,
                   risk_description, audit_reason, full_json
            FROM audit_results WHERE id = %s
        """, (record_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row:
            return jsonify({
                "id": row[0], "image_name": row[1], "image_type": row[2],
                "date": row[3], "total_amount": row[4], "relevant_party": row[5],
                "risk_rating": row[6], "audit_conclusion": row[7], "kb_rule_ids": row[8],
                "audit_time": row[9].strftime("%Y-%m-%d %H:%M:%S") if row[9] else None,
                "invoice_code": row[10], "invoice_number": row[11], "tax_id": row[12],
                "image_path": row[13], "classified_save_path": row[14],
                "seal_type": row[15], "seal_number": row[16], "seal_clarity": row[17],
                "joint_seal": row[18], "unified_social_credit_code": row[19],
                "legal_person": row[20], "valid_period": row[21],
                "asset_tag": row[22], "asset_name": row[23], "location": row[24],
                "quantity": row[25], "progress": row[26], "signer": row[27],
                "approval_level": row[28], "attachment_complete": row[29],
                "other_info": row[30],
                "date_valid": bool(row[31]) if row[31] is not None else None,
                "amount_valid": bool(row[32]) if row[32] is not None else None,
                "code_format_valid": bool(row[33]) if row[33] is not None else None,
                "no_missing_field": bool(row[34]) if row[34] is not None else None,
                "image_normal": bool(row[35]) if row[35] is not None else None,
                "no_duplicate": bool(row[36]) if row[36] is not None else None,
                "consistent_info": bool(row[37]) if row[37] is not None else None,
                "compliance": bool(row[38]) if row[38] is not None else None,
                "no_fraud": bool(row[39]) if row[39] is not None else None,
                "risk_description": row[40], "audit_reason": row[41], "full_json": row[42]
            })
        else:
            return jsonify({"error": "记录不存在"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/knowledge_base/<int:kb_id>')
def get_knowledge_base(kb_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, category, rule_id, rule_name, content, risk_level, created_at
            FROM knowledge_base WHERE id = %s
        """, (kb_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row:
            return jsonify({
                "id": row[0], "category": row[1], "rule_id": row[2],
                "rule_name": row[3], "content": row[4], "risk_level": row[5],
                "created_at": row[6].strftime("%Y-%m-%d %H:%M:%S") if row[6] else None
            })
        else:
            return jsonify({"error": "知识库记录不存在"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/knowledge_base/batch')
def get_knowledge_base_batch():
    kb_ids = request.args.get('ids', '')
    if not kb_ids:
        return jsonify([])
    ids_list = [int(x.strip()) for x in kb_ids.split(',') if x.strip().isdigit()]
    if not ids_list:
        return jsonify([])
    conn = get_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(ids_list))
        cur.execute(f"""
            SELECT id, category, rule_id, rule_name, content, risk_level, created_at
            FROM knowledge_base WHERE id IN ({placeholders})
        """, tuple(ids_list))
        rows = cur.fetchall()
        cur.close(); conn.close()
        data = []
        for row in rows:
            data.append({
                "id": row[0], "category": row[1], "rule_id": row[2],
                "rule_name": row[3], "content": row[4], "risk_level": row[5],
                "created_at": row[6].strftime("%Y-%m-%d %H:%M:%S") if row[6] else None
            })
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/statistics')
def get_statistics():
    conn = get_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM audit_results")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM audit_results WHERE audit_conclusion = '通过'")
        passed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM audit_results WHERE audit_conclusion = '不通过'")
        failed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM audit_results WHERE audit_conclusion = '人工复核'")
        manual = cur.fetchone()[0]
        cur.execute("SELECT risk_rating, COUNT(*) FROM audit_results GROUP BY risk_rating")
        risk_dist = {r[0]: r[1] for r in cur.fetchall()}
        cur.execute("SELECT image_type, COUNT(*) FROM audit_results GROUP BY image_type ORDER BY COUNT(*) DESC LIMIT 5")
        type_dist = [{"type": r[0], "count": r[1]} for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM knowledge_base")
        kb_count = cur.fetchone()[0]
        cur.close(); conn.close()
        return jsonify({
            "total_records": total, "passed_count": passed,
            "failed_count": failed, "manual_count": manual,
            "risk_distribution": risk_dist, "type_distribution": type_dist,
            "knowledge_base_count": kb_count
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/all_knowledge_base')
def get_all_knowledge_base():
    conn = get_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, category, rule_id, rule_name, content, risk_level, created_at FROM knowledge_base ORDER BY category, rule_id")
        rows = cur.fetchall()
        cur.close(); conn.close()
        data = []
        for row in rows:
            data.append({
                "id": row[0], "category": row[1], "rule_id": row[2],
                "rule_name": row[3], "content": row[4], "risk_level": row[5],
                "created_at": row[6].strftime("%Y-%m-%d %H:%M:%S") if row[6] else None
            })
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# CPA 知识库 - 页面路由
# ============================================================

@app.route('/knowledge_base')
def knowledge_base():
    return render_template('knowledge_base.html')

@app.route('/kb_browser')
def kb_browser():
    return render_template('kb_browser.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

@app.route('/settings')
def settings_page():
    return render_template('settings.html')

# ============================================================
# CPA 知识库 - 搜索 API
# ============================================================

@app.route('/api/cpa_knowledge/search', methods=['POST'])
def cpa_knowledge_search():
    data = request.json or {}
    query = data.get('query', '')
    mode = data.get('mode', 'vector')
    top_k = data.get('top_k', 10)
    books = data.get('books')
    if not query:
        return jsonify({"error": "查询内容为空"}), 400
    mode_map = {
        'vector': search_knowledge_base,
        'bm25': search_knowledge_base_bm25,
        'hybrid': search_knowledge_base_hybrid,
        'graph': search_knowledge_base_graph,
    }
    search_func = mode_map.get(mode, search_knowledge_base)
    results = search_func(query, top_k=top_k, books=books if books else None)
    return jsonify({"results": results, "mode": mode, "total": len(results)})

# ============================================================
# CPA 知识库 - 浏览/管理 API
# ============================================================

@app.route('/api/cpa_knowledge/list', methods=['POST'])
def cpa_kb_list():
    data = request.json or {}
    page = data.get('page', 1)
    page_size = data.get('page_size', 20)
    search = data.get('search', '')
    source_id = data.get('source_id')
    conn = get_cpa_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        conditions = []
        params = []
        if search:
            conditions.append("chunk_content ILIKE %s")
            params.append(f'%{search}%')
        if source_id:
            conditions.append("source_id = %s")
            params.append(int(source_id))
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        cur.execute(f"SELECT COUNT(*) FROM cpa_embeddings WHERE {where_clause}", params)
        total = cur.fetchone()[0]
        offset = (page - 1) * page_size
        cur.execute(f"""
            SELECT id, source_type, source_id, LEFT(chunk_content, 200) as content_preview,
                   LENGTH(chunk_content) as content_len, created_at
            FROM cpa_embeddings WHERE {where_clause}
            ORDER BY id DESC LIMIT %s OFFSET %s
        """, params + [page_size, offset])
        items = []
        for row in cur.fetchall():
            items.append({
                "id": row[0], "source_type": row[1], "source_id": row[2],
                "content_preview": row[3], "content_len": row[4],
                "created_at": str(row[5]) if row[5] else ""
            })
        cur.close(); conn.close()
        return jsonify({
            "items": items, "total": total, "page": page,
            "page_size": page_size, "total_pages": (total + page_size - 1) // page_size
        })
    except Exception as e:
        print(f"查询知识库失败: {e}")
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/cpa_knowledge/detail', methods=['POST'])
def cpa_kb_detail():
    data = request.json
    item_id = data.get('id')
    if not item_id:
        return jsonify({"error": "缺少ID"}), 400
    conn = get_cpa_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, source_type, source_id, chunk_content, chunk_summary,
                   metadata, created_at
            FROM cpa_embeddings WHERE id = %s
        """, (item_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            return jsonify({"error": "记录不存在"}), 404
        meta = None
        try:
            if row[5]: meta = json.loads(row[5])
        except Exception: pass
        return jsonify({
            "id": row[0], "source_type": row[1], "source_id": row[2],
            "content": row[3], "summary": row[4], "metadata": meta,
            "created_at": str(row[6]) if row[6] else ""
        })
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/cpa_knowledge/delete', methods=['POST'])
def cpa_kb_delete():
    data = request.json
    item_id = data.get('id')
    if not item_id:
        return jsonify({"error": "缺少ID"}), 400
    conn = get_cpa_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM cpa_embeddings WHERE id = %s", (item_id,))
        deleted = cur.rowcount
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "deleted": deleted})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/cpa_knowledge/stats', methods=['GET'])
def cpa_kb_stats():
    conn = get_cpa_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cpa_embeddings")
        total_chunks = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cpa_entities")
        entity_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cpa_relationships")
        relation_count = cur.fetchone()[0]
        cur.execute("SELECT source_type, COUNT(*) FROM cpa_embeddings GROUP BY source_type")
        type_stats = {r[0]: r[1] for r in cur.fetchall()}
        cur.execute("SELECT category, COUNT(*) FROM cpa_entities GROUP BY category ORDER BY COUNT(*) DESC")
        category_stats = {r[0]: r[1] for r in cur.fetchall()}
        cur.close(); conn.close()
        return jsonify({
            "success": True, "total_chunks": total_chunks,
            "entity_count": entity_count, "relation_count": relation_count,
            "type_stats": type_stats, "category_stats": category_stats
        })
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

# ============================================================
# CPA 知识库 - 教材列表
# ============================================================

@app.route('/api/cpa_knowledge/books', methods=['GET'])
def cpa_kb_books():
    conn = get_cpa_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT metadata->>'book' as book_name
            FROM cpa_embeddings
            WHERE metadata->>'book' IS NOT NULL
            ORDER BY book_name
        """)
        books = [r[0] for r in cur.fetchall()]
        cur.close(); conn.close()
        return jsonify({"success": True, "books": books})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

# ============================================================
# 历史问答 API
# ============================================================

@app.route('/api/cpa_qa_history/list', methods=['POST'])
def cpa_qa_history_list():
    data = request.json or {}
    page = data.get('page', 1)
    page_size = data.get('page_size', 20)
    search = data.get('search', '')
    conn = get_cpa_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        conditions = []
        params = []
        if search:
            conditions.append("(question ILIKE %s OR answer ILIKE %s)")
            params.extend([f'%{search}%', f'%{search}%'])
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        cur.execute(f"SELECT COUNT(*) FROM cpa_qa_history WHERE {where_clause}", params)
        total = cur.fetchone()[0]
        offset = (page - 1) * page_size
        cur.execute(f"""
            SELECT id, session_id, LEFT(question, 100) as question_preview,
                   LEFT(answer, 200) as answer_preview, created_at
            FROM cpa_qa_history WHERE {where_clause}
            ORDER BY id DESC LIMIT %s OFFSET %s
        """, params + [page_size, offset])
        items = []
        for row in cur.fetchall():
            items.append({
                "id": row[0], "session_id": row[1],
                "question_preview": row[2], "answer_preview": row[3],
                "created_at": str(row[4]) if row[4] else ""
            })
        cur.close(); conn.close()
        return jsonify({
            "items": items, "total": total, "page": page,
            "page_size": page_size, "total_pages": (total + page_size - 1) // page_size
        })
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/cpa_qa_history/detail', methods=['POST'])
def cpa_qa_history_detail():
    data = request.json
    item_id = data.get('id')
    if not item_id:
        return jsonify({"error": "缺少ID"}), 400
    conn = get_cpa_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, session_id, question, answer, metadata, created_at
            FROM cpa_qa_history WHERE id = %s
        """, (item_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            return jsonify({"error": "记录不存在"}), 404
        meta = None
        try:
            if row[4]: meta = json.loads(row[4])
        except Exception: pass
        return jsonify({
            "id": row[0], "session_id": row[1],
            "question": row[2], "answer": row[3],
            "metadata": meta,
            "created_at": str(row[5]) if row[5] else ""
        })
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/cpa_qa_history/delete', methods=['POST'])
def cpa_qa_history_delete():
    data = request.json
    item_id = data.get('id')
    if not item_id:
        return jsonify({"error": "缺少ID"}), 400
    conn = get_cpa_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM cpa_qa_history WHERE id = %s", (item_id,))
        deleted = cur.rowcount
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "deleted": deleted})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

# ============================================================
# 做梦知识 API
# ============================================================

@app.route('/api/dream/start', methods=['POST'])
def dream_start():
    try:
        import threading
        from services.dream_service import run_dream_consolidation
        thread = threading.Thread(target=run_dream_consolidation, daemon=True)
        thread.start()
        return jsonify({"success": True, "message": "做梦已开始，请稍后查看状态"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/dream/status', methods=['GET'])
def dream_status():
    try:
        conn = get_cpa_connection()
        if not conn:
            return jsonify({"error": "数据库连接失败"}), 500
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cpa_dream_knowledge")
        total = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(MAX(dream_batch), 0) FROM cpa_dream_knowledge")
        batch = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cpa_dream_knowledge WHERE created_at >= NOW() - INTERVAL '1 hour'")
        recent = cur.fetchone()[0]
        cur.close(); conn.close()
        return jsonify({
            "success": True, "total_knowledge": total,
            "current_batch": batch, "recent_count": recent,
            "is_running": False
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/dream/knowledge/list', methods=['POST'])
def dream_knowledge_list():
    data = request.json or {}
    page = data.get('page', 1)
    page_size = data.get('page_size', 20)
    search = data.get('search', '')
    category = data.get('category', '')
    conn = get_cpa_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        conditions = []
        params = []
        if search:
            conditions.append("(topic ILIKE %s OR content ILIKE %s OR summary ILIKE %s)")
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        if category:
            conditions.append("category = %s")
            params.append(category)
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        cur.execute(f"SELECT COUNT(*) FROM cpa_dream_knowledge WHERE {where_clause}", params)
        total = cur.fetchone()[0]
        offset = (page - 1) * page_size
        cur.execute(f"""
            SELECT id, topic, LEFT(content, 200) as content_preview, summary,
                   category, confidence, dream_batch, created_at
            FROM cpa_dream_knowledge WHERE {where_clause}
            ORDER BY id DESC LIMIT %s OFFSET %s
        """, params + [page_size, offset])
        items = []
        for row in cur.fetchall():
            items.append({
                "id": row[0], "topic": row[1], "content_preview": row[2],
                "summary": row[3], "category": row[4], "confidence": float(row[5]) if row[5] else 0,
                "dream_batch": row[6],
                "created_at": str(row[7]) if row[7] else ""
            })
        cur.close(); conn.close()
        return jsonify({
            "items": items, "total": total, "page": page,
            "page_size": page_size, "total_pages": (total + page_size - 1) // page_size
        })
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/dream/knowledge/categories', methods=['GET'])
def dream_knowledge_categories():
    conn = get_cpa_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT category FROM cpa_dream_knowledge WHERE category IS NOT NULL AND category != '' ORDER BY category")
        categories = [r[0] for r in cur.fetchall()]
        cur.close(); conn.close()
        return jsonify({"success": True, "categories": categories})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/dream/knowledge/detail', methods=['POST'])
def dream_knowledge_detail():
    data = request.json
    item_id = data.get('id')
    if not item_id:
        return jsonify({"error": "缺少ID"}), 400
    conn = get_cpa_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, topic, content, summary, category, confidence,
                   contradiction_ids, dream_batch, source_session, created_at, updated_at
            FROM cpa_dream_knowledge WHERE id = %s
        """, (item_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            return jsonify({"error": "记录不存在"}), 404
        return jsonify({
            "id": row[0], "topic": row[1], "content": row[2],
            "summary": row[3], "category": row[4],
            "confidence": float(row[5]) if row[5] else 0,
            "contradiction_ids": row[6], "dream_batch": row[7],
            "source_session": row[8],
            "created_at": str(row[9]) if row[9] else "",
            "updated_at": str(row[10]) if row[10] else ""
        })
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/dream/knowledge/delete', methods=['POST'])
def dream_knowledge_delete():
    data = request.json
    item_id = data.get('id')
    if not item_id:
        return jsonify({"error": "缺少ID"}), 400
    conn = get_cpa_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM cpa_dream_knowledge WHERE id = %s", (item_id,))
        deleted = cur.rowcount
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "deleted": deleted})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

# ============================================================
# 配置 API
# ============================================================

@app.route('/api/config/get', methods=['GET'])
def api_config_get():
    config = load_model_config()
    return jsonify({"success": True, "config": config})

@app.route('/api/config/save', methods=['POST'])
def api_config_save():
    try:
        data = request.json
        if not data or "config" not in data:
            return jsonify({"success": False, "error": "无效的配置数据"}), 400
        new_config = data["config"]
        if "providers" not in new_config:
            return jsonify({"success": False, "error": "缺少 providers 字段"}), 400
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(new_config, f, ensure_ascii=False, indent=2)
        global DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL
        ds = get_deepseek_config()
        DEEPSEEK_API_KEY = ds["api_key"]
        DEEPSEEK_API_URL = ds["api_url"]
        DEEPSEEK_MODEL = ds["model"]
        return jsonify({"success": True, "message": "配置已保存"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================
# 审计 AI 辅导
# ============================================================

@app.route('/api/ask_ai', methods=['POST'])
def ask_ai():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "请求数据为空"}), 400
        search_mode = data.get('search_mode', 'vector')
        record_id = data.get('id', '')
        image_type = data.get('image_type', '未知')
        risk_rating = data.get('risk_rating', '未知')
        audit_conclusion = data.get('audit_conclusion', '未知')
        risk_description = data.get('risk_description', '')
        audit_reason = data.get('audit_reason', '')
        total_amount = data.get('total_amount', '')
        relevant_party = data.get('relevant_party', '')
        date = data.get('date', '')
        kb_rules_text = data.get('kb_rules_text', '')

        query_parts = []
        if risk_description: query_parts.append(risk_description)
        if audit_reason: query_parts.append(audit_reason)
        if image_type and image_type != '未知': query_parts.append(f"{image_type} 审计")
        query = "；".join(query_parts) if query_parts else f"{image_type} 审计风险 辅导"

        mode_map = {
            'vector': search_knowledge_base,
            'bm25': search_knowledge_base_bm25,
            'hybrid': search_knowledge_base_hybrid,
            'graph': search_knowledge_base_graph,
        }
        search_func = mode_map.get(search_mode, search_knowledge_base)
        kb_results = search_func(query, top_k=5)

        cpa_context = ""
        if kb_results:
            cpa_context = "以下是从CPA教材知识库中检索到的相关内容：\n\n"
            for i, r in enumerate(kb_results, 1):
                source = r.get("source_label", f"来源 #{r.get('source_id', '')}")
                content = r.get("content", "")
                similarity = r.get("similarity", 0)
                cpa_context += f"[{i}] {source} (相似度: {similarity:.2f})\n{content[:500]}\n\n"

        audit_context = f"""
=== 审计记录详情 ===
记录ID: {record_id}
票据类型: {image_type}
风险评级: {risk_rating}
审计结论: {audit_conclusion}
总金额: {total_amount}
相关方: {relevant_party}
日期: {date}
"""
        if risk_description: audit_context += f"风险说明: {risk_description}\n"
        if audit_reason: audit_context += f"审计说明: {audit_reason}\n"
        if kb_rules_text: audit_context += f"\n关联知识库规则:\n{kb_rules_text[:1000]}\n"

        full_context = audit_context
        if cpa_context: full_context += f"\n\n{cpa_context}"

        tutor_prompt = """你是一名经验丰富的注册会计师(CPA)考试辅导专家，精通审计实务、会计准则和风险管理。
请基于以下审计记录详情和CPA教材知识库内容，提供专业的审计辅导分析。

请从以下几个方面进行分析：
1. **风险分析**：分析该票据/凭证存在的关键风险点
2. **知识链接**：结合CPA教材知识库，解释相关的审计准则或会计处理原则
3. **审计建议**：给出具体的审计程序建议和注意事项
4. **学习指引**：指出CPA考试中与该审计场景相关的知识点和章节

请用专业但易懂的语言，结构清晰地进行回答。"""

        answer = call_deepseek_api(tutor_prompt, "请根据以上审计记录和知识库内容，提供专业的审计辅导分析。", context=full_context)

        if not answer:
            return jsonify({"error": "AI生成回答失败"}), 500

        try:
            save_qa_history(f"audit_{record_id}", query or f"{image_type}审计辅导", answer, prompt_key="audit_tutor", referenced_sources=kb_results)
        except Exception as e:
            print(f"保存审计问答历史失败: {e}")

        return jsonify({
            "success": True, "answer": answer,
            "cpa_referenced": [{
                "source_label": r.get("source_label", ""),
                "similarity": r.get("similarity", 0),
                "content_preview": r.get("content", "")[:500]
            } for r in kb_results] if kb_results else []
        })
    except Exception as e:
        print(f"审计AI辅导失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ask_ai_stream', methods=['POST'])
def ask_ai_stream():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "请求数据为空"}), 400
        search_mode = data.get('search_mode', 'vector')
        model_provider = data.get('model_provider', '')
        user_question = data.get('user_question', '').strip()
        record_id = data.get('id', '')
        image_type = data.get('image_type', '未知')
        risk_rating = data.get('risk_rating', '未知')
        audit_conclusion = data.get('audit_conclusion', '未知')
        risk_description = data.get('risk_description', '')
        audit_reason = data.get('audit_reason', '')
        total_amount = data.get('total_amount', '')
        relevant_party = data.get('relevant_party', '')
        date = data.get('date', '')
        kb_rules_text = data.get('kb_rules_text', '')

        query_parts = []
        if risk_description: query_parts.append(risk_description)
        if audit_reason: query_parts.append(audit_reason)
        if image_type and image_type != '未知': query_parts.append(f"{image_type} 审计")
        query = "；".join(query_parts) if query_parts else f"{image_type} 审计风险 辅导"

        mode_map = {
            'vector': search_knowledge_base,
            'bm25': search_knowledge_base_bm25,
            'hybrid': search_knowledge_base_hybrid,
            'graph': search_knowledge_base_graph,
        }
        search_func = mode_map.get(search_mode, search_knowledge_base)
        kb_results = search_func(query, top_k=5)

        cpa_context = ""
        if kb_results:
            cpa_context = "以下是从CPA教材知识库中检索到的相关内容：\n\n"
            for i, r in enumerate(kb_results, 1):
                source = r.get("source_label", f"来源 #{r.get('source_id', '')}")
                content = r.get("content", "")
                similarity = r.get("similarity", 0)
                cpa_context += f"[{i}] {source} (相似度: {similarity:.2f})\n{content[:500]}\n\n"

        audit_context = f"""
=== 审计记录详情 ===
记录ID: {record_id}
票据类型: {image_type}
风险评级: {risk_rating}
审计结论: {audit_conclusion}
总金额: {total_amount}
相关方: {relevant_party}
日期: {date}
"""
        if risk_description: audit_context += f"风险说明: {risk_description}\n"
        if audit_reason: audit_context += f"审计说明: {audit_reason}\n"
        if kb_rules_text: audit_context += f"\n关联知识库规则:\n{kb_rules_text[:1000]}\n"

        full_context = audit_context
        if cpa_context: full_context += f"\n\n{cpa_context}"

        cpa_meta = []
        if kb_results:
            cpa_meta = [{
                "source_label": r.get("source_label", ""),
                "similarity": r.get("similarity", 0),
                "content_preview": r.get("content", "")[:500]
            } for r in kb_results]

        def generate():
            yield f"data: {json.dumps({'type': 'meta', 'cpa_referenced': cpa_meta})}\n\n"
            if user_question:
                tutor_prompt = """你是一名经验丰富的注册会计师(CPA)考试辅导专家，精通审计实务、会计准则和风险管理。
请基于以下审计记录详情和CPA教材知识库内容，回答用户的问题。

请结合审计记录中的具体情况进行专业分析，引用CPA教材中的相关知识。"""
                user_msg = f"用户问题：{user_question}\n\n请根据以上审计记录和知识库内容回答。"
            else:
                tutor_prompt = """你是一名经验丰富的注册会计师(CPA)考试辅导专家，精通审计实务、会计准则和风险管理。
请基于以下审计记录详情和CPA教材知识库内容，提供专业的审计辅导分析。

请从以下几个方面进行分析：
1. **风险分析**：分析该票据/凭证存在的关键风险点
2. **知识链接**：结合CPA教材知识库，解释相关的审计准则或会计处理原则
3. **审计建议**：给出具体的审计程序建议和注意事项
4. **学习指引**：指出CPA考试中与该审计场景相关的知识点和章节

请用专业但易懂的语言，结构清晰地进行回答。"""
                user_msg = "请根据以上审计记录和知识库内容，提供专业的审计辅导分析。"
            full_answer_parts = []
            for chunk in call_deepseek_stream(tutor_prompt, user_msg, context=full_context, provider=model_provider if model_provider else None):
                if chunk:
                    if chunk.startswith('data:') and '"content"' in chunk:
                        try:
                            chk_data = json.loads(chunk[6:])
                            if chk_data.get('type') == 'content':
                                full_answer_parts.append(chk_data.get('content', ''))
                        except:
                            pass
                    yield chunk
            full_answer = ''.join(full_answer_parts)
            if full_answer:
                try:
                    save_qa_history(f"audit_stream_{record_id}", query or user_question or f"{image_type}审计辅导", full_answer, prompt_key="audit_tutor_stream", referenced_sources=kb_results)
                except Exception as e:
                    print(f"保存流式审计问答历史失败: {e}")
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    except Exception as e:
        def error_gen():
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return Response(stream_with_context(error_gen()), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)