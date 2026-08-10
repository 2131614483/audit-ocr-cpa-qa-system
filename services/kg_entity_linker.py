"""
知识图谱 — 实体对齐与去重
============================================================
功能: 将新抽取的实体与数据库已有实体对比，自动对齐/合并
策略:
  1. 精确名称 + 同类型 → 直接合并 source_chunk_ids
  2. 精确名称 + 不同类型 → 保留两个，标注别名
  3. 名称相近（编辑距离≤2） → 合并 + 添加别名
  4. 完全新实体 → 直接插入
============================================================
"""

import psycopg2
import psycopg2.extras
from typing import Optional

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _sys
if hasattr(_sys.stdout, 'reconfigure'):
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    _sys.stderr.reconfigure(encoding='utf-8', errors='replace')


class EntityLinker:
    """实体对齐去重器"""

    def __init__(self, db_conn):
        self.conn = db_conn
        self._cache = {}  # {name: {id, entity_type, aliases, source_chunk_ids}}

    def load_existing(self):
        """加载所有已有实体到内存缓存"""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, name, entity_type, aliases, source_chunk_ids FROM kg_entities"
        )
        for row in cur.fetchall():
            eid, name, etype, aliases, chunk_ids = row
            self._cache[name] = {
                "id": eid,
                "entity_type": etype,
                "aliases": set(aliases or []),
                "source_chunk_ids": set(chunk_ids or []),
            }
            # 同时用别名索引
            for alias in (aliases or []):
                if alias not in self._cache:
                    self._cache[alias] = self._cache[name]
        cur.close()
        print(f"  📦 已加载 {len(self._cache)} 条实体索引")

    def find_match(self, name: str, entity_type: str) -> Optional[dict]:
        """查找匹配的已有实体，返回实体信息或None"""
        # 1. 精确匹配
        if name in self._cache:
            existing = self._cache[name]
            if existing["entity_type"] == entity_type:
                return {**existing, "match_type": "exact"}
            else:
                return {**existing, "match_type": "type_diff"}

        # 2. 编辑距离匹配（≤2且长度≥3）
        best_match = None
        best_dist = 999
        for existing_name, info in self._cache.items():
            if len(name) >= 3 and len(existing_name) >= 3:
                dist = self._edit_distance(name, existing_name)
                if dist <= 2 and dist < best_dist:
                    best_dist = dist
                    best_match = {**info, "match_type": f"fuzzy_{dist}"}

        return best_match

    @staticmethod
    def _edit_distance(s1: str, s2: str) -> int:
        """Levenshtein编辑距离"""
        if len(s1) < len(s2):
            return EntityLinker._edit_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr = [i + 1]
            for j, c2 in enumerate(s2):
                insert = prev[j + 1] + 1
                delete = curr[j] + 1
                sub = prev[j] + (0 if c1 == c2 else 1)
                curr.append(min(insert, delete, sub))
            prev = curr
        return prev[-1]

    def upsert_entity(self, name: str, entity_type: str, category: str,
                      definition: str, chapter_ref: str, chunk_id: int,
                      importance: str = "中") -> int:
        """
        插入或更新实体
        返回: entity_id（新建或已存在的）
        """
        match = self.find_match(name, entity_type)

        cur = self.conn.cursor()

        if match and match["match_type"] == "exact":
            # 精确匹配：追加chunk_id
            eid = match["id"]
            chunk_ids = match.get("source_chunk_ids", set())
            if chunk_id not in chunk_ids:
                chunk_ids.add(chunk_id)
                cur.execute(
                    "UPDATE kg_entities SET source_chunk_ids = %s, updated_at = NOW() WHERE id = %s",
                    (list(chunk_ids), eid),
                )
                self.conn.commit()
            cur.close()
            return eid

        elif match and match["match_type"] == "type_diff":
            # 同名但不同类型：添加别名后新建
            eid = match["id"]
            existing_name = name
            new_name = f"{name}({entity_type})"
            aliases = match.get("aliases", set())
            if existing_name not in aliases:
                aliases.add(existing_name)
                cur.execute(
                    "UPDATE kg_entities SET aliases = %s WHERE id = %s",
                    (list(aliases), eid),
                )
                self.conn.commit()
            # 插入新实体
            cur.execute(
                """INSERT INTO kg_entities (name, entity_type, category, definition,
                   chapter_ref, source_chunk_ids, importance, aliases)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (name, entity_type) DO UPDATE
                   SET source_chunk_ids = kg_entities.source_chunk_ids || EXCLUDED.source_chunk_ids,
                       updated_at = NOW()
                   RETURNING id""",
                (new_name, entity_type, category, definition, chapter_ref,
                 [chunk_id], importance, [existing_name]),
            )
            new_id = cur.fetchone()[0]
            # 更新缓存
            self._cache[new_name] = {
                "id": new_id, "entity_type": entity_type,
                "aliases": {existing_name}, "source_chunk_ids": {chunk_id},
            }
            self.conn.commit()
            cur.close()
            return new_id

        elif match and match["match_type"].startswith("fuzzy"):
            # 模糊匹配：合并到已有实体，添加别名
            eid = match["id"]
            chunk_ids = match.get("source_chunk_ids", set())
            chunk_ids.add(chunk_id)
            aliases = match.get("aliases", set())
            aliases.add(name)
            cur.execute(
                """UPDATE kg_entities
                   SET source_chunk_ids = %s, aliases = %s, updated_at = NOW()
                   WHERE id = %s""",
                (list(chunk_ids), list(aliases), eid),
            )
            # 更新缓存
            if name not in self._cache:
                self._cache[name] = self._cache.get(
                    next(k for k, v in self._cache.items() if v["id"] == eid),
                    match
                )
            self.conn.commit()
            cur.close()
            return eid

        else:
            # 完全新实体
            cur.execute(
                """INSERT INTO kg_entities (name, entity_type, category, definition,
                   chapter_ref, source_chunk_ids, importance)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (name, entity_type) DO UPDATE
                   SET source_chunk_ids = kg_entities.source_chunk_ids || EXCLUDED.source_chunk_ids,
                       updated_at = NOW()
                   RETURNING id""",
                (name, entity_type, category, definition, chapter_ref,
                 [chunk_id], importance),
            )
            new_id = cur.fetchone()[0]
            self._cache[name] = {
                "id": new_id, "entity_type": entity_type,
                "aliases": set(), "source_chunk_ids": {chunk_id},
            }
            self.conn.commit()
            cur.close()
            return new_id

    def upsert_relationship(self, source_id: int, target_id: int,
                            relation_type: str, description: str,
                            formula: str = None, confidence: float = 0.5,
                            chunk_id: int = None) -> bool:
        """插入关系（去重）"""
        cur = self.conn.cursor()
        try:
            cur.execute(
                """INSERT INTO kg_relationships
                   (source_entity_id, target_entity_id, relation_type,
                    description, formula, confidence, source_chunk_ids)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (source_entity_id, target_entity_id, relation_type)
                   DO UPDATE SET
                     description = EXCLUDED.description,
                     confidence = GREATEST(kg_relationships.confidence, EXCLUDED.confidence),
                     source_chunk_ids = kg_relationships.source_chunk_ids || EXCLUDED.source_chunk_ids""",
                (source_id, target_id, relation_type, description,
                 formula, confidence, [chunk_id] if chunk_id else []),
            )
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            self.conn.rollback()
            cur.close()
            return False

    def insert_formula(self, entity_id: int, formula_data: dict,
                       chunk_id: int) -> bool:
        """插入公式"""
        cur = self.conn.cursor()
        try:
            cur.execute(
                """INSERT INTO kg_formulas
                   (entity_id, name, expression, inputs, output, conditions, example, source_chunk_ids)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (entity_id,
                 formula_data.get("name", ""),
                 formula_data.get("expression", ""),
                 formula_data.get("inputs", []),
                 formula_data.get("output", ""),
                 formula_data.get("conditions", ""),
                 formula_data.get("example", ""),
                 [chunk_id]),
            )
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            self.conn.rollback()
            cur.close()
            return False

    def insert_confusion_pair(self, a_id: int, b_id: int,
                              pair_data: dict) -> bool:
        """插入易混概念对"""
        if a_id == b_id:
            return False
        # 保证顺序一致
        if a_id > b_id:
            a_id, b_id = b_id, a_id
        cur = self.conn.cursor()
        try:
            cur.execute(
                """INSERT INTO kg_confusion_pairs
                   (entity_a_id, entity_b_id, distinction, typical_question,
                    scenario_a, scenario_b)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (entity_a_id, entity_b_id) DO UPDATE SET
                     distinction = EXCLUDED.distinction,
                     typical_question = COALESCE(EXCLUDED.typical_question, kg_confusion_pairs.typical_question)""",
                (a_id, b_id,
                 pair_data.get("distinction", ""),
                 pair_data.get("typical_question", ""),
                 pair_data.get("scenario_a", ""),
                 pair_data.get("scenario_b", "")),
            )
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            self.conn.rollback()
            cur.close()
            return False

    def resolve_entity_id(self, name: str) -> Optional[int]:
        """根据名称查找实体ID"""
        if name in self._cache:
            return self._cache[name]["id"]
        # 尝试在数据库中搜索
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM kg_entities WHERE name = %s", (name,))
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None
