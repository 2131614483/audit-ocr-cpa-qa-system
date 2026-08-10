"""
CPA知识库导入工具 - 支持分批导入和断点续传
用法: 
  python import_cpa_knowledge.py              # 全部导入
  python import_cpa_knowledge.py --batch 1    # 导入第1批
  python import_cpa_knowledge.py --course KJ  # 只导入会计科目
"""

# ============================================================
# CPA 知识库数据导入工具
# 功能: 将教材 Markdown 文件解析为结构化章节数据，
#       导入到 cpa_courses/cpa_books/cpa_chapters 表
# 注意: 此脚本为旧版导入方式，新版使用 import_all_cpa_8b.py
# ============================================================

import os
import sys
import re
import json
import hashlib
import psycopg2
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config_cpa import DB_CONFIG, DATA_SOURCES, CHUNK_CONFIG, EMBEDDING_CONFIG
import requests
import time

def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    return conn

def get_local_embedding(text: str) -> list | None:
    """使用本地 Ollama 获取 embedding"""
    if not text or not text.strip():
        return None
    
    model = EMBEDDING_CONFIG.get("model", "nomic-embed-text")
    api_url = EMBEDDING_CONFIG.get("api_url", "http://localhost:11434/api/embeddings")
    
    payload = {"model": model, "prompt": text.strip()}
    for retry in range(3):
        try:
            r = requests.post(api_url, json=payload, timeout=120)
            r.raise_for_status()
            data = r.json()
            if "embedding" in data:
                return data["embedding"]
            if "embeddings" in data and len(data["embeddings"]) > 0:
                return data["embeddings"][0]
            raise ValueError(f"响应中无embedding: {data}")
        except Exception as e:
            if retry < 2:
                time.sleep(3)
                continue
            print(f"  ⚠️ Ollama embedding失败: {str(e)}")
            return None

def init_schema(conn):
    print("📦 初始化数据库Schema...")
    with open(Path(__file__).parent / "schema.sql", "r", encoding="utf-8") as f:
        schema_sql = f.read()

    cur = conn.cursor()
    statements = schema_sql.split(';')
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt or stmt.startswith('--'):
            continue
        if 'CREATE TABLE' in stmt or 'INSERT INTO' in stmt or 'CREATE INDEX' in stmt:
            try:
                cur.execute(stmt)
            except Exception as e:
                if "already exists" not in str(e):
                    pass
    conn.commit()
    print("  ✅ Schema初始化完成")

def parse_markdown_content(md_text: str) -> list[dict]:
    chunks = []
    lines = md_text.split("\n")

    current_chapter = {"number": "", "title": "", "content": ""}
    current_section = {"title": "", "content": ""}
    content_buffer = []

    # 更宽松的正则表达式：允许#前后有空格，章节标题可以出现在行中任何位置
    chapter_pattern = re.compile(r"(?:^|\s)#\s*(第[一二三四五六七八九十百千\d]+章[^\n]*)")
    section_pattern = re.compile(r"(?:^|\s)##\s*([^\n]+)")

    def flush_content():
        nonlocal content_buffer
        if content_buffer:
            content = "\n".join(content_buffer).strip()
            if content:
                return {
                    "type": "content",
                    "content": content,
                    "chapter": current_chapter["number"],
                    "section": current_section["title"]
                }
        return None

    for line in lines:
        line = line.rstrip()

        chapter_match = chapter_pattern.match(line)
        if chapter_match:
            chunk = flush_content()
            if chunk:
                chunks.append(chunk)

            title = chapter_match.group(1).strip()
            num_match = re.search(r"第([一二三四五六七八九十百千\d]+)章", title)
            current_chapter = {
                "number": num_match.group(1) if num_match else "",
                "title": re.sub(r"第[一二三四五六七八九十百千\d]+章", "", title).strip(),
                "content": ""
            }
            current_section = {"title": "", "content": ""}
            content_buffer = []
            continue

        section_match = section_pattern.match(line)
        if section_match:
            chunk = flush_content()
            if chunk:
                chunks.append(chunk)

            current_section = {"title": section_match.group(1).strip(), "content": ""}
            content_buffer = []
            continue

        if line.strip():
            content_buffer.append(line)
        elif content_buffer:
            chunk = flush_content()
            if chunk:
                chunks.append(chunk)
            content_buffer = []

    final_chunk = flush_content()
    if final_chunk:
        chunks.append(final_chunk)

    return chunks

def create_chunks(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        if start > 0:
            start = max(0, start - overlap)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end

    return chunks

def get_batch_sources(batch_num, batch_size=3):
    """按批次获取数据源"""
    start = (batch_num - 1) * batch_size
    end = start + batch_size
    return DATA_SOURCES[start:end]

def get_course_sources(course_code):
    """获取指定科目的数据源"""
    return [src for src in DATA_SOURCES if src["course_code"] == course_code]

def import_cpa_knowledge(sources=None):
    print("=" * 60)
    print("📚 CPA知识库导入工具")
    print("=" * 60)

    if sources is None:
        sources = DATA_SOURCES
        print(f"🎯 导入全部 {len(sources)} 本教材")
    else:
        print(f"🎯 导入 {len(sources)} 本教材")

    conn = get_db_connection()
    init_schema(conn)

    cur = conn.cursor()
    total_imported = 0
    failed_files = []

    for source in sources:
        md_path = Path(__file__).parent / source["path"]

        if not md_path.exists():
            print(f"\n❌ 路径不存在: {md_path}")
            failed_files.append(source["book_name"])
            continue

        md_files = list(md_path.glob("*_noimg.md"))
        if not md_files:
            md_files = list(md_path.glob("*.md"))
        if not md_files:
            print(f"\n❌ 未找到MD文件: {md_path}")
            failed_files.append(source["book_name"])
            continue

        for md_file in md_files:
            print(f"\n📖 处理文件: {md_file.name}")

            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    md_content = f.read()
            except Exception as e:
                print(f"  ❌ 读取文件失败: {e}")
                failed_files.append(source["book_name"])
                continue

            cur.execute("SELECT id FROM cpa_courses WHERE course_code = %s", (source["course_code"],))
            course_row = cur.fetchone()
            if not course_row:
                print(f"  ❌ 未知科目代码: {source['course_code']}")
                failed_files.append(source["book_name"])
                continue
            course_id = course_row[0]

            cur.execute("""
                INSERT INTO cpa_books (course_id, book_name, book_type, md_file_path, publish_year)
                VALUES (%s, %s, %s, %s, 2026)
                ON CONFLICT DO NOTHING
                RETURNING id
            """, (course_id, source["book_name"], source["book_type"], str(md_file)))
            book_result = cur.fetchone()
            if not book_result:
                cur.execute("SELECT id FROM cpa_books WHERE book_name = %s", (source["book_name"],))
                book_result = cur.fetchone()
            book_id = book_result[0]
            print(f"  ✅ 教材ID: {book_id}")

            chunks = parse_markdown_content(md_content)
            print(f"  📝 解析出 {len(chunks)} 个内容块")

            for chunk in chunks:
                chapter_num = chunk.get("chapter", "")
                chapter_num_db = chapter_num.replace("第", "").replace("章", "")

                cur.execute("""
                    INSERT INTO cpa_chapters (book_id, chapter_number, chapter_title, md_content, content_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (book_id, chapter_number) DO UPDATE
                    SET md_content = EXCLUDED.md_content
                    RETURNING id
                """, (
                    book_id,
                    chapter_num_db,
                    chunk.get("section", chunk.get("chapter", "")),
                    chunk.get("content", ""),
                    hashlib.md5(chunk.get("content", "").encode()).hexdigest()
                ))
                chapter_result = cur.fetchone()
                chapter_id = chapter_result[0]

                content = chunk.get("content", "")
                if len(content) > CHUNK_CONFIG["min_chunk_length"]:
                    text_chunks = create_chunks(
                        content,
                        CHUNK_CONFIG["chunk_size"],
                        CHUNK_CONFIG["chunk_overlap"]
                    )

                    for idx, text_chunk in enumerate(text_chunks):
                        try:
                            embedding_list = get_local_embedding(text_chunk)
                            if embedding_list and isinstance(embedding_list, list):
                                import numpy as np
                                embedding_bytes = np.array(embedding_list, dtype=np.float32).tobytes()
                            else:
                                embedding_bytes = None
                        except Exception as e:
                            print(f"  ⚠️ 向量生成失败: {e}")
                            embedding_bytes = None

                        metadata = {
                            "course_code": source["course_code"],
                            "book_name": source["book_name"],
                            "chapter": chapter_num,
                            "chunk_index": idx,
                            "source_file": md_file.name
                        }

                        cur.execute("""
                            INSERT INTO cpa_embeddings (
                                source_type, source_id, chunk_content, embedding, metadata
                            )
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            "chapter_chunk",
                            chapter_id,
                            text_chunk,
                            psycopg2.Binary(embedding_bytes) if embedding_bytes else None,
                            json.dumps(metadata)
                        ))

                        total_imported += 1

                        if total_imported % 50 == 0:
                            conn.commit()
                            print(f"    已导入 {total_imported} 个文本块...")

            conn.commit()
            print(f"  ✅ 完成: 累计 {total_imported} 个文本块")

    print("\n" + "=" * 60)
    print(f"🎉 导入完成！共导入 {total_imported} 个文本块")
    if failed_files:
        print(f"⚠️ 失败 {len(failed_files)} 个文件: {failed_files}")
    print("=" * 60)

    cur.execute("SELECT course_name, COUNT(*) FROM cpa_books b JOIN cpa_courses c ON b.course_id = c.id GROUP BY course_name")
    for row in cur.fetchall():
        print(f"  📚 {row[0]}: {row[1]} 本教材")

    cur.execute("SELECT COUNT(*) FROM cpa_chapters")
    print(f"  📖 章节数: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM cpa_embeddings")
    print(f"  🔢 向量记录: {cur.fetchone()[0]}")

    conn.close()

if __name__ == "__main__":
    sources = None
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--batch":
            if len(sys.argv) > 2:
                batch_num = int(sys.argv[2])
                print(f"📦 导入第 {batch_num} 批教材")
                sources = get_batch_sources(batch_num)
        elif sys.argv[1] == "--course":
            if len(sys.argv) > 2:
                course_code = sys.argv[2]
                print(f"📚 导入科目: {course_code}")
                sources = get_course_sources(course_code)
    
    import_cpa_knowledge(sources)