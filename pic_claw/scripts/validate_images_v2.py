#!/usr/bin/env python3
"""
审计票据图片校验 & 清洗管道 (v2 — 优化版)
快速校验 + 精确重复检测，避免 O(n^2) 瓶颈
"""

import os
import sys
import json
import argparse
import hashlib
from pathlib import Path
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from PIL import Image, ImageStat
import warnings
warnings.filterwarnings("ignore")


def compute_phash(img, hash_size=8):
    """感知哈希 — 8x8=64bit，快速且够用"""
    try:
        small = img.convert("L").resize((hash_size, hash_size), Image.LANCZOS)
        pixels = list(small.getdata())
        avg = sum(pixels) / len(pixels)
        bits = 0
        for p in pixels:
            bits = (bits << 1) | (1 if p > avg else 0)
        return bits  # 返回整数，比较更快
    except Exception:
        return None


def md5_file(filepath, chunk_size=8192):
    """计算文件 MD5 — 用于精确重复检测"""
    try:
        h = hashlib.md5()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def validate_single_image(filepath, config):
    """单图校验 — 返回结果 dict"""
    result = {
        "path": filepath,
        "filename": Path(filepath).name,
        "valid": True,
        "issues": [],
        "width": 0, "height": 0,
        "file_size_kb": 0,
        "variance": 0.0,
        "phash": None,
        "md5": None,
        "aspect_ratio": 0.0,
    }

    # 1. 文件大小
    try:
        file_size = os.path.getsize(filepath)
        result["file_size_kb"] = round(file_size / 1024, 2)
    except OSError:
        result["valid"] = False
        result["issues"].append("文件不可读")
        return result

    if file_size < config["min_file_kb"] * 1024:
        result["valid"] = False
        result["issues"].append(f"文件过小({result['file_size_kb']}KB)")

    # 2. PIL 打开 & 损坏检测
    try:
        with Image.open(filepath) as img:
            img.verify()
    except Exception as e:
        result["valid"] = False
        result["issues"].append(f"图片损坏({type(e).__name__})")
        return result

    # 3. 重新加载做内容分析
    try:
        with Image.open(filepath) as img:
            img.load()
            w, h = img.size
            result["width"] = w
            result["height"] = h
            result["aspect_ratio"] = round(w / h, 3) if h > 0 else 0

            # 尺寸检查
            if w < config["min_dimension"] or h < config["min_dimension"]:
                result["valid"] = False
                result["issues"].append(f"尺寸过小({w}x{h})")

            # 宽高比
            ar = result["aspect_ratio"]
            if ar > 0 and (ar > config["max_aspect_ratio"] or ar < config["min_aspect_ratio"]):
                result["valid"] = False
                result["issues"].append(f"宽高比异常({ar})")

            # 方差 — 信息量
            try:
                gray = img.convert("L")
                stat = ImageStat.Stat(gray)
                var = stat.var[0] if stat.var else 0
                result["variance"] = round(var, 2)
                if var < config["min_variance"]:
                    result["valid"] = False
                    result["issues"].append(f"信息量低(方差={var:.0f})")
            except Exception:
                result["variance"] = -1

            # 感知哈希
            try:
                result["phash"] = compute_phash(img.copy())
            except Exception:
                pass

    except Exception as e:
        result["valid"] = False
        result["issues"].append(f"加载失败({type(e).__name__})")
        return result

    # 4. MD5 (用于精确重复检测，只对有效图片算)
    if result["valid"]:
        result["md5"] = md5_file(filepath)

    return result


def run_validation(image_dir, config, max_workers=8):
    """并行校验所有图片"""
    image_dir = Path(image_dir)
    # 用 os.scandir 获取唯一文件，避免 Windows 大小写重复
    valid_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    all_images = []
    seen_paths = set()
    for entry in os.scandir(image_dir):
        if entry.is_file():
            ext = Path(entry.name).suffix.lower()
            if ext in valid_exts:
                real = os.path.realpath(entry.path)
                if real not in seen_paths:
                    seen_paths.add(real)
                    all_images.append(entry.path)

    total = len(all_images)
    print(f"[INFO] {total} images found, validating...")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(validate_single_image, str(p), config): str(p) for p in all_images}
        done = 0
        for fut in as_completed(futures):
            done += 1
            if done % 1000 == 0 or done == total:
                print(f"  [{done}/{total}] {done*100//total}%")
            try:
                results.append(fut.result())
            except Exception as e:
                results.append({
                    "path": futures[fut], "filename": Path(futures[fut]).name,
                    "valid": False, "issues": [f"异常:{e}"],
                    "width": 0, "height": 0, "file_size_kb": 0,
                    "variance": 0, "phash": None, "md5": None, "aspect_ratio": 0,
                })

    # --- 精确重复检测 (MD5) ---
    print("[INFO] Detecting exact duplicates (MD5)...")
    md5_map = defaultdict(list)
    for r in results:
        if r["md5"]:
            md5_map[r["md5"]].append(r)

    exact_dupe_count = 0
    for md5, group in md5_map.items():
        if len(group) > 1:
            # 保留第一个，标记其余
            for r in group[1:]:
                r["valid"] = False
                r["issues"].append(f"MD5重复(同{group[0]['filename']})")
                exact_dupe_count += 1

    # --- 感知哈希近似重复 (仅对有效图片，用哈希桶加速) ---
    print("[INFO] Detecting near-duplicates (pHash buckets)...")
    phash_map = defaultdict(list)
    for r in results:
        if r["valid"] and r["phash"] is not None:
            # 用高16位做桶，减少比较量
            bucket = r["phash"] >> 48
            phash_map[bucket].append(r)

    near_dupe_count = 0
    for bucket, group in phash_map.items():
        if len(group) < 2:
            continue
        # 桶内两两比较
        seen = set()
        for i in range(len(group)):
            if id(group[i]) in seen:
                continue
            for j in range(i + 1, len(group)):
                if id(group[j]) in seen:
                    continue
                # 汉明距离
                diff = bin(group[i]["phash"] ^ group[j]["phash"]).count("1")
                if diff < config["duplicate_threshold"]:
                    group[j]["valid"] = False
                    group[j]["issues"].append(f"近似重复(同{group[i]['filename']})")
                    seen.add(id(group[j]))
                    near_dupe_count += 1

    print(f"[INFO] Duplicates: exact={exact_dupe_count}, near={near_dupe_count}")
    return results


def generate_report(results, output_dir, config):
    """生成校验报告"""
    output_dir = Path(output_dir)
    total = len(results)
    valid = [r for r in results if r["valid"]]
    invalid = [r for r in results if not r["valid"]]

    # 问题统计
    issue_stats = Counter()
    for r in invalid:
        for issue in r["issues"]:
            cat = issue.split("(")[0].strip()
            issue_stats[cat] += 1

    # 类别统计
    cat_stats = defaultdict(lambda: {"total": 0, "valid": 0, "invalid": 0})
    for r in results:
        parts = r["filename"].rsplit("_", 1)
        cat = parts[0] if len(parts) > 1 else "未知"
        cat_stats[cat]["total"] += 1
        if r["valid"]:
            cat_stats[cat]["valid"] += 1
        else:
            cat_stats[cat]["invalid"] += 1

    # 有效图统计
    widths = [r["width"] for r in valid if r["width"] > 0]
    heights = [r["height"] for r in valid if r["height"] > 0]
    sizes = [r["file_size_kb"] for r in valid if r["file_size_kb"] > 0]

    report = {
        "summary": {
            "total": total,
            "valid": len(valid),
            "invalid": len(invalid),
            "valid_rate": f"{len(valid)*100/total:.1f}%" if total else "0%",
        },
        "issue_breakdown": dict(issue_stats.most_common()),
        "valid_stats": {
            "width_range": f"{min(widths)}-{max(widths)}" if widths else "N/A",
            "height_range": f"{min(heights)}-{max(heights)}" if heights else "N/A",
            "avg_size_kb": round(sum(sizes)/len(sizes), 1) if sizes else 0,
        },
        "category_stats": {c: s for c, s in sorted(cat_stats.items())},
        "invalid_list": [
            {"file": r["filename"], "issues": r["issues"],
             "size_kb": r["file_size_kb"], "dim": f"{r['width']}x{r['height']}"}
            for r in invalid
        ],
    }

    # JSON 报告
    with open(output_dir / "validation_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # TXT 报告
    with open(output_dir / "validation_report.txt", "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("  审计票据图片校验报告\n")
        f.write("=" * 60 + "\n\n")
        f.write("【总体概况】\n")
        f.write(f"  总图片:   {total}\n")
        f.write(f"  有效:     {len(valid)} ({report['summary']['valid_rate']})\n")
        f.write(f"  无效:     {len(invalid)}\n\n")
        f.write("【问题分布】\n")
        for issue, cnt in issue_stats.most_common():
            f.write(f"  {issue}: {cnt}\n")
        f.write("\n")
        f.write("【有效图片统计】\n")
        if valid:
            f.write(f"  尺寸: {report['valid_stats']['width_range']} x {report['valid_stats']['height_range']}\n")
            f.write(f"  均值: {report['valid_stats']['avg_size_kb']}KB\n")
        f.write("\n")
        f.write("【问题类别 (invalid > 0)】\n")
        f.write(f"  {'类别':<30} {'总':>5} {'有效':>5} {'无效':>5} {'率':>7}\n")
        f.write(f"  {'-'*30} {'-'*5} {'-'*5} {'-'*5} {'-'*7}\n")
        for c, s in sorted(cat_stats.items(), key=lambda x: -x[1]["invalid"]):
            if s["invalid"] > 0:
                rate = f"{s['valid']*100/s['total']:.0f}%"
                f.write(f"  {c:<30} {s['total']:>5} {s['valid']:>5} {s['invalid']:>5} {rate:>7}\n")
        f.write("\n")
        f.write("【无效图片清单 (前300条)】\n")
        for i, item in enumerate(report["invalid_list"][:300]):
            f.write(f"  {i+1}. {item['file']} | {'; '.join(item['issues'])} | {item['dim']} | {item['size_kb']}KB\n")
        if len(invalid) > 300:
            f.write(f"  ... +{len(invalid)-300} more (see bad_images_list.txt)\n")

    # 问题清单
    with open(output_dir / "bad_images_list.txt", "w", encoding="utf-8") as f:
        f.write(f"# Bad images: {len(invalid)}\n")
        f.write(f"# file\tissues\tdimensions\tsize_kb\n")
        for r in invalid:
            f.write(f"{r['filename']}\t{'; '.join(r['issues'])}\t{r['width']}x{r['height']}\t{r['file_size_kb']}\n")

    return report


def clean_jsonl_files(dataset_dir, invalid_paths, output_dir):
    """清洗 JSONL — 移除无效图片对应的条目"""
    dataset_dir = Path(dataset_dir)
    output_dir = Path(output_dir)
    invalid_set = set(Path(p).name for p in invalid_paths)

    stats = {}
    for split in ["train", "val"]:
        src = dataset_dir / f"{split}.jsonl"
        if not src.exists():
            continue
        dst = output_dir / f"{split}_clean.jsonl"
        orig = kept = removed = 0
        with open(src, "r", encoding="utf-8") as fin, open(dst, "w", encoding="utf-8") as fout:
            for line in fin:
                orig += 1
                try:
                    entry = json.loads(line.strip())
                    img_name = Path(entry.get("image", "")).name
                    if img_name in invalid_set:
                        removed += 1
                        continue
                    fout.write(line)
                    kept += 1
                except json.JSONDecodeError:
                    removed += 1
        stats[split] = {"original": orig, "kept": kept, "removed": removed}
        print(f"  {split}: {orig} -> {kept} kept, {removed} removed")
    return stats


def main():
    parser = argparse.ArgumentParser(description="审计票据图片校验管道 v2")
    parser.add_argument("--dataset_dir", required=True)
    parser.add_argument("--output_dir", default=None)
    parser.add_argument("--min_dimension", type=int, default=100)
    parser.add_argument("--min_file_kb", type=float, default=3.0)
    parser.add_argument("--min_variance", type=float, default=50.0)
    parser.add_argument("--min_aspect_ratio", type=float, default=0.2)
    parser.add_argument("--max_aspect_ratio", type=float, default=8.0)
    parser.add_argument("--duplicate_threshold", type=int, default=5)
    parser.add_argument("--max_workers", type=int, default=8)
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    output_dir = Path(args.output_dir) if args.output_dir else dataset_dir
    image_dir = dataset_dir / "images"

    config = {
        "min_dimension": args.min_dimension,
        "min_file_kb": args.min_file_kb,
        "min_variance": args.min_variance,
        "min_aspect_ratio": args.min_aspect_ratio,
        "max_aspect_ratio": args.max_aspect_ratio,
        "duplicate_threshold": args.duplicate_threshold,
    }

    print("=" * 60)
    print("  审计票据图片校验管道 v2")
    print(f"  Dataset: {dataset_dir}")
    print(f"  Config:  {json.dumps(config)}")
    print("=" * 60)

    results = run_validation(image_dir, config, args.max_workers)
    report = generate_report(results, str(output_dir), config)

    invalid_paths = [r["path"] for r in results if not r["valid"]]
    if (dataset_dir / "train.jsonl").exists():
        print("\n[CLEAN] Cleaning JSONL...")
        clean_jsonl_files(str(dataset_dir), invalid_paths, str(output_dir))

    valid_cnt = len([r for r in results if r["valid"]])
    print(f"\n{'='*60}")
    print(f"  DONE! Valid: {valid_cnt} / {len(results)}")
    print(f"  Report: {output_dir}/validation_report.txt")
    print(f"  Clean:  {output_dir}/train_clean.jsonl")
    print(f"          {output_dir}/val_clean.jsonl")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
