"""
知识图谱 API Blueprint
============================================================
所有路由以 /api/kg/ 为前缀，与现有 /api/* 不冲突。
挂载方式：在 web_app.py 中添加:
  from blueprints.kg_api import kg_bp
  app.register_blueprint(kg_bp)
============================================================
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Blueprint, request, jsonify, render_template, Response, stream_with_context
from services.kg_search import KnowledgeGraphSearch
from services.kg_traversal import GraphTraverser
from services.kg_extractor import KnowledgeGraphExtractor
from services.kg_entity_linker import EntityLinker
import psycopg2
import json
import time
import threading

kg_bp = Blueprint('knowledge_graph', __name__, url_prefix='/api/kg')

# ============================================================
# 数据库配置
# ============================================================
GRAPH_DB = {
    "host": "localhost", "port": 5432,
    "dbname": "cpa_knowledge_graph",
    "user": "postgres", "password": "admin",
}

SOURCE_DB = {
    "host": "localhost", "port": 5432,
    "dbname": "cpa_knowledge",
    "user": "postgres", "password": "admin",
}


def get_graph_conn():
    return psycopg2.connect(**GRAPH_DB)


def get_source_conn():
    return psycopg2.connect(**SOURCE_DB)


# ============================================================
# 检索接口
# ============================================================

@kg_bp.route('/search', methods=['POST'])
def kg_search():
    """知识图谱检索"""
    try:
        data = request.json or {}
        query = data.get('query', '').strip()
        if not query:
            return jsonify({"error": "查询不能为空"}), 400

        top_k = data.get('top_k', 10)
        max_hops = data.get('max_hops', 3)
        books = data.get('books')

        kg = KnowledgeGraphSearch()
        result = kg.search(query, top_k=top_k, max_hops=max_hops, books=books)
        kg.close()

        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 实体接口
# ============================================================

@kg_bp.route('/entities', methods=['GET'])
def kg_list_entities():
    """列出实体，支持分页和过滤"""
    entity_type = request.args.get('type', '')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 50))
    offset = (page - 1) * page_size

    conn = get_graph_conn()
    cur = conn.cursor()

    if entity_type:
        cur.execute("""
            SELECT id, name, entity_type, category, definition,
                   chapter_ref, importance, array_length(source_chunk_ids, 1)
            FROM kg_entities WHERE entity_type = %s
            ORDER BY importance DESC, id
            LIMIT %s OFFSET %s
        """, (entity_type, page_size, offset))
        entity_rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM kg_entities WHERE entity_type = %s", (entity_type,))
        total = cur.fetchone()[0]
    else:
        cur.execute("""
            SELECT id, name, entity_type, category, definition,
                   chapter_ref, importance, array_length(source_chunk_ids, 1)
            FROM kg_entities
            ORDER BY id
            LIMIT %s OFFSET %s
        """, (page_size, offset))
        entity_rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM kg_entities")
        total = cur.fetchone()[0]

    entities = []
    for row in entity_rows:
        entities.append({
            "id": row[0], "name": row[1], "entity_type": row[2],
            "category": row[3], "definition": row[4],
            "chapter_ref": row[5], "importance": row[6],
            "chunk_count": row[7] or 0,
        })

    cur.close()
    conn.close()

    return jsonify({
        "success": True,
        "entities": entities,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    })


@kg_bp.route('/entities/<int:entity_id>', methods=['GET'])
def kg_get_entity(entity_id):
    """获取实体详情 + 关联关系"""
    conn = get_graph_conn()

    # 实体信息
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, entity_type, category, definition,
               chapter_ref, source_chunk_ids, importance, aliases, metadata
        FROM kg_entities WHERE id = %s
    """, (entity_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return jsonify({"error": "实体不存在"}), 404

    entity = {
        "id": row[0], "name": row[1], "entity_type": row[2],
        "category": row[3], "definition": row[4],
        "chapter_ref": row[5], "source_chunk_ids": row[6] or [],
        "importance": row[7], "aliases": row[8] or [],
        "metadata": row[9],
    }

    # 关联关系
    cur.execute("""
        SELECT r.id, r.relation_type, r.description, r.formula,
               r.confidence, r.weight,
               e_src.id, e_src.name, e_src.entity_type,
               e_tgt.id, e_tgt.name, e_tgt.entity_type
        FROM kg_relationships r
        JOIN kg_entities e_src ON r.source_entity_id = e_src.id
        JOIN kg_entities e_tgt ON r.target_entity_id = e_tgt.id
        WHERE r.source_entity_id = %s OR r.target_entity_id = %s
        ORDER BY r.confidence DESC, r.weight DESC
        LIMIT 50
    """, (entity_id, entity_id))

    relations = []
    for r in cur.fetchall():
        direction = "outgoing" if r[6] == entity_id else "incoming"
        relations.append({
            "id": r[0],
            "relation_type": r[1],
            "description": r[2],
            "formula": r[3],
            "confidence": float(r[4]) if r[4] else 0,
            "direction": direction,
            "source": {"id": r[6], "name": r[7], "entity_type": r[8]},
            "target": {"id": r[9], "name": r[10], "entity_type": r[11]},
        })

    # 易混概念
    cur.execute("""
        SELECT ea.id, ea.name, eb.id, eb.name, kp.distinction, kp.typical_question
        FROM kg_confusion_pairs kp
        JOIN kg_entities ea ON kp.entity_a_id = ea.id
        JOIN kg_entities eb ON kp.entity_b_id = eb.id
        WHERE kp.entity_a_id = %s OR kp.entity_b_id = %s
    """, (entity_id, entity_id))

    confusions = []
    for r in cur.fetchall():
        confusions.append({
            "concept_a": {"id": r[0], "name": r[1]},
            "concept_b": {"id": r[2], "name": r[3]},
            "distinction": r[4],
            "typical_question": r[5],
        })

    # 公式
    cur.execute("""
        SELECT id, name, expression, inputs, output, conditions, example
        FROM kg_formulas WHERE entity_id = %s
    """, (entity_id,))
    formulas = [{
        "id": r[0], "name": r[1], "expression": r[2],
        "inputs": r[3], "output": r[4], "conditions": r[5], "example": r[6],
    } for r in cur.fetchall()]

    cur.close()
    conn.close()

    return jsonify({
        "success": True,
        "entity": entity,
        "relations": relations,
        "confusion_pairs": confusions,
        "formulas": formulas,
    })


@kg_bp.route('/entities/search', methods=['POST'])
def kg_search_entities():
    """搜索实体（用于前端搜索框）"""
    data = request.json or {}
    query = (data.get('query') or '').strip()
    if not query or len(query) < 1:
        return jsonify({"entities": []})

    conn = get_graph_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, entity_type, category, definition,
               similarity(name, %s) as sim
        FROM kg_entities
        WHERE name ILIKE %s
        ORDER BY sim DESC
        LIMIT 20
    """, (query, f"%{query}%"))
    entities = [{
        "id": r[0], "name": r[1], "entity_type": r[2],
        "category": r[3], "definition": r[4], "score": float(r[5]),
    } for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify({"entities": entities})


# ============================================================
# 图遍历接口
# ============================================================

@kg_bp.route('/path', methods=['POST'])
def kg_find_path():
    """查找两个实体间的最短路径"""
    data = request.json or {}
    from_name = (data.get('from') or '').strip()
    to_name = (data.get('to') or '').strip()
    if not from_name or not to_name:
        return jsonify({"error": "请指定 from 和 to 实体名"}), 400

    conn = get_graph_conn()
    traverser = GraphTraverser(conn)
    paths = traverser.find_paths(from_name, to_name, max_depth=5)
    conn.close()

    return jsonify({"success": True, "paths": paths, "count": len(paths)})


@kg_bp.route('/expand', methods=['POST'])
def kg_expand():
    """展开实体邻域（用于可视化）"""
    data = request.json or {}
    entity_id = data.get('entity_id')
    depth = data.get('depth', 1)
    if not entity_id:
        return jsonify({"error": "请指定 entity_id"}), 400

    conn = get_graph_conn()
    traverser = GraphTraverser(conn)
    result = traverser.expand_entity(int(entity_id), depth=int(depth))
    conn.close()

    if result is None:
        return jsonify({"error": "实体不存在"}), 404

    return jsonify({"success": True, **result})


@kg_bp.route('/relations', methods=['GET'])
def kg_list_relations():
    """列出关系（用于初始图谱加载）"""
    limit = int(request.args.get('limit', 200))

    conn = get_graph_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, source_entity_id, target_entity_id, relation_type,
               description, confidence, weight
        FROM kg_relationships
        ORDER BY id
        LIMIT %s
    """, (limit,))
    relations = [{
        "id": r[0], "source_entity_id": r[1], "target_entity_id": r[2],
        "relation_type": r[3], "description": r[4],
        "confidence": float(r[5]) if r[5] else 0, "weight": float(r[6]) if r[6] else 0,
    } for r in cur.fetchall()]
    cur.close()
    conn.close()

    return jsonify({"success": True, "relations": relations, "total": len(relations)})


# ============================================================
# 社区接口
# ============================================================

@kg_bp.route('/communities', methods=['GET'])
def kg_list_communities():
    """列出所有社区"""
    conn = get_graph_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, community_label, array_length(entity_ids, 1) as member_count,
               summary, topic_keywords, modularity_score
        FROM kg_communities
        ORDER BY modularity_score DESC, member_count DESC
    """)
    communities = [{
        "id": r[0], "label": r[1], "member_count": r[2] or 0,
        "summary": r[3], "keywords": r[4], "modularity": float(r[5]) if r[5] else 0,
    } for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify({"success": True, "communities": communities})


# ============================================================
# 统计接口
# ============================================================

@kg_bp.route('/stats', methods=['GET'])
def kg_stats():
    """图谱统计信息"""
    try:
        kg = KnowledgeGraphSearch()
        stats = kg.get_stats()
        kg.close()

        # 额外：构建日志
        conn = get_graph_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, build_type, status, chunks_processed,
                   entities_created, relations_created, started_at, finished_at
            FROM kg_build_log ORDER BY id DESC LIMIT 5
        """)
        stats["recent_builds"] = [{
            "id": r[0], "type": r[1], "status": r[2],
            "chunks": r[3], "entities": r[4], "relations": r[5],
            "started": str(r[6]) if r[6] else None,
            "finished": str(r[7]) if r[7] else None,
        } for r in cur.fetchall()]
        cur.close()
        conn.close()

        return jsonify({"success": True, **stats})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 构建接口
# ============================================================

_build_status = {}  # {build_id: {status, progress, ...}}


@kg_bp.route('/build', methods=['POST'])
def kg_build():
    """触发图谱构建"""
    data = request.json or {}
    book = data.get('book')
    limit = data.get('limit', 100)
    stages = set(data.get('stages', ['entities', 'relationships', 'formulas', 'confusions']))

    # 创建构建日志
    conn = get_graph_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO kg_build_log (build_type, status, book_filter) VALUES ('entity_extraction', 'running', %s) RETURNING id",
        (book,),
    )
    build_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    _build_status[build_id] = {"status": "running", "progress": 0, "message": "正在准备..."}

    # 后台线程执行构建
    def run_build():
        import subprocess
        try:
            _build_status[build_id] = {"status": "running", "progress": 10,
                                        "message": "正在提取实体和关系..."}
            # 这里简化处理，实际应调用 build_kg 的函数
            from knowledge.build_kg import build_graph
            build_graph(
                book_filter=book,
                limit=limit,
                concurrent=2,
                stages=stages,
            )
            _build_status[build_id] = {"status": "completed", "progress": 100,
                                        "message": "构建完成"}
        except Exception as e:
            _build_status[build_id] = {"status": "failed", "progress": 0,
                                        "message": str(e)}

    thread = threading.Thread(target=run_build, daemon=True)
    thread.start()

    return jsonify({"success": True, "build_id": build_id, "status": "started"})


@kg_bp.route('/build/status/<int:build_id>', methods=['GET'])
def kg_build_status(build_id):
    """查询构建进度"""
    status = _build_status.get(build_id)
    if status:
        return jsonify({"success": True, **status})

    # 查数据库
    conn = get_graph_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT status, chunks_processed, entities_created, relations_created FROM kg_build_log WHERE id = %s",
        (build_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        return jsonify({"success": True, "status": row[0], "chunks_processed": row[1],
                        "entities_created": row[2], "relations_created": row[3]})
    return jsonify({"error": "构建记录不存在"}), 404


# ============================================================
# 页面路由
# ============================================================

@kg_bp.route('/explorer', methods=['GET'])
def kg_explorer_page():
    """知识图谱可视化页面 — 重定向到 template（如已挂载在主app上）"""
    # 注意：由于 Blueprint 的 url_prefix 是 /api/kg，
    # 这个路由实际映射到 /api/kg/explorer。
    # 如果要在根路径访问，需要在主 app 中额外注册。
    return jsonify({"message": "请访问 /kg/explorer 查看可视化页面"})


# ============================================================
# 辅助函数：注册到主 Flask app
# ============================================================

def register_kg_routes(app):
    """
    将页面路由注册到主 app（非 Blueprint 方式）
    在 app 上直接注册 /kg/* 页面路由
    """
    @app.route('/kg/explorer')
    def kg_explorer():
        """知识图谱可视化页面"""
        return render_template('kg_explorer.html')

    @app.route('/kg/search')
    def kg_search_page():
        """知识图谱搜索对比页面"""
        return render_template('kg_search.html')

    return app
