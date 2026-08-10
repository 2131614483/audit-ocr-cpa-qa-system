"""智谱API单张图片测试：分类+提取+JSON输出"""
import sys, os, time, json, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['PYTHONUNBUFFERED'] = '1'

from config.settings import set_provider
set_provider("zhipu")

from pic_claw.agent1_classify import classify_single_image
from pic_claw.agent2_extract import extract_single_image
from pic_claw.pipeline_db import get_extracted_fields
import psycopg2, psycopg2.extras

OUTPUT_DIR = Path(__file__).parent / "test_output_zhipu"
OUTPUT_DIR.mkdir(exist_ok=True)

conn = psycopg2.connect(host='localhost', port=5432, dbname='audit_pipeline_db', user='postgres', password='admin')

# 取1张待测试图片
with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
    cur.execute("""
        SELECT id, file_path, file_name, doc_type_name, category_name
        FROM voucher_images
        WHERE batch_id = 4 AND classify_status = 'pending'
        ORDER BY id
        LIMIT 1
    """)
    img = cur.fetchone()
    if img:
        img = dict(img)
    else:
        print("没有待处理的图片")
        conn.close()
        sys.exit(0)

conn.close()

print("=" * 70)
print("🚀 智谱API单张测试")
print(f"📄 {img['file_name']}")
print(f"   真实类型: {img['doc_type_name']} ({img['category_name']})")
print("=" * 70)

# ---- Agent1 分类 ----
print(f"\n🤖 Agent1 分类中...")
t1 = time.time()
cls_result = classify_single_image(img["id"], img["file_path"], img["file_name"])
t_cls = time.time() - t1

if cls_result["status"] == "done":
    print(f"✅ 分类: {cls_result['type_name']} (置信度: {cls_result['confidence']:.0%}) [{t_cls:.1f}s]")
else:
    print(f"❌ 分类失败: {cls_result.get('error', '')[:80]}")
    sys.exit(1)

# ---- Agent2 提取 ----
print(f"\n🔍 Agent2 提取中...")
t2 = time.time()
ext_result = extract_single_image(
    img["id"], img["file_path"], img["file_name"],
    img["doc_type_name"], img["category_name"]
)
t_ext = time.time() - t2

fields = []
if ext_result["status"] == "done":
    fields = get_extracted_fields(img["id"])
    print(f"✅ 提取: {ext_result['extracted_count']}个字段 [{t_ext:.1f}s]")
else:
    print(f"❌ 提取失败: {ext_result.get('error', '')[:80]}")

# ---- 构建JSON输出 ----
output_json = {
    "file_name": img["file_name"],
    "file_path": img["file_path"],
    "real_type": img["doc_type_name"],
    "real_category": img["category_name"],
    "classify_result": {
        "type_name": cls_result.get("type_name"),
        "confidence": cls_result.get("confidence"),
        "duration_ms": cls_result.get("duration_ms"),
        "status": cls_result.get("status")
    },
    "extract_result": {
        "status": ext_result.get("status"),
        "extracted_count": ext_result.get("extracted_count"),
        "duration_ms": ext_result.get("duration_ms"),
        "fields": {f["field_name"]: f["field_value"] for f in fields}
    },
    "is_correct": cls_result.get("type_name") == img["doc_type_name"]
}

# ---- 复制图片到输出目录 ----
src_path = Path(img['file_path'])
if src_path.exists():
    cls_name = cls_result.get('type_name', 'unknown')
    match_tag = "CORRECT" if output_json["is_correct"] else "WRONG"
    new_name = f"{cls_name}_{match_tag}{src_path.suffix}"
    dst_path = OUTPUT_DIR / new_name
    shutil.copy2(str(src_path), str(dst_path))
    output_json["output_image_path"] = str(dst_path)

# ---- 输出JSON ----
print(f"\n{'=' * 70}")
print("📋 JSON输出:")
print("=" * 70)
print(json.dumps(output_json, ensure_ascii=False, indent=2))

# 保存JSON文件
json_path = OUTPUT_DIR / f"{cls_name}_{match_tag}.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(output_json, f, ensure_ascii=False, indent=2)
print(f"\n💾 JSON已保存: {json_path}")
print(f"📁 输出目录: {OUTPUT_DIR}")