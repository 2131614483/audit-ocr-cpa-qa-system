"""
CPA知识库 - JSON格式导入脚本
读取 content_list.json（无图片噪音、有page_idx、type分离）
替代基于MD文件的 import_all_cpa_8b.py
"""

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import os
import sys
import json
import time
import re
import asyncio
import requests
import psycopg2
from psycopg2.extras import execute_values
import threading
import aiohttp
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cpazs.config_cpa import DB_CONFIG, DATA_SOURCES, CHUNK_CONFIG

EMBED_CONFIG = {
    "model": "qwen3-embedding:8b",
    "dimension": 4096,
    "api_url": "http://localhost:11434/api/embeddings"
}

progress_lock = threading.Lock()
processed_count = 0

# ==================== 工具函数 ====================

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def get_json_path(source):
    book_key = source["path"].split("/")[0]
    json_dir = Path(__file__).parent / "cpazs" / "json格式"
    # 精确匹配
    exact = json_dir / f"{book_key}_content_list.json"
    if exact.exists():
        return exact
    # 容错：尝试去空格匹配（文件名中(OCR)前可能没有空格）
    alt_key = book_key.replace(" ", "")
    alt = json_dir / f"{alt_key}_content_list.json"
    if alt.exists():
        return alt
    return exact  # 返回不存在的路径，由调用方处理

def get_md_path(source):
    return Path(__file__).parent / "cpazs" / "md格式"

# ==================== 从 content_list.json 解析章节结构 ====================

CHAPTER_PATTERN = re.compile(r"^(?:第[一二三四五六七八九十百千\d]+章|附录)")
SECTION_PATTERN = re.compile(r"^第[一二三四五六七八九十百千\d]+节")
SUBSECTION_PATTERN = re.compile(r"^[一二三四五六七八九十]+[、．.]")
SUBSUBSECTION_PATTERN = re.compile(r"^（[一二三四五六七八九十百千\d]+）")

def semantic_chunk_text(text, min_size=200, max_size=800):
    """语义分块：按段落/句子边界切割，保持语义完整"""
    if len(text) <= max_size:
        return [text]

    # 先按段落拆分
    paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip() and len(p.strip()) >= 10]

    chunks = []
    current = ""

    for para in paragraphs:
        # 单个段落超过 max_size，按句子切分
        if len(para) > max_size:
            if current:
                chunks.append(current)
                current = ""
            sentences = re.split(r"(?<=[。！？；])", para)
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                if len(sent) > max_size:
                    if current:
                        chunks.append(current)
                        current = ""
                    chunks.append(sent)
                elif len(current) + len(sent) > max_size:
                    if current:
                        chunks.append(current)
                    current = sent
                else:
                    current += sent
            continue

        # 段落不长，尝试合并
        if not current:
            current = para
        elif len(current) + len(para) <= max_size:
            current += "\n" + para
        else:
            if len(current) >= min_size:
                chunks.append(current)
            else:
                if chunks:
                    chunks[-1] += "\n" + current
                else:
                    chunks.append(current)
            current = para

    if current:
        if len(current) >= min_size:
            chunks.append(current)
        elif chunks:
            chunks[-1] += "\n" + current
        else:
            chunks.append(current)

    return chunks


def is_garbage_content(text):
    """判断是否为垃圾内容（广告、纯数学符号等）"""
    # 轻一教材的"解锁章节"广告
    if "恭喜您解锁新章节" in text:
        return True
    # "听作者好课"推广短内容
    if "听作者好课" in text and len(text) < 150:
        return True
    # 以"（STEP1）听作者好课"开头的纯广告
    if text.startswith("（STEP1）听作者好课") or text.startswith("免费（STEP1）听作者好课"):
        return True
    # 含STEP推广且内容极短
    if "STEP" in text and len(text) < 150:
        return True
    # 纯数学符号/公式（无中文字符）
    if len(text) > 0:
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        if chinese_chars == 0 and len(text) < 100:
            return True
        # 中文字符占比太低
        if len(text) >= 20 and chinese_chars / max(len(text), 1) < 0.1:
            return True
    return False


def parse_content_list(json_path):
    """从 content_list.json 解析为章节结构列表"""
    with open(json_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    # 预处理：把包含多个节标题的 item 拆分为独立 item
    processed = []
    for item in items:
        if item.get("type") != "text":
            processed.append(item)
            continue
        text = item.get("text", "")
        sections = re.split(r"(?=第[一二三四五六七八九十百千\d]+节\s)", text)
        if len(sections) > 1:
            for sec in sections:
                if sec.strip():
                    processed.append({"type": "text", "text": sec.strip(), "text_level": item.get("text_level"), "page_idx": item.get("page_idx")})
        else:
            processed.append(item)

    chunks = []
    current_chapter = ""
    current_section = ""
    current_subsection = ""
    buffer = []
    buffer_start_page = None
    buffer_types = set()

    def flush():
        nonlocal buffer
        if not buffer:
            return None
        text = "".join(buffer).strip()
        if len(text) < 50:
            buffer = []
            return None
        chunk = {
            "chapter": current_chapter,
            "section": current_section,
            "subsection": current_subsection,
            "content": re.sub(r"\n{3,}", "\n\n", text).strip(),
            "page_start": buffer_start_page,
            "has_table": "table" in buffer_types,
            "has_equation": "equation" in buffer_types
        }
        buffer = []
        buffer_types.clear()
        return chunk

    for item in processed:
        if item.get("type") != "text":
            buffer_types.add(item.get("type", ""))
            continue

        text = item.get("text", "").strip()
        if not text:
            continue

        page = item.get("page_idx")

        if CHAPTER_PATTERN.match(text):
            chunk = flush()
            if chunk:
                chunks.append(chunk)
            current_chapter = re.sub(r"\s*\d*\s*$", "", text).strip()
            current_section = ""
            current_subsection = ""
            buffer_start_page = page
            buffer_types.clear()
            buffer = [text + "\n"]
            continue

        if SECTION_PATTERN.match(text):
            chunk = flush()
            if chunk:
                chunks.append(chunk)
            current_section = text.strip()
            current_subsection = ""
            buffer_start_page = page
            buffer_types.clear()
            buffer = [text + "\n"]
            continue

        if SUBSECTION_PATTERN.match(text):
            chunk = flush()
            if chunk:
                chunks.append(chunk)
            current_subsection = text.strip()[:60]
            buffer_start_page = page
            buffer_types.clear()
            buffer = [text + "\n"]
            continue

        if buffer_start_page is None:
            buffer_start_page = page
        buffer.append(text + "\n")

    chunk = flush()
    if chunk:
        chunks.append(chunk)

    return chunks

# ==================== 向量化 ====================

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

async def batch_embeddings(texts, max_concurrent=10, verbose=False):
    global processed_count
    processed_count = 0
    total = len(texts)

    async with aiohttp.ClientSession() as session:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def work(idx, text):
            async with semaphore:
                emb = await async_get_embedding(session, text, EMBED_CONFIG["model"], EMBED_CONFIG["api_url"])
                global processed_count
                with progress_lock:
                    processed_count += 1
                    n = processed_count
                    if verbose and (n % 50 == 0 or n == total):
                        print(f"    向量化 {n}/{total} ({n*100//total}%)")
                if emb and isinstance(emb, list):
                    return {"idx": idx, "text": text, "vector": '[' + ','.join(map(str, emb)) + ']'}
                return None

        tasks = [work(i, t) for i, t in enumerate(texts)]
        results = await asyncio.gather(*tasks)

    return [r for r in results if r is not None]

# ==================== 主导入函数 ====================

def import_from_json(sources=None):
    print("=" * 60)
    print("📚 CPA知识库导入工具 - JSON模式")
    print("=" * 60)

    if sources is None:
        sources = DATA_SOURCES
        print(f"🎯 导入全部 {len(sources)} 本教材")
    else:
        print(f"🎯 导入 {len(sources)} 本教材")

    conn = get_db()
    cur = conn.cursor()

    total_imported = 0
    failed = []

    for source in sources:
        book_name = source["book_name"]
        json_path = get_json_path(source)

        # 检查JSON是否存在
        if not json_path.exists():
            print(f"\n⚠️ JSON不存在: {json_path.name}，尝试MD回退...")
            md_path = get_md_path(source)
            md_files = list(md_path.glob("*_noimg.md")) or list(md_path.glob("*.md"))
            if not md_files:
                print(f"  ❌ 无MD文件可用")
                failed.append(book_name)
                continue
            print(f"  ⚠️ 使用MD回退: {md_files[0].name}")

        print(f"\n📖 {book_name}")
        chunks = parse_content_list(json_path) if json_path.exists() else []

        # MD回退：调用旧解析逻辑
        if not chunks and json_path.exists():
            pass  # JSON解析成功但为空
        elif not json_path.exists():
            # 从MD解析
            md_path = get_md_path(source)
            md_files = list(md_path.glob("*_noimg.md")) or list(md_path.glob("*.md"))
            if md_files:
                from import_all_cpa_8b import parse_markdown_content as md_parse
                with open(md_files[0], "r", encoding="utf-8") as f:
                    md_content = f.read()
                md_chunks = md_parse(md_content)
                for mc in md_chunks:
                    chunks.append({
                        "chapter": mc.get("chapter", ""),
                        "section": mc.get("section", ""),
                        "subsection": "",
                        "content": mc.get("content", ""),
                        "page_start": None
                    })
                print(f"  MD解析出 {len(chunks)} 个内容块")

        print(f"  JSON解析出 {len(chunks)} 个内容块")

        if not chunks:
            failed.append(book_name)
            continue

        # 2. 获取/创建教材记录
        cur.execute("SELECT id FROM cpa_courses WHERE course_code = %s", (source["course_code"],))
        course = cur.fetchone()
        if not course:
            failed.append(book_name)
            continue
        course_id = course[0]

        cur.execute("""
            INSERT INTO cpa_books (course_id, book_name, book_type, publish_year)
            VALUES (%s, %s, %s, 2026)
            ON CONFLICT DO NOTHING RETURNING id
        """, (course_id, book_name, source["book_type"]))
        book = cur.fetchone()
        if not book:
            cur.execute("SELECT id FROM cpa_books WHERE book_name = %s", (book_name,))
            book = cur.fetchone()
        book_id = book[0]
        print(f"  教材ID: {book_id}")

        # 3. 获取科目名
        cur.execute("SELECT bk.book_name, co.course_name FROM cpa_books bk JOIN cpa_courses co ON bk.course_id=co.id WHERE bk.id=%s", (book_id,))
        book_name_db, course_name = cur.fetchone()

        # 4. 入库章节
        insert_chunks = []
        for ch in chunks:
            chapter_num = ch["chapter"]
            section_title = ch["section"]
            content = ch["content"]
            if len(content) < 50:
                continue

            cur.execute("""
                INSERT INTO cpa_chapters (book_id, chapter_number, chapter_title, md_content, content_hash)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (book_id, chapter_number) DO UPDATE SET md_content=EXCLUDED.md_content
                RETURNING id
            """, (book_id, (chapter_num or "前言")[:20], (section_title or chapter_num or "前言")[:200], content, hash(content) % (10**8)))
            chapter_result = cur.fetchone()
            if not chapter_result:
                continue
            chapter_id = chapter_result[0]

            text_chunks = []
            if len(content) > 50:
                text_chunks = semantic_chunk_text(content, min_size=300, max_size=700)
                text_chunks = [tc for tc in text_chunks if len(tc) >= 50 and not is_garbage_content(tc)]

            heading_path = f"{chapter_num} > {section_title}" if section_title else chapter_num
            for tc in text_chunks:
                insert_chunks.append((chapter_id, chapter_num, section_title, heading_path, tc))

        total_to_vectorize = len(insert_chunks)
        print(f"  收集 {total_to_vectorize} 个文本块，开始异步向量化...")

        # 5. 向量化
        flat_texts = [c[4][:2000] for c in insert_chunks]
        mapping = [(c[0], c[1], c[2], c[3]) for c in insert_chunks]  # chapter_id, chapter_num, section_title, heading_path

        results = asyncio.run(batch_embeddings(flat_texts, max_concurrent=10, verbose=True))
        results.sort(key=lambda x: x["idx"])
        print(f"  向量化完成: {len(results)}/{total_to_vectorize}")

        # 6. 批量写入DB
        batch_rows = []
        for r in results:
            idx = r["idx"]
            chapter_id, chapter_num, section_title, heading_path = mapping[idx]
            content_text = r["text"]

            summary = re.sub(r"\s+", "", content_text)[:80]

            meta = json.dumps({
                "course": course_name,
                "book": book_name_db,
                "chapter": chapter_num[:50],
                "section": section_title[:100],
                "heading_path": heading_path
            }, ensure_ascii=False)

            batch_rows.append(("chapter_chunk", chapter_id, content_text, summary, meta, r["vector"]))

            if len(batch_rows) >= 1000:
                execute_values(cur, """
                    INSERT INTO cpa_embeddings (source_type, source_id, chunk_content, chunk_summary, metadata, embedding)
                    VALUES %s
                """, batch_rows)
                conn.commit()
                total_imported += len(batch_rows)
                batch_rows = []

        if batch_rows:
            execute_values(cur, """
                INSERT INTO cpa_embeddings (source_type, source_id, chunk_content, chunk_summary, metadata, embedding)
                VALUES %s
            """, batch_rows)
            conn.commit()
            total_imported += len(batch_rows)

        print(f"  ✅ 已导入 {len(results)} 个向量")

    print("\n" + "=" * 60)
    print(f"🎉 完成！共导入 {total_imported} 个向量")
    if failed:
        print(f"⚠️ 失败 {len(failed)}: {failed}")

    cur.execute("SELECT COUNT(*) FROM cpa_books")
    cur.execute("SELECT COUNT(*) FROM cpa_embeddings")
    emb_count = cur.fetchone()[0]
    print(f"  🔢 cpa_embeddings 总计: {emb_count}")

    conn.close()


if __name__ == "__main__":
    # 测试Ollama连接
    try:
        r = requests.post(EMBED_CONFIG["api_url"],
                          json={"model": EMBED_CONFIG["model"], "prompt": "test"}, timeout=10)
        r.raise_for_status()
        print(f"✅ Ollama连接成功 ({EMBED_CONFIG['model']})")
    except Exception as e:
        print(f"❌ Ollama连接失败: {e}")
        sys.exit(1)

    # 选择导入模式
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            sources = DATA_SOURCES[:1]
            import_from_json(sources)
        elif sys.argv[1] == "--course":
            code = sys.argv[2]
            sources = [s for s in DATA_SOURCES if s["course_code"] == code]
            import_from_json(sources)
        elif sys.argv[1] in ("--batch", "--all"):
            import_from_json()
        else:
            print("用法: python json_import_cpa.py [--test|--course KJ|--all]")
    else:
        # 默认先测试一本
        import_from_json(DATA_SOURCES[:1])
