"""
知识图谱 — 检索服务
============================================================
功能: 实体链接 + 多跳图检索 + 易混概念查询 + 跨库取chunk
依赖: cpa_knowledge_graph (kg_*) + cpa_knowledge (cpa_embeddings 只读)
============================================================
"""

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import json
import re
import psycopg2
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jieba
from services.kg_traversal import GraphTraverser

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

# 加载jieba词典
_dict_path = Path(__file__).resolve().parent.parent / "data" / "cpa_dict.txt"
if _dict_path.exists():
    jieba.load_userdict(str(_dict_path))


# ============================================================
# 检索服务
# ============================================================

class KnowledgeGraphSearch:
    """知识图谱检索服务"""

    def __init__(self):
        self.graph_conn = None
        self.source_conn = None
        self.traverser = None
        self._init_connections()

    def _init_connections(self):
        try:
            self.graph_conn = psycopg2.connect(**GRAPH_DB)
            self.source_conn = psycopg2.connect(**SOURCE_DB)
            self.traverser = GraphTraverser(self.graph_conn)
            self.traverser.load_graph()
        except Exception as e:
            print(f"[kg_search] 数据库连接失败: {e}")

    def search(self, query: str, top_k: int = 10, max_hops: int = 3,
               books: list = None) -> dict:
        """
        完整图检索流程
        返回: {graph_results, matched_entities, traversal_paths,
               confusion_pairs, community_context, fallback}
        """
        result = {
            "graph_results": [],
            "matched_entities": [],
            "traversal_paths": [],
            "confusion_pairs": [],
            "community_context": "",
            "fallback": False,
        }

        if not self.traverser:
            result["fallback"] = True
            return result

        try:
            # Step 1: 实体链接
            entities = self.entity_link(query)
            result["matched_entities"] = entities

            if not entities:
                result["fallback"] = True
                return result

            entity_ids = [e["entity_id"] for e in entities[:5]]

            # Step 2: BFS多跳遍历
            traversal = self.traverser.bfs(
                entity_ids,
                max_depth=max_hops,
                max_results=50,
            )
            result["traversal_paths"] = self._format_paths(traversal)

            # Step 3: 收集chunk_ids
            related_chunk_ids = self._collect_chunk_ids(entity_ids, traversal)

            # Step 4: 查易混概念
            result["confusion_pairs"] = self._check_confusion(entity_ids)

            # Step 5: 跨库取chunk内容
            if related_chunk_ids:
                result["graph_results"] = self._fetch_chunks(
                    related_chunk_ids, top_k, books
                )

            if not result["graph_results"]:
                result["fallback"] = True

        except Exception as e:
            print(f"[kg_search] 检索失败: {e}")
            result["fallback"] = True

        return result

    # ---- 实体链接 ----

    def entity_link(self, query: str) -> list[dict]:
        """从查询中链接到知识图谱实体"""
        # 1. jieba分词
        words = jieba.cut(query, cut_all=False)
        keywords = [
            w.strip() for w in words
            if w.strip() and len(w.strip()) >= 2
            and not re.match(r'^[的了吗是啥我问你和与或如何什么怎样]$', w.strip())
        ]
        keywords = list(set(keywords))[:10]

        if not keywords:
            return []

        # 2. 在kg_entities中匹配（ILIKE + trigram）
        cur = self.graph_conn.cursor()
        like_clauses = " OR ".join(["e.name ILIKE %s" for _ in keywords])
        like_params = [f"%{kw}%" for kw in keywords]

        cur.execute(f"""
            SELECT e.id, e.name, e.entity_type, e.category, e.definition,
                   e.source_chunk_ids, e.importance,
                   GREATEST(
                       similarity(e.name, %s),
                       { " + ".join([f"similarity(e.name, %s)" for _ in keywords]) }
                   ) as match_score
            FROM kg_entities e
            WHERE {like_clauses}
            ORDER BY match_score DESC
            LIMIT 20
        """, [query] + like_params + like_params)

        results = []
        for row in cur.fetchall():
            results.append({
                "entity_id": row[0],
                "name": row[1],
                "entity_type": row[2],
                "category": row[3],
                "definition": row[4],
                "source_chunk_ids": row[5] or [],
                "importance": row[6],
                "match_score": float(row[7]) if row[7] else 0,
            })
        cur.close()
        return results

    # ---- chunk收集 ----

    def _collect_chunk_ids(self, entity_ids: list,
                           traversal: list[dict]) -> set:
        """从实体和遍历结果中收集所有关联chunk_id"""
        chunk_ids = set()
        cur = self.graph_conn.cursor()

        # 从匹配实体收集
        id_placeholders = ','.join(['%s'] * len(entity_ids))
        cur.execute(f"""
            SELECT source_chunk_ids FROM kg_entities WHERE id IN ({id_placeholders})
        """, entity_ids)
        for row in cur.fetchall():
            if row[0]:
                chunk_ids.update(row[0])

        # 从遍历到的实体收集
        traversed_ids = [t["entity_id"] for t in traversal if t["entity_id"] not in entity_ids]
        if traversed_ids:
            id_pl = ','.join(['%s'] * len(traversed_ids))
            cur.execute(f"""
                SELECT source_chunk_ids FROM kg_entities WHERE id IN ({id_pl})
            """, traversed_ids)
            for row in cur.fetchall():
                if row[0]:
                    chunk_ids.update(row[0])

        cur.close()
        return chunk_ids

    # ---- 跨库取chunk ----

    def _fetch_chunks(self, chunk_ids: set, top_k: int = 10,
                      books: list = None) -> list[dict]:
        """从 cpa_knowledge.cpa_embeddings 取原文"""
        if not chunk_ids:
            return []

        id_list = list(chunk_ids)[:top_k * 3]
        cur = self.source_conn.cursor()

        id_placeholders = ','.join(['%s'] * len(id_list))

        if books:
            book_clauses = " OR ".join(
                ["metadata->>'book' LIKE %s" for _ in books]
            )
            book_params = [f"%{b}%" for b in books]
            cur.execute(f"""
                SELECT id, chunk_content, source_type, source_id,
                       chunk_summary, metadata
                FROM cpa_embeddings
                WHERE id IN ({id_placeholders})
                  AND ({book_clauses})
                LIMIT %s
            """, id_list + book_params + [top_k])
        else:
            cur.execute(f"""
                SELECT id, chunk_content, source_type, source_id,
                       chunk_summary, metadata
                FROM cpa_embeddings
                WHERE id IN ({id_placeholders})
                LIMIT %s
            """, id_list + [top_k])

        results = []
        for row in cur.fetchall():
            meta = row[5]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}

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
                "summary": row[4],
                "metadata": meta,
                "source_label": source_label or f"教材 #{row[3]}",
                "similarity": 0.85,
            })

        cur.close()
        return results[:top_k]

    # ---- 易混概念 ----

    def _check_confusion(self, entity_ids: list) -> list[dict]:
        """检查实体列表中是否有易混概念对"""
        cur = self.graph_conn.cursor()
        id_pl = ','.join(['%s'] * len(entity_ids))
        cur.execute(f"""
            SELECT ea.name, eb.name, kp.distinction, kp.typical_question,
                   kp.scenario_a, kp.scenario_b
            FROM kg_confusion_pairs kp
            JOIN kg_entities ea ON kp.entity_a_id = ea.id
            JOIN kg_entities eb ON kp.entity_b_id = eb.id
            WHERE kp.entity_a_id IN ({id_pl}) OR kp.entity_b_id IN ({id_pl})
            LIMIT 5
        """, entity_ids * 2)
        results = []
        for row in cur.fetchall():
            results.append({
                "concept_a": row[0],
                "concept_b": row[1],
                "distinction": row[2],
                "typical_question": row[3],
                "scenario_a": row[4],
                "scenario_b": row[5],
            })
        cur.close()
        return results

    # ---- 路径格式化 ----

    def _format_paths(self, traversal: list[dict]) -> list[str]:
        """将BFS遍历结果格式化为可读的路径描述"""
        paths = []
        for t in traversal:
            if t["depth"] <= 1:
                continue
            path_nodes = t.get("path", [])
            if len(path_nodes) >= 2:
                path_str = " → ".join([
                    f"{n['name']}" for n in path_nodes
                ])
                paths.append(path_str)
        # 去重
        return list(set(paths))[:10]

    # ---- 统计 ----

    def get_stats(self) -> dict:
        """获取图谱统计"""
        cur = self.graph_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM kg_entities")
        entity_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM kg_relationships")
        relation_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM kg_confusion_pairs")
        confusion_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM kg_formulas")
        formula_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM kg_communities")
        community_count = cur.fetchone()[0]

        cur.execute(
            "SELECT entity_type, COUNT(*) FROM kg_entities GROUP BY entity_type ORDER BY COUNT(*) DESC"
        )
        type_dist = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute(
            "SELECT relation_type, COUNT(*) FROM kg_relationships GROUP BY relation_type ORDER BY COUNT(*) DESC"
        )
        relation_dist = {r[0]: r[1] for r in cur.fetchall()}

        cur.close()
        return {
            "entity_count": entity_count,
            "relation_count": relation_count,
            "confusion_pair_count": confusion_count,
            "formula_count": formula_count,
            "community_count": community_count,
            "entity_type_distribution": type_dist,
            "relation_type_distribution": relation_dist,
        }

    def close(self):
        if self.graph_conn:
            self.graph_conn.close()
        if self.source_conn:
            self.source_conn.close()
