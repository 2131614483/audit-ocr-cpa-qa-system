#!/usr/bin/env python3
"""
审计票据图片校验 & 清洗管道
================================
对 dataset_vlm/images/ 下的所有图片执行多维度校验：
  1. 损坏检测 — PIL 能否正常打开并 decode
  2. 尺寸检测 — 宽或高 < min_dimension 的图片标记为过小
  3. 文件大小 — < min_file_kb 的可能是缩略图/占位图
  4. 内容信息量 — 图像方差过低 = 近似空白/纯色
  5. 重复检测 — 感知哈希(phash) 找近似重复
  6. 宽高比异常 — 排除细长条/正方形小图等非票据形态

输出：
  - validation_report.json  详细报告
  - validation_report.txt   可读摘要
  - train_clean.jsonl       清洗后的训练集
  - val_clean.jsonl         清洗后的验证集
  - bad_images_list.txt     所有问题图片清单（含原因）
"""

import os
import sys
import json
import hashlib
import argparse
from pathlib import Path
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from PIL import Image, ImageStat
    import struct
except ImportError:
    print("[ERROR] 需要 Pillow: pip install Pillow")
    sys.exit(1)


# ============================================================
# 1. 单图校验函数
# ============================================================

def compute_phash(img, hash_size=16):
    """简化版感知哈希 — 不依赖 imagehash 库"""
    try:
        small = img.convert("L").resize((hash_size, hash_size), Image.LANCZOS)
        pixels = list(small.getdata())
        avg = sum(pixels) / len(pixels)
        bits = 0
        for p in pixels:
            bits = (bits << 1) | (1 if p > avg else 0)
        return format(bits, f'0{hash_size * hash_size}b')
    except Exception:
        return None


def hamming_distance(h1, h2):
    """计算两个二进制字符串的汉明距离"""
    if not h1 or not h2 or len(h1) != len(h2):
        return 999
    return sum(c1 != c2 for c1, c2 in zip(h1, h2))


def validate_single_image(filepath, config):
    """
    对单张图片执行所有校验。
    返回 dict: {
        "path": str,
        "valid": bool,
        "issues": [str],
        "width": int,
        "height": int,
        "file_size_kb": float,
        "variance": float,
        "phash": str,
        "aspect_ratio": float,
    }
    """
    result = {
        "path": filepath,
        "valid": True,
        "issues": [],
        "width": 0,
        "height": 0,
        "file_size_kb": 0,
        "variance": 0.0,
        "phash": None,
        "aspect_ratio": 0.0,
    }

    # --- 检查1: 文件是否存在 & 大小 ---
    try:
        file_size = os.path.getsize(filepath)
        result["file_size_kb"] = round(file_size / 1024, 2)
    except OSError:
        result["valid"] = False
        result["issues"].append("文件不可读")
        return result

    if file_size < config["min_file_kb"] * 1024:
        result["valid"] = False
        result["issues"].append(f"文件过小 ({result['file_size_kb']}KB < {config['min_file_kb']}KB)")

    # --- 检查2: PIL 打开 & 损坏检测 ---
    try:
        with Image.open(filepath) as img:
            img.verify()  # 验证文件完整性
    except Exception as e:
        result["valid"] = False
        result["issues"].append(f"图片损坏: {type(e).__name__}")
        return result

    # --- 重新打开（verify 后需要重新打开才能操作） ---
    try:
        with Image.open(filepath) as img:
            img.load()
            width, height = img.size
            result["width"] = width
            result["height"] = height
            result["aspect_ratio"] = round(width / height, 3) if height > 0 else 0

            # --- 检查3: 尺寸 ---
            if width < config["min_dimension"] or height < config["min_dimension"]:
                result["valid"] = False
                result["issues"].append(
                    f"尺寸过小 ({width}x{height} < {config['min_dimension']}px)"
                )

            # --- 检查4: 宽高比异常 ---
            ar = result["aspect_ratio"]
            if ar > 0:
                if ar > config["max_aspect_ratio"] or ar < config["min_aspect_ratio"]:
                    result["valid"] = False
                    result["issues"].append(
                        f"宽高比异常 ({ar}, 正常范围 {config['min_aspect_ratio']}-{config['max_aspect_ratio']})"
                    )

            # --- 检查5: 内容信息量（方差） ---
            try:
                gray = img.convert("L")
                stat = ImageStat.Stat(gray)
                variance = stat.var[0] if stat.var else 0
                result["variance"] = round(variance, 2)

                if variance < config["min_variance"]:
                    result["valid"] = False
                    result["issues"].append(
                        f"内容信息量过低 (方差={variance:.1f} < {config['min_variance']})"
                    )
            except Exception:
                result["variance"] = -1

            # --- 检查6: 感知哈希（用于后续重复检测） ---
            try:
                result["phash"] = compute_phash(img.copy())
            except Exception:
                result["phash"] = None

    except Exception as e:
        result["valid"] = False
        result["issues"].append(f"加载失败: {type(e).__name__}: {e}")
        return result

    return result


# ============================================================
# 2. 批量校验 + 重复检测
# ============================================================

def validate_all_images(image_dir, config, max_workers=8):
    """并行校验所有图片"""
    image_dir = Path(image_dir)
    all_images = []
    for ext in ('*.jpg', '*.jpeg', '*.png', '*.webp', '*.bmp', '*.JPG', '*.JPEG', '*.PNG'):
        all_images.extend(image_dir.glob(ext))

    print(f"[INFO] 发现 {len(all_images)} 张图片，开始校验...")
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {
            executor.submit(validate_single_image, str(p), config): str(p)
            for p in all_images
        }
        done_count = 0
        for future in as_completed(future_to_path):
            done_count += 1
            if done_count % 500 == 0:
                print(f"  进度: {done_count}/{len(all_images)} ({done_count*100//len(all_images)}%)")
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                path = future_to_path[future]
                results.append({
                    "path": path,
                    "valid": False,
                    "issues": [f"处理异常: {e}"],
                    "width": 0, "height": 0,
                    "file_size_kb": 0, "variance": 0,
                    "phash": None, "aspect_ratio": 0,
                })

    print(f"[INFO] 基础校验完成，开始重复检测...")

    # --- 重复检测：感知哈希聚类 ---
    phash_map = defaultdict(list)
    for r in results:
        if r["phash"]:
            phash_map[r["phash"][:64]].append(r["path"])  # 用前64位做粗聚类

    exact_dupes = {h: paths for h, paths in phash_map.items() if len(paths) > 1}
    for h, paths in exact_dupes.items():
        # 保留第一个，标记其余为重复
        for p in paths[1:]:
            for r in results:
                if r["path"] == p:
                    r["valid"] = False
                    r["issues"].append(f"重复图片 (与 {paths[0]} 相同)")

    # --- 近似重复检测（汉明距离 < threshold） ---
    phash_list = [(r["phash"], r["path"]) for r in results if r["phash"]]
    near_dup_groups = []
    checked = set()

    for i, (h1, p1) in enumerate(phash_list):
        if p1 in checked:
            continue
        group = [p1]
        for j, (h2, p2) in enumerate(phash_list):
            if i == j or p2 in checked:
                continue
            dist = hamming_distance(h1, h2)
            if dist < config["duplicate_threshold"]:
                group.append(p2)
                checked.add(p2)
        if len(group) > 1:
            near_dup_groups.append(group)
            checked.add(p1)

    for group in near_dup_groups:
        # 保留第一张，其余标记
        for p in group[1:]:
            for r in results:
                if r["path"] == p and r["valid"]:
                    r["valid"] = False
                    r["issues"].append(f"近似重复 (同组: {group[0]} 等)")

    print(f"[INFO] 重复检测完成: 精确重复 {len(exact_dupes)} 组, 近似重复 {len(near_dup_groups)} 组")
    return results


# ============================================================
# 3. 报告生成
# ============================================================

def generate_report(results, output_dir, config):
    """生成校验报告"""
    output_dir = Path(output_dir)

    total = len(results)
    valid = [r for r in results if r["valid"]]
    invalid = [r for r in results if not r["valid"]]

    # 按问题类型统计
    issue_stats = Counter()
    for r in invalid:
        for issue in r["issues"]:
            # 取问题类别（第一个冒号前的部分）
            cat = issue.split(":")[0].split("(")[0].strip()
            issue_stats[cat] += 1

    # 按类别统计（从文件名推断类别）
    category_stats = defaultdict(lambda: {"total": 0, "valid": 0, "invalid": 0})
    for r in results:
        fname = Path(r["path"]).stem
        # 文件名格式: 类别_编号
        parts = fname.rsplit("_", 1)
        category = parts[0] if len(parts) > 1 else "未知"
        category_stats[category]["total"] += 1
        if r["valid"]:
            category_stats[category]["valid"] += 1
        else:
            category_stats[category]["invalid"] += 1

    # 尺寸分布
    widths = [r["width"] for r in valid if r["width"] > 0]
    heights = [r["height"] for r in valid if r["height"] > 0]
    sizes = [r["file_size_kb"] for r in valid if r["file_size_kb"] > 0]

    report = {
        "config": config,
        "summary": {
            "total_images": total,
            "valid_images": len(valid),
            "invalid_images": len(invalid),
            "valid_rate": f"{len(valid)*100/total:.1f}%" if total > 0 else "0%",
            "invalid_rate": f"{len(invalid)*100/total:.1f}%" if total > 0 else "0%",
        },
        "issue_breakdown": dict(issue_stats.most_common()),
        "category_breakdown": {
            cat: stats for cat, stats in sorted(category_stats.items())
        },
        "valid_image_stats": {
            "width_range": f"{min(widths)}-{max(widths)}px" if widths else "N/A",
            "height_range": f"{min(heights)}-{max(heights)}px" if heights else "N/A",
            "avg_file_size_kb": round(sum(sizes) / len(sizes), 2) if sizes else 0,
            "median_width": sorted(widths)[len(widths)//2] if widths else 0,
            "median_height": sorted(heights)[len(heights)//2] if heights else 0,
        },
        "invalid_images": [
            {"path": Path(r["path"]).name, "issues": r["issues"],
             "size_kb": r["file_size_kb"], "dimensions": f"{r['width']}x{r['height']}"}
            for r in invalid
        ],
    }

    # 保存 JSON 报告
    report_path = output_dir / "validation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 保存可读文本报告
    txt_path = output_dir / "validation_report.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("  审计票据图片校验报告\n")
        f.write("=" * 60 + "\n\n")

        f.write("【总体概况】\n")
        f.write(f"  总图片数:     {total}\n")
        f.write(f"  有效图片:     {len(valid)} ({report['summary']['valid_rate']})\n")
        f.write(f"  无效图片:     {len(invalid)} ({report['summary']['invalid_rate']})\n")
        f.write(f"  有效率:       {report['summary']['valid_rate']}\n\n")

        f.write("【问题分布】\n")
        for issue, count in issue_stats.most_common():
            f.write(f"  {issue}: {count} 张\n")
        f.write("\n")

        f.write("【有效图片统计】\n")
        if valid:
            f.write(f"  尺寸范围:     {report['valid_image_stats']['width_range']} (宽) x "
                    f"{report['valid_image_stats']['height_range']} (高)\n")
            f.write(f"  中位尺寸:     {report['valid_image_stats']['median_width']}x"
                    f"{report['valid_image_stats']['median_height']}\n")
            f.write(f"  平均文件大小: {report['valid_image_stats']['avg_file_size_kb']}KB\n")
        f.write("\n")

        f.write("【按类别统计（仅显示有问题的类别）】\n")
        problem_cats = {cat: s for cat, s in category_stats.items() if s["invalid"] > 0}
        if problem_cats:
            f.write(f"  {'类别':<30} {'总数':>6} {'有效':>6} {'无效':>6} {'有效率':>8}\n")
            f.write(f"  {'-'*30} {'-'*6} {'-'*6} {'-'*6} {'-'*8}\n")
            for cat, s in sorted(problem_cats.items(), key=lambda x: -x[1]["invalid"]):
                rate = f"{s['valid']*100/s['total']:.1f}%" if s['total'] > 0 else "N/A"
                f.write(f"  {cat:<30} {s['total']:>6} {s['valid']:>6} {s['invalid']:>6} {rate:>8}\n")
        else:
            f.write("  无问题类别\n")
        f.write("\n")

        f.write("【无效图片清单（前200条）】\n")
        for i, item in enumerate(report["invalid_images"][:200]):
            f.write(f"  {i+1}. {item['path']}\n")
            f.write(f"     问题: {'; '.join(item['issues'])}\n")
            f.write(f"     尺寸: {item['dimensions']}, 大小: {item['size_kb']}KB\n")
        if len(invalid) > 200:
            f.write(f"  ... 还有 {len(invalid) - 200} 条，详见 bad_images_list.txt\n")

    # 保存无效图片清单
    bad_list_path = output_dir / "bad_images_list.txt"
    with open(bad_list_path, "w", encoding="utf-8") as f:
        f.write(f"# 无效图片清单 (共 {len(invalid)} 张)\n")
        f.write(f"# 格式: 文件名 | 问题 | 尺寸 | 大小KB\n")
        f.write("=" * 80 + "\n")
        for r in invalid:
            fname = Path(r["path"]).name
            issues = "; ".join(r["issues"])
            f.write(f"{fname}\t{issues}\t{r['width']}x{r['height']}\t{r['file_size_kb']}KB\n")

    print(f"\n[REPORT] 报告已保存:")
    print(f"  - {report_path}")
    print(f"  - {txt_path}")
    print(f"  - {bad_list_path}")
    print(f"\n  总计: {total} 张 | 有效: {len(valid)} ({report['summary']['valid_rate']}) | 无效: {len(invalid)}")

    return report


# ============================================================
# 4. 清洗 JSONL
# ============================================================

def clean_jsonl(train_jsonl, val_jsonl, invalid_paths, output_dir):
    """根据无效图片列表，生成清洗后的 JSONL"""
    output_dir = Path(output_dir)
    invalid_set = set(Path(p).name for p in invalid_paths)

    stats = {"train": {"original": 0, "kept": 0, "removed": 0},
             "val": {"original": 0, "kept": 0, "removed": 0}}

    for split_name, jsonl_path in [("train", train_jsonl), ("val", val_jsonl)]:
        if not os.path.exists(jsonl_path):
            print(f"[WARN] {jsonl_path} 不存在，跳过")
            continue

        clean_path = output_dir / f"{split_name}_clean.jsonl"
        with open(jsonl_path, "r", encoding="utf-8") as fin, \
             open(clean_path, "w", encoding="utf-8") as fout:
            for line in fin:
                stats[split_name]["original"] += 1
                try:
                    entry = json.loads(line.strip())
                    img_name = Path(entry.get("image", "")).name
                    if img_name in invalid_set:
                        stats[split_name]["removed"] += 1
                        continue
                    fout.write(line)
                    stats[split_name]["kept"] += 1
                except json.JSONDecodeError:
                    stats[split_name]["removed"] += 1

        print(f"[CLEAN] {split_name}: 原始 {stats[split_name]['original']} → "
              f"保留 {stats[split_name]['kept']} → 移除 {stats[split_name]['removed']}")

    return stats


# ============================================================
# 5. 主函数
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="审计票据图片校验 & 清洗管道")
    parser.add_argument("--dataset_dir", required=True,
                        help="数据集目录 (包含 images/, train.jsonl, val.jsonl)")
    parser.add_argument("--output_dir", default=None,
                        help="报告输出目录 (默认同 dataset_dir)")
    parser.add_argument("--min_dimension", type=int, default=100,
                        help="最小像素尺寸 (默认100px)")
    parser.add_argument("--min_file_kb", type=float, default=3.0,
                        help="最小文件大小KB (默认3KB)")
    parser.add_argument("--min_variance", type=float, default=50.0,
                        help="最小图像方差 (默认50, 低于=疑似空白)")
    parser.add_argument("--min_aspect_ratio", type=float, default=0.2,
                        help="最小宽高比 (默认0.2)")
    parser.add_argument("--max_aspect_ratio", type=float, default=8.0,
                        help="最大宽高比 (默认8.0)")
    parser.add_argument("--duplicate_threshold", type=int, default=5,
                        help="感知哈希汉明距离阈值 (默认5, 越小越严格)")
    parser.add_argument("--max_workers", type=int, default=8,
                        help="并行线程数 (默认8)")
    parser.add_argument("--skip_duplicate", action="store_true",
                        help="跳过重复检测 (加速)")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    output_dir = Path(args.output_dir) if args.output_dir else dataset_dir

    image_dir = dataset_dir / "images"
    if not image_dir.exists():
        print(f"[ERROR] 图片目录不存在: {image_dir}")
        sys.exit(1)

    config = {
        "min_dimension": args.min_dimension,
        "min_file_kb": args.min_file_kb,
        "min_variance": args.min_variance,
        "min_aspect_ratio": args.min_aspect_ratio,
        "max_aspect_ratio": args.max_aspect_ratio,
        "duplicate_threshold": args.duplicate_threshold,
        "skip_duplicate": args.skip_duplicate,
    }

    print("=" * 60)
    print("  审计票据图片校验 & 清洗管道")
    print("=" * 60)
    print(f"  数据集目录: {dataset_dir}")
    print(f"  图片目录:   {image_dir}")
    print(f"  配置:       {json.dumps(config, ensure_ascii=False)}")
    print("=" * 60 + "\n")

    # Step 1: 校验所有图片
    results = validate_all_images(image_dir, config, args.max_workers)

    # Step 2: 生成报告
    report = generate_report(results, output_dir, config)

    # Step 3: 清洗 JSONL
    train_jsonl = dataset_dir / "train.jsonl"
    val_jsonl = dataset_dir / "val.jsonl"
    invalid_paths = [r["path"] for r in results if not r["valid"]]

    if train_jsonl.exists() and val_jsonl.exists():
        print("\n[INFO] 开始清洗 JSONL 文件...")
        clean_stats = clean_jsonl(str(train_jsonl), str(val_jsonl),
                                   invalid_paths, output_dir)
    else:
        print("\n[WARN] 未找到 train.jsonl / val.jsonl，跳过清洗步骤")

    # Step 4: 汇总
    print("\n" + "=" * 60)
    print("  校验完成！")
    print("=" * 60)
    print(f"  有效图片:   {len([r for r in results if r['valid']])}")
    print(f"  无效图片:   {len(invalid_paths)}")
    print(f"  报告文件:   {output_dir}/validation_report.txt")
    print(f"  清洗JSONL:  {output_dir}/train_clean.jsonl")
    print(f"              {output_dir}/val_clean.jsonl")
    print(f"  问题清单:   {output_dir}/bad_images_list.txt")
    print("=" * 60)


if __name__ == "__main__":
    main()
