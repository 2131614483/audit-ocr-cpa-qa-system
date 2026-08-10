# ============================================================
# CPA 知识库问答系统 - Web服务
# 版本: 20260514
# 最后更新: 2026-05-14
# 功能: Flask + Socket.IO Web服务，流式回答，知识库管理
# ============================================================

from flask import Flask, render_template, request, jsonify, send_from_directory, Response, stream_with_context
from flask_socketio import SocketIO, emit
import os
import json
import time
import uuid
import requests
import psycopg2
import numpy as np
from datetime import datetime
from pathlib import Path
from services.dream_service import save_dream_knowledge, search_dream_knowledge, run_dream_consolidation, get_dream_stats
from services.agent_service import list_agents, get_agent, create_agent, update_agent, delete_agent
from services.team_service import list_teams, get_team, create_team, update_team, delete_team
from services.orchestrator import run_team, run_team_stream
import jieba
import re
from config.settings import cfg

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _sys
if hasattr(_sys.stdout, 'reconfigure'):
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    _sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 加载 jieba 中文分词词典
_dict_path = os.path.join(os.path.dirname(__file__), 'data', 'cpa_dict.txt')
if os.path.exists(_dict_path):
    jieba.load_userdict(_dict_path)
    print(f"📖 已加载 CPA 分词词典 ({os.path.getsize(_dict_path)//1024}KB)")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cpa_qa_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# 创建上传目录
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'files'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'images'), exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")

# 知识图谱 Blueprint（独立 cpa_knowledge_graph 库）—— 统一入口注册
# 若图谱库/模块不可用则跳过，不影响其余功能
try:
    from blueprints.kg_api import kg_bp, register_kg_routes
    app.register_blueprint(kg_bp)
    register_kg_routes(app)
    print("✅ 知识图谱 Blueprint 已注册 → /api/kg/*, /kg/explorer")
except Exception as _kg_err:
    print(f"⚠️ 知识图谱模块跳过注册: {_kg_err}")

# DeepSeek API配置 - 从 model_config.json 读取
CONFIG_PATH = Path(__file__).parent / "data" / "model_config.json"
PROMPTS_PATH = Path(__file__).parent / "data" / "prompts_config.json"
SYSTEM_CONFIG_PATH = Path(__file__).parent / "data" / "config.json"

def load_model_config():
    """加载模型配置"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"current_provider": "deepseek", "providers": {}}

def get_deepseek_config():
    """获取当前使用的DeepSeek配置（provider 用于区分 Ollama/OpenAI 兼容格式）"""
    config = load_model_config()
    provider = config.get("current_provider", "deepseek")
    providers = config.get("providers", {})
    pcfg = providers.get(provider, {})
    return {
        "provider": provider,
        "api_key": pcfg.get("api_key", ""),
        "api_url": pcfg.get("chat_api", "https://api.deepseek.com/v1/chat/completions"),
        "model": pcfg.get("models", {}).get("main", "deepseek-chat"),
        "reason_model": pcfg.get("models", {}).get("fix", "deepseek-chat"),
    }

# 兼容旧代码的全局变量（从配置加载）
_model_config = get_deepseek_config()
DEEPSEEK_API_KEY = _model_config["api_key"]
DEEPSEEK_API_URL = _model_config["api_url"]
DEEPSEEK_MODEL = _model_config["model"]
DEEPSEEK_REASON_MODEL = _model_config["reason_model"]

# 默认提示词 - 从 prompts_config.json 加载
DEFAULT_PROMPTS = {}
SKILLS = []

def load_prompts_config():
    """加载提示词和Skills配置"""
    global DEFAULT_PROMPTS, SKILLS
    if PROMPTS_PATH.exists():
        try:
            with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            DEFAULT_PROMPTS = data.get("prompts", {})
            SKILLS = data.get("skills", [])
            return
        except Exception as e:
            print(f"加载 prompts_config.json 失败: {e}")
    # 默认值
    DEFAULT_PROMPTS = {
        "accounting": {
            "name": "会计",
            "prompt": "你是一名专业的注册会计师考试《会计》科目辅导专家。请根据提供的知识库内容回答问题，重点围绕会计准则、财务报表、收入确认、长期股权投资、合并报表等会计专业知识。回答要准确、详细，并引用相关知识点。",
            "desc": "会计准则与财务报表"
        },
        "auditing": {
            "name": "审计",
            "prompt": "你是一名专业的注册会计师考试《审计》科目辅导专家。精通审计准则、审计程序、审计证据、审计报告等专业知识。请根据知识库内容提供专业的审计相关回答。",
            "desc": "审计准则与实务"
        },
        "tax": {
            "name": "税法",
            "prompt": "你是一名专业的注册会计师考试《税法》科目辅导专家。熟悉中国税法法规、增值税、企业所得税、个人所得税、税收优惠等专业知识。请提供准确的税务咨询和法规解释。",
            "desc": "中国税法法规"
        },
        "economic_law": {
            "name": "经济法",
            "prompt": "你是一名专业的注册会计师考试《经济法》科目辅导专家。精通公司法、证券法、合同法、破产法、物权法等经济法律法规。请根据知识库内容提供专业的经济法相关回答。",
            "desc": "公司/合同/证券法"
        },
        "financial_management": {
            "name": "财管",
            "prompt": "你是一名专业的注册会计师考试《财务成本管理》科目辅导专家。擅长财务管理、成本计算、资本预算、财务分析、价值评估等专业知识。请根据知识库内容提供专业的财管相关回答。",
            "desc": "财务成本管理"
        },
        "strategy": {
            "name": "战略",
            "prompt": "你是一名专业的注册会计师考试《公司战略与风险管理》科目辅导专家。精通战略分析、战略选择、风险管理、内部控制等专业知识。请根据知识库内容提供专业的战略相关回答。",
            "desc": "战略与风险管理"
        },
        "general": {
            "name": "综合",
            "prompt": "你是一名综合性的CPA考试全科辅导专家，擅长解答会计、审计、税法、经济法、财务成本管理、公司战略与风险管理等全部科目的问题。能够跨科目综合分析，帮助考生建立完整的知识体系。",
            "desc": "全科综合辅导"
        }
    }
    SKILLS = [
        {"id": "knowledge_search", "name": "知识库检索", "description": "从CPA教材知识库中检索相关内容"},
        {"id": "qa_history_search", "name": "历史问答检索", "description": "从历史对话中检索相关问题"},
        {"id": "calculator", "name": "计算器", "description": "进行数学计算"},
        {"id": "file_analysis", "name": "文件分析", "description": "分析上传的文件内容"},
        {"id": "image_analysis", "name": "图片分析", "description": "分析上传的图片"}
    ]

load_prompts_config()

# 存储会话数据
sessions = {}

def load_session(session_id):
    """加载或创建会话"""
    if session_id not in sessions:
        sessions[session_id] = {
            "history": [],
            "pinned_context": [],  # 用户选定作为上下文的对话
            "context": "",
            "selected_prompt": "general",
            "enabled_skills": ["knowledge_search"],
            "uploaded_files": [],
            "uploaded_images": []
        }
    return sessions[session_id]

def get_db_connection():
    """获取数据库连接"""
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            dbname='cpa_knowledge',
            user='postgres',
            password='admin'
        )
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def get_ollama_embedding(text):
    """调用Ollama获取向量"""
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

def search_knowledge_base(query, top_k=5, books=None):
    """从知识库检索相关内容，books参数为教材名列表，None表示全部"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        # 获取查询向量
        query_embedding = get_ollama_embedding(query)
        if not query_embedding:
            return []
        
        # 将向量转换为pgvector格式字符串
        query_vector_str = '[' + ','.join(map(str, query_embedding)) + ']'
        
        cur = conn.cursor()
        
        # 使用余弦相似度检索，同时获取 metadata 和摘要
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
                    meta = json.loads(row[6]) if isinstance(row[6], str) else row[6]
            except Exception:
                pass
            
            # 构建可读的来源信息
            source_label = ""
            if meta:
                parts = []
                if meta.get("course"):
                    parts.append(meta["course"])
                if meta.get("book"):
                    parts.append(meta["book"])
                if meta.get("heading_path"):
                    parts.append(meta["heading_path"])
                source_label = " > ".join(parts)
            
            results.append({
                "id": row[0],
                "content": row[1],
                "source_type": row[2],
                "source_id": row[3],
                "similarity": float(row[4]) if row[4] else 0,
                "summary": row[5],
                "metadata": meta,
                "source_label": source_label or f"教材 #{row[3]}"
            })
        
        cur.close()
        conn.close()
        return results
    
    except Exception as e:
        print(f"知识库检索失败: {e}")
        if conn:
            conn.close()
        return []


# ============================================================
# 多模式检索：BM25全文检索 / 混合检索 / GraphRAG
# ============================================================

def search_knowledge_base_bm25(query, top_k=5, books=None):
    """BM25全文检索：jieba 中文分词 + ILIKE 模糊匹配 + 按关键词匹配数评分"""
    conn = get_db_connection()
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
                if row[5]: meta = json.loads(row[5]) if isinstance(row[5], str) else row[5]
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
    """混合检索：向量检索 + BM25 通过RRF融合"""
    vector_results = search_knowledge_base(query, top_k=top_k*2, books=books)
    bm25_results = search_knowledge_base_bm25(query, top_k=top_k*2, books=books)

    if not vector_results and not bm25_results:
        return []
    if not vector_results:
        return bm25_results[:top_k]
    if not bm25_results:
        return vector_results[:top_k]

    # RRF融合：score = 1 / (k + rank)
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
        if cid not in details:
            details[cid] = r

    sorted_items = sorted(scores.items(), key=lambda x: -x[1])
    results = []
    for cid, score in sorted_items[:top_k]:
        item = dict(details[cid])
        item["similarity"] = round(min(score * 30, 0.99), 4)
        results.append(item)
    return results


def search_knowledge_base_graph(query, top_k=5, books=None):
    """GraphRAG检索：利用结构化知识图谱（章节树）+ 实体关系扩散"""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()

        # 1. 用 jieba 分词提取查询中的关键词
        query_words = jieba.cut(query, cut_all=False)
        keywords = [w.strip() for w in query_words
                    if w.strip() and len(w.strip()) >= 2
                    and not re.match(r'^[的了吗是啥我问你]$', w.strip())]
        keywords = list(set(keywords))[:10]

        if not keywords:
            cur.close()
            conn.close()
            return search_knowledge_base(query, top_k=top_k, books=books)

        # 2. 在实体表中搜索匹配的实体
        like_clauses = " OR ".join(["e.name LIKE %s" for _ in range(len(keywords))])
        like_params = [f"%{kw}%" for kw in keywords]

        # 如果有教材筛选
        if books and len(books) > 0:
            book_clauses = " OR ".join(["e.description LIKE %s" for _ in range(len(books))])
            book_params = [f"%{b}%" for b in books]
            cur.execute(f"""
                SELECT e.id, e.name, e.category, e.source_chunk_ids
                FROM cpa_entities e
                WHERE ({like_clauses})
                  AND ({book_clauses})
                ORDER BY
                    CASE e.category
                        WHEN '章' THEN 1
                        WHEN '节' THEN 2
                        WHEN '编' THEN 3
                        ELSE 4
                    END
                LIMIT 20
            """, like_params + book_params)
        else:
            cur.execute(f"""
                SELECT e.id, e.name, e.category, e.source_chunk_ids
                FROM cpa_entities e
                WHERE {like_clauses}
                ORDER BY
                    CASE e.category
                        WHEN '章' THEN 1
                        WHEN '节' THEN 2
                        WHEN '编' THEN 3
                        ELSE 4
                    END
                LIMIT 20
            """, like_params)

        entities = cur.fetchall()

        # 3. 收集所有相关 chunk_id
        related_chunk_ids = set()
        matched_entity_ids = set()

        for e in entities:
            eid = e[0]
            matched_entity_ids.add(eid)
            if e[3]:  # source_chunk_ids
                for cid in e[3]:
                    related_chunk_ids.add(cid)

        # 4. 通过关系扩散：找关联实体的 chunk
        if matched_entity_ids:
            id_placeholders = ','.join(['%s'] * len(matched_entity_ids))
            # 找下游实体
            cur.execute(f"""
                SELECT DISTINCT r.target_entity_id, e2.source_chunk_ids
                FROM cpa_relationships r
                JOIN cpa_entities e2 ON e2.id = r.target_entity_id
                WHERE r.source_entity_id IN ({id_placeholders})
                LIMIT 30
            """, list(matched_entity_ids))
            for r in cur.fetchall():
                if r[1]:
                    for cid in r[1]:
                        related_chunk_ids.add(cid)

            # 找上游实体
            cur.execute(f"""
                SELECT DISTINCT r.source_entity_id, e2.source_chunk_ids
                FROM cpa_relationships r
                JOIN cpa_entities e2 ON e2.id = r.source_entity_id
                WHERE r.target_entity_id IN ({id_placeholders})
                LIMIT 30
            """, list(matched_entity_ids))
            for r in cur.fetchall():
                if r[1]:
                    for cid in r[1]:
                        related_chunk_ids.add(cid)

        # 5. 用收集到的 chunk_id 去 cpa_embeddings 查内容
        if related_chunk_ids:
            id_list = list(related_chunk_ids)[:top_k * 3]
            id_placeholders = ','.join(['%s'] * len(id_list))
            cur.execute(f"""
                SELECT e.id, e.chunk_content, e.source_type, e.source_id,
                       0.85 as similarity, e.chunk_summary, e.metadata
                FROM cpa_embeddings e
                WHERE e.id IN ({id_placeholders})
                LIMIT %s
            """, id_list + [top_k])
            graph_rows = cur.fetchall()
        else:
            graph_rows = []

        cur.close()
        conn.close()

        # 6. 如果结构化图谱没有结果，回退到向量检索
        if not graph_rows:
            return search_knowledge_base(query, top_k=top_k, books=books)

        results = []
        for row in graph_rows:
            meta = None
            try:
                if row[6]:
                    meta = json.loads(row[6]) if isinstance(row[6], str) else row[6]
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
                "id": row[0],
                "content": row[1],
                "source_type": row[2],
                "source_id": row[3],
                "similarity": float(row[4]) if row[4] else 0,
                "summary": row[5],
                "metadata": meta,
                "source_label": source_label or f"教材 #{row[3]}"
            })
        return results[:top_k]

    except Exception as e:
        print(f"GraphRAG检索失败: {e}")
        if conn: conn.close()
        return search_knowledge_base(query, top_k=top_k, books=books)


def save_qa_history(session_id, question, answer, prompt_key="general", referenced_sources=None):
    """将问答对保存到历史问答表并生成向量"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        # 拼接问题和答案用于向量化
        combined = f"问题：{question}\n答案：{answer[:500]}"
        
        # 生成向量
        embedding = get_ollama_embedding(combined)
        if not embedding:
            print("❌ 生成问答向量失败")
            conn.close()
            return False
        
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        # 收集引用来源信息
        ref_list = []
        if referenced_sources:
            for src in referenced_sources:
                ref_list.append({
                    "type": "textbook" if src.get("source_type") != "qa_history" else "qa_history",
                    "source_id": src.get("source_id", 0),
                    "similarity": round(src.get("similarity", 0), 4),
                    "source_label": src.get("source_label", "")
                })
        
        # 元数据
        metadata = json.dumps({
            "source": "qa_history",
            "prompt": prompt_key,
            "question_len": len(question),
            "answer_len": len(answer),
            "referenced_sources": ref_list
        }, ensure_ascii=False)
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO cpa_qa_history (session_id, question, answer, combined_content, embedding, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (session_id, question, answer, combined, embedding_str, metadata))
        qa_id = cur.fetchone()[0]
        
        conn.commit()
        cur.close()
        conn.close()
        
        return qa_id
    
    except Exception as e:
        print(f"保存问答历史失败: {e}")
        if conn:
            conn.close()
        return None


def _update_qa_answer(qa_id, question, answer):
    """流式完成后更新问答记录的完整回答"""
    combined = f"问题：{question}\n答案：{answer[:500]}"
    embedding = get_ollama_embedding(combined)
    if not embedding:
        return
    embedding_str = '[' + ','.join(map(str, embedding)) + ']'
    conn = get_db_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("UPDATE cpa_qa_history SET answer=%s, combined_content=%s, embedding=%s WHERE id=%s",
                    (answer, combined, embedding_str, qa_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"更新问答答案失败: {e}")
        if conn:
            conn.close()


def search_qa_history(query, top_k=5):
    """从历史问答中检索相关内容"""
    conn = get_db_connection()
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
                   1 - (embedding <-> %s) as similarity,
                   created_at
            FROM cpa_qa_history
            ORDER BY embedding <-> %s
            LIMIT %s
        """, (query_vector_str, query_vector_str, top_k))
        
        results = []
        for row in cur.fetchall():
            results.append({
                "content": f"问题：{row[0]}\n答案：{row[1]}",
                "question": row[0],
                "answer": row[1],
                "source_type": "qa_history",
                "source_id": 0,
                "similarity": float(row[3]) if row[3] else 0,
                "created_at": str(row[4]) if row[4] else ""
            })
        
        cur.close()
        conn.close()
        return results
    
    except Exception as e:
        print(f"历史问答检索失败: {e}")
        if conn:
            conn.close()
        return []

def call_deepseek_api(prompt, question, context="", use_reason=False, history=None):
    """调用DeepSeek API生成回答（从配置动态读取，兼容Ollama格式）"""
    try:
        cfg = get_deepseek_config()
        provider = cfg["provider"]
        api_key = cfg["api_key"]
        api_url = cfg["api_url"]
        model = cfg["reason_model"] if use_reason else cfg["model"]

        messages = [
            {"role": "system", "content": prompt},
        ]

        # 插入对话历史（实现上下文召回）
        if history:
            messages.extend(history)

        # 添加上下文（知识库检索结果）
        if context:
            messages.append({"role": "user", "content": f"上下文信息：\n{context}"})

        # 添加问题
        messages.append({"role": "user", "content": question})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        response = requests.post(api_url, json=payload, headers=headers, timeout=120)

        if response.status_code == 200:
            result = response.json()
            # Ollama 返回 message.content；OpenAI 兼容返回 choices[0].message.content
            if provider == "ollama":
                return result.get('message', {}).get('content', '')
            return result['choices'][0]['message']['content']
        else:
            print(f"DeepSeek API错误: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"调用DeepSeek API失败: {e}")
        return None

def call_deepseek_stream(prompt, question, context="", use_reason=False, history=None):
    """流式调用DeepSeek API生成回答（从配置动态读取，兼容Ollama NDJSON格式）"""
    try:
        cfg = get_deepseek_config()
        provider = cfg["provider"]
        api_key = cfg["api_key"]
        api_url = cfg["api_url"]
        model = cfg["reason_model"] if use_reason else cfg["model"]

        messages = [
            {"role": "system", "content": prompt},
        ]
        
        # 插入对话历史（实现上下文召回）
        if history:
            messages.extend(history)
        
        # 添加上下文（知识库检索结果）
        if context:
            messages.append({"role": "user", "content": f"上下文信息：\n{context}"})
        
        # 添加问题
        messages.append({"role": "user", "content": question})
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4000,
            "stream": True
        }

        if provider == "ollama":
            answer = call_deepseek_api(prompt, question, context, use_reason, history)
            if answer:
                yield "data: " + json.dumps({"choices": [{"delta": {"content": answer}}]}) + "\n\n"
            else:
                yield None
            return

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 本地大模型生成慢，超时放宽；云端保持默认
        timeout = 300 if provider == "ollama" else 30

        response = requests.post(api_url, json=payload, headers=headers, stream=True, timeout=timeout)
        
        if response.status_code == 200:
            for chunk in response.iter_content(chunk_size=None):
                if chunk:
                    yield chunk.decode('utf-8')
        else:
            print(f"DeepSeek API错误: {response.status_code} - {response.text}")
            yield None
    
    except Exception as e:
        print(f"调用DeepSeek API失败: {e}")
        yield None

@app.route('/')
def index():
    return render_template('index.html', 
                         prompts=DEFAULT_PROMPTS, 
                         skills=SKILLS)

@app.route('/upload/file', methods=['POST'])
def upload_file():
    """上传文件"""
    session_id = request.form.get('session_id', str(uuid.uuid4()))
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file:
        filename = f"{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'files', filename)
        file.save(filepath)
        
        session = load_session(session_id)
        session['uploaded_files'].append({
            "name": file.filename,
            "path": filepath,
            "size": os.path.getsize(filepath),
            "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return jsonify({
            "success": True,
            "message": f"文件 {file.filename} 上传成功",
            "session_id": session_id,
            "files": session['uploaded_files']
        })
    
    return jsonify({"error": "上传失败"}), 500

@app.route('/upload/image', methods=['POST'])
def upload_image():
    """上传图片"""
    session_id = request.form.get('session_id', str(uuid.uuid4()))
    
    if 'image' not in request.files:
        return jsonify({"error": "No image part"}), 400
    
    image = request.files['image']
    if image.filename == '':
        return jsonify({"error": "No selected image"}), 400
    
    if image:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        ext = image.filename.rsplit('.', 1)[1].lower() if '.' in image.filename else ''
        
        if ext not in allowed_extensions:
            return jsonify({"error": "不支持的图片格式"}), 400
        
        filename = f"{uuid.uuid4()}_{image.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'images', filename)
        image.save(filepath)
        
        session = load_session(session_id)
        session['uploaded_images'].append({
            "name": image.filename,
            "path": filepath,
            "url": f"/uploads/images/{filename}",
            "size": os.path.getsize(filepath),
            "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return jsonify({
            "success": True,
            "message": f"图片 {image.filename} 上传成功",
            "session_id": session_id,
            "images": session['uploaded_images'],
            "url": f"/uploads/images/{filename}"
        })
    
    return jsonify({"error": "上传失败"}), 500

@app.route('/uploads/<folder>/<filename>')
def uploaded_file(folder, filename):
    """提供上传文件的访问"""
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], folder), filename)

@app.route('/api/set_context', methods=['POST'])
def set_context():
    """设置上下文"""
    data = request.json
    session_id = data.get('session_id', str(uuid.uuid4()))
    context = data.get('context', '')
    
    session = load_session(session_id)
    session['context'] = context
    
    return jsonify({"success": True, "session_id": session_id})

@app.route('/api/set_prompt', methods=['POST'])
def set_prompt():
    """设置默认提示词"""
    data = request.json
    session_id = data.get('session_id', str(uuid.uuid4()))
    prompt_key = data.get('prompt_key', 'general')
    
    session = load_session(session_id)
    session['selected_prompt'] = prompt_key
    
    return jsonify({
        "success": True, 
        "session_id": session_id,
        "prompt": DEFAULT_PROMPTS.get(prompt_key, DEFAULT_PROMPTS['general'])
    })

@app.route('/api/toggle_skill', methods=['POST'])
def toggle_skill():
    """切换Skill状态"""
    data = request.json
    session_id = data.get('session_id', str(uuid.uuid4()))
    skill_id = data.get('skill_id')
    
    session = load_session(session_id)
    
    if skill_id in session['enabled_skills']:
        session['enabled_skills'].remove(skill_id)
        enabled = False
    else:
        session['enabled_skills'].append(skill_id)
        enabled = True
    
    return jsonify({
        "success": True, 
        "session_id": session_id,
        "skill_id": skill_id,
        "enabled": enabled,
        "enabled_skills": session['enabled_skills']
    })

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    """清除对话历史"""
    data = request.json
    session_id = data.get('session_id')
    
    if session_id in sessions:
        sessions[session_id]['history'] = []
        sessions[session_id]['pinned_context'] = []
    
    return jsonify({"success": True})

@app.route('/api/pin_message', methods=['POST'])
def pin_message():
    """将消息固定为上下文"""
    data = request.json
    session_id = data.get('session_id', str(uuid.uuid4()))
    role = data.get('role', '')
    content = data.get('content', '')
    
    if not role or not content:
        return jsonify({"error": "缺少消息内容"}), 400
    
    session = load_session(session_id)
    
    # 避免重复固定
    for msg in session['pinned_context']:
        if msg['role'] == role and msg['content'] == content:
            return jsonify({"success": True, "pinned": session['pinned_context']})
    
    session['pinned_context'].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({"success": True, "pinned": session['pinned_context']})

@app.route('/api/unpin_message', methods=['POST'])
def unpin_message():
    """取消固定消息"""
    data = request.json
    session_id = data.get('session_id', str(uuid.uuid4()))
    index = data.get('index', -1)
    
    if index < 0:
        return jsonify({"error": "无效的索引"}), 400
    
    session = load_session(session_id)
    
    if index < len(session['pinned_context']):
        session['pinned_context'].pop(index)
    
    return jsonify({"success": True, "pinned": session['pinned_context']})

@app.route('/api/unpin_message_by_content', methods=['POST'])
def unpin_message_by_content():
    """按内容取消固定消息"""
    data = request.json
    session_id = data.get('session_id', str(uuid.uuid4()))
    role = data.get('role', '')
    content = data.get('content', '')
    
    if not role or not content:
        return jsonify({"error": "缺少消息内容"}), 400
    
    session = load_session(session_id)
    
    for i, msg in enumerate(session['pinned_context']):
        if msg['role'] == role and msg['content'] == content:
            session['pinned_context'].pop(i)
            break
    
    return jsonify({"success": True, "pinned": session['pinned_context']})

@app.route('/api/get_pinned_context', methods=['POST'])
def get_pinned_context():
    """获取选定的上下文集"""
    data = request.json
    session_id = data.get('session_id', str(uuid.uuid4()))
    
    session = load_session(session_id)
    
    return jsonify({"success": True, "pinned": session['pinned_context']})

@app.route('/api/get_session', methods=['POST'])
def get_session():
    """获取会话状态"""
    data = request.json
    session_id = data.get('session_id', str(uuid.uuid4()))
    
    session = load_session(session_id)
    
    return jsonify({
        "session_id": session_id,
        "history": session['history'],
        "pinned_context": session['pinned_context'],
        "context": session['context'],
        "selected_prompt": session['selected_prompt'],
        "enabled_skills": session['enabled_skills'],
        "uploaded_files": session['uploaded_files'],
        "uploaded_images": session['uploaded_images']
    })

@socketio.on('ask_question')
def handle_question(data):
    """处理问题"""
    session_id = data.get('session_id', str(uuid.uuid4()))
    question = data.get('question', '')
    use_reason = data.get('use_reason', False)
    selected_books = data.get('selected_books', [])
    search_mode = data.get('search_mode', 'vector')  # vector / bm25 / hybrid / graph
    
    session = load_session(session_id)
    
    # 添加用户问题到历史
    session['history'].append({
        "role": "user",
        "content": question,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # 发送打字状态
    emit('typing', {'status': True})
    
    try:
        # 获取系统提示词
        system_prompt = DEFAULT_PROMPTS.get(session['selected_prompt'], DEFAULT_PROMPTS['general'])['prompt']
        
        # 构建上下文（包含知识库检索结果和历史问答）
        context_parts = []
        search_results = []
        
        # 如果启用了知识库检索
        if 'knowledge_search' in session['enabled_skills']:
            # 根据检索模式选择对应函数
            mode_map = {
                'vector': search_knowledge_base,
                'bm25': search_knowledge_base_bm25,
                'hybrid': search_knowledge_base_hybrid,
                'graph': search_knowledge_base_graph,
            }
            search_func = mode_map.get(search_mode, search_knowledge_base)
            search_results = search_func(question, top_k=10, books=selected_books if selected_books else None)
            print(f"📚 教材知识库检索结果 ({search_mode}): {len(search_results) if search_results else 0}")
            if search_results:
                # 按相似度从大到小排序
                search_results.sort(key=lambda x: x['similarity'], reverse=True)
                context_parts.append("教材知识库检索结果：")
                for i, result in enumerate(search_results, 1):
                    context_parts.append(f"{i}. {result['content'][:500]}...")
        else:
            print("❌ 教材知识库检索技能未启用")
        
        # 如果启用了历史问答检索
        qa_results = []
        if 'qa_history_search' in session['enabled_skills']:
            qa_results = search_qa_history(question, top_k=5)
            print(f"📋 历史问答检索结果: {len(qa_results)}")
            if qa_results:
                context_parts.append("历史相关问答：")
                for i, result in enumerate(qa_results, 1):
                    context_parts.append(f"{i}. {result['content'][:500]}...")
        
        # 检索做梦归档知识库
        dream_results = []
        try:
            dream_results = search_dream_knowledge(question, top_k=5)
            if dream_results:
                print(f"🧠 做梦归档知识检索结果: {len(dream_results)}")
                context_parts.append("归档知识库检索结果：")
                for i, result in enumerate(dream_results, 1):
                    context_parts.append(f"{i}. {result['content'][:500]}...")
        except Exception as e:
            print(f"⚠️ 归档知识检索失败: {e}")
        
        # 合并所有检索结果（教材知识库 + 历史问答 + 归档知识）
        all_search_results = (search_results or []) + (qa_results or []) + (dream_results or [])
        
        # 添加自定义上下文
        if session['context']:
            context_parts.append(f"自定义上下文：{session['context']}")
        
        full_context = "\n\n".join(context_parts) if context_parts else ""
        
        # 发送知识库检索结果（用于展示）
        emit('knowledge_results', {
            "session_id": session_id,
            "results": all_search_results,
            "search_mode": search_mode,
            "knowledge_base": search_results or [],
            "qa_history": qa_results or [],
            "dream_knowledge": dream_results or []
        })
        
        # 从 session 中获取用户选定的上下文（pinned 的消息）
        # 只有用户手动固定的消息才会传给 DeepSeek
        conv_history = []
        for msg in session['pinned_context']:
            conv_history.append({
                "role": msg['role'],
                "content": msg['content']
            })
        
        # 流式调用DeepSeek API生成回答
        full_answer = ""
        thinking_process = ""
        
        for chunk in call_deepseek_stream(system_prompt, question, full_context, use_reason, history=conv_history):
            if chunk is None:
                continue
            
            try:
                # 解析流式响应
                lines = chunk.strip().split('\n')
                for line in lines:
                    if line.startswith('data:'):
                        json_str = line[5:].strip()
                        if json_str == '[DONE]':
                            continue
                        try:
                            import json
                            data_chunk = json.loads(json_str)
                            if data_chunk.get('choices'):
                                delta = data_chunk['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                full_answer += content
                                
                                # 如果是reason模型，提取思考过程
                                if use_reason and 'thought' in delta:
                                    thinking_process += delta.get('thought', '')
                                
                                # 发送流式回答片段
                                emit('stream_answer', {
                                    "session_id": session_id,
                                    "content": content,
                                    "thinking": delta.get('thought', '') if use_reason else ""
                                })
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"解析流式响应失败: {e}")
                continue
        
        # 如果流式调用失败，使用普通调用
        if not full_answer:
            full_answer = call_deepseek_api(system_prompt, question, full_context, use_reason, history=conv_history)
            if not full_answer:
                full_answer = f"抱歉，暂时无法回答您的问题「{question}」。请稍后重试。"
            # 发送完整回答
            emit('stream_answer', {
                "session_id": session_id,
                "content": full_answer,
                "thinking": "",
                "finished": True
            })
        
    except Exception as e:
        print(f"处理问题失败: {e}")
        full_answer = f"处理问题时发生错误：{str(e)}"
        emit('stream_answer', {
            "session_id": session_id,
            "content": full_answer,
            "thinking": "",
            "finished": True
        })
    
    # 停止打字状态
    emit('typing', {'status': False})
    
    # 保存问答对到历史问答表（作为第二知识库）
    if full_answer and not full_answer.startswith("处理问题"):
        try:
            save_qa_history(session_id, question, full_answer, session.get('selected_prompt', 'general'), all_search_results)
        except Exception as e:
            print(f"保存问答历史失败: {e}")
    
    # 添加完整回答到历史
    session['history'].append({
        "role": "assistant",
        "content": full_answer,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sources": ["CPA 知识库"]
    })
    
    # 发送完成信号（包含知识库检索结果）
    emit('answer_finished', {
        "session_id": session_id,
        "answer": full_answer,
        "sources": ["CPA 知识库"],
        "knowledge_results": all_search_results,
        "knowledge_base": search_results or [],
        "qa_history": qa_results or [],
        "dream_knowledge": dream_results or [],
        "search_mode": search_mode,
        "history": session['history']
    })

# ========== 知识库管理 API ==========

@app.route('/admin')
def admin_page():
    """知识库管理页面"""
    return render_template('admin.html')

@app.route('/api/knowledge_base/list', methods=['POST'])
def kb_list():
    """获取教材知识库列表"""
    data = request.json or {}
    page = data.get('page', 1)
    page_size = data.get('page_size', 20)
    search = data.get('search', '')
    source_id = data.get('source_id')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    
    try:
        cur = conn.cursor()
        
        # 构建查询条件
        conditions = []
        params = []
        if search:
            conditions.append("chunk_content ILIKE %s")
            params.append(f'%{search}%')
        if source_id:
            conditions.append("source_id = %s")
            params.append(int(source_id))
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # 查询总数
        cur.execute(f"SELECT COUNT(*) FROM cpa_embeddings WHERE {where_clause}", params)
        total = cur.fetchone()[0]
        
        # 查询列表
        offset = (page - 1) * page_size
        cur.execute(f"""
            SELECT id, source_type, source_id, chunk_content as content_preview,
                   LENGTH(chunk_content) as content_len, created_at
            FROM cpa_embeddings 
            WHERE {where_clause}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """, params + [page_size, offset])
        
        items = []
        for row in cur.fetchall():
            items.append({
                "id": row[0],
                "source_type": row[1],
                "source_id": row[2],
                "content_preview": row[3],
                "content_len": row[4],
                "created_at": str(row[5]) if row[5] else ""
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })
    
    except Exception as e:
        print(f"查询知识库失败: {e}")
        if conn:
            conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/knowledge_base/delete', methods=['POST'])
def kb_delete():
    """删除教材知识库条目"""
    data = request.json
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({"error": "请选择要删除的条目"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    
    try:
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(ids))
        cur.execute(f"DELETE FROM cpa_embeddings WHERE id IN ({placeholders})", ids)
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True, "deleted": deleted, "message": f"已删除 {deleted} 条记录"})
    
    except Exception as e:
        print(f"删除知识库失败: {e}")
        if conn:
            conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/knowledge_base/detail', methods=['POST'])
def kb_detail():
    """获取知识库条目详情"""
    data = request.json
    item_id = data.get('id')
    
    if not item_id:
        return jsonify({"error": "缺少ID"}), 400
    
    conn = get_db_connection()
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
        cur.close()
        conn.close()
        
        if not row:
            return jsonify({"error": "记录不存在"}), 404
        
        return jsonify({
            "id": row[0],
            "source_type": row[1],
            "source_id": row[2],
            "content": row[3],
            "summary": row[4],
            "metadata": row[5],
            "created_at": str(row[6]) if row[6] else ""
        })
    
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/knowledge_base/browse', methods=['POST'])
def kb_browse():
    """按指定模式浏览/检索知识库"""
    data = request.json or {}
    query = data.get('query', '').strip()
    mode = data.get('mode', 'vector')
    top_k = data.get('top_k', 20)
    books = data.get('books')

    if not query:
        return jsonify({"error": "请输入搜索内容"}), 400

    mode_map = {
        'vector': search_knowledge_base,
        'bm25': search_knowledge_base_bm25,
        'hybrid': search_knowledge_base_hybrid,
        'graph': search_knowledge_base_graph,
    }
    search_func = mode_map.get(mode, search_knowledge_base)
    results = search_func(query, top_k=top_k, books=books)

    mode_labels = {
        'vector': '向量检索',
        'bm25': '全文检索',
        'hybrid': '混合检索',
        'graph': '知识图谱'
    }

    return jsonify({
        "success": True,
        "mode": mode,
        "mode_label": mode_labels.get(mode, mode),
        "query": query,
        "results": results or []
    })

@app.route('/kb-browser')
def kb_browser_page():
    """知识库浏览器（4种检索模式）"""
    return render_template('kb_browser.html')

@app.route('/kb_browser')
def kb_browser_underscore():
    return render_template('kb_browser.html')

@app.route('/knowledge_base')
def knowledge_base_page():
    return render_template('knowledge_base.html')

@app.route('/api/qa_history/list', methods=['POST'])
def qa_history_list():
    """获取历史问答列表"""
    data = request.json or {}
    page = data.get('page', 1)
    page_size = data.get('page_size', 20)
    search = data.get('search', '')
    
    conn = get_db_connection()
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
                   LEFT(answer, 100) as answer_preview, created_at
            FROM cpa_qa_history 
            WHERE {where_clause}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """, params + [page_size, offset])
        
        items = []
        for row in cur.fetchall():
            items.append({
                "id": row[0],
                "session_id": row[1],
                "question_preview": row[2],
                "answer_preview": row[3],
                "created_at": str(row[4]) if row[4] else ""
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })
    
    except Exception as e:
        print(f"查询历史问答失败: {e}")
        if conn:
            conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/qa_history/delete', methods=['POST'])
def qa_history_delete():
    """删除历史问答条目"""
    data = request.json
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({"error": "请选择要删除的条目"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    
    try:
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(ids))
        cur.execute(f"DELETE FROM cpa_qa_history WHERE id IN ({placeholders})", ids)
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True, "deleted": deleted, "message": f"已删除 {deleted} 条记录"})
    
    except Exception as e:
        print(f"删除历史问答失败: {e}")
        if conn:
            conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/qa_history/detail', methods=['POST'])
def qa_history_detail():
    """获取历史问答详情"""
    data = request.json
    item_id = data.get('id')
    
    if not item_id:
        return jsonify({"error": "缺少ID"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, session_id, question, answer, combined_content, metadata, created_at
            FROM cpa_qa_history WHERE id = %s
        """, (item_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not row:
            return jsonify({"error": "记录不存在"}), 404
        
        return jsonify({
            "id": row[0],
            "session_id": row[1],
            "question": row[2],
            "answer": row[3],
            "combined": row[4],
            "metadata": row[5],
            "created_at": str(row[6]) if row[6] else ""
        })
    
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def stats():
    """获取知识库统计"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    
    try:
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM cpa_embeddings")
        kb_total = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM cpa_qa_history")
        qa_total = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM cpa_books")
        book_total = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM cpa_chapters")
        chapter_total = cur.fetchone()[0]
        
        # 各类型分布 - 按教材名分组（metadata中的book字段）
        cur.execute("""
            SELECT COALESCE(metadata->>'book', source_type) as book_name, COUNT(*) as cnt 
            FROM cpa_embeddings 
            GROUP BY book_name 
            ORDER BY cnt DESC
            LIMIT 30
        """)
        type_dist = [{"type": r[0], "count": r[1]} for r in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        return jsonify({
            "kb_total": kb_total,
            "qa_total": qa_total,
            "book_total": book_total,
            "chapter_total": chapter_total,
            "type_distribution": type_dist
        })
    
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({"error": str(e)}), 500


@app.route('/api/books/list', methods=['GET'])
def books_list():
    """获取教材列表"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, book_name, book_type FROM cpa_books ORDER BY id")
        books = [{"id": r[0], "name": r[1], "type": r[2]} for r in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify({"success": True, "books": books})
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({"error": str(e)}), 500


# ============================================================
# GraphRAG 知识图谱 API
# ============================================================
@app.route('/api/graph/build', methods=['POST'])
def graph_build():
    """从知识库提取实体并构建知识图谱"""
    try:
        data = request.json or {}
        limit = data.get('limit', 200)  # 默认处理200条
        offset = data.get('offset', 0)

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "数据库连接失败"}), 500

        cur = conn.cursor()
        # 获取chunk数据
        cur.execute("""
            SELECT id, chunk_content, chunk_summary, metadata
            FROM cpa_embeddings
            ORDER BY id
            LIMIT %s OFFSET %s
        """, (limit, offset))
        rows = cur.fetchall()

        if not rows:
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "没有更多数据需要处理", "count": 0})

        # 用LLM提取实体和关系
        import requests as http_req
        import json

        # 加载API配置
        config_path = os.path.join(os.path.dirname(__file__), 'data', 'model_config.json')
        api_key = ""
        api_url = "https://api.deepseek.com/v1/chat/completions"
        model = "deepseek-chat"
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            provider = cfg.get("current_provider", "deepseek")
            pcfg = cfg.get("providers", {}).get(provider, {})
            api_key = pcfg.get("api_key", "")
            api_url = pcfg.get("chat_api", api_url)
            model = pcfg.get("models", {}).get("main", model)

        entity_count = 0
        relation_count = 0

        for row in rows:
            chunk_id = row[0]
            content = row[1]
            summary = row[2] or content[:200]

            # 用LLM提取实体
            if not api_key:
                continue

            prompt = f"""从以下CPA教材内容中提取关键实体和它们之间的关系。
要求：
1. 实体：提取重要的概念、术语、方法名称（如"审计风险"、"存货监盘"等）
2. 关系：提取实体之间的关系（如"包含"、"定义"、"举例"等）
3. 每个实体用简短描述说明

内容：{content[:1500]}

以JSON格式输出，格式如下：
{{
  "entities": [{{"name": "实体名", "category": "类别", "description": "描述"}}],
  "relationships": [{{"source": "实体名1", "target": "实体名2", "type": "关系类型", "description": "关系描述"}}]
}}

只输出JSON，不要其他文字。"""

            try:
                resp = http_req.post(api_url, json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 2000,
                }, headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }, timeout=30)

                if resp.status_code == 200:
                    result_text = resp.json()["choices"][0]["message"]["content"]
                    # 提取JSON
                    json_start = result_text.find('{')
                    json_end = result_text.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        parsed = json.loads(result_text[json_start:json_end])
                        entities = parsed.get("entities", [])
                        relationships = parsed.get("relationships", [])

                        # 保存实体
                        for ent in entities:
                            name = ent.get("name", "").strip()
                            if not name or len(name) < 2:
                                continue
                            category = ent.get("category", "")
                            description = ent.get("description", "")

                            # 检查是否已存在
                            cur.execute("SELECT id, source_chunk_ids FROM cpa_entities WHERE name=%s", (name,))
                            existing = cur.fetchone()
                            if existing:
                                eid = existing[0]
                                existing_ids = existing[1] or []
                                if chunk_id not in existing_ids:
                                    new_ids = existing_ids + [chunk_id]
                                    cur.execute("UPDATE cpa_entities SET source_chunk_ids=%s WHERE id=%s", (new_ids, eid))
                            else:
                                cur.execute("""
                                    INSERT INTO cpa_entities (name, category, description, source_chunk_ids)
                                    VALUES (%s, %s, %s, %s)
                                """, (name, category, description, [chunk_id]))
                                entity_count += 1

                        # 保存关系
                        for rel in relationships:
                            source_name = rel.get("source", "").strip()
                            target_name = rel.get("target", "").strip()
                            rel_type = rel.get("type", "related")
                            rel_desc = rel.get("description", "")

                            if not source_name or not target_name:
                                continue

                            # 找source和target的ID
                            cur.execute("SELECT id FROM cpa_entities WHERE name=%s", (source_name,))
                            src_row = cur.fetchone()
                            cur.execute("SELECT id FROM cpa_entities WHERE name=%s", (target_name,))
                            tgt_row = cur.fetchone()

                            if src_row and tgt_row:
                                src_id = src_row[0]
                                tgt_id = tgt_row[0]
                                # 检查是否已存在
                                cur.execute("""
                                    SELECT id FROM cpa_relationships
                                    WHERE source_entity_id=%s AND target_entity_id=%s AND relation_type=%s
                                """, (src_id, tgt_id, rel_type))
                                if not cur.fetchone():
                                    cur.execute("""
                                        INSERT INTO cpa_relationships (source_entity_id, target_entity_id, relation_type, description)
                                        VALUES (%s, %s, %s, %s)
                                    """, (src_id, tgt_id, rel_type, rel_desc))
                                    relation_count += 1

            except Exception as e:
                print(f"[GraphRAG] 处理chunk {chunk_id} 失败: {e}")
                continue

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"处理完成，新增 {entity_count} 个实体，{relation_count} 条关系",
            "entity_count": entity_count,
            "relation_count": relation_count,
            "processed": len(rows)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/graph/stats', methods=['GET'])
def graph_stats():
    """获取知识图谱统计信息"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cpa_entities")
        entity_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cpa_relationships")
        relation_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT category) FROM cpa_entities")
        category_count = cur.fetchone()[0]
        # 按类别统计
        cur.execute("SELECT category, COUNT(*) FROM cpa_entities GROUP BY category ORDER BY COUNT(*) DESC")
        category_stats = {r[0]: r[1] for r in cur.fetchall()}
        cur.close()
        conn.close()
        return jsonify({
            "success": True,
            "entity_count": entity_count,
            "relation_count": relation_count,
            "category_count": category_count,
            "category_stats": category_stats
        })
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500


# ============================================================
# 做梦知识 API
# 功能: 手动触发做梦、查看状态、管理归档知识
# ============================================================
@app.route('/api/dream/start', methods=['POST'])
def dream_start():
    """手动触发做梦：矛盾检测 + 去重合并"""
    try:
        def progress_callback(stage, data):
            print(f"[dream] {stage}: {data}")

        import threading
        thread = threading.Thread(target=run_dream_consolidation, args=(progress_callback,), daemon=True)
        thread.start()

        return jsonify({"success": True, "message": "做梦已开始，请稍后查看状态"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/dream/status', methods=['GET'])
def dream_status():
    """获取做梦状态和统计"""
    try:
        # 检查是否有正在运行的做梦
        conn = psycopg2.connect(host='localhost', port=5432, dbname='cpa_knowledge', user='postgres', password='admin')
        cur = conn.cursor()
        cur.execute("SELECT status FROM cpa_dream_log ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        is_running = row and row[0] == 'running'
        cur.close()
        conn.close()

        stats = get_dream_stats()
        stats["is_running"] = is_running
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/dream/knowledge/categories', methods=['GET'])
def dream_knowledge_categories():
    """获取归档知识分类列表"""
    try:
        conn = psycopg2.connect(host='localhost', port=5432, dbname='cpa_knowledge', user='postgres', password='admin')
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT category FROM cpa_dream_knowledge WHERE category IS NOT NULL AND category != '' ORDER BY category")
        categories = [r[0] for r in cur.fetchall()]
        cur.close(); conn.close()
        return jsonify({"categories": categories})
    except Exception as e:
        return jsonify({"categories": []})

@app.route('/api/dream/knowledge/list', methods=['POST'])
def dream_knowledge_list():
    """获取归档知识列表"""
    data = request.json or {}
    page = data.get('page', 1)
    page_size = data.get('page_size', 20)
    search = data.get('search', '')
    category = data.get('category', '')

    conn = psycopg2.connect(host='localhost', port=5432, dbname='cpa_knowledge', user='postgres', password='admin')
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
        SELECT id, topic, LEFT(content, 200) as content_preview, summary, category, confidence,
               dream_batch, created_at
        FROM cpa_dream_knowledge
        WHERE {where_clause}
        ORDER BY confidence DESC, id DESC
        LIMIT %s OFFSET %s
    """, params + [page_size, offset])

    items = []
    for row in cur.fetchall():
        items.append({
            "id": row[0], "topic": row[1], "content_preview": row[2],
            "summary": row[3], "category": row[4], "confidence": float(row[5]) if row[5] else 0,
            "dream_batch": row[6], "created_at": str(row[7]) if row[7] else ""
        })

    # 获取分类列表
    cur.execute("SELECT DISTINCT category FROM cpa_dream_knowledge WHERE category IS NOT NULL AND category != '' ORDER BY category")

    cur.close()
    conn.close()

    return jsonify({
        "items": items, "total": total, "page": page, "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    })

@app.route('/api/dream/knowledge/detail', methods=['POST'])
def dream_knowledge_detail():
    """获取归档知识详情"""
    data = request.json
    item_id = data.get('id')
    if not item_id:
        return jsonify({"error": "缺少ID"}), 400

    conn = psycopg2.connect(host='localhost', port=5432, dbname='cpa_knowledge', user='postgres', password='admin')
    cur = conn.cursor()
    cur.execute("""
        SELECT id, topic, content, summary, category, confidence, source_session_id,
               source_qa_ids, contradictions, dream_batch, created_at, updated_at
        FROM cpa_dream_knowledge WHERE id = %s
    """, (item_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "记录不存在"}), 404

    return jsonify({
        "id": row[0], "topic": row[1], "content": row[2], "summary": row[3],
        "category": row[4], "confidence": float(row[5]) if row[5] else 0,
        "source_session": row[6], "source_session_id": row[6],
        "source_qa_ids": row[7],
        "contradiction_ids": row[8], "contradictions": row[8],
        "dream_batch": row[9],
        "created_at": str(row[10]) if row[10] else "",
        "updated_at": str(row[11]) if row[11] else ""
    })

@app.route('/api/dream/knowledge/delete', methods=['POST'])
def dream_knowledge_delete():
    """删除归档知识"""
    data = request.json
    ids = data.get('ids', [])
    if not ids:
        return jsonify({"error": "请选择要删除的条目"}), 400

    conn = psycopg2.connect(host='localhost', port=5432, dbname='cpa_knowledge', user='postgres', password='admin')
    cur = conn.cursor()
    placeholders = ','.join(['%s'] * len(ids))
    cur.execute(f"DELETE FROM cpa_dream_knowledge WHERE id IN ({placeholders})", ids)
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True, "deleted": deleted})

# ============================================================
# Agent & Team 页面路由
# ============================================================
@app.route('/agents')
def agents_page():
    return render_template('agents.html')

@app.route('/teams')
def teams_page():
    return render_template('teams.html')

@app.route('/teams/<int:team_id>')
def team_chat_page(team_id):
    from services.team_service import get_team
    team = get_team(team_id)
    if not team:
        return render_template('404.html'), 404
    return render_template('team_chat.html', team=team)

# ============================================================
# Agent CRUD API
# ============================================================
@app.route('/api/agents/list', methods=['GET'])
def api_agents_list():
    search = request.args.get('search', '')
    return jsonify(list_agents(search))

@app.route('/api/agents/get', methods=['POST'])
def api_agents_get():
    data = request.json
    agent = get_agent(data.get('id'))
    if not agent:
        return jsonify({"error": "Agent不存在"}), 404
    return jsonify(agent)

@app.route('/api/agents/create', methods=['POST'])
def api_agents_create():
    data = request.json
    agent = create_agent(data)
    return jsonify(agent)

@app.route('/api/agents/update', methods=['POST'])
def api_agents_update():
    data = request.json
    agent = update_agent(data.get('id'), data)
    if not agent:
        return jsonify({"error": "Agent不存在"}), 404
    return jsonify(agent)

@app.route('/api/agents/delete', methods=['POST'])
def api_agents_delete():
    data = request.json
    deleted = delete_agent(data.get('id'))
    return jsonify({"success": deleted > 0, "deleted": deleted})

# ============================================================
# Team CRUD API
# ============================================================
@app.route('/api/teams/list', methods=['GET'])
def api_teams_list():
    search = request.args.get('search', '')
    return jsonify(list_teams(search))

@app.route('/api/teams/get', methods=['POST'])
def api_teams_get():
    data = request.json
    team = get_team(data.get('id'))
    if not team:
        return jsonify({"error": "团队不存在"}), 404
    return jsonify(team)

@app.route('/api/teams/create', methods=['POST'])
def api_teams_create():
    data = request.json
    team = create_team(data)
    return jsonify(team)

@app.route('/api/teams/update', methods=['POST'])
def api_teams_update():
    data = request.json
    team = update_team(data.get('id'), data)
    if not team:
        return jsonify({"error": "团队不存在"}), 404
    return jsonify(team)

@app.route('/api/teams/delete', methods=['POST'])
def api_teams_delete():
    data = request.json
    deleted = delete_team(data.get('id'))
    return jsonify({"success": deleted > 0, "deleted": deleted})

@app.route('/api/teams/run', methods=['POST'])
def api_teams_run():
    data = request.json
    team_id = data.get('team_id')
    question = data.get('question', '')
    session_id = data.get('session_id', '')

    if not team_id or not question:
        return jsonify({"error": "缺少参数"}), 400

    result = run_team(team_id, question, session_id)
    if result.get("answer"):
        try:
            save_qa_history(session_id or f"team_{team_id}", question, result["answer"], prompt_key="team_chat")
        except Exception as e:
            print(f"保存团队问答历史失败: {e}")
    return jsonify(result)

@app.route('/api/teams/run_stream', methods=['POST'])
def api_teams_run_stream():
    """流式运行团队（SSE），逐步返回每个Agent的讨论过程"""
    data = request.json
    team_id = data.get('team_id')
    question = data.get('question', '')
    session_id = data.get('session_id', '')

    if not team_id or not question:
        return jsonify({"error": "缺少参数"}), 400

    def generate():
        last_answer = None
        last_question = question
        try:
            for event in run_team_stream(team_id, question, session_id):
                if event.startswith('data:') and '"answer"' in event:
                    try:
                        import json as _j
                        evt = _j.loads(event[6:])
                        if evt.get('type') == 'done':
                            last_answer = evt.get('answer', '')
                            if last_answer:
                                try:
                                    save_qa_history(session_id or f"team_{team_id}", last_question, last_answer, prompt_key="team_chat")
                                except Exception as e:
                                    print(f"保存团队问答历史失败: {e}")
                    except:
                        pass
                yield event
        except Exception as e:
            print(f"[run_stream] 生成器异常: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'error': f'服务端处理异常: {str(e)}'})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/teams/<int:team_id>/history', methods=['GET'])
def api_teams_history(team_id):
    """获取团队对话历史"""
    session_id = request.args.get('session_id', '')
    conn = psycopg2.connect(host='localhost', port=5432, dbname='cpa_knowledge', user='postgres', password='admin')
    cur = conn.cursor()
    if session_id:
        cur.execute("""
            SELECT id, question, final_answer, status, created_at
            FROM cpa_workflow_runs
            WHERE team_id = %s AND session_id = %s AND status = 'done' AND final_answer IS NOT NULL
            ORDER BY id ASC
        """, (team_id, session_id))
    else:
        cur.execute("""
            SELECT id, question, final_answer, status, created_at
            FROM cpa_workflow_runs
            WHERE team_id = %s AND status = 'done' AND final_answer IS NOT NULL
            ORDER BY id ASC
        """, (team_id,))
    items = []
    for r in cur.fetchall():
        items.append({
            "id": r[0], "workflow_id": r[0], "question": r[1], "answer": r[2],
            "status": r[3], "created_at": str(r[4]) if r[4] else ""
        })
    cur.close()
    conn.close()
    return jsonify(items)

@app.route('/api/teams/steps/<int:workflow_id>', methods=['GET'])
def api_teams_steps(workflow_id):
    """获取团队讨论过程的详细步骤"""
    conn = psycopg2.connect(host='localhost', port=5432, dbname='cpa_knowledge', user='postgres', password='admin')
    cur = conn.cursor()
    cur.execute("""
        SELECT step_order, agent_name, output_text, decision, created_at
        FROM cpa_workflow_steps
        WHERE workflow_id = %s
        ORDER BY step_order ASC
    """, (workflow_id,))
    steps = []
    for r in cur.fetchall():
        steps.append({
            "step_order": r[0], "agent_name": r[1],
            "output_text": r[2], "decision": r[3],
            "created_at": str(r[4]) if r[4] else ""
        })
    cur.close()
    conn.close()
    return jsonify(steps)

@app.route('/api/teams/<int:team_id>/clear', methods=['POST'])
def api_teams_clear(team_id):
    """清除团队对话历史"""
    data = request.json or {}
    session_id = data.get('session_id', '')
    conn = psycopg2.connect(host='localhost', port=5432, dbname='cpa_knowledge', user='postgres', password='admin')
    cur = conn.cursor()
    if session_id:
        cur.execute("DELETE FROM cpa_workflow_runs WHERE team_id = %s AND session_id = %s", (team_id, session_id))
    else:
        cur.execute("DELETE FROM cpa_workflow_runs WHERE team_id = %s", (team_id,))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True, "deleted": deleted})

# ============================================================
# 审计AI辅导接口 - 审计仪表盘调用
# 功能: 接收审计记录详情 → 检索CPA知识库 → DeepSeek生成辅导
# ============================================================
@app.route('/api/audit_tutor', methods=['POST'])
def audit_tutor():
    """审计AI辅导：结合风险详情和CPA知识库给出专业辅导"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "请求数据为空"}), 400
        
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
        search_mode = data.get('search_mode', 'vector')
        user_question = data.get('user_question', '')
        
        # 构建查询 - 从风险描述和审计原因中提取关键词
        query_parts = []
        if user_question:
            query_parts.append(user_question)
        if risk_description:
            query_parts.append(risk_description)
        if audit_reason:
            query_parts.append(audit_reason)
        if image_type and image_type != '未知':
            query_parts.append(f"{image_type} 审计")
        query = "；".join(query_parts) if query_parts else f"{image_type} 审计风险 辅导"
        
        # 根据检索模式选择对应函数
        mode_map = {
            'vector': search_knowledge_base,
            'bm25': search_knowledge_base_bm25,
            'hybrid': search_knowledge_base_hybrid,
            'graph': search_knowledge_base_graph,
        }
        search_func = mode_map.get(search_mode, search_knowledge_base)
        kb_results = search_func(query, top_k=5)
        
        # 构建CPA知识库上下文
        cpa_context = ""
        if kb_results:
            cpa_context = "以下是从CPA教材知识库中检索到的相关内容：\n\n"
            for i, r in enumerate(kb_results, 1):
                source = r.get("source_label", f"来源 #{r.get('source_id', '')}")
                content = r.get("content", "")
                similarity = r.get("similarity", 0)
                cpa_context += f"[{i}] {source} (相似度: {similarity:.2f})\n{content}\n\n"
        
        # 构建审计记录上下文
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
        if risk_description:
            audit_context += f"风险说明: {risk_description}\n"
        if audit_reason:
            audit_context += f"审计说明: {audit_reason}\n"
        if kb_rules_text:
            audit_context += f"\n关联知识库规则:\n{kb_rules_text}\n"
        
        # 组合完整上下文
        full_context = audit_context
        if cpa_context:
            full_context += f"\n\n{cpa_context}"
        
        # 调用DeepSeek生成辅导
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
        
        return jsonify({
            "success": True,
            "answer": answer,
            "cpa_referenced": [{
                "source_label": r.get("source_label", ""),
                "similarity": r.get("similarity", 0),
                "content_preview": r.get("content", "")
            } for r in kb_results] if kb_results else []
        })
    
    except Exception as e:
        print(f"审计AI辅导失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ask_ai', methods=['POST'])
def ask_ai():
    return audit_tutor()

# ============================================================
# 审计AI辅导 - 流式输出版本
# ============================================================
@app.route('/api/audit_tutor_stream', methods=['POST'])
def audit_tutor_stream():
    """审计AI辅导流式输出：检索CPA知识库 + DeepSeek流式生成"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "请求数据为空"}), 400
        
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
        search_mode = data.get('search_mode', 'vector')
        user_question = data.get('user_question', '')
        history = data.get('history', [])
        
        # 构建查询
        query_parts = []
        if user_question:
            query_parts.append(user_question)
        if risk_description:
            query_parts.append(risk_description)
        if audit_reason:
            query_parts.append(audit_reason)
        if image_type and image_type != '未知':
            query_parts.append(f"{image_type} 审计")
        query = "；".join(query_parts) if query_parts else f"{image_type} 审计风险 辅导"
        
        # 首次提问才检索知识库，追问直接用历史
        if not history:
            mode_map = {
                'vector': search_knowledge_base,
                'bm25': search_knowledge_base_bm25,
                'hybrid': search_knowledge_base_hybrid,
                'graph': search_knowledge_base_graph,
            }
            search_func = mode_map.get(search_mode, search_knowledge_base)
            kb_results = search_func(query, top_k=5)
        else:
            kb_results = []
        
        # 构建CPA知识库上下文
        cpa_context = ""
        if kb_results:
            cpa_context = "以下是从CPA教材知识库中检索到的相关内容：\n\n"
            for i, r in enumerate(kb_results, 1):
                source = r.get("source_label", f"来源 #{r.get('source_id', '')}")
                content = r.get("content", "")
                similarity = r.get("similarity", 0)
                cpa_context += f"[{i}] {source} (相似度: {similarity:.2f})\n{content}\n\n"
        
        # 构建审计记录上下文
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
        if risk_description:
            audit_context += f"风险说明: {risk_description}\n"
        if audit_reason:
            audit_context += f"审计说明: {audit_reason}\n"
        if kb_rules_text:
            audit_context += f"\n关联知识库规则:\n{kb_rules_text}\n"
        
        full_context = audit_context
        if cpa_context:
            full_context += f"\n\n{cpa_context}"
        
        # 构建CPA引用元数据
        cpa_meta = []
        if kb_results:
            cpa_meta = [{
                "source_label": r.get("source_label", ""),
                "similarity": r.get("similarity", 0),
                "content_preview": r.get("content", "")
            } for r in kb_results]
        
        def generate():
            full_answer = ""
            
            # 立即保存问题（即使流式失败也保证记录存在）
            qa_id = None
            try:
                qa_id = save_qa_history(f"audit_{record_id}", query, "", prompt_key="audit_tutor", referenced_sources=kb_results)
                if qa_id:
                    print(f"审计辅导已保存(#{qa_id}), 等待流式完成...")
            except Exception as e:
                print(f"审计辅导初始保存失败: {e}")
            
            # 1. 先发送元数据（CPA引用来源）
            yield f"data: {json.dumps({'type': 'meta', 'cpa_referenced': cpa_meta})}\n\n"
            
            # 2. 流式调用DeepSeek
            tutor_prompt = """你是一名经验丰富的注册会计师(CPA)考试辅导专家，精通审计实务、会计准则和风险管理。
请基于以下审计记录详情和CPA教材知识库内容，提供专业的审计辅导分析。

请从以下几个方面进行分析：
1. **风险分析**：分析该票据/凭证存在的关键风险点
2. **知识链接**：结合CPA教材知识库，解释相关的审计准则或会计处理原则
3. **审计建议**：给出具体的审计程序建议和注意事项
4. **学习指引**：指出CPA考试中与该审计场景相关的知识点和章节

请用专业但易懂的语言，结构清晰地进行回答。"""
            
            tutor_question = user_question if user_question else "请根据以上审计记录和知识库内容，提供专业的审计辅导分析。"
            
            for chunk in call_deepseek_stream(tutor_prompt, tutor_question, context=full_context, history=history if history else None):
                if chunk is None:
                    continue
                try:
                    lines = chunk.strip().split('\n')
                    for line in lines:
                        if line.startswith('data:'):
                            json_str = line[5:].strip()
                            if json_str == '[DONE]':
                                continue
                            try:
                                data_chunk = json.loads(json_str)
                                if data_chunk.get('choices'):
                                    delta = data_chunk['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        full_answer += content
                                        yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                            except json.JSONDecodeError:
                                continue
                except Exception:
                    continue
            
            # 流式完成后，更新保存的问答记录（补充完整回答）
            if qa_id and full_answer:
                try:
                    _update_qa_answer(qa_id, query, full_answer)
                    print(f"审计辅导答案已更新(#{qa_id})")
                except Exception as e:
                    print(f"审计辅导答案更新失败: {e}")
            
            # 触发做梦提炼（审计问答数据也纳入归档知识库）
            try:
                if full_answer and len(full_answer) > 100:
                    save_dream_knowledge(query, full_answer, f"audit_{record_id}")
            except Exception as e:
                print(f"审计问答做梦提炼失败: {e}")
            
            # 3. 发送完成信号
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    
    except Exception as e:
        print(f"审计AI辅导流式输出失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ask_ai_stream', methods=['POST'])
def ask_ai_stream():
    return audit_tutor_stream()

@app.route('/api/audit_chat_history/<int:record_id>', methods=['GET'])
def get_audit_chat_history(record_id):
    """获取审计记录的历史对话"""
    session_id = f"audit_{record_id}"
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, question, answer, metadata, created_at
            FROM cpa_qa_history
            WHERE session_id = %s
            ORDER BY id ASC
        """, (session_id,))
        items = []
        for row in cur.fetchall():
            meta = None
            try:
                if row[3]:
                    meta = json.loads(row[3]) if isinstance(row[3], str) else row[3]
            except Exception:
                pass
            items.append({
                "id": row[0],
                "question": row[1],
                "answer": row[2],
                "metadata": meta,
                "created_at": str(row[4]) if row[4] else ""
            })
        cur.close(); conn.close()
        return jsonify({"items": items, "total": len(items)})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/audit_chat_history/<int:record_id>/clear', methods=['POST'])
def clear_audit_chat_history(record_id):
    """清空审计记录的历史对话"""
    session_id = f"audit_{record_id}"
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM cpa_qa_history WHERE session_id = %s", (session_id,))
        deleted = cur.rowcount
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "deleted": deleted})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500


@app.route('/settings')
def settings_page():
    """API配置管理页面"""
    return render_template('settings.html')


@app.route('/api/config/get', methods=['GET'])
def api_config_get():
    """获取当前配置"""
    config = load_model_config()
    return jsonify({"success": True, "config": config})


@app.route('/api/config/save', methods=['POST'])
def api_config_save():
    """保存配置"""
    try:
        data = request.json
        if not data or "config" not in data:
            return jsonify({"success": False, "error": "无效的配置数据"}), 400

        new_config = data["config"]

        if "providers" not in new_config:
            return jsonify({"success": False, "error": "缺少 providers 字段"}), 400

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(new_config, f, ensure_ascii=False, indent=2)

        global DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL, DEEPSEEK_REASON_MODEL
        ds = get_deepseek_config()
        DEEPSEEK_API_KEY = ds["api_key"]
        DEEPSEEK_API_URL = ds["api_url"]
        DEEPSEEK_MODEL = ds["model"]
        DEEPSEEK_REASON_MODEL = ds["reason_model"]

        return jsonify({"success": True, "message": "配置已保存"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
# 系统配置 (config.json) API
# ============================================================

@app.route('/api/system_config/get', methods=['GET'])
def api_system_config_get():
    try:
        config = {}
        if SYSTEM_CONFIG_PATH.exists():
            with open(SYSTEM_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
        return jsonify({"success": True, "config": config})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/system_config/save', methods=['POST'])
def api_system_config_save():
    try:
        data = request.json
        if not data or "config" not in data:
            return jsonify({"success": False, "error": "无效的配置数据"}), 400
        SYSTEM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        saved_config = data["config"]
        with open(SYSTEM_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(saved_config, f, ensure_ascii=False, indent=2)
        # 直接更新全局 cfg 对象的属性，无需重载导入
        for k, v in saved_config.items():
            setattr(cfg, k, v)
        return jsonify({"success": True, "message": "系统配置已保存"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
# 提示词 & Skills 配置 (prompts_config.json) API
# ============================================================

@app.route('/api/prompts/get', methods=['GET'])
def api_prompts_get():
    try:
        data = {}
        if PROMPTS_PATH.exists():
            with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        return jsonify({"success": True, "prompts": data.get("prompts", DEFAULT_PROMPTS), "skills": data.get("skills", SKILLS)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/prompts/save', methods=['POST'])
def api_prompts_save():
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "无效的配置数据"}), 400
        PROMPTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PROMPTS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        global DEFAULT_PROMPTS, SKILLS
        DEFAULT_PROMPTS = data.get("prompts", {})
        SKILLS = data.get("skills", [])
        return jsonify({"success": True, "message": "提示词配置已保存"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
# CPA 知识库兼容路由别名（兼容 app.py 的 /api/cpa_knowledge/* 路径）
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

@app.route('/api/cpa_knowledge/list', methods=['POST'])
def cpa_kb_list():
    return kb_list()

@app.route('/api/cpa_knowledge/detail', methods=['POST'])
def cpa_kb_detail():
    data = request.json
    item_id = data.get('id')
    if not item_id:
        return jsonify({"error": "缺少ID"}), 400
    conn = get_db_connection()
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
            if row[5]:
                meta = json.loads(row[5]) if isinstance(row[5], str) else row[5]
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
    conn = get_db_connection()
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
    conn = get_db_connection()
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
        cur.execute("SELECT COUNT(*) FROM cpa_qa_history WHERE session_id LIKE 'audit_%%'")
        audit_count = cur.fetchone()[0]
        if audit_count > 0:
            type_stats['audit_tutor'] = audit_count
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

@app.route('/api/cpa_knowledge/books', methods=['GET'])
def cpa_kb_books():
    conn = get_db_connection()
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

@app.route('/api/cpa_knowledge/audit_list', methods=['POST'])
def cpa_kb_audit_list():
    data = request.json or {}
    page = data.get('page', 1)
    page_size = data.get('page_size', 20)
    search = data.get('search', '')
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        offset = (page - 1) * page_size
        if search:
            cur.execute("""
                SELECT id, session_id, question, answer, metadata, created_at,
                       COUNT(*) OVER() as total
                FROM cpa_qa_history
                WHERE session_id LIKE 'audit_%%' AND (question ILIKE %s OR answer ILIKE %s)
                ORDER BY id DESC LIMIT %s OFFSET %s
            """, (f'%{search}%', f'%{search}%', page_size, offset))
        else:
            cur.execute("""
                SELECT id, session_id, question, answer, metadata, created_at,
                       COUNT(*) OVER() as total
                FROM cpa_qa_history
                WHERE session_id LIKE 'audit_%%'
                ORDER BY id DESC LIMIT %s OFFSET %s
            """, (page_size, offset))
        rows = cur.fetchall()
        total = rows[0][6] if rows else 0
        items = []
        for r in rows:
            meta = None
            try:
                if r[4]:
                    meta = json.loads(r[4]) if isinstance(r[4], str) else r[4]
            except: pass
            record_id = (r[1] or '').replace('audit_', '') if r[1] else ''
            summary = (r[2] or r[3] or '')
            items.append({
                "id": r[0],
                "source_type": "audit_tutor",
                "source_id": record_id,
                "content": (r[3] or ''),
                "summary": summary,
                "metadata": {"record_id": record_id, "question": (r[2] or '')},
                "created_at": str(r[5]) if r[5] else ''
            })
        cur.close(); conn.close()
        return jsonify({"items": items, "total": total, "page": page, "total_pages": max(1, (total + page_size - 1) // page_size)})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/cpa_knowledge/audit_delete', methods=['POST'])
def cpa_kb_audit_delete():
    data = request.json or {}
    ids = data.get('ids', [])
    if not ids:
        return jsonify({"error": "缺少ID"}), 400
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    try:
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(ids))
        cur.execute(f"DELETE FROM cpa_qa_history WHERE id IN ({placeholders}) AND session_id LIKE 'audit_%%'", ids)
        deleted = cur.rowcount
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "deleted": deleted})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/cpa_qa_history/list', methods=['POST'])
def cpa_qa_history_list():
    data = request.json or {}
    page = data.get('page', 1)
    page_size = data.get('page_size', 20)
    search = data.get('search', '')
    conn = get_db_connection()
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
            SELECT id, session_id, question as question_preview,
                   answer as answer_preview, created_at
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
    conn = get_db_connection()
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
        return jsonify({
            "id": row[0], "session_id": row[1],
            "question": row[2], "answer": row[3],
            "metadata": row[4], "created_at": str(row[5]) if row[5] else ""
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
    conn = get_db_connection()
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
# 审计数据仪表盘 - 端口统一合并路由
# ============================================================

def get_audit_connection():
    try:
        return psycopg2.connect(
            host=getattr(cfg, "DB_HOST", "localhost"),
            port=getattr(cfg, "DB_PORT", 5432),
            dbname=getattr(cfg, "DB_NAME", "audit_ocr"),
            user=getattr(cfg, "DB_USER", "postgres"),
            password=getattr(cfg, "DB_PASSWORD", "admin"),
        )
    except Exception as e:
        print(f"审计数据库连接失败: {str(e)}")
        return None

@app.route('/images/<path:filename>')
def serve_image(filename):
    image_dirs = ['input_pic', 'output']
    for dir_name in image_dirs:
        full_path = os.path.join(app.root_path, dir_name, filename)
        if os.path.exists(full_path):
            return send_from_directory(os.path.join(app.root_path, dir_name), filename)
    return "图片未找到", 404

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/audit_data')
def get_audit_data():
    conn = get_audit_connection()
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
    conn = get_audit_connection()
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
                "approval_level": row[28], "attachment_complete": row[29], "other_info": row[30],
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
        return jsonify({"error": "记录不存在"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/knowledge_base/<int:kb_id>')
def get_knowledge_base(kb_id):
    conn = get_audit_connection()
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
    conn = get_audit_connection()
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
    conn = get_audit_connection()
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
    conn = get_audit_connection()
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


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True, allow_unsafe_werkzeug=True)