# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import os
import sys
import hashlib
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pic_claw.pipeline_db import create_batch, insert_voucher_image, update_batch_progress, insert_pipeline_log

DOWNLOADED_DIR = Path(__file__).parent / "downloaded"
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}

CATEGORY_GROUPS = [
    ("发票类", 0, 20),
    ("差旅票据类", 20, 28),
    ("银行/资金类", 28, 46),
    ("函证/审计类", 46, 60),
    ("税务类", 60, 74),
    ("企业内部管理类", 74, 90),
    ("薪酬/人事/合同类", 90, 100),
    ("账簿/分录/报表类", 100, 112),
    ("固定资产/成本类", 112, 120),
    ("收据/合同/资质类", 120, 130),
]

CATEGORIES = [
    "增值税专用发票", "增值税普通发票", "增值税电子普通发票", "增值税电子专用发票",
    "全电发票", "定额发票", "通用机打发票", "红字发票", "机动车销售发票", "二手车销售发票",
    "农产品收购发票", "服务业发票", "建筑安装业发票", "交通运输业发票", "餐饮发票",
    "住宿发票", "物业费发票", "水电费发票", "通信费发票", "保险费发票",
    "航空运输电子客票", "铁路车票", "出租车发票", "过路费发票", "停车费发票",
    "航空运输货运单", "船票", "汽车客运票",
    "银行回单", "银行对账单", "银行进账单", "电汇凭证", "银行承兑汇票", "商业承兑汇票",
    "转账支票", "现金支票", "利息单", "手续费回单", "信用证", "保函",
    "贴现凭证", "贷款借据", "还款凭证", "结汇水单", "国际汇款申请书", "现金缴款单",
    "银行询证函", "企业询证函", "应收账款询证函", "应付账款询证函", "存货询证函",
    "对账函", "催款函", "审计报告", "验资报告", "审计工作底稿", "审计业务约定书",
    "管理层声明书", "专项审计报告", "内部控制审计报告",
    "完税凭证", "海关进口增值税缴款书", "非税收入票据", "税收缴款书", "纳税申报表",
    "个人所得税纳税记录", "增值税发票汇总表", "出口退税申报表", "税务登记证",
    "税务事项通知书", "企业所得税汇算清缴", "印花税票", "房产税申报表", "车辆购置税发票",
    "费用报销单", "差旅费报销单", "付款申请单", "借款单", "入库单", "出库单",
    "调拨单", "盘点表", "现金盘点表", "银行存款余额调节表", "内部转账单",
    "出差申请单", "采购申请单", "验收单", "送货单", "比价单",
    "工资单", "劳务费发放表", "社保缴费凭证", "公积金缴存凭证", "考勤表",
    "年终奖金表", "加班工资表", "劳动合同", "劳务合同", "福利费发放表",
    "记账凭证", "原始凭证", "收款凭证", "付款凭证", "转账凭证",
    "总账", "明细账", "日记账", "资产负债表", "利润表", "现金流量表", "所有者权益变动表",
    "固定资产卡片", "固定资产报废单", "折旧计算表", "成本计算单", "材料领用单",
    "固定资产调拨单", "固定资产增加单", "无形资产台账",
    "收据", "捐赠收据", "会费收据", "购销合同", "租赁合同",
    "营业执照", "开户许可证", "组织机构代码证", "医疗收费票据", "诉讼费票据",
]


def build_type_to_category_map():
    mapping = {}
    for cat_name, start, end in CATEGORY_GROUPS:
        for i in range(start, end):
            if i < len(CATEGORIES):
                mapping[CATEGORIES[i]] = cat_name
    return mapping


def get_file_md5(filepath: Path) -> str:
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def scan_images(downloaded_dir: Path) -> list:
    entries = []
    if not downloaded_dir.exists():
        print(f"目录不存在: {downloaded_dir}")
        return entries

    for subdir in sorted(downloaded_dir.iterdir()):
        if not subdir.is_dir():
            continue
        type_name = subdir.name
        image_files = []
        for f in subdir.iterdir():
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                image_files.append(f)
        if image_files:
            entries.append((type_name, sorted(image_files)))
            print(f"  {type_name}: {len(image_files)} 张图片")
    return entries


def import_batch(batch_no: str = None, batch_name: str = "", max_per_type: int = None):
    if batch_no is None:
        batch_no = f"BATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    type_to_cat = build_type_to_category_map()
    entries = scan_images(DOWNLOADED_DIR)

    total_images = 0
    for type_name, files in entries:
        if max_per_type:
            total_images += min(len(files), max_per_type)
        else:
            total_images += len(files)

    print(f"\n创建批次: {batch_no} (共 {total_images} 张图片)")
    batch_id = create_batch(batch_no, batch_name or f"批量导入 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                            source="import", total_images=total_images)
    print(f"批次ID: {batch_id}")

    inserted = 0
    errors = 0
    start_time = time.time()

    for type_name, files in entries:
        category_name = type_to_cat.get(type_name, "其他")
        file_list = files[:max_per_type] if max_per_type else files

        for fpath in file_list:
            try:
                file_md5 = get_file_md5(fpath)
                file_size = fpath.stat().st_size
                file_format = fpath.suffix.lower().lstrip('.')
                if file_format in ('jpg', 'jpeg'):
                    file_format = 'jpg'

                insert_voucher_image(
                    batch_id=batch_id,
                    file_name=fpath.name,
                    file_path=str(fpath.resolve()),
                    file_md5=file_md5,
                    file_size=file_size,
                    file_format=file_format,
                    doc_type_name=type_name,
                    category_name=category_name,
                )
                inserted += 1
            except Exception as e:
                errors += 1
                print(f"  ✗ 导入失败 [{type_name}/{fpath.name}]: {e}")

        if inserted % 500 == 0:
            elapsed = time.time() - start_time
            print(f"  进度: {inserted}/{total_images} ({elapsed:.1f}s)")

    elapsed = time.time() - start_time
    update_batch_progress(batch_id, total_images=inserted, status="pending",
                          remark=f"导入完成: 成功{inserted}, 失败{errors}, 耗时{elapsed:.1f}s")
    insert_pipeline_log(None, batch_id, "import", "done" if errors == 0 else "partial",
                        f"导入完成: 成功{inserted}, 失败{errors}, 耗时{elapsed:.1f}s")

    print(f"\n{'='*50}")
    print(f"导入完成!")
    print(f"  批次ID: {batch_id}")
    print(f"  批次号: {batch_no}")
    print(f"  成功: {inserted}")
    print(f"  失败: {errors}")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"{'='*50}")
    return batch_id


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="将 downloaded/ 图片导入 audit_pipeline_db")
    parser.add_argument("--batch-no", help="批次号 (默认自动生成)")
    parser.add_argument("--batch-name", help="批次名称", default="")
    parser.add_argument("--max-per-type", type=int, help="每类最多导入张数")
    args = parser.parse_args()

    import_batch(batch_no=args.batch_no, batch_name=args.batch_name,
                 max_per_type=args.max_per_type)