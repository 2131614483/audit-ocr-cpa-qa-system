"""
仅验证语义分块效果，不涉及任何数据库操作
读取 content_list.json，用 semantic_chunk_text 分块后统计长度分布
"""
import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from json_import_cpa import semantic_chunk_text, parse_content_list

# 选几本有代表性的教材测试
test_books = [
    "会计轻一（上册） (OCR)",
    "审计轻一（上册） (OCR)",
    "财管轻一（上册） (OCR)",
    "2026年注册会计师（会计）官方教材",
]

json_dir = Path(__file__).parent / "cpazs" / "json格式"

all_stats = {}

for book_name in test_books:
    json_path = json_dir / f"{book_name}_content_list.json"
    if not json_path.exists():
        print(f"❌ 找不到: {json_path.name}")
        continue

    print(f"\n{'='*60}")
    print(f"📖 {book_name}")
    print(f"{'='*60}")

    chunks = parse_content_list(json_path)
    print(f"  章节块数: {len(chunks)}")

    # 对每个章节块应用语义分块
    all_sub_chunks = []
    chunk_sizes = []
    for ch in chunks:
        content = ch.get("content", "")
        if len(content) < 50:
            continue
        sub_chunks = semantic_chunk_text(content, min_size=200, max_size=800)
        sub_chunks = [sc for sc in sub_chunks if len(sc) >= 50]
        for sc in sub_chunks:
            all_sub_chunks.append(sc)
            chunk_sizes.append(len(sc))

    if not chunk_sizes:
        print("  ⚠️ 没有生成子块")
        continue

    # 统计
    total = len(chunk_sizes)
    min_size = min(chunk_sizes)
    max_size = max(chunk_sizes)
    avg_size = sum(chunk_sizes) / total

    # 分布统计
    ranges = [
        (0, 100), (100, 200), (200, 300), (300, 400),
        (400, 500), (500, 600), (600, 700), (700, 800),
        (800, 1000), (1000, 99999)
    ]
    dist = {}
    for lo, hi in ranges:
        label = f"{lo}-{hi}" if hi < 99999 else f"{lo}+"
        cnt = sum(1 for s in chunk_sizes if lo <= s < hi)
        if cnt > 0:
            dist[label] = cnt

    print(f"  总块数: {total}")
    print(f"  最短: {min_size}字符")
    print(f"  最长: {max_size}字符")
    print(f"  平均: {avg_size:.0f}字符")
    print(f"  分布:")
    for label, cnt in sorted(dist.items()):
        bar = "█" * max(1, cnt * 40 // total)
        print(f"    {label:>10}: {cnt:>4}块 {bar}")

    # 显示几个示例
    print(f"\n  示例块:")
    for i, sc in enumerate(all_sub_chunks[:3]):
        preview = sc[:100].replace("\n", " ")
        print(f"    [{len(sc):>4}字符] {preview}...")

    all_stats[book_name] = {
        "total": total,
        "min": min_size,
        "max": max_size,
        "avg": avg_size,
        "dist": dist,
    }

print(f"\n\n{'='*60}")
print("📊 汇总对比")
print(f"{'='*60}")
print(f"{'教材名':<30} {'总块数':>6} {'最短':>5} {'最长':>5} {'平均':>5}")
print("-" * 60)
for name, st in all_stats.items():
    short = name[:28]
    print(f"{short:<30} {st['total']:>6} {st['min']:>5} {st['max']:>5} {st['avg']:>5.0f}")