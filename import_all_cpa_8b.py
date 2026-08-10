"""
CPA知识库一键导入脚本 - 8b 版本
功能：导入23本教材，向量化(4096维,10并发)，metadata+摘要
"""

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import os
import sys
import time
import re
import json
import asyncio
import requests
import psycopg2
from psycopg2.extras import execute_values
import threading
from pathlib import Path
import aiohttp

progress_lock = threading.Lock()
processed_count = 0

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cpazs.config_cpa import DB_CONFIG, DATA_SOURCES, CHUNK_CONFIG, EMBEDDING_CONFIG

EMBEDDING_CONFIG = EMBEDDING_CONFIG.copy()
EMBEDDING_CONFIG["model"] = "qwen3-embedding:8b"
EMBEDDING_CONFIG["dimension"] = 4096

def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn

def init_courses(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM cpa_courses")
    if cur.fetchone()[0] == 0:
        print("📝 初始化科目数据...")
        courses = [
            ('KJ', '会计', 'Accounting', '会计专业知识', '最高'),
            ('SJ', '审计', 'Auditing', '审计专业知识', '较高'),
            ('SF', '税法', 'Tax Law', '税法专业知识', '中等'),
            ('CW', '财务成本管理', 'Financial Management', '财务管理专业知识', '中等'),
            ('JJ', '经济法', 'Economic Law', '经济法专业知识', '较低'),
            ('ZZ', '公司战略与风险管理', 'Business Strategy', '战略管理专业知识', '较低'),
        ]
        for course in courses:
            cur.execute("""
                INSERT INTO cpa_courses (course_code, course_name, course_name_en, description, exam_weight)
                VALUES (%s, %s, %s, %s, %s)
            """, course)
        conn.commit()
        print("  ✅ 科目数据初始化完成")

async def async_get_embedding(session, text, model, api_url):
    if not text or not text.strip():
        return None
    payload = {"model": model, "prompt": text.strip()}
    for retry in range(3):
        try:
            async with session.post(api_url, json=payload, timeout=120) as response:
                if response.status == 200:
                    data = await response.json()
                    if "embedding" in data:
                        return data["embedding"]
                    if "embeddings" in data and len(data["embeddings"]) > 0:
                        return data["embeddings"][0]
        except Exception:
            if retry < 2:
                await asyncio.sleep(1)
                continue
    return None

async def batch_get_embeddings(text_chunks, max_concurrent=10, verbose=False):
    model = EMBEDDING_CONFIG["model"]
    api_url = EMBEDDING_CONFIG["api_url"]

    global processed_count
    processed_count = 0
    chunk_count = len(text_chunks)

    async with aiohttp.ClientSession() as session:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_limit(idx, text):
            async with semaphore:
                embedding = await async_get_embedding(session, text, model, api_url)
                global processed_count
                with progress_lock:
                    processed_count += 1
                    if verbose and (processed_count % 100 == 0 or processed_count == chunk_count):
                        print(f"  ⚡ 并发处理 {processed_count}/{chunk_count} ({processed_count*100//chunk_count}%)")
                if embedding and isinstance(embedding, list):
                    embedding_vector = '[' + ','.join(map(str, embedding)) + ']'
                    return {'idx': idx, 'text': text, 'vector': embedding_vector}
                return None

        tasks = [process_with_limit(i, chunk) for i, chunk in enumerate(text_chunks)]
        results = await asyncio.gather(*tasks)

    return [r for r in results if r is not None]

def create_chunks(text, chunk_size=600, overlap=100):
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

def parse_markdown_content(md_text):
    chunks = []
    lines = md_text.split("\n")

    current_chapter = {"number": "", "title": ""}
    current_section = {"title": ""}
    content_buffer = []

    chapter_pattern = re.compile(r"(?:^|\s)#\s*(第[一二三四五六七八九十百千\d]+章[^\n]*)")
    section_pattern = re.compile(r"(?:^|\s)##\s*([^\n]+)")

    def flush_content():
        nonlocal content_buffer
        if content_buffer:
            content = "\n".join(content_buffer).strip()
            cleaned = re.sub(r'【图片：[^\]]+】', '', content)
            cleaned = re.sub(r'\$\$[^$]*\$\$', '', cleaned)
            cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
            if len(cleaned) >= 50:
                return {
                    "type": "content",
                    "content": cleaned,
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
                "title": re.sub(r"第[一二三四五六七八九十百千\d]+章", "", title).strip()
            }
            current_section = {"title": ""}
            content_buffer = []
            continue

        section_match = section_pattern.match(line)
        if section_match:
            chunk = flush_content()
            if chunk:
                chunks.append(chunk)
            current_section = {"title": section_match.group(1).strip()}
            content_buffer = []
            continue

        if line.strip():
            content_buffer.append(line)

    final_chunk = flush_content()
    if final_chunk:
        chunks.append(final_chunk)

    return chunks

def import_cpa_knowledge(sources=None):
    print("=" * 60)
    print("📚 CPA知识库一键导入工具")
    print("=" * 60)

    if sources is None:
        sources = DATA_SOURCES
        print(f"🎯 导入全部 {len(sources)} 本教材")
    else:
        print(f"🎯 导入 {len(sources)} 本教材")

    conn = get_db_connection()
    cur = conn.cursor()

    init_courses(conn)

    total_imported = 0
    failed_files = []

    for source in sources:
        md_path = Path(__file__).parent / "cpazs" / source["path"]

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

            cur.execute("""
                SELECT bk.book_name, co.course_name 
                FROM cpa_books bk 
                JOIN cpa_courses co ON bk.course_id = co.id 
                WHERE bk.id = %s
            """, (book_id,))
            book_info = cur.fetchone()
            book_name = book_info[0] if book_info else source["book_name"]
            course_name = book_info[1] if book_info else source["course_code"]

            all_pending = []
            for chunk in chunks:
                chapter_num = chunk.get("chapter", "")
                section_title = chunk.get("section", "")
                content = chunk.get("content", "")
                if len(content) < CHUNK_CONFIG["min_chunk_length"]:
                    continue

                cur.execute("""
                    INSERT INTO cpa_chapters (book_id, chapter_number, chapter_title, md_content, content_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (book_id, chapter_number) DO UPDATE SET md_content = EXCLUDED.md_content
                    RETURNING id
                """, (book_id, chapter_num, section_title, content, hash(content) % (10**8)))
                chapter_result = cur.fetchone()
                if chapter_result:
                    chapter_id = chapter_result[0]
                    text_chunks = create_chunks(content, CHUNK_CONFIG["chunk_size"], CHUNK_CONFIG["chunk_overlap"])
                    text_chunks = [tc for tc in text_chunks if len(tc) >= 50]
                    if text_chunks:
                        heading_path = section_title if section_title else chapter_num
                        all_pending.append((chapter_id, text_chunks, chapter_num, section_title, heading_path))

            total_chunks = sum(len(tc) for _, tc, _, _, _ in all_pending)
            print(f"  📚 收集 {len(all_pending)} 个章节，共 {total_chunks} 个文本块，开始异步向量化（10并发）...")

            flat_texts = []
            mapping = []
            for chapter_id, text_chunks, chapter_num, section_title, heading_path in all_pending:
                for tc in text_chunks:
                    flat_texts.append(tc)
                    mapping.append((chapter_id, chapter_num, section_title, heading_path))

            flat_results = asyncio.run(batch_get_embeddings(flat_texts, max_concurrent=10, verbose=True))
            flat_results.sort(key=lambda x: x['idx'])
            print(f"  ✅ 向量化完成，成功 {len(flat_results)}/{total_chunks} 个")

            print(f"  📥 开始导入数据库（每1000条批量写入）...")
            batch_rows = []
            for i, result in enumerate(flat_results):
                idx = result['idx']
                chapter_id, chapter_num, section_title, heading_path = mapping[idx]
                content_text = result['text'][:2000]

                text_for_summary = content_text.replace('\n', ' ').strip()
                sentences = re.split(r'(?<=[。！？])', text_for_summary)
                summary_parts = []
                for sent in sentences:
                    sent = sent.strip()
                    if len(sent) < 5:
                        continue
                    summary_parts.append(sent)
                    combined = ''.join(summary_parts)
                    if len(combined) >= 80:
                        break
                summary = ''.join(summary_parts) if summary_parts else text_for_summary[:80]
                if len(summary) > 150:
                    summary = summary[:150]

                meta = json.dumps({
                    "course": course_name,
                    "book": book_name,
                    "chapter": chapter_num,
                    "section": section_title,
                    "heading_path": heading_path,
                    "source_file": md_file.name
                }, ensure_ascii=False)

                batch_rows.append(('chapter_chunk', chapter_id, content_text, summary, meta, result['vector']))

                if len(batch_rows) >= 1000:
                    execute_values(cur, """
                        INSERT INTO cpa_embeddings (source_type, source_id, chunk_content, chunk_summary, metadata, embedding)
                        VALUES %s
                    """, batch_rows)
                    conn.commit()
                    total_imported += len(batch_rows)
                    print(f"  🔢 已导入 {total_imported} 个向量")
                    batch_rows = []

            if batch_rows:
                execute_values(cur, """
                    INSERT INTO cpa_embeddings (source_type, source_id, chunk_content, chunk_summary, metadata, embedding)
                    VALUES %s
                """, batch_rows)
                conn.commit()
                total_imported += len(batch_rows)
                print(f"  🔢 已导入 {total_imported} 个向量")

    print("\n" + "=" * 60)
    print(f"🎉 导入完成！共导入 {total_imported} 个文本块")
    if failed_files:
        print(f"⚠️ 失败 {len(failed_files)} 个文件: {failed_files}")

    cur.execute("SELECT COUNT(*) FROM cpa_books")
    book_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM cpa_chapters")
    chap_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM cpa_embeddings")
    emb_count = cur.fetchone()[0]

    print(f"\n📊 最终统计:")
    print(f"  📖 教材数: {book_count}")
    print(f"  📑 章节数: {chap_count}")
    print(f"  🔢 向量记录: {emb_count}")

    conn.close()

if __name__ == "__main__":
    try:
        r = requests.post(
            EMBEDDING_CONFIG["api_url"],
            json={"model": EMBEDDING_CONFIG["model"], "prompt": "test"}
        )
        r.raise_for_status()
        data = r.json()
        if "embedding" in data:
            print(f"✅ Ollama连接成功 (模型: {EMBEDDING_CONFIG['model']})")
        else:
            print("❌ Ollama响应格式异常")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 无法连接Ollama: {e}")
        sys.exit(1)

    if len(sys.argv) > 1:
        if sys.argv[1] == "--batch":
            batch_num = int(sys.argv[2])
            batch_size = 3
            start = (batch_num - 1) * batch_size
            end = start + batch_size
            sources = DATA_SOURCES[start:end]
            import_cpa_knowledge(sources)
        elif sys.argv[1] == "--course":
            course_code = sys.argv[2]
            sources = [src for src in DATA_SOURCES if src["course_code"] == course_code]
            import_cpa_knowledge(sources)
        else:
            print("未知参数")
    else:
        import_cpa_knowledge()
