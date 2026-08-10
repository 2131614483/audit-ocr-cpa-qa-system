"""
知识图谱 — 图遍历引擎
============================================================
功能: BFS/DFS多跳遍历、最短路径查找、子图展开
依赖: cpa_knowledge_graph 数据库（kg_entities + kg_relationships）
============================================================
"""

from collections import deque
from typing import Optional


class GraphTraverser:
    """图遍历引擎 — 基于PostgreSQL的BFS/DFS实现"""

    def __init__(self, db_conn):
        self.conn = db_conn
        # 缓存邻接表加速遍历
        self._adj_out = {}   # {entity_id: [(target_id, relation_type, weight, description)]}
        self._adj_in = {}    # {entity_id: [(source_id, relation_type, weight, description)]}
        self._entities = {}  # {entity_id: {name, entity_type, category, definition}}
        self._loaded = False

    def load_graph(self):
        """将全部实体和关系加载到内存（小型图，3000+实体完全够用）"""
        if self._loaded:
            return

        cur = self.conn.cursor()

        # 加载实体
        cur.execute(
            "SELECT id, name, entity_type, category, definition FROM kg_entities"
        )
        for row in cur.fetchall():
            self._entities[row[0]] = {
                "name": row[1],
                "entity_type": row[2],
                "category": row[3],
                "definition": row[4],
            }

        # 加载关系 → 构建邻接表
        cur.execute("""
            SELECT source_entity_id, target_entity_id, relation_type,
                   description, weight
            FROM kg_relationships
            ORDER BY weight DESC
        """)
        for row in cur.fetchall():
            src, tgt, rtype, desc, weight = row
            self._adj_out.setdefault(src, []).append((tgt, rtype, weight, desc))
            self._adj_in.setdefault(tgt, []).append((src, rtype, weight, desc))

        cur.close()
        self._loaded = True

    def bfs(self, start_ids: list, max_depth: int = 3,
            relation_types: list = None, max_results: int = 100) -> list[dict]:
        """
        BFS多跳遍历
        返回: [{entity_id, name, entity_type, depth, path: [...], relation_chain}]
        """
        self.load_graph()

        visited = {}  # {entity_id: (depth, prev_id, relation_type)}
        queue = deque()

        for sid in start_ids:
            if sid in self._entities:
                visited[sid] = (0, None, None)
                queue.append(sid)

        while queue:
            current = queue.popleft()
            depth = visited[current][0]

            if depth >= max_depth:
                continue

            # 遍历出边
            for neighbor in self._adj_out.get(current, []):
                tgt_id, rtype, weight, desc = neighbor
                if relation_types and rtype not in relation_types:
                    continue
                if tgt_id not in visited:
                    visited[tgt_id] = (depth + 1, current, rtype)
                    queue.append(tgt_id)
                    if len(visited) >= max_results:
                        queue.clear()
                        break

            # 遍历入边（反向）
            for neighbor in self._adj_in.get(current, []):
                src_id, rtype, weight, desc = neighbor
                if relation_types and rtype not in relation_types:
                    continue
                if src_id not in visited:
                    visited[src_id] = (depth + 1, current, f"<-{rtype}")
                    queue.append(src_id)
                    if len(visited) >= max_results:
                        queue.clear()
                        break

        # 构建结果
        results = []
        for eid, (depth, prev, rel) in visited.items():
            if eid not in self._entities:
                continue
            ent = self._entities[eid]
            results.append({
                "entity_id": eid,
                "name": ent["name"],
                "entity_type": ent["entity_type"],
                "category": ent.get("category", ""),
                "definition": ent.get("definition", ""),
                "depth": depth,
                "path": self._reconstruct_path(eid, visited),
            })
        return results

    def _reconstruct_path(self, entity_id: int,
                          visited: dict) -> list[dict]:
        """重建从起始节点到当前节点的路径"""
        path = []
        current = entity_id
        while current is not None and current in visited:
            depth, prev, rel = visited[current]
            name = self._entities.get(current, {}).get("name", str(current))
            path.append({
                "entity_id": current,
                "name": name,
                "relation": rel,
            })
            current = prev
        path.reverse()
        return path

    def find_paths(self, source_name: str, target_name: str,
                   max_depth: int = 5) -> list[list[dict]]:
        """
        双向BFS查找两个实体间的最短路径
        """
        self.load_graph()

        # 查找实体ID
        source_id = self._find_entity_id(source_name)
        target_id = self._find_entity_id(target_name)
        if not source_id or not target_id:
            return []

        if source_id == target_id:
            return [[{
                "entity_id": source_id,
                "name": source_name,
                "relation": "self",
            }]]

        # 双向BFS
        forward = {source_id: (None, None)}  # {id: (prev_id, relation)}
        backward = {target_id: (None, None)}
        f_queue = deque([source_id])
        b_queue = deque([target_id])

        paths = []
        depth = 0
        found = False

        while depth < max_depth and not found:
            depth += 1

            # 扩展前向
            f_next = set()
            for current in list(f_queue):
                for neighbor in self._adj_out.get(current, []):
                    tgt, rtype, _, _ = neighbor
                    if tgt not in forward:
                        forward[tgt] = (current, rtype)
                        f_next.add(tgt)
                        if tgt in backward:
                            paths = self._merge_paths(source_id, tgt, target_id,
                                                      forward, backward)
                            found = True
                            break
            f_queue = deque(f_next)

            if found:
                break

            # 扩展后向
            b_next = set()
            for current in list(b_queue):
                for neighbor in self._adj_out.get(current, []):
                    tgt, rtype, _, _ = neighbor
                    if tgt not in backward:
                        backward[tgt] = (current, rtype)
                        b_next.add(tgt)
                        if tgt in forward:
                            paths = self._merge_paths(source_id, tgt, target_id,
                                                      forward, backward)
                            found = True
                            break
            b_queue = deque(b_next)

        return paths

    def _merge_paths(self, source_id: int, meet_id: int, target_id: int,
                     forward: dict, backward: dict) -> list[list[dict]]:
        """合并双向BFS的路径"""
        # 从前向构建到meeting点
        f_path = []
        cur = meet_id
        while cur is not None:
            f_path.append({"entity_id": cur, "name": self._entities.get(cur, {}).get("name", str(cur))})
            if cur in forward:
                cur = forward[cur][0]
            else:
                break
        f_path.reverse()

        # 从后向构建
        b_path = []
        cur = meet_id
        if cur in backward:
            cur = backward[cur][0]
        while cur is not None:
            b_path.append({"entity_id": cur, "name": self._entities.get(cur, {}).get("name", str(cur))})
            if cur in backward:
                cur = backward[cur][0]
            else:
                break

        full_path = f_path + b_path
        return [full_path]

    def _find_entity_id(self, name: str) -> Optional[int]:
        """按名称查找实体ID"""
        for eid, ent in self._entities.items():
            if ent["name"] == name:
                return eid
        # 模糊搜索
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id FROM kg_entities WHERE name ILIKE %s LIMIT 1",
            (f"%{name}%",),
        )
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None

    def expand_entity(self, entity_id: int, depth: int = 1) -> dict:
        """
        展开单个实体的邻域（用于可视化）
        返回: {entity, neighbors: {incoming: [...], outgoing: [...]}}
        """
        self.load_graph()

        if entity_id not in self._entities:
            return None

        entity = self._entities[entity_id]
        entity["id"] = entity_id

        result = {
            "entity": entity,
            "neighbors": {
                "incoming": [],
                "outgoing": [],
            },
        }

        # 出边
        for tgt_id, rtype, weight, desc in self._adj_out.get(entity_id, []):
            if tgt_id in self._entities:
                result["neighbors"]["outgoing"].append({
                    "entity": {"id": tgt_id, **self._entities[tgt_id]},
                    "relation_type": rtype,
                    "description": desc,
                    "weight": weight,
                })

        # 入边
        for src_id, rtype, weight, desc in self._adj_in.get(entity_id, []):
            if src_id in self._entities:
                result["neighbors"]["incoming"].append({
                    "entity": {"id": src_id, **self._entities[src_id]},
                    "relation_type": rtype,
                    "description": desc,
                    "weight": weight,
                })

        return result

    def get_entity_by_type(self, entity_type: str, limit: int = 100) -> list:
        """按类型获取实体列表"""
        self.load_graph()
        return [
            {"id": eid, **ent}
            for eid, ent in self._entities.items()
            if ent["entity_type"] == entity_type
        ][:limit]

    def get_entity_count(self) -> int:
        """获取实体总数"""
        self.load_graph()
        return len(self._entities)
