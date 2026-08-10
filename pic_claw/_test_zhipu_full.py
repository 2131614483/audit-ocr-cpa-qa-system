"""按类别复制图片到文件夹，并输出JSON结构结果文件"""
import os
import re
import json
import shutil
import base64
import time
import requests
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import psycopg2, psycopg2.extras

# ===================== 配置 =====================
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "audit_pipeline_db",
    "user": "postgres",
    "password": "admin"
}

# 智谱API配置
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ZHIPU_API_KEY = "6fc16aaab7a24b93acd04f02942bf216.3XB3qLs03JoPNIaE"
ZHIPU_MODEL = "GLM-4.6V-FlashX"

# 输出目录
OUTPUT_ROOT = Path(__file__).parent / "分类结果_智谱"
OUTPUT_ROOT.mkdir(exist_ok=True)

# 图像类型列表（130种）
IMAGE_TYPES = [
    "增值税专用发票", "增值税普通发票", "增值税电子普通发票", "增值税电子专用发票", "全电发票",
    "定额发票", "通用机打发票", "红字发票", "机动车销售发票", "二手车销售发票",
    "农产品收购发票", "服务业发票", "建筑安装业发票", "交通运输业发票", "餐饮发票",
    "住宿发票", "物业费发票", "水电费发票", "通信费发票", "保险费发票",
    "航空运输电子客票", "铁路车票", "出租车发票", "过路费发票", "停车费发票",
    "银行回单", "电子回单", "银行对账单", "银行承兑汇票", "商业承兑汇票",
    "现金支票", "转账支票", "银行存款凭证", "现金日记账", "银行存款日记账",
    "企业询证函", "银行询证函", "往来款项对账函", "催款函", "对账函",
    "入库单", "出库单", "送货单", "验收单", "领料单",
    "借款单", "报销单", "付款申请单", "差旅费报销单", "费用报销单",
    "工资表", "工资条", "社保缴费凭证", "公积金缴费凭证", "个人所得税纳税记录",
    "记账凭证", "原始凭证", "汇总凭证", "转账凭证", "收款凭证", "付款凭证",
    "总账", "明细账", "日记账", "多栏账", "辅助账",
    "资产负债表", "利润表", "现金流量表", "所有者权益变动表", "财务报表附注",
    "审计报告", "专项审计报告", "审计工作底稿", "验资报告", "资产评估报告",
    "营业执照", "开户许可证", "税务登记证", "组织机构代码证", "资质证书",
    "合同", "协议", "租赁合同", "采购合同", "销售合同",
    "完税凭证", "税收缴款书", "印花税票", "海关单据", "报关单",
    "保函", "信用证", "担保合同", "抵押合同", "质押合同",
    "股东会决议", "董事会决议", "会议纪要", "立项审批表", "签字页",
    "固定资产增加单", "固定资产减少单", "固定资产盘点表", "资产转移单", "资产报废单",
    "折旧计算表", "摊销计算表", "成本计算表", "费用分配表", "利润计算表",
    "会费收据", "捐赠收据", "押金收据", "违约金收据", "结算单",
    "个人所得税纳税记录", "企业所得税汇算清缴", "税务事项通知书", "税务行政处罚决定书", "税务登记表",
    "发票领用簿", "发票验旧表", "发票缴销表", "发票挂失表", "发票代开申请",
    "银行余额调节表", "银行存款余额调节表", "现金盘点表", "存货盘点表", "固定资产盘点表",
    "往来款项明细表", "应收账款账龄分析表", "应付账款明细表", "预收账款明细表", "预付账款明细表",
    "其他应收款明细表", "其他应付款明细表", "长期股权投资明细表", "固定资产明细表", "无形资产明细表",
]

# 10大类分组
CATEGORY_GROUPS = {
    "发票类": ["增值税专用发票", "增值税普通发票", "增值税电子普通发票", "增值税电子专用发票", "全电发票",
              "定额发票", "通用机打发票", "红字发票", "机动车销售发票", "二手车销售发票",
              "农产品收购发票", "服务业发票", "建筑安装业发票", "交通运输业发票", "餐饮发票",
              "住宿发票", "物业费发票", "水电费发票", "通信费发票", "保险费发票"],
    "差旅票据类": ["航空运输电子客票", "铁路车票", "出租车发票", "过路费发票", "停车费发票"],
    "银行金融类": ["银行回单", "电子回单", "银行对账单", "银行承兑汇票", "商业承兑汇票",
                  "现金支票", "转账支票", "银行存款凭证", "现金日记账", "银行存款日记账"],
    "函证审计类": ["企业询证函", "银行询证函", "往来款项对账函", "催款函", "对账函"],
    "出入库类": ["入库单", "出库单", "送货单", "验收单", "领料单"],
    "报销付款类": ["借款单", "报销单", "付款申请单", "差旅费报销单", "费用报销单"],
    "薪酬社保类": ["工资表", "工资条", "社保缴费凭证", "公积金缴费凭证", "个人所得税纳税记录"],
    "记账凭证类": ["记账凭证", "原始凭证", "汇总凭证", "转账凭证", "收款凭证", "付款凭证"],
    "账簿类": ["总账", "明细账", "日记账", "多栏账", "辅助账"],
    "财务报表类": ["资产负债表", "利润表", "现金流量表", "所有者权益变动表", "财务报表附注"],
    "审计报告类": ["审计报告", "专项审计报告", "审计工作底稿", "验资报告", "资产评估报告"],
    "证照资质类": ["营业执照", "开户许可证", "税务登记证", "组织机构代码证", "资质证书"],
    "合同协议类": ["合同", "协议", "租赁合同", "采购合同", "销售合同"],
    "海关税务类": ["完税凭证", "税收缴款书", "印花税票", "海关单据", "报关单"],
    "担保信用类": ["保函", "信用证", "担保合同", "抵押合同", "质押合同"],
    "审批决议类": ["股东会决议", "董事会决议", "会议纪要", "立项审批表", "签字页"],
    "资产管理类": ["固定资产增加单", "固定资产减少单", "固定资产盘点表", "资产转移单", "资产报废单"],
    "计算分配类": ["折旧计算表", "摊销计算表", "成本计算表", "费用分配表", "利润计算表"],
    "收据结算类": ["会费收据", "捐赠收据", "押金收据", "违约金收据", "结算单"],
    "税务管理类": ["个人所得税纳税记录", "企业所得税汇算清缴", "税务事项通知书", "税务行政处罚决定书", "税务登记表"],
}

# 反转映射：类型→大类
TYPE_TO_CATEGORY = {}
for cat, types in CATEGORY_GROUPS.items():
    for t in types:
        TYPE_TO_CATEGORY[t] = cat


def get_category(type_name: str) -> str:
    """获取凭证类型所属大类"""
    return TYPE_TO_CATEGORY.get(type_name, "其他类")


def image_to_base64(image_path: str) -> str:
    """图片转base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def call_zhipu(prompt: str, image_base64: str = None) -> str:
    """调用智谱API"""
    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }

    content = []
    if image_base64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
        })
    content.append({"type": "text", "text": prompt})

    payload = {
        "model": ZHIPU_MODEL,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1,
        "max_tokens": 4096
    }

    resp = requests.post(ZHIPU_API_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def classify_image(image_path: str, file_name: str) -> Dict[str, Any]:
    """分类单张图片"""
    type_list = "\n".join([f"- {t}" for t in IMAGE_TYPES])
    prompt = f"""请识别这张图片的凭证类型，从以下列表中选择最匹配的一项：

{type_list}

如果图片内容模糊、无关或不在列表中，请回复"其他"。

只输出类型名称，不要输出其他内容。"""

    b64 = image_to_base64(image_path)
    result = call_zhipu(prompt, b64).strip()
    return {"type_name": result, "category": get_category(result)}


def extract_fields(image_path: str, type_name: str, category: str) -> Dict[str, Any]:
    """提取图片字段（参考参考代码.py的JSON结构）"""
    prompt = f"""你是一位专业的审计凭证信息提取专家。请从这张图片中提取所有可见的关键字段信息。

凭证类型：{type_name}
所属大类：{category}

请严格按照以下JSON格式输出（只输出JSON，不要包含任何其他文字）：
{{
    "image_type": "{type_name}",
    "ocr_extract": {{
        "invoice_code": "发票代码或N/A",
        "invoice_number": "发票号码或N/A",
        "date": "日期(YYYY-MM-DD)或N/A",
        "total_amount": "金额(纯数字)或N/A",
        "relevant_party": "相关方名称或N/A",
        "tax_rate": "税率或N/A",
        "tax_id": "纳税人识别号或N/A",
        "bank_info": "银行信息或N/A",
        "serial_number": "流水号或N/A",
        "details": "摘要/备注或N/A",
        "seal_info": {{
            "seal_type": "印章类型或N/A",
            "seal_number": "印章编号或N/A",
            "seal_clarity": "印章清晰度(清晰/模糊/无)或N/A",
            "joint_seal": "是否联合盖章(是/否)或N/A"
        }},
        "license_info": {{
            "unified_social_credit_code": "统一社会信用代码或N/A",
            "legal_person": "法定代表人或N/A",
            "valid_period": "有效期限或N/A"
        }},
        "asset_info": {{
            "asset_tag": "资产标签或N/A",
            "asset_name": "资产名称或N/A",
            "location": "位置或N/A",
            "quantity": "数量或N/A",
            "progress": "进度或N/A"
        }},
        "internal_control_info": {{
            "signer": "签字人或N/A",
            "approval_level": "审批级别或N/A",
            "attachment_complete": "附件是否完整(是/否)或N/A"
        }},
        "other_info": "其他信息或N/A"
    }},
    "validation_result": {{
        "date_valid": true,
        "amount_valid": true,
        "code_format_valid": true,
        "no_missing_field": true,
        "image_normal": true,
        "no_duplicate": true,
        "consistent_info": true,
        "compliance": true,
        "no_fraud": true
    }},
    "risk_rating": "高风险/中风险/低风险",
    "risk_description": "风险说明",
    "audit_conclusion": "通过/不通过/人工复核",
    "reason": "审计说明",
    "audit_value": "数字化审计留痕，可核对、可预警",
    "_confidence": 0.95,
    "_summary": "简要描述该凭证的核心内容（20字以内）"
}}

注意：
1. 不存在的字段填"N/A"
2. 金额只填数字，去掉货币符号
3. 日期统一为YYYY-MM-DD格式
4. 布尔值填true或false
5. 仔细阅读图片中的所有文字"""

    b64 = image_to_base64(image_path)
    result = call_zhipu(prompt, b64)

    # 提取JSON
    result = result.strip().replace("```json", "").replace("```", "").strip()
    json_match = re.search(r"\{[\s\S]*\}", result)
    if json_match:
        return json.loads(json_match.group())
    return {"error": "JSON解析失败", "raw": result[:500]}


def process_single_image(file_path: str, file_name: str) -> Dict[str, Any]:
    """处理单张图片：分类+提取"""
    print(f"\n{'─' * 60}")
    print(f"📄 {file_name}")

    # 分类
    print("  🤖 分类中...")
    t1 = time.time()
    try:
        cls_result = classify_image(file_path, file_name)
        t_cls = time.time() - t1
        print(f"  ✅ {cls_result['type_name']} ({cls_result['category']}) [{t_cls:.1f}s]")
    except Exception as e:
        print(f"  ❌ 分类失败: {e}")
        return {"file_name": file_name, "error": f"分类失败: {e}"}

    # 提取
    print("  🔍 提取中...")
    t2 = time.time()
    try:
        ext_result = extract_fields(file_path, cls_result["type_name"], cls_result["category"])
        t_ext = time.time() - t2
        field_count = len([v for v in ext_result.get("ocr_extract", {}).values() if v != "N/A"])
        print(f"  ✅ 提取{field_count}个字段 [{t_ext:.1f}s]")
    except Exception as e:
        print(f"  ❌ 提取失败: {e}")
        ext_result = {"error": str(e)}

    # 构建完整结果
    result = {
        "file_name": file_name,
        "file_path": file_path,
        "classify_result": {
            "type_name": cls_result["type_name"],
            "category": cls_result["category"],
            "duration_s": round(t_cls, 1)
        },
        "extract_result": ext_result,
        "process_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_duration_s": round(time.time() - t1, 1)
    }

    return result


def copy_and_organize(results: List[Dict[str, Any]]):
    """按类别复制图片到文件夹，并生成JSON结果文件"""
    print(f"\n{'=' * 60}")
    print("📁 整理输出...")

    for r in results:
        if "error" in r:
            continue

        type_name = r["classify_result"]["type_name"]
        category = r["classify_result"]["category"]
        file_name = r["file_name"]
        src_path = r["file_path"]

        # 创建类别文件夹
        type_dir = OUTPUT_ROOT / category / type_name
        type_dir.mkdir(parents=True, exist_ok=True)

        # 复制图片
        if Path(src_path).exists():
            dst_path = type_dir / file_name
            shutil.copy2(src_path, str(dst_path))
            r["output_path"] = str(dst_path)
            print(f"  ✓ {category}/{type_name}/{file_name}")

        # 保存JSON结果
        json_path = type_dir / f"{Path(file_name).stem}_result.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)

    # 生成汇总JSON
    summary_path = OUTPUT_ROOT / "汇总结果.json"
    summary = {
        "process_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_images": len(results),
        "success_count": len([r for r in results if "error" not in r]),
        "error_count": len([r for r in results if "error" in r]),
        "results": results
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n📊 汇总结果: {summary_path}")
    print(f"📁 输出目录: {OUTPUT_ROOT}")


def main():
    """主函数：从数据库取1张测试图片并处理"""
    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT id, file_path, file_name, doc_type_name, category_name
            FROM voucher_images
            WHERE batch_id = 4 AND classify_status = 'pending'
            ORDER BY id
            LIMIT 1
        """)
        img = cur.fetchone()
        if not img:
            print("没有待处理的图片")
            conn.close()
            return
        img = dict(img)
    conn.close()

    print("=" * 60)
    print("🚀 智谱API全流程测试（1张）")
    print(f"📄 {img['file_name']}")
    print(f"   真实类型: {img['doc_type_name']} ({img['category_name']})")
    print("=" * 60)

    result = process_single_image(img["file_path"], img["file_name"])
    copy_and_organize([result])

    # 打印JSON结果
    print(f"\n{'=' * 60}")
    print("📋 JSON输出:")
    print("=" * 60)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()