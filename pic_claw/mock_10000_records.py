"""
模拟写入10000条随机数据到Agent1和Agent2表
- Agent1: agent1_classify_results (分类结果)
- Agent2: 10大类独立表 (提取结果)
"""
import psycopg2
import psycopg2.extras
import json
import random
from datetime import datetime, timedelta

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "audit_pipeline_db",
    "user": "postgres",
    "password": "admin"
}

# 10大类及子类
CATEGORIES = {
    "发票类": [
        "增值税专用发票", "增值税普通发票", "增值税电子普通发票", "增值税电子专用发票",
        "全电发票", "定额发票", "通用机打发票", "红字发票", "机动车销售发票",
        "二手车销售发票", "农产品收购发票", "服务业发票", "建筑安装业发票",
        "交通运输业发票", "餐饮发票", "住宿发票", "物业费发票", "水电费发票",
        "通信费发票", "保险费发票"
    ],
    "差旅票据类": [
        "航空运输电子客票", "铁路车票", "出租车发票", "过路费发票",
        "停车费发票", "航空运输货运单", "船票", "汽车客运票"
    ],
    "银行/资金类": [
        "银行回单", "银行对账单", "银行进账单", "电汇凭证", "银行承兑汇票",
        "商业承兑汇票", "转账支票", "现金支票", "利息单", "手续费回单",
        "信用证", "保函", "贴现凭证", "贷款借据", "还款凭证", "结汇水单",
        "国际汇款申请书", "现金缴款单"
    ],
    "企业内部管理类": [
        "费用报销单", "差旅费报销单", "付款申请单", "借款单", "入库单",
        "出库单", "调拨单", "盘点表", "现金盘点表", "银行存款余额调节表",
        "内部转账单", "出差申请单", "采购申请单", "验收单", "送货单", "比价单"
    ],
    "税务类": [
        "完税凭证", "海关进口增值税缴款书", "非税收入票据", "税收缴款书",
        "纳税申报表", "个人所得税纳税记录", "增值税发票汇总表", "出口退税申报表",
        "税务登记证", "税务事项通知书", "企业所得税汇算清缴", "印花税票",
        "房产税申报表", "车辆购置税发票"
    ],
    "资产类": [
        "固定资产卡片", "固定资产报废单", "折旧计算表", "成本计算单",
        "材料领用单", "固定资产调拨单", "固定资产增加单", "无形资产台账"
    ],
    "合同/协议类": [
        "购销合同", "租赁合同"
    ],
    "函证/审计类": [
        "银行询证函", "企业询证函", "应收账款询证函", "应付账款询证函",
        "存货询证函", "对账函", "催款函", "审计报告", "验资报告",
        "审计工作底稿", "审计业务约定书", "管理层声明书", "专项审计报告",
        "内部控制审计报告"
    ],
    "证照/资质类": [
        "营业执照", "开户许可证", "组织机构代码证"
    ],
    "人事/薪酬类": [
        "工资单", "劳务费发放表", "社保缴费凭证", "公积金缴存凭证",
        "考勤表", "年终奖金表", "加班工资表", "劳动合同", "劳务合同", "福利费发放表"
    ],
}

# 公司名称
COMPANIES = [
    "北京某某科技有限公司", "上海某某贸易有限公司", "广州某某制造有限公司",
    "深圳某某电子有限公司", "杭州某某网络有限公司", "成都某某商贸有限公司",
    "武汉某某物流有限公司", "南京某某建筑工程有限公司", "天津某某化工有限公司",
    "重庆某某食品有限公司", "苏州某某纺织有限公司", "西安某某能源有限公司"
]

# 银行信息
BANKS = [
    "工商银行北京中关村支行", "建设银行上海浦东分行", "农业银行广州天河支行",
    "中国银行深圳南山支行", "交通银行杭州西湖支行", "招商银行成都高新支行"
]

# 人名
NAMES = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十"]

# 随机日期
def random_date(start_year=2023, end_year=2024):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return start + timedelta(days=random_days)

# 随机金额
def random_amount(min_val=100, max_val=500000):
    return round(random.uniform(min_val, max_val), 2)

# Agent1 JSON格式
def gen_agent1_json(category, doc_type):
    return {
        "type_name": doc_type,
        "category_name": category,
        "confidence": round(random.uniform(0.75, 0.99), 2),
        "reasoning": random.choice([
            "标题文字匹配", "布局特征符合", "印章类型一致", "表格结构匹配",
            "关键字段吻合", "格式规范符合", "视觉特征一致"
        ])
    }

# Agent2 JSON格式 - 按大类生成
def gen_agent2_json(category, doc_type):
    base = {
        "date": random_date().strftime("%Y-%m-%d"),
        "total_amount": str(random_amount()),
        "relevant_party": random.choice(COMPANIES),
        "tax_id": f"91110108MA{random.randint(10000, 99999)}X",
        "serial_number": f"SN{random.randint(10000000, 99999999)}",
        "details": random.choice([
            "购买办公用品一批", "支付货款", "差旅费报销", "服务费结算",
            "设备采购", "材料采购", "工程款支付", "租金支付"
        ]),
        "bank_info": random.choice(BANKS),
        "tax_rate": random.choice(["13%", "9%", "6%", "3%", "N/A"]),
        "invoice_code": f"{random.randint(100000000000, 999999999999)}",
        "invoice_number": f"{random.randint(10000000, 99999999)}",
        "seal_info": {
            "seal_type": random.choice(["发票专用章", "财务专用章", "合同专用章", "业务专用章", "N/A"]),
            "seal_number": f"{random.randint(100000, 999999)}",
            "seal_clarity": random.choice(["清晰", "模糊", "N/A"]),
            "joint_seal": random.choice(["是", "否"])
        },
        "license_info": {
            "unified_social_credit_code": f"91110108MA{random.randint(10000, 99999)}X",
            "legal_person": random.choice(NAMES),
            "valid_period": f"{random_date().strftime('%Y-%m-%d')}至长期"
        },
        "asset_info": {
            "asset_tag": f"FA-{random.randint(1000, 9999)}",
            "asset_name": random.choice(["笔记本电脑", "打印机", "办公桌", "服务器", "车辆"]),
            "location": random.choice(["3楼办公室", "仓库A", "生产车间", "机房"]),
            "quantity": f"{random.randint(1, 100)}台/件",
            "progress": random.choice(["已盘点", "待盘点", "已报废"])
        },
        "internal_control_info": {
            "signer": random.choice(NAMES),
            "approval_level": random.choice(["部门经理审批", "总经理审批", "财务总监审批"]),
            "attachment_complete": random.choice(["是", "否"])
        },
        "other_info": "N/A"
    }
    
    # 根据类别调整字段
    if category == "差旅票据类":
        base["relevant_party"] = random.choice(NAMES)
        base["tax_id"] = "N/A"
        base["invoice_code"] = "N/A"
        base["invoice_number"] = "N/A"
        base["seal_info"] = {"seal_type": "N/A", "seal_number": "N/A", "seal_clarity": "N/A", "joint_seal": "N/A"}
        base["license_info"] = {"unified_social_credit_code": "N/A", "legal_person": "N/A", "valid_period": "N/A"}
        base["asset_info"] = {"asset_tag": "N/A", "asset_name": "N/A", "location": "N/A", "quantity": "N/A", "progress": "N/A"}
        base["internal_control_info"] = {"signer": "N/A", "approval_level": "N/A", "attachment_complete": "N/A"}
    elif category == "银行/资金类":
        base["tax_id"] = "N/A"
        base["tax_rate"] = "N/A"
        base["invoice_code"] = "N/A"
        base["invoice_number"] = "N/A"
        base["license_info"] = {"unified_social_credit_code": "N/A", "legal_person": "N/A", "valid_period": "N/A"}
        base["asset_info"] = {"asset_tag": "N/A", "asset_name": "N/A", "location": "N/A", "quantity": "N/A", "progress": "N/A"}
        base["internal_control_info"] = {"signer": "N/A", "approval_level": "N/A", "attachment_complete": "N/A"}
    elif category == "证照/资质类":
        base["total_amount"] = "N/A"
        base["serial_number"] = "N/A"
        base["details"] = "N/A"
        base["tax_rate"] = "N/A"
        base["invoice_code"] = "N/A"
        base["invoice_number"] = "N/A"
        base["seal_info"] = {"seal_type": "N/A", "seal_number": "N/A", "seal_clarity": "N/A", "joint_seal": "N/A"}
        base["asset_info"] = {"asset_tag": "N/A", "asset_name": "N/A", "location": "N/A", "quantity": "N/A", "progress": "N/A"}
        base["internal_control_info"] = {"signer": "N/A", "approval_level": "N/A", "attachment_complete": "N/A"}
    elif category == "函证/审计类":
        base["total_amount"] = "N/A"
        base["tax_id"] = "N/A"
        base["tax_rate"] = "N/A"
        base["invoice_code"] = "N/A"
        base["invoice_number"] = "N/A"
        base["seal_info"] = {"seal_type": "N/A", "seal_number": "N/A", "seal_clarity": "N/A", "joint_seal": "N/A"}
        base["license_info"] = {"unified_social_credit_code": "N/A", "legal_person": "N/A", "valid_period": "N/A"}
        base["asset_info"] = {"asset_tag": "N/A", "asset_name": "N/A", "location": "N/A", "quantity": "N/A", "progress": "N/A"}
        base["internal_control_info"] = {"signer": "N/A", "approval_level": "N/A", "attachment_complete": "N/A"}
    elif category == "人事/薪酬类":
        base["tax_id"] = "N/A"
        base["tax_rate"] = "N/A"
        base["invoice_code"] = "N/A"
        base["invoice_number"] = "N/A"
        base["bank_info"] = "N/A"
        base["seal_info"] = {"seal_type": "N/A", "seal_number": "N/A", "seal_clarity": "N/A", "joint_seal": "N/A"}
        base["license_info"] = {"unified_social_credit_code": "N/A", "legal_person": "N/A", "valid_period": "N/A"}
        base["asset_info"] = {"asset_tag": "N/A", "asset_name": "N/A", "location": "N/A", "quantity": "N/A", "progress": "N/A"}
    elif category == "资产类":
        base["total_amount"] = "N/A"
        base["relevant_party"] = "N/A"
        base["tax_id"] = "N/A"
        base["tax_rate"] = "N/A"
        base["invoice_code"] = "N/A"
        base["invoice_number"] = "N/A"
        base["bank_info"] = "N/A"
        base["seal_info"] = {"seal_type": "N/A", "seal_number": "N/A", "seal_clarity": "N/A", "joint_seal": "N/A"}
        base["license_info"] = {"unified_social_credit_code": "N/A", "legal_person": "N/A", "valid_period": "N/A"}
    elif category == "合同/协议类":
        base["tax_id"] = "N/A"
        base["tax_rate"] = "N/A"
        base["invoice_code"] = "N/A"
        base["invoice_number"] = "N/A"
        base["serial_number"] = "N/A"
        base["license_info"] = {"unified_social_credit_code": "N/A", "legal_person": "N/A", "valid_period": "N/A"}
        base["asset_info"] = {"asset_tag": "N/A", "asset_name": "N/A", "location": "N/A", "quantity": "N/A", "progress": "N/A"}
        base["internal_control_info"] = {"signer": "N/A", "approval_level": "N/A", "attachment_complete": "N/A"}
    
    return base

def gen_validation():
    return {
        "date_valid": random.choice([True, True, True, False]),
        "amount_valid": random.choice([True, True, True, False]),
        "code_format_valid": random.choice([True, True, True, False]),
        "no_missing_field": random.choice([True, True, False]),
        "image_normal": random.choice([True, True, True, False]),
        "no_duplicate": random.choice([True, True, True, False]),
        "consistent_info": random.choice([True, True, True, False]),
        "compliance": random.choice([True, True, True, False]),
        "no_fraud": random.choice([True, True, True, False])
    }

def gen_risk():
    r = random.random()
    if r < 0.7:
        return "低风险", "凭证信息完整，格式规范"
    elif r < 0.9:
        return "中风险", random.choice(["金额较大需关注", "字段缺失需核实", "日期异常需确认"])
    else:
        return "高风险", random.choice(["涉嫌虚假发票", "金额异常偏高", "重复报销嫌疑"])

def gen_audit_conclusion(risk):
    if risk == "低风险":
        return random.choice(["通过", "通过", "通过", "人工复核"])
    elif risk == "中风险":
        return random.choice(["人工复核", "人工复核", "不通过"])
    else:
        return random.choice(["不通过", "人工复核"])

# 类别→表名映射
CATEGORY_TABLE_MAP = {
    "发票类": "agent2_extract_发票类",
    "差旅票据类": "agent2_extract_差旅票据类",
    "银行/资金类": "agent2_extract_银行资金类",
    "企业内部管理类": "agent2_extract_企业内部管理类",
    "税务类": "agent2_extract_税务类",
    "资产类": "agent2_extract_资产类",
    "合同/协议类": "agent2_extract_合同协议类",
    "函证/审计类": "agent2_extract_函证审计类",
    "证照/资质类": "agent2_extract_证照资质类",
    "人事/薪酬类": "agent2_extract_人事薪酬类",
}

def main():
    print("=" * 60)
    print(" 模拟写入10000条随机数据")
    print("=" * 60)
    
    conn = psycopg2.connect(**DB_CONFIG)
    
    # 获取batch 4的image_id列表
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM voucher_images WHERE batch_id = 4")
        image_ids = [r[0] for r in cur.fetchall()]
    
    if not image_ids:
        print(" 没有可用的image_id")
        return
    
    print(f"📊 可用image_id: {len(image_ids)}个")
    
    # 生成10000条数据
    total = 10000
    batch_size = 500
    
    # Agent1数据
    agent1_data = []
    # Agent2数据按类别分组
    agent2_data = {cat: [] for cat in CATEGORY_TABLE_MAP.keys()}
    
    for i in range(total):
        # 随机选择类别和子类
        category = random.choice(list(CATEGORIES.keys()))
        doc_type = random.choice(CATEGORIES[category])
        image_id = random.choice(image_ids)
        
        # Agent1数据
        a1_json = gen_agent1_json(category, doc_type)
        agent1_data.append((
            image_id, 4, a1_json["type_name"], a1_json["category_name"],
            a1_json["confidence"], a1_json["reasoning"],
            doc_type, category, True, "GLM-4.6V-FlashX",
            json.dumps(a1_json, ensure_ascii=False), random.randint(2000, 8000),
            0, "done", None
        ))
        
        # Agent2数据
        a2_json = gen_agent2_json(category, doc_type)
        validation = gen_validation()
        risk, risk_desc = gen_risk()
        conclusion = gen_audit_conclusion(risk)
        
        field_count = len([v for v in a2_json.values() if v != "N/A" and not isinstance(v, dict)])
        for v in a2_json.values():
            if isinstance(v, dict):
                field_count += len([vv for vv in v.values() if vv != "N/A"])
        
        a2_record = (
            image_id, 4, doc_type,
            json.dumps(a2_json, ensure_ascii=False), field_count,
            json.dumps(validation, ensure_ascii=False),
            risk, risk_desc, conclusion,
            random.choice(["凭证要素齐全", "信息完整合规", "需进一步核实"]),
            f"{doc_type}，金额{a2_json['total_amount']}" if a2_json['total_amount'] != "N/A" else doc_type,
            round(random.uniform(0.8, 0.98), 2),
            "GLM-4.6V-FlashX", json.dumps(a2_json, ensure_ascii=False),
            random.randint(3000, 10000), 0, "done", None
        )
        agent2_data[category].append(a2_record)
    
    # 批量写入Agent1
    print(f"\n📝 写入Agent1分类结果: {len(agent1_data)}条")
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO agent1_classify_results (
                image_id, batch_id, predicted_type, predicted_category,
                confidence, reasoning, actual_type, actual_category,
                is_correct, model_name, raw_output, duration_ms,
                retry_count, status, error_msg
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, agent1_data)
        conn.commit()
    print(f"  ✅ Agent1写入完成")
    
    # 批量写入Agent2（按类别）
    for category, records in agent2_data.items():
        table = CATEGORY_TABLE_MAP[category]
        print(f"\n📝 写入Agent2 {category}: {len(records)}条")
        with conn.cursor() as cur:
            cur.executemany(f"""
                INSERT INTO {table} (
                    image_id, batch_id, doc_type_name, extracted_fields, field_count,
                    validation_result, risk_rating, risk_description, audit_conclusion,
                    audit_reason, summary, summary_confidence, model_name, raw_output,
                    duration_ms, retry_count, status, error_msg
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, records)
            conn.commit()
        print(f"  ✅ {category}写入完成")
    
    # 解析JSON到独立字段
    print(f"\n 解析JSON到独立字段...")
    for category, table in CATEGORY_TABLE_MAP.items():
        with conn.cursor() as cur:
            cur.execute(f"""
                UPDATE {table} SET
                    f_date = NULLIF(extracted_fields->>'date', 'N/A')::DATE,
                    f_amount = NULLIF(extracted_fields->>'total_amount', 'N/A')::NUMERIC,
                    f_party = NULLIF(extracted_fields->>'relevant_party', 'N/A'),
                    f_tax_id = NULLIF(extracted_fields->>'tax_id', 'N/A'),
                    f_serial_no = NULLIF(extracted_fields->>'serial_number', 'N/A'),
                    f_details = NULLIF(extracted_fields->>'details', 'N/A'),
                    f_bank_info = NULLIF(extracted_fields->>'bank_info', 'N/A'),
                    f_tax_rate = NULLIF(extracted_fields->>'tax_rate', 'N/A'),
                    f_invoice_code = NULLIF(extracted_fields->>'invoice_code', 'N/A'),
                    f_invoice_no = NULLIF(extracted_fields->>'invoice_number', 'N/A'),
                    f_seal_type = NULLIF(extracted_fields->'seal_info'->>'seal_type', 'N/A'),
                    f_seal_clarity = NULLIF(extracted_fields->'seal_info'->>'seal_clarity', 'N/A'),
                    f_joint_seal = NULLIF(extracted_fields->'seal_info'->>'joint_seal', 'N/A'),
                    f_other = NULLIF(extracted_fields->>'other_info', 'N/A'),
                    f_license_info = extracted_fields->'license_info',
                    f_asset_info = extracted_fields->'asset_info',
                    f_internal_control_info = extracted_fields->'internal_control_info'
                WHERE f_date IS NULL;
            """)
            conn.commit()
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            cnt = cur.fetchone()[0]
            print(f"  ✅ {category}: {cnt}条已解析")
    
    conn.close()
    
    # 打印统计
    print(f"\n{'=' * 60}")
    print("📊 数据统计")
    print(f"{'=' * 60}")
    
    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM agent1_classify_results WHERE batch_id = 4")
        print(f"  Agent1分类结果: {cur.fetchone()[0]}条")
        
        for category, table in CATEGORY_TABLE_MAP.items():
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE batch_id = 4")
            print(f"  Agent2 {category}: {cur.fetchone()[0]}条")
        
        # 风险分布
        cur.execute("""
            SELECT risk_rating, COUNT(*) FROM (
                SELECT risk_rating FROM agent2_extract_发票类 WHERE batch_id = 4
                UNION ALL SELECT risk_rating FROM agent2_extract_差旅票据类 WHERE batch_id = 4
                UNION ALL SELECT risk_rating FROM agent2_extract_银行资金类 WHERE batch_id = 4
                UNION ALL SELECT risk_rating FROM agent2_extract_企业内部管理类 WHERE batch_id = 4
                UNION ALL SELECT risk_rating FROM agent2_extract_税务类 WHERE batch_id = 4
                UNION ALL SELECT risk_rating FROM agent2_extract_资产类 WHERE batch_id = 4
                UNION ALL SELECT risk_rating FROM agent2_extract_合同协议类 WHERE batch_id = 4
                UNION ALL SELECT risk_rating FROM agent2_extract_函证审计类 WHERE batch_id = 4
                UNION ALL SELECT risk_rating FROM agent2_extract_证照资质类 WHERE batch_id = 4
                UNION ALL SELECT risk_rating FROM agent2_extract_人事薪酬类 WHERE batch_id = 4
            ) t GROUP BY risk_rating
        """)
        print(f"\n  风险分布:")
        for row in cur.fetchall():
            print(f"    {row[0]}: {row[1]}条")
        
        # 审计结论分布
        cur.execute("""
            SELECT audit_conclusion, COUNT(*) FROM (
                SELECT audit_conclusion FROM agent2_extract_发票类 WHERE batch_id = 4
                UNION ALL SELECT audit_conclusion FROM agent2_extract_差旅票据类 WHERE batch_id = 4
                UNION ALL SELECT audit_conclusion FROM agent2_extract_银行资金类 WHERE batch_id = 4
                UNION ALL SELECT audit_conclusion FROM agent2_extract_企业内部管理类 WHERE batch_id = 4
                UNION ALL SELECT audit_conclusion FROM agent2_extract_税务类 WHERE batch_id = 4
                UNION ALL SELECT audit_conclusion FROM agent2_extract_资产类 WHERE batch_id = 4
                UNION ALL SELECT audit_conclusion FROM agent2_extract_合同协议类 WHERE batch_id = 4
                UNION ALL SELECT audit_conclusion FROM agent2_extract_函证审计类 WHERE batch_id = 4
                UNION ALL SELECT audit_conclusion FROM agent2_extract_证照资质类 WHERE batch_id = 4
                UNION ALL SELECT audit_conclusion FROM agent2_extract_人事薪酬类 WHERE batch_id = 4
            ) t GROUP BY audit_conclusion
        """)
        print(f"\n  审计结论分布:")
        for row in cur.fetchall():
            print(f"    {row[0]}: {row[1]}条")
    
    conn.close()
    print(f"\n✅ 完成！共写入10000条模拟数据")

if __name__ == "__main__":
    main()
