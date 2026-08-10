"""
CPA知识图谱 — 批量构建脚本
============================================================
用法:
  python knowledge/build_kg.py --book "会计" --limit 100
  python knowledge/build_kg.py --book "审计" --stage entities
  python knowledge/build_kg.py --all --concurrent 5
  python knowledge/build_kg.py --stage community

独立运行，从 cpa_knowledge 只读查询chunk，写入 cpa_knowledge_graph。
============================================================
"""

import argparse
import sys
import io
import json
import os
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 控制台输出强制 UTF-8（os.environ.setdefault 对已初始化的 stdout 无效，必须用 reconfigure）
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from services.kg_extractor import KnowledgeGraphExtractor
from services.kg_entity_linker import EntityLinker

# ============================================================
# 数据库配置
# ============================================================

SOURCE_DB = {
    "host": "localhost", "port": 5432,
    "dbname": "cpa_knowledge",
    "user": "postgres", "password": "admin",
}

GRAPH_DB = {
    "host": "localhost", "port": 5432,
    "dbname": "cpa_knowledge_graph",
    "user": "postgres", "password": "admin",
}


def get_source_conn():
    return psycopg2.connect(**SOURCE_DB)


def get_graph_conn():
    return psycopg2.connect(**GRAPH_DB)


# ============================================================
# 构建逻辑
# ============================================================

def parse_chapter_info(metadata: dict) -> str:
    """从metadata JSONB提取章节信息"""
    if not metadata:
        return "未知"
    parts = []
    if metadata.get("course"):
        parts.append(metadata["course"])
    if metadata.get("book"):
        parts.append(metadata["book"])
    if metadata.get("heading_path"):
        parts.append(metadata["heading_path"])
    elif metadata.get("chapter"):
        parts.append(metadata["chapter"])
    return " > ".join(parts) if parts else "未知"


def fetch_chunks(book_filter: str = None, limit: int = None,
                 offset: int = 0) -> list[dict]:
    """从 cpa_knowledge.cpa_embeddings 读取chunk"""
    conn = get_source_conn()
    cur = conn.cursor()

    if book_filter:
        cur.execute("""
            SELECT id, chunk_content, chunk_summary, metadata
            FROM cpa_embeddings
            WHERE metadata->>'book' LIKE %s
            ORDER BY id
            LIMIT %s OFFSET %s
        """, (f"%{book_filter}%", limit or 1000, offset))
    else:
        cur.execute("""
            SELECT id, chunk_content, chunk_summary, metadata
            FROM cpa_embeddings
            ORDER BY id
            LIMIT %s OFFSET %s
        """, (limit or 1000, offset))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    chunks = []
    for row in rows:
        meta = row[3]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}

        chunks.append({
            "id": row[0],
            "content": row[1],
            "summary": row[2] or "",
            "metadata": meta,
            "chapter_info": parse_chapter_info(meta),
        })
    return chunks


def process_single_chunk(extractor: KnowledgeGraphExtractor,
                         chunk: dict, stages: set) -> dict:
    """处理单个chunk"""
    chunk_id = chunk["id"]
    try:
        result = extractor.process_chunk(
            chunk["content"],
            chapter_info=chunk["chapter_info"],
            stages=stages,
        )
        return {"chunk_id": chunk_id, "success": True, **result}
    except Exception as e:
        return {"chunk_id": chunk_id, "success": False, "error": str(e)}


def build_graph(book_filter: str = None, limit: int = None,
                offset: int = 0, concurrent: int = 3,
                stages: set = None):
    """
    主构建流程
    """
    if stages is None:
        stages = {"entities", "relationships", "formulas", "confusions"}

    print("=" * 60)
    print("   CPA 知识图谱构建")
    print(f"   教材范围: {book_filter or '全部'}")
    print(f"   处理限制: {limit or '无限制'}")
    print(f"   并发数:   {concurrent}")
    print(f"   阶段:     {', '.join(stages)}")
    print("=" * 60)

    # 创建构建日志
    graph_conn = get_graph_conn()
    cur = graph_conn.cursor()
    cur.execute(
        """INSERT INTO kg_build_log (build_type, status, book_filter)
           VALUES ('entity_extraction', 'running', %s) RETURNING id""",
        (book_filter,),
    )
    build_id = cur.fetchone()[0]
    graph_conn.commit()
    cur.close()

    # 加载实体索引
    linker = EntityLinker(graph_conn)
    linker.load_existing()

    # 读取chunk
    print("\n📖 读取教材chunk...")
    chunks = fetch_chunks(book_filter, limit, offset)
    print(f"   共获取 {len(chunks)} 个chunk")

    if not chunks:
        print("   ⚠️ 没有找到匹配的chunk，请检查教材名称筛选条件")
        return

    # 逐chunk处理
    extractor = KnowledgeGraphExtractor()
    stats = {
        "entities_created": 0,
        "entities_updated": 0,
        "relations_created": 0,
        "formulas_created": 0,
        "confusion_pairs_created": 0,
        "chunks_processed": 0,
        "chunks_failed": 0,
    }
    start_time = time.time()

    print(f"\n🔄 开始处理（{'并发' if concurrent > 1 else '顺序'}模式）...")

    if concurrent > 1:
        # 并发模式
        with ThreadPoolExecutor(max_workers=concurrent) as pool:
            futures = {
                pool.submit(process_single_chunk, extractor, chunk, stages): chunk
                for chunk in chunks
            }
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                _persist_result(result, linker, stats)
                if (i + 1) % 10 == 0 or (i + 1) == len(chunks):
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    print(f"  进度: {i+1}/{len(chunks)} ({rate:.1f} chunk/s) "
                          f"| 实体:{stats['entities_created']} "
                          f"关系:{stats['relations_created']} "
                          f"易混:{stats['confusion_pairs_created']}")
    else:
        # 顺序模式
        for i, chunk in enumerate(chunks):
            result = process_single_chunk(extractor, chunk, stages)
            _persist_result(result, linker, stats)
            if (i + 1) % 5 == 0 or (i + 1) == len(chunks):
                print(f"  进度: {i+1}/{len(chunks)} "
                      f"| 实体:{stats['entities_created']} "
                      f"关系:{stats['relations_created']}")

    elapsed = time.time() - start_time

    # 更新构建日志
    cur = graph_conn.cursor()
    cur.execute(
        """UPDATE kg_build_log SET
           status = 'completed', chunks_processed = %s,
           entities_created = %s, relations_created = %s,
           formulas_created = %s, confusion_pairs_created = %s,
           finished_at = NOW()
           WHERE id = %s""",
        (stats["chunks_processed"],
         stats["entities_created"], stats["relations_created"],
         stats["formulas_created"], stats["confusion_pairs_created"],
         build_id),
    )
    graph_conn.commit()
    cur.close()
    graph_conn.close()

    # 汇总
    print(f"\n{'='*60}")
    print(f"✅ 构建完成! 耗时 {elapsed:.1f}秒")
    print(f"   处理chunk: {stats['chunks_processed']} (失败 {stats['chunks_failed']})")
    print(f"   新增实体:  {stats['entities_created']}")
    print(f"   更新实体:  {stats['entities_updated']}")
    print(f"   新增关系:  {stats['relations_created']}")
    print(f"   新增公式:  {stats['formulas_created']}")
    print(f"   易混概念:  {stats['confusion_pairs_created']}")
    print(f"{'='*60}")


def _persist_result(result: dict, linker: EntityLinker, stats: dict):
    """将一个chunk的抽取结果写入数据库"""
    if not result.get("success"):
        stats["chunks_failed"] += 1
        return

    chunk_id = result["chunk_id"]
    stats["chunks_processed"] += 1

    # 1. 持久化实体
    entity_id_map = {}  # {entity_name: entity_id}
    for ent in result.get("entities", []):
        eid = linker.upsert_entity(
            name=ent["name"],
            entity_type=ent.get("entity_type", "Concept"),
            category=ent.get("category", "其他"),
            definition=ent.get("definition", ent["name"]),
            chapter_ref=ent.get("chapter_ref", ""),
            chunk_id=chunk_id,
            importance=ent.get("importance", "中"),
        )
        entity_id_map[ent["name"]] = eid
        stats["entities_created"] += 1

    # 2. 持久化关系
    for rel in result.get("relationships", []):
        src_name = rel["source"]
        tgt_name = rel["target"]
        src_id = entity_id_map.get(src_name) or linker.resolve_entity_id(src_name)
        tgt_id = entity_id_map.get(tgt_name) or linker.resolve_entity_id(tgt_name)

        if src_id and tgt_id:
            ok = linker.upsert_relationship(
                source_id=src_id, target_id=tgt_id,
                relation_type=rel["relation_type"],
                description=rel.get("description", ""),
                formula=rel.get("formula"),
                confidence=rel.get("confidence", 0.5),
                chunk_id=chunk_id,
            )
            if ok:
                stats["relations_created"] += 1

    # 3. 持久化公式
    for formula in result.get("formulas", []):
        formula_name = formula.get("name", "")
        eid = entity_id_map.get(formula_name) or linker.resolve_entity_id(formula_name)
        if eid:
            linker.insert_formula(eid, formula, chunk_id)
            stats["formulas_created"] += 1

    # 4. 持久化易混概念对
    for pair in result.get("confusion_pairs", []):
        a_name = pair.get("concept_a", "")
        b_name = pair.get("concept_b", "")
        a_id = entity_id_map.get(a_name) or linker.resolve_entity_id(a_name)
        b_id = entity_id_map.get(b_name) or linker.resolve_entity_id(b_name)
        if a_id and b_id:
            linker.insert_confusion_pair(a_id, b_id, pair)
            stats["confusion_pairs_created"] += 1


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CPA知识图谱构建工具")
    parser.add_argument("--book", type=str, default=None,
                        help="教材名称筛选（如 '会计'）")
    parser.add_argument("--all", action="store_true",
                        help="处理全部教材")
    parser.add_argument("--limit", type=int, default=None,
                        help="限制处理的chunk数量（用于测试）")
    parser.add_argument("--offset", type=int, default=0,
                        help="偏移量")
    parser.add_argument("--concurrent", type=int, default=3,
                        help="并发数（默认3）")
    parser.add_argument("--stage", type=str, default="all",
                        choices=["all", "entities", "relationships", "formulas", "confusions", "community"],
                        help="处理阶段（默认all）")

    args = parser.parse_args()

    if not args.book and not args.all:
        print("❌ 请指定 --book \"教材名\" 或 --all")
        print("   示例: python knowledge/build_kg.py --book \"会计\" --limit 100")
        sys.exit(1)

    stages = {"entities", "relationships", "formulas", "confusions"}
    if args.stage != "all":
        stages = {args.stage}

    build_graph(
        book_filter=args.book if not args.all else None,
        limit=args.limit,
        offset=args.offset,
        concurrent=args.concurrent,
        stages=stages,
    )
