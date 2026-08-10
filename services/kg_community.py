"""
知识图谱 — 社区检测服务
============================================================
功能: Leiden算法社区检测 + LLM社区摘要生成
依赖: python-igraph, leidenalg, DeepSeek API
============================================================
"""

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import json
import sys
import os
from pathlib import Path

import psycopg2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GRAPH_DB = {
    "host": "localhost", "port": 5432,
    "dbname": "cpa_knowledge_graph",
    "user": "postgres", "password": "admin",
}


def get_graph_conn():
    return psycopg2.connect(**GRAPH_DB)


class CommunityDetector:
    """知识图谱社区检测器"""

    def __init__(self):
        self.conn = get_graph_conn()
        self.entity_map = {}  # {entity_id: {name, entity_type, ...}}
        self.entity_id_to_idx = {}  # {entity_id: igraph_index}
        self.idx_to_entity_id = {}  # {igraph_index: entity_id}

    def load_graph(self):
        """加载实体和关系到内存"""
        cur = self.conn.cursor()

        cur.execute("SELECT id, name, entity_type, category, definition FROM kg_entities")
        entities = cur.fetchall()
        self.entity_map = {}
        for i, row in enumerate(entities):
            eid, name, etype, cat, definition = row
            self.entity_map[eid] = {
                "name": name,
                "entity_type": etype,
                "category": cat,
                "definition": definition,
            }
            self.entity_id_to_idx[eid] = i
            self.idx_to_entity_id[i] = eid

        cur.execute("""
            SELECT source_entity_id, target_entity_id, relation_type, weight, confidence
            FROM kg_relationships
        """)
        self.relations = cur.fetchall()
        cur.close()

        print(f"  节点: {len(self.entity_map)}, 边: {len(self.relations)}")

    def detect(self, resolution: float = 1.0) -> dict:
        """
        运行Leiden算法
        返回: {community_id: [entity_ids]}
        """
        try:
            import igraph as ig
        except ImportError:
            print("[WARN] python-igraph未安装，pip install python-igraph leidenalg")
            return {}

        self.load_graph()

        if len(self.entity_map) < 3:
            print("  ⚠️ 实体太少，跳过社区检测（至少需要3个实体）")
            return {}

        # 构建igraph图
        n = len(self.entity_map)
        edges = []
        weights = []

        for src, tgt, rtype, weight, confidence in self.relations:
            if src in self.entity_id_to_idx and tgt in self.entity_id_to_idx:
                edges.append((self.entity_id_to_idx[src], self.entity_id_to_idx[tgt]))
                w = float(weight or 1.0) * float(confidence or 0.5)
                weights.append(w)

        if not edges:
            print("  ⚠️ 没有关系边，跳过社区检测")
            return {}

        g = ig.Graph(n=n, edges=edges, directed=True)
        g.es['weight'] = weights

        print(f"  构建图完成: {g.vcount()} 节点, {g.ecount()} 边")

        # 运行Leiden算法
        try:
            partition = g.community_leiden(
                objective_function="modularity",
                weights="weight",
                resolution=resolution,
                n_iterations=10,
            )
        except Exception as e:
            print(f"  Leiden算法失败: {e}, 尝试不加权...")
            partition = g.community_leiden(
                objective_function="modularity",
                n_iterations=10,
            )

        # 整理结果
        communities = {}
        for idx, community_id in enumerate(partition.membership):
            eid = self.idx_to_entity_id[idx]
            communities.setdefault(community_id, []).append(eid)

        print(f"  检测到 {len(communities)} 个社区")
        for cid, members in communities.items():
            names = [self.entity_map[eid]["name"] for eid in members[:5]]
            print(f"    社区{cid}: {len(members)}个实体 | {' | '.join(names)}...")

        return communities

    def generate_summaries(self, communities: dict) -> list[dict]:
        """
        对每个社区用LLM生成主题摘要
        返回: [{community_label, entity_ids, summary, topic_keywords}]
        """
        # 导入抽取器的LLM调用函数
        from services.kg_extractor import call_llm

        summaries = []
        for cid, entity_ids in communities.items():
            entities_info = []
            for eid in entity_ids[:30]:  # 最多30个实体
                ent = self.entity_map.get(eid, {})
                entities_info.append(
                    f"- {ent.get('name', '?')} ({ent.get('entity_type', '?')}): {ent.get('definition', '')[:80]}"
                )

            if len(entities_info) < 2:
                continue

            prompt = f"""以下是一组CPA知识实体，它们属于同一个主题聚类：

{chr(10).join(entities_info)}

请为这个聚类：
1. 生成一个简洁的主题标签（10字以内）
2. 写一段内容摘要（100字以内），概括这个主题的核心内容
3. 提取3-5个关键词

以JSON格式输出：
{{"label": "...", "summary": "...", "keywords": ["...", "..."]}}
只输出JSON。"""

            result = call_llm(
                "你是一位CPA知识体系专家。请为CPA知识点聚类生成主题标签和摘要。",
                prompt,
                temperature=0.3,
                max_tokens=500,
            )

            if result:
                summaries.append({
                    "community_label": result.get("label", f"社区{cid}"),
                    "entity_ids": entity_ids,
                    "summary": result.get("summary", ""),
                    "topic_keywords": result.get("keywords", []),
                    "modularity_score": 0,
                })
            else:
                # LLM失败，用实体名拼接
                names = [self.entity_map.get(eid, {}).get("name", "?") for eid in entity_ids[:5]]
                summaries.append({
                    "community_label": "、".join(names[:3]),
                    "entity_ids": entity_ids,
                    "summary": f"涵盖{len(entity_ids)}个知识点的主题聚类",
                    "topic_keywords": names[:5],
                    "modularity_score": 0,
                })

        return summaries

    def save_communities(self, summaries: list[dict]):
        """将社区检测结果存入数据库"""
        cur = self.conn.cursor()

        # 清空旧数据
        cur.execute("DELETE FROM kg_communities")

        for s in summaries:
            cur.execute(
                """INSERT INTO kg_communities
                   (community_label, entity_ids, summary, topic_keywords, modularity_score)
                   VALUES (%s, %s, %s, %s, %s)""",
                (s["community_label"],
                 s["entity_ids"],
                 s["summary"],
                 s["topic_keywords"],
                 s.get("modularity_score", 0)),
            )

        self.conn.commit()
        cur.close()
        print(f"  ✅ 已保存 {len(summaries)} 个社区")

    def run(self, resolution: float = 1.0):
        """完整流程：检测 → 摘要 → 保存"""
        print("\n🔍 开始社区检测...")
        communities = self.detect(resolution)

        if not communities:
            print("  ⚠️ 未检测到社区")
            return

        print("\n📝 生成社区摘要...")
        summaries = self.generate_summaries(communities)

        print("\n💾 保存社区结果...")
        self.save_communities(summaries)

        return summaries

    def close(self):
        if self.conn:
            self.conn.close()


# ============================================================
# CLI入口
# ============================================================

if __name__ == "__main__":
    detector = CommunityDetector()
    try:
        summaries = detector.run(resolution=1.0)
        if summaries:
            print(f"\n🎉 社区检测完成！共 {len(summaries)} 个社区")
    finally:
        detector.close()
