"""智谱API测试：10张图片全流程（分类+提取+导出）"""
import sys, os, time, json, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['PYTHONUNBUFFERED'] = '1'

from config.settings import set_provider
set_provider("zhipu")

from pic_claw.agent1_classify import classify_single_image
from pic_claw.agent2_extract import extract_single_image
from pic_claw.pipeline_db import get_extracted_fields, insert_pipeline_log
import psycopg2, psycopg2.extras

OUTPUT_DIR = Path(__file__).parent / "test_output_zhipu"
OUTPUT_DIR.mkdir(exist_ok=True)

conn = psycopg2.connect(host='localhost', port=5432, dbname='audit_pipeline_db', user='postgres', password='admin')

# 取前10张不同类别的图片
with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
    cur.execute("""
        SELECT id, file_path, file_name, doc_type_name, category_name
        FROM voucher_images
        WHERE batch_id = 4
        ORDER BY id
        LIMIT 10
    """)
    images = [dict(r) for r in cur.fetchall()]
conn.close()

print("=" * 70)
print("🚀 智谱API全流程测试（10张）")
print(f"  模型: GLM-4.6V-FlashX")
print("=" * 70)

for i, img in enumerate(images, 1):
    print(f"\n{'─' * 70}")
    print(f"[{i}/10] 📄 {img['file_name']}")
    print(f"       真实类型: {img['doc_type_name']} ({img['category_name']})")
    print(f"{'─' * 70}")

    # ---- Agent1 分类 ----
    print(f"  🤖 Agent1 分类中...")
    t1 = time.time()
    cls_result = classify_single_image(img["id"], img["file_path"], img["file_name"])
    t_cls = time.time() - t1

    is_correct = "✅" if cls_result["status"] == "done" and cls_result["type_name"] == img["doc_type_name"] else "⚠️"
    if cls_result["status"] == "done":
        print(f"  {is_correct} 分类: {cls_result['type_name']} (置信度: {cls_result['confidence']:.0%}) [{cls_result['duration_ms']/1000:.1f}s]")
    else:
        print(f"  ❌ 分类失败: {cls_result.get('error', '')[:80]}")
        continue

    # ---- Agent2 提取 ----
    print(f"  🔍 Agent2 提取中...")
    t2 = time.time()
    ext_result = extract_single_image(
        img["id"], img["file_path"], img["file_name"],
        img["doc_type_name"], img["category_name"]
    )
    t_ext = time.time() - t2

    fields = []
    if ext_result["status"] == "done":
        fields = get_extracted_fields(img["id"])
        print(f"  ✅ 提取: {ext_result['extracted_count']}个字段 [{ext_result['duration_ms']/1000:.1f}s]")
        for f in fields:
            print(f"       • {f['field_name']}: {f['field_value']}")
    else:
        print(f"  ❌ 提取失败: {ext_result.get('error', '')[:80]}")

    # ---- 复制图片到输出目录并标注 ----
    src_path = Path(img['file_path'])
    if src_path.exists():
        # 构建标注文件名
        cls_name = cls_result.get('type_name', 'unknown') if cls_result['status'] == 'done' else 'failed'
        cls_conf = f"{cls_result.get('confidence', 0):.0%}" if cls_result['status'] == 'done' else '0%'
        ext_count = ext_result.get('extracted_count', 0) if ext_result['status'] == 'done' else 0
        match_tag = "CORRECT" if is_correct == "✅" else "WRONG"

        # 新文件名：序号_真实类型_分类结果_置信度_提取字段数_匹配标签.扩展名
        new_name = f"{i:02d}_{img['doc_type_name']}_{cls_name}_{cls_conf}_{ext_count}f_{match_tag}{src_path.suffix}"
        dst_path = OUTPUT_DIR / new_name
        shutil.copy2(str(src_path), str(dst_path))
        print(f"  💾 已保存: {new_name}")

# ---- 汇总 ----
print(f"\n\n{'=' * 70}")
print("📊 测试汇总")
print("=" * 70)

conn = psycopg2.connect(host='localhost', port=5432, dbname='audit_pipeline_db', user='postgres', password='admin')
with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
    cur.execute("""
        SELECT vi.id, vi.file_name, vi.doc_type_name, vi.category_name,
               vi.classify_status, vi.classify_confidence,
               vi.extract_status
        FROM voucher_images vi
        WHERE vi.batch_id = 4 AND vi.classify_status = 'done'
        ORDER BY vi.id
        LIMIT 10
    """)
    results = cur.fetchall()

    correct = 0
    total = len(results)
    for r in results:
        match = "✅" if r['doc_type_name'] == '（待分类）' else "✓"
        print(f"  {r['file_name']}")
        print(f"    真实: {r['doc_type_name']} | 分类: {r['classify_status']} | 提取: {r['extract_status']}")

conn.close()

print(f"\n输出目录: {OUTPUT_DIR}")
print(f"文件列表:")
for f in sorted(OUTPUT_DIR.iterdir()):
    print(f"  {f.name}")
print(f"\n{'=' * 70}")
print("✅ 测试完成")
print(f"{'=' * 70}")