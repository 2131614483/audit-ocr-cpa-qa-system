# ============================================================
# 审计知识库 - 全量导入工具
# 功能: 将所有 Markdown 知识库文件解析并导入到数据库
# 用法: python knowledge/import_all_knowledge.py
# ============================================================

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import re
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import psycopg2
import psycopg2.extras
from datetime import datetime

from services.embedding_service import get_embedding

DB = {"host": "localhost", "port": 5432, "dbname": "audit_ocr", "user": "postgres", "password": "admin"}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FILES = [
    "审计凭证OCR智能识别与审验知识库.md",
    "审计凭证OCR——全类别凭证风险评估手册.md",
    "audit_knowledge_base.json",
    "发票校验规则库.md",
    "凭证类型识别指南.md",
    "金额转换规则库.md",
]


def parse_md_to_chunks(filepath: str, source_name: str) -> list[dict]:
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # 按一级标题拆分（一、二、三... 或 ##, ###）
    chunks = []
    lines = text.split("\n")

    current_section = "概述"
    current_subsection = ""
    current_content = []
    current_risk_level = "中"
    seq = 0

    def flush():
        nonlocal seq
        if current_content:
            content = "\n".join(current_content).strip()
            if len(content) > 30:
                # 如果内容太长，再按段落拆
                if len(content) > 600:
                    paras = [p.strip() for p in content.split("\n\n") if p.strip()]
                    para_group = []
                    char_count = 0
                    for p in paras:
                        if char_count + len(p) > 500 and para_group:
                            seq += 1
                            title = f"{current_section} / {current_subsection}" if current_subsection else current_section
                            chunks.append({
                                "category": source_name.replace(".md", "").replace("——", "-"),
                                "rule_id": f"MD-{seq:03d}",
                                "rule_name": title,
                                "section_title": title,
                                "content": "\n\n".join(para_group),
                                "risk_level": current_risk_level,
                                "source": source_name,
                            })
                            para_group = [p]
                            char_count = len(p)
                        else:
                            para_group.append(p)
                            char_count += len(p)
                    if para_group:
                        seq += 1
                        title = f"{current_section} / {current_subsection}" if current_subsection else current_section
                        chunks.append({
                            "category": source_name.replace(".md", "").replace("——", "-"),
                            "rule_id": f"MD-{seq:03d}",
                            "rule_name": title,
                            "section_title": title,
                            "content": "\n\n".join(para_group),
                            "risk_level": current_risk_level,
                            "source": source_name,
                        })
                else:
                    seq += 1
                    title = f"{current_section} / {current_subsection}" if current_subsection else current_section
                    chunks.append({
                        "category": source_name.replace(".md", "").replace("——", "-"),
                        "rule_id": f"MD-{seq:03d}",
                        "rule_name": title,
                        "section_title": title,
                        "content": content,
                        "risk_level": current_risk_level,
                        "source": source_name,
                    })

            elif content:
                seq += 1
                title = f"{current_section} / {current_subsection}" if current_subsection else current_section
                chunks.append({
                    "category": source_name.replace(".md", "").replace("——", "-"),
                    "rule_id": f"MD-{seq:03d}",
                    "rule_name": title,
                    "section_title": title,
                    "content": content,
                    "risk_level": current_risk_level,
                    "source": source_name,
                })

    h1_pattern = re.compile(r"^[一二三四五六七八九十]+、")
    h2_pattern = re.compile(r"^（[一二三四五六七八九十]+）")
    risk_pattern = re.compile(r"风险等级[：:]([🔴🟡🟢]?)(高|中|低)风险")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 检测风险等级
        risk_match = risk_pattern.search(stripped)
        if risk_match:
            level = risk_match.group(2)
            current_risk_level = level

        # 新的一级标题
        if h1_pattern.match(stripped) or stripped.startswith("## "):
            flush()
            current_section = stripped.replace("## ", "").strip()
            current_subsection = ""
            current_content = []
            continue

        # 新的二级标题
        if h2_pattern.match(stripped) or stripped.startswith("### "):
            flush()
            current_subsection = stripped.replace("### ", "").strip()
            current_content = []
            continue

        current_content.append(stripped)

    flush()
    return chunks


def parse_json_to_chunks(filepath: str) -> list[dict]:
    import json
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = []
    for cat in data.get("categories", []):
        category = cat["category"]
        for rule in cat.get("rules", []):
            chunks.append({
                "category": category,
                "rule_id": rule.get("id", "N/A"),
                "rule_name": rule.get("name", "N/A"),
                "section_title": f"{rule['id']} {rule['name']}",
                "content": rule["content"],
                "risk_level": rule.get("risk_level", "中"),
                "source": os.path.basename(filepath),
            })
    return chunks


# ===== 清空旧数据 =====
conn = psycopg2.connect(**DB)
conn.autocommit = True
cur = conn.cursor()
cur.execute("DELETE FROM knowledge_base")
print("✅ 旧知识库已清空")

all_chunks = []

# 解析 .md 文件
for fname in FILES:
    fpath = os.path.join(BASE_DIR, fname)
    if not os.path.exists(fpath):
        print(f"⚠️ 文件不存在，跳过: {fname}")
        continue

    if fname.endswith(".json"):
        chunks = parse_json_to_chunks(fpath)
    else:
        chunks = parse_md_to_chunks(fpath, fname)

    print(f"📄 {fname}: 解析出 {len(chunks)} 个段落")
    all_chunks.extend(chunks)

print(f"\n📊 共 {len(all_chunks)} 个段落，开始生成向量...")

# ===== 入库 =====
success = 0
fail = 0
batch_size = 3  # 每批3条，避免embedding耗时过长

for i, chunk in enumerate(all_chunks):
    embed_text = f"{chunk['category']} - {chunk['section_title']}: {chunk['content']}"
    print(f"  [{i+1}/{len(all_chunks)}] {chunk['section_title'][:40]:40s} ... ", end="", flush=True)

    if i > 0 and i % batch_size == 0:
        print()

    embedding = get_embedding(embed_text)

    cur.execute("""
        INSERT INTO knowledge_base (category, rule_id, rule_name, section_title, content, risk_level, source, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::double precision[])
    """, (
        chunk["category"],
        chunk.get("rule_id", "N/A"),
        chunk.get("rule_name", "N/A"),
        chunk["section_title"],
        chunk["content"],
        chunk["risk_level"],
        chunk["source"],
        "{" + ",".join(str(x) for x in embedding) + "}" if embedding else None,
    ))
    success += 1
    print("✅")

print(f"\n{'='*50}")
print(f"✅ 入库完成！")
print(f"   总段落: {success} 条")
print(f"   来源: {len(FILES)} 个文件")

cur.close()
conn.close()
