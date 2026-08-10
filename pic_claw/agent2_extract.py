# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import os
import sys
import json
import re
import time
import base64
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pic_claw.pipeline_db import (
    get_pending_extract_images, update_extract_status,
    insert_extracted_field, insert_agent_log, insert_pipeline_log,
    get_batch, update_batch_progress, get_extract_stats,
    get_expected_fields
)
from services.ollama_client import call_llm, get_main_model

MAX_WORKERS = 5
BATCH_SIZE = 50

# ============================================================
# Agent2 提取提示词系统
# 设计原则：
#   1. 按10大类别提供基础字段模板
#   2. 按130种具体凭证类型提供视觉线索和提取指引
#   3. 统一的输出格式和置信度评分标准
#   4. 包含提取规则和常见错误防范
# ============================================================

# ---- 10大类基础字段模板 ----
FIELD_TEMPLATES = {
    "发票类": [
        {"name": "invoice_code", "type": "text", "label": "发票代码"},
        {"name": "invoice_number", "type": "text", "label": "发票号码"},
        {"name": "date", "type": "date", "label": "开票日期"},
        {"name": "amount", "type": "amount", "label": "金额(含税)"},
        {"name": "amount_without_tax", "type": "amount", "label": "金额(不含税)"},
        {"name": "tax_amount", "type": "amount", "label": "税额"},
        {"name": "buyer_name", "type": "text", "label": "购买方名称"},
        {"name": "seller_name", "type": "text", "label": "销售方名称"},
        {"name": "buyer_tax_id", "type": "text", "label": "购买方纳税人识别号"},
        {"name": "seller_tax_id", "type": "text", "label": "销售方纳税人识别号"},
    ],
    "差旅票据类": [
        {"name": "passenger_name", "type": "text", "label": "乘客姓名"},
        {"name": "date", "type": "date", "label": "日期"},
        {"name": "amount", "type": "amount", "label": "金额"},
        {"name": "from_city", "type": "text", "label": "出发地"},
        {"name": "to_city", "type": "text", "label": "到达地"},
        {"name": "transport_type", "type": "text", "label": "交通工具类型"},
        {"name": "seat_class", "type": "text", "label": "座位等级"},
    ],
    "银行/资金类": [
        {"name": "account_no", "type": "text", "label": "账号"},
        {"name": "account_name", "type": "text", "label": "户名"},
        {"name": "bank_name", "type": "text", "label": "开户行"},
        {"name": "trade_date", "type": "date", "label": "交易日期"},
        {"name": "amount", "type": "amount", "label": "交易金额"},
        {"name": "direction", "type": "text", "label": "借贷方向"},
        {"name": "summary", "type": "text", "label": "摘要/用途"},
        {"name": "balance", "type": "amount", "label": "账户余额"},
    ],
    "函证/审计类": [
        {"name": "company_name", "type": "text", "label": "公司名称"},
        {"name": "audit_firm", "type": "text", "label": "审计机构"},
        {"name": "balance_amount", "type": "amount", "label": "往来余额"},
        {"name": "confirm_date", "type": "date", "label": "函证日期"},
        {"name": "conclusion", "type": "text", "label": "结论"},
        {"name": "project_name", "type": "text", "label": "项目名称"},
    ],
    "税务类": [
        {"name": "taxpayer_name", "type": "text", "label": "纳税人名称"},
        {"name": "taxpayer_id", "type": "text", "label": "纳税人识别号"},
        {"name": "tax_type", "type": "text", "label": "税种"},
        {"name": "tax_period", "type": "text", "label": "所属时期"},
        {"name": "tax_amount", "type": "amount", "label": "税款金额"},
        {"name": "tax_authority", "type": "text", "label": "税务机关"},
    ],
    "企业内部管理类": [
        {"name": "dept_name", "type": "text", "label": "部门"},
        {"name": "applicant", "type": "text", "label": "申请人"},
        {"name": "date", "type": "date", "label": "日期"},
        {"name": "amount", "type": "amount", "label": "金额"},
        {"name": "description", "type": "text", "label": "事由/摘要"},
        {"name": "approver", "type": "text", "label": "审批人"},
    ],
    "薪酬/人事/合同类": [
        {"name": "employee_name", "type": "text", "label": "员工姓名"},
        {"name": "salary_amount", "type": "amount", "label": "工资金额"},
        {"name": "period", "type": "text", "label": "所属期间"},
        {"name": "company_name", "type": "text", "label": "单位名称"},
        {"name": "id_number", "type": "text", "label": "身份证号"},
    ],
    "账簿/分录/报表类": [
        {"name": "account_name", "type": "text", "label": "科目名称"},
        {"name": "period", "type": "text", "label": "会计期间"},
        {"name": "debit_amount", "type": "amount", "label": "借方金额"},
        {"name": "credit_amount", "type": "amount", "label": "贷方金额"},
        {"name": "balance", "type": "amount", "label": "余额"},
        {"name": "company_name", "type": "text", "label": "单位名称"},
    ],
    "固定资产/成本类": [
        {"name": "asset_name", "type": "text", "label": "资产名称"},
        {"name": "asset_no", "type": "text", "label": "资产编号"},
        {"name": "original_value", "type": "amount", "label": "原值"},
        {"name": "net_value", "type": "amount", "label": "净值"},
        {"name": "depreciation", "type": "amount", "label": "折旧额"},
        {"name": "dept_name", "type": "text", "label": "使用部门"},
    ],
    "收据/合同/资质类": [
        {"name": "receipt_no", "type": "text", "label": "收据编号"},
        {"name": "payer_name", "type": "text", "label": "付款方"},
        {"name": "amount", "type": "amount", "label": "金额"},
        {"name": "date", "type": "date", "label": "日期"},
        {"name": "description", "type": "text", "label": "内容摘要"},
        {"name": "party_a", "type": "text", "label": "甲方"},
        {"name": "party_b", "type": "text", "label": "乙方"},
    ],
}

# ---- 130种凭证类型视觉线索和提取指引 ----
# 格式: "凭证类型名称": "视觉特征描述和提取要点"
TYPE_VISUAL_GUIDANCE = {
    # ===== 发票类 (22种) =====
    "增值税专用发票": "通常为黄色或绿色底纹，左上角有'增值税专用发票'字样，右侧有发票联/抵扣联标识。包含购销双方名称、税号、金额、税额、价税合计等关键信息。注意区分密码区和备注栏。",
    "增值税普通发票": "通常为蓝色或红色底纹，左上角有'增值税普通发票'字样。与专票类似但无抵扣联，注意发票代码和号码的印刷格式。",
    "增值税电子发票": "电子发票版式，通常有'增值税电子普通发票'或'电子发票'字样，右上角有二维码。注意电子发票号码和校验码。",
    "机动车销售发票": "通常为浅绿色底纹，有'机动车销售统一发票'字样。包含车辆类型、厂牌型号、合格证号、发动机号、车架号等车辆信息。",
    "二手车销售发票": "通常为浅蓝色底纹，有'二手车销售统一发票'字样。包含车辆信息、成交价格、原车主和新车主信息。",
    "通用机打发票": "通常为白色或浅色底纹，有'通用机打发票'字样。格式较简单，包含发票代码、号码、金额和收款单位。",
    "定额发票": "固定面额的小张发票，有'定额发票'字样。主要提取发票代码、号码、面额金额。",
    "航空运输电子客票": "行程单格式，有'航空运输电子客票行程单'字样。包含航班号、日期、时间、起止地、票价、燃油附加费、民航发展基金。",
    "航空运输货运单": "货运单据格式，有'航空货运单'字样。包含发货人、收货人、始发站、目的站、货物信息、运费。",
    "铁路车票": "火车票格式，有'铁路车票'或行程信息提示字样。包含车次、日期、发站、到站、座位号、票价。",
    "汽车客运票": "汽车票格式，有'客运发票'或'汽车票'字样。包含日期、时间、起止站点、票价。",
    "船票": "船票格式，有'船票'字样。包含航线、日期、时间、舱位等级、票价。",
    "停车费发票": "停车收费小票格式，有'停车费'字样。包含车牌号、入场时间、出场时间、停车时长、收费金额。",
    "过路费发票": "高速公路收费票据，有'通行费发票'字样。包含入口、出口、车型、收费金额、日期。",
    "餐饮发票": "餐饮业发票，有'餐饮发票'或'饮食业发票'字样。包含消费金额、日期、商家名称。",
    "住宿费发票": "住宿业发票，有'住宿发票'字样。包含入住日期、离店日期、房费金额、酒店名称。",
    "物业费发票": "物业管理费发票，有'物业费发票'字样。包含物业公司名称、业主信息、收费期间、金额。",
    "水电费发票": "水电费缴费凭证，有'水费/电费发票'字样。包含户号、户名、地址、用量、金额、收费期间。",
    "通信费发票": "通信服务发票，有'通信费发票'字样。包含电话号码、套餐名称、消费金额、账期。",
    "车辆购置税发票": "车辆购置税完税证明，有'车辆购置税'字样。包含车辆信息、计税金额、税率、税款。",
    "海关进口增值税缴款书": "海关缴款书格式，有'海关进口增值税专用缴款书'字样。包含海关编号、纳税人识别号、完税价格、税率、税款金额。",
    "非税收入票据": "非税收入统一票据格式，有'非税收入统一票据'字样。包含执收单位、项目名称、金额、缴款人。",

    # ===== 差旅票据类 (8种) =====
    "差旅费报销单": "企业内部报销单格式，有'差旅费报销单'标题。包含出差人、部门、出差事由、起止日期、交通费、住宿费、补助等明细。",
    "出差申请单": "企业内部申请单格式，有'出差申请单'标题。包含申请人、部门、出差地点、起止日期、预计费用、审批人。",
    "航空运输电子客票": "同发票类，已在上方定义。",
    "铁路车票": "同发票类，已在上方定义。",
    "汽车客运票": "同发票类，已在上方定义。",
    "船票": "同发票类，已在上方定义。",
    "住宿费发票": "同发票类，已在上方定义。",
    "餐饮发票": "同发票类，已在上方定义。",

    # ===== 银行/资金类 (14种) =====
    "银行回单": "银行交易回单格式，有'业务回单'或'电子回单'字样。包含交易日期、收款人、付款人、金额、摘要、交易流水号。注意区分贷方回单和借方回单。",
    "银行对账单": "银行对账单格式，有'银行对账单'字样。包含账户信息、交易明细列表（日期、摘要、借方、贷方、余额）。提取所有交易明细。",
    "银行进账单": "银行进账单格式，有'进账单'字样。包含出票人、收款人、金额、票据种类、票据号码。",
    "银行承兑汇票": "银行承兑汇票格式，有'银行承兑汇票'字样。包含出票人、收款人、承兑行、票面金额、到期日、汇票号码。",
    "银行询证函": "银行询证函格式，有'银行询证函'字样。包含被审计单位名称、银行账户信息、余额、函证事项。",
    "银行存款余额调节表": "企业内部调节表格式，有'银行存款余额调节表'标题。包含银行对账单余额、企业账面余额、未达账项（加项/减项）、调节后余额。",
    "现金支票": "现金支票格式，有'现金支票'字样。包含出票日期、收款人、金额（大小写）、用途、付款行名称、出票人账号。",
    "转账支票": "转账支票格式，有'转账支票'字样。与现金支票类似但不可取现，包含出票日期、收款人、金额、用途。",
    "电汇凭证": "电汇凭证格式，有'电汇凭证'字样。包含汇款人、收款人、汇出行、汇入行、金额、用途。",
    "结汇水单": "结汇水单格式，有'结汇水单'或'外汇兑换'字样。包含外币金额、汇率、人民币金额、结汇日期、客户名称。",
    "贴现凭证": "贴现凭证格式，有'贴现凭证'字样。包含票据信息、贴现率、贴现利息、实付金额。",
    "贷款借据": "贷款借据格式，有'借款借据'或'贷款凭证'字样。包含借款人、贷款金额、利率、期限、还款方式。",
    "还款凭证": "还款凭证格式，有'还款凭证'字样。包含借款人、还款金额、还款日期、贷款合同号。",
    "现金缴款单": "现金缴款单格式，有'现金缴款单'字样。包含缴款单位、账号、金额、款项来源。",

    # ===== 函证/审计类 (8种) =====
    "银行询证函": "同银行/资金类，已在上方定义。",
    "企业询证函": "企业间往来询证函格式，有'企业询证函'字样。包含被函证单位、函证事项、往来余额、回函要求。",
    "往来款项询证函": "往来款项询证函格式，有'往来款项询证函'字样。包含应收账款/应付账款余额、账龄、函证期间。",
    "管理层声明书": "管理层声明书格式，有'管理层声明书'字样。包含被审计单位名称、审计期间、声明事项、签字盖章。",
    "验资报告": "验资报告格式，有'验资报告'字样。包含被审验单位、注册资本、实收资本、验资事项说明。",
    "审计报告": "审计报告格式，有'审计报告'字样。包含被审计单位、审计意见类型、审计期间、签字注册会计师。",
    "税务事项通知书": "税务事项通知书格式，有'税务事项通知书'字样。包含纳税人名称、通知事项、处理决定、日期。",
    "税务登记证": "税务登记证格式，有'税务登记证'字样。包含纳税人名称、纳税人识别号、地址、登记日期。",

    # ===== 税务类 (8种) =====
    "纳税申报表": "纳税申报表格式，有'纳税申报表'字样。包含纳税人信息、税种、申报期间、计税依据、应纳税额、已缴税额、应补退税额。",
    "增值税纳税申报表": "增值税专用申报表格式，有'增值税纳税申报表'字样。包含销售额、进项税额、销项税额、应纳税额、免抵退税额。",
    "企业所得税申报表": "企业所得税申报表格式，有'企业所得税申报表'字样。包含收入总额、成本费用、应纳税所得额、税率、应纳税额。",
    "个人所得税申报表": "个人所得税申报表格式，有'个人所得税申报表'字样。包含纳税人信息、收入额、扣除项、应纳税额。",
    "税收缴款书": "税收缴款书格式，有'税收缴款书'字样。包含纳税人名称、税种、所属时期、缴款金额、缴款期限。",
    "完税凭证": "完税凭证格式，有'完税证明'或'税收完税证明'字样。包含纳税人名称、税种、税款所属期、实缴金额、开具日期。",
    "车辆购置税发票": "同发票类，已在上方定义。",
    "社保缴费凭证": "社保缴费凭证格式，有'社会保险费缴费凭证'字样。包含单位名称、社保号、缴费基数、缴费金额、所属期。",

    # ===== 企业内部管理类 (16种) =====
    "费用报销单": "企业内部报销单格式，有'费用报销单'标题。包含报销部门、报销人、报销日期、费用明细（多行）、合计金额、审批签字。",
    "差旅费报销单": "同差旅票据类，已在上方定义。",
    "付款申请单": "付款申请单格式，有'付款申请单'标题。包含申请部门、申请人、收款方信息、付款金额、付款事由、审批流程。",
    "借款单": "借款单格式，有'借款单'标题。包含借款人、借款金额、借款日期、预计还款日期、借款事由、审批人。",
    "入库单": "入库单格式，有'入库单'标题。包含入库日期、供应商、物料/商品明细（名称、规格、数量、单价、金额）、入库人、验收人。",
    "出库单": "出库单格式，有'出库单'标题。包含出库日期、领用部门、物料明细（名称、规格、数量、单价、金额）、领用人、发货人。",
    "调拨单": "调拨单格式，有'调拨单'标题。包含调出部门、调入部门、调拨日期、物料明细、调拨原因。",
    "盘点表": "盘点表格式，有'盘点表'标题。包含盘点日期、盘点区域、物料列表（账面数量、实盘数量、差异）、盘点人、监盘人。",
    "现金盘点表": "现金盘点表格式，有'现金盘点表'标题。包含盘点日期、币种、面额明细、账面余额、实盘余额、差异、出纳、监盘人。",
    "银行存款余额调节表": "同银行/资金类，已在上方定义。",
    "内部转账单": "内部转账单格式，有'内部转账单'标题。包含转出部门、转入部门、金额、转账事由、审批人。",
    "出差申请单": "同差旅票据类，已在上方定义。",
    "采购申请单": "采购申请单格式，有'采购申请单'标题。包含申请部门、申请人、采购物品明细、预算金额、需求日期、审批人。",
    "验收单": "验收单格式，有'验收单'标题。包含供应商、验收日期、物品明细、验收结论、验收人。",
    "送货单": "送货单格式，有'送货单'标题。包含送货单位、收货单位、送货日期、物品明细、签收人。",
    "比价单": "比价单格式，有'比价单'标题。包含采购物品、供应商列表（名称、报价、交货期）、比价结论、审批人。",

    # ===== 薪酬/人事/合同类 (10种) =====
    "工资单": "工资条格式，有'工资单'或'工资条'字样。包含员工姓名、部门、基本工资、津贴、奖金、扣款（社保、公积金、个税）、实发工资、所属月份。",
    "劳务费发放表": "劳务费发放表格式，有'劳务费发放表'标题。包含领款人、身份证号、劳务内容、金额、代扣税款、实发金额。",
    "社保缴费凭证": "同税务类，已在上方定义。",
    "公积金缴存凭证": "公积金缴存凭证格式，有'住房公积金缴存凭证'字样。包含单位名称、个人账号、缴存基数、单位缴存额、个人缴存额、所属期。",
    "考勤表": "考勤表格式，有'考勤表'标题。包含部门、姓名、日期、出勤情况（正常/迟到/早退/请假/加班）、汇总统计。",
    "年终奖金表": "年终奖发放表格式，有'年终奖金表'标题。包含员工姓名、部门、奖金基数、考核系数、实发奖金、所属年度。",
    "加班工资表": "加班工资表格式，有'加班工资表'标题。包含员工姓名、加班日期、加班时长、加班类型（平日/周末/节假日）、加班费。",
    "劳动合同": "劳动合同格式，有'劳动合同'标题。包含员工姓名、身份证号、合同期限、工作岗位、工资标准、签订日期。",
    "劳务合同": "劳务合同格式，有'劳务合同'标题。包含甲方、乙方、劳务内容、报酬、合同期限、签订日期。",
    "福利费发放表": "福利费发放表格式，有'福利费发放表'标题。包含领款人、福利项目、金额、所属期间、发放日期。",

    # ===== 账簿/分录/报表类 (12种) =====
    "记账凭证": "记账凭证格式，有'记账凭证'标题。包含凭证编号、日期、摘要、科目名称、借方金额、贷方金额、附单据数、制单人。",
    "原始凭证": "原始凭证格式，有'原始凭证'标题。包含凭证名称、日期、编号、经济业务内容、金额、经办人、负责人。",
    "收款凭证": "收款凭证格式，有'收款凭证'标题。包含凭证编号、日期、借方科目（通常为银行存款/现金）、贷方科目、金额、摘要。",
    "付款凭证": "付款凭证格式，有'付款凭证'标题。包含凭证编号、日期、贷方科目（通常为银行存款/现金）、借方科目、金额、摘要。",
    "转账凭证": "转账凭证格式，有'转账凭证'标题。包含凭证编号、日期、摘要、借方科目、贷方科目、金额。",
    "总账": "总账格式，有'总账'标题。包含科目名称、会计期间、期初余额、本期发生额（借方/贷方）、期末余额。",
    "明细账": "明细账格式，有'明细账'标题。包含科目名称、日期、凭证号、摘要、借方金额、贷方金额、余额。",
    "日记账": "日记账格式，有'日记账'或'现金/银行存款日记账'标题。包含日期、凭证号、摘要、对方科目、收入、支出、余额。",
    "资产负债表": "资产负债表格式，有'资产负债表'标题。包含资产（流动资产/非流动资产）、负债（流动负债/非流动负债）、所有者权益各项目金额及合计。提取主要项目金额。",
    "利润表": "利润表格式，有'利润表'标题。包含营业收入、营业成本、税金及附加、期间费用、营业利润、利润总额、净利润。",
    "现金流量表": "现金流量表格式，有'现金流量表'标题。包含经营活动/投资活动/筹资活动现金流量各项目金额。",
    "所有者权益变动表": "所有者权益变动表格式，有'所有者权益变动表'标题。包含实收资本、资本公积、盈余公积、未分配利润各项目变动情况。",

    # ===== 固定资产/成本类 (8种) =====
    "固定资产卡片": "固定资产卡片格式，有'固定资产卡片'标题。包含资产名称、编号、规格型号、使用部门、存放地点、原值、折旧方法、使用年限、净残值率。",
    "固定资产报废单": "固定资产报废单格式，有'固定资产报废单'标题。包含资产名称、编号、原值、已提折旧、净值、报废原因、审批意见。",
    "折旧计算表": "折旧计算表格式，有'折旧计算表'标题。包含资产列表（名称、原值、折旧方法、月折旧额、累计折旧、净值）、合计。",
    "成本计算单": "成本计算单格式，有'成本计算单'标题。包含产品名称、直接材料、直接人工、制造费用、合计、完工数量、单位成本。",
    "材料领用单": "材料领用单格式，有'材料领用单'标题。包含领用部门、领用日期、材料名称、规格、数量、单价、金额、用途。",
    "固定资产调拨单": "固定资产调拨单格式，有'固定资产调拨单'标题。包含资产名称、编号、调出部门、调入部门、调拨原因、审批人。",
    "固定资产增加单": "固定资产增加单格式，有'固定资产增加单'标题。包含资产名称、规格、数量、原值、使用部门、增加方式（购入/自建/捐赠等）。",
    "无形资产台账": "无形资产台账格式，有'无形资产台账'标题。包含无形资产名称、取得日期、原值、摊销方法、累计摊销、净值。",

    # ===== 收据/合同/资质类 (10种) =====
    "收据": "收据格式，有'收据'标题。包含收据编号、交款人、收款方式、金额（大小写）、收款事由、收款单位、收款日期。",
    "捐赠收据": "捐赠收据格式，有'捐赠收据'或'公益事业捐赠票据'字样。包含捐赠人、捐赠金额、捐赠项目、捐赠日期。",
    "会费收据": "会费收据格式，有'会费收据'字样。包含交费人、会费期间、会费金额、开票日期。",
    "购销合同": "购销合同格式，有'购销合同'标题。包含甲方、乙方、合同标的、数量、单价、总金额、交货日期、付款方式、签订日期。",
    "租赁合同": "租赁合同格式，有'租赁合同'标题。包含出租方、承租方、租赁物、租赁期限、租金、押金、签订日期。",
    "营业执照": "营业执照格式，有'营业执照'字样。包含统一社会信用代码、名称、类型、法定代表人、经营范围、注册资本、成立日期、营业期限。",
    "开户许可证": "开户许可证格式，有'开户许可证'字样。包含核准号、开户银行、账号、单位名称、法定代表人、开户日期。",
    "组织机构代码证": "组织机构代码证格式，有'组织机构代码证'字样。包含代码号、机构名称、机构类型、有效期。",
    "医疗收费票据": "医疗收费票据格式，有'医疗收费票据'字样。包含患者姓名、病历号、收费项目明细、合计金额、医保报销金额、自付金额。",
    "诉讼费票据": "诉讼费票据格式，有'诉讼费票据'字样。包含案件号、当事人、收费项目、金额、收费日期。",
}

# ---- 提取规则和置信度评分标准 ----
EXTRACTION_RULES = """
## 提取规则

### 1. 金额字段处理规则
- 只提取纯数字，去掉货币符号（¥、$、€等）
- 保留小数点后两位（如 1234.56）
- 千分位分隔符要去掉（如 1,234.56 → 1234.56）
- 金额范围用连字符（如 1000-2000）
- 大写金额不提取，只提取阿拉伯数字金额

### 2. 日期字段处理规则
- 统一格式为 YYYY-MM-DD
- 如看到"2024年3月5日" → "2024-03-05"
- 如看到"24.3.5" → "2024-03-05"
- 如看到"2024/3/5" → "2024-03-05"
- 只有年份和月份时用 YYYY-MM（如 "2024-03"）
- 只有年份时用 YYYY（如 "2024"）

### 3. 文本字段处理规则
- 保留原文内容，不要改写
- 去除首尾空格
- 多行文本用空格连接成一行
- 英文统一使用小写（专有名词除外）

### 4. 字段名命名规则
- 使用英文小写+下划线
- 通用字段名：amount, date, description, name, code, number
- 业务字段名：invoice_code, buyer_name, seller_name, tax_amount 等
- 不要使用中文作为字段名

### 5. 置信度评分标准
- _confidence: 0.95-1.00 = 文字清晰可见，所有字段都能准确识别
- _confidence: 0.80-0.94 = 大部分文字清晰，个别字段可能有模糊
- _confidence: 0.60-0.79 = 部分文字模糊或遮挡，核心字段可识别
- _confidence: 0.40-0.59 = 图片质量差，只能识别少量信息
- _confidence: 0.00-0.39 = 几乎无法识别，仅能猜测
"""

# ---- 输出格式示例 ----
OUTPUT_EXAMPLES = """
## 输出示例

### 示例1：增值税专用发票
{
    "invoice_code": "3100213410",
    "invoice_number": "12345678",
    "date": "2024-03-15",
    "buyer_name": "上海华兴科技有限公司",
    "buyer_tax_id": "91310115MA7XXXXXX",
    "seller_name": "深圳创新电子有限公司",
    "seller_tax_id": "91440300MA5XXXXXX",
    "amount": 113000.00,
    "amount_without_tax": 100000.00,
    "tax_amount": 13000.00,
    "_confidence": 0.97,
    "_summary": "增值税专用发票，金额113000元"
}

### 示例2：银行回单
{
    "trade_date": "2024-03-15",
    "account_name": "上海华兴科技有限公司",
    "account_no": "3100156789001234567",
    "bank_name": "工商银行浦东支行",
    "direction": "贷方",
    "amount": 50000.00,
    "summary": "货款收入",
    "balance": 350000.00,
    "_confidence": 0.95,
    "_summary": "银行贷方回单，收款50000元"
}

### 示例3：费用报销单
{
    "dept_name": "市场部",
    "applicant": "张三",
    "date": "2024-03-20",
    "amount": 3500.00,
    "description": "3月份市场推广活动费用",
    "approver": "李四",
    "_confidence": 0.88,
    "_summary": "市场部费用报销单3500元"
}

### 示例4：记账凭证
{
    "date": "2024-03-31",
    "account_name": "管理费用",
    "debit_amount": 5000.00,
    "credit_amount": 0,
    "description": "报销办公用品费用",
    "period": "2024-03",
    "_confidence": 0.92,
    "_summary": "记账凭证，管理费用5000元"
}
"""


def build_extract_prompt(doc_type_name: str, category_name: str) -> str:
    """构建优化的提取提示词

    策略：
    1. 先查数据库中的 expected_fields（最精确）
    2. 如果没有，使用大类模板 FIELD_TEMPLATES
    3. 如果都没有，使用默认的3个通用字段
    4. 加入视觉线索指导模型识别
    5. 加入提取规则和输出示例
    """
    # 获取字段模板
    db_fields = get_expected_fields(doc_type_name)
    if db_fields:
        fields = db_fields
    else:
        fields = FIELD_TEMPLATES.get(category_name, [])
        if not fields:
            fields = [
                {"name": "amount", "type": "amount", "label": "金额"},
                {"name": "date", "type": "date", "label": "日期"},
                {"name": "description", "type": "text", "label": "摘要"},
            ]

    # 格式化字段列表
    field_lines = []
    for f in fields:
        field_lines.append(f'    "{f["name"]}": "{f["label"]}"')
    field_list = "\n".join(field_lines)

    # 获取视觉线索
    visual_guide = TYPE_VISUAL_GUIDANCE.get(doc_type_name, "")
    if not visual_guide:
        visual_guide = f"这是一张{doc_type_name}类型的凭证，属于{category_name}大类。请仔细识别图片中的所有文字信息。"

    # 构建完整提示词
    prompt = f"""你是一位专业的审计凭证信息提取专家。请从这张图片中提取所有可见的关键字段信息。

## 凭证信息
- 凭证类型：{doc_type_name}
- 所属大类：{category_name}

## 视觉识别指引
{visual_guide}

## 参考字段（请尽量使用以下字段名，如果图片中有其他重要信息也一并提取）
{field_list}
{EXTRACTION_RULES}
{OUTPUT_EXAMPLES}

## 输出要求
请严格按照以下JSON格式输出（只输出JSON，不要包含任何其他文字）：
{{
    "字段名1": "字段值1",
    "字段名2": "字段值2",
    "_confidence": 0.95,
    "_summary": "简要描述该凭证的核心内容（20字以内）"
}}

注意：
1. 字段名使用英文小写+下划线
2. 不存在的字段不要包含在输出中
3. 金额只提取数字，去掉货币符号
4. 日期统一为 YYYY-MM-DD 格式
5. 提取所有你能找到的有用信息，不限于参考字段列表
6. 仔细阅读图片中的文字，确保提取准确
7. 如果图片内容与凭证类型不符，在_summary中说明"""
    return prompt


def image_to_base64(filepath: str) -> str:
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_single_image(image_id: int, file_path: str, file_name: str,
                         doc_type_name: str, category_name: str) -> dict:
    start_time = time.time()
    model_name = get_main_model()

    try:
        image_b64 = image_to_base64(file_path)
        prompt = build_extract_prompt(doc_type_name, category_name)
        raw_response = call_llm(prompt, model_key="main", image_base64=image_b64)
        duration_ms = int((time.time() - start_time) * 1000)

        json_str = raw_response.strip()
        json_str = re.sub(r"^```(?:json)?\s*", "", json_str)
        json_str = re.sub(r"\s*```$", "", json_str)
        result = json.loads(json_str)

        skip_keys = {"_confidence", "_summary", "_raw", "_note", "raw_response"}
        extracted_count = 0
        for field_name, field_value in result.items():
            if field_name in skip_keys:
                continue
            if field_value is None or str(field_value).strip() == "":
                continue

            field_value_str = str(field_value).strip()
            field_type = "text"
            if any(k in field_name for k in ("amount", "price", "total", "sum", "fee", "tax", "salary", "cost")):
                field_type = "amount"
            elif any(k in field_name for k in ("date", "time", "period")):
                field_type = "date"

            confidence = result.get("_confidence", 0.9)
            insert_extracted_field(
                image_id=image_id,
                field_name=field_name,
                field_value=field_value_str,
                field_type=field_type,
                confidence=confidence,
                extract_method="llm",
                source_text=None
            )
            extracted_count += 1

        update_extract_status(image_id, status="done")

        insert_agent_log(
            image_id=image_id,
            agent_stage="extract",
            input_summary=f"图片: {file_name} (类型: {doc_type_name})",
            output_json={
                "doc_type": doc_type_name,
                "category": category_name,
                "fields": result,
                "extracted_count": extracted_count,
                "raw_response": raw_response
            },
            llm_model=model_name,
            duration_ms=duration_ms,
            status="done"
        )

        return {
            "image_id": image_id,
            "status": "done",
            "doc_type_name": doc_type_name,
            "extracted_count": extracted_count,
            "duration_ms": duration_ms
        }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)

        update_extract_status(image_id, status="failed")

        insert_agent_log(
            image_id=image_id,
            agent_stage="extract",
            input_summary=f"图片: {file_name} (类型: {doc_type_name})",
            output_json={"error": error_msg},
            llm_model=get_main_model(),
            duration_ms=duration_ms,
            status="failed",
            error_msg=error_msg
        )

        return {
            "image_id": image_id,
            "status": "failed",
            "error": error_msg,
            "duration_ms": duration_ms
        }


def run_extract(batch_id: int = None, max_images: int = None, workers: int = MAX_WORKERS):
    print(f"Agent2 提取管道启动...")
    print(f"  并发数: {workers}")
    print(f"  模型: {get_main_model()}")
    if batch_id:
        batch_info = get_batch(batch_id)
        print(f"  批次: {batch_info['batch_no'] if batch_info else batch_id}")

    total_processed = 0
    total_done = 0
    total_failed = 0
    total_start = time.time()

    while True:
        images = get_pending_extract_images(batch_id=batch_id, limit=BATCH_SIZE)
        if not images:
            break

        if max_images and total_processed >= max_images:
            break

        batch_images = images
        if max_images:
            remaining = max_images - total_processed
            if len(batch_images) > remaining:
                batch_images = batch_images[:remaining]

        print(f"\n批次处理: {len(batch_images)} 张图片 (已处理 {total_processed})")

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for img in batch_images:
                future = executor.submit(
                    extract_single_image,
                    img["id"], img["file_path"], img["file_name"],
                    img["doc_type_name"], img["category_name"]
                )
                futures[future] = img

            for future in as_completed(futures):
                img = futures[future]
                try:
                    result = future.result()
                    total_processed += 1
                    if result["status"] == "done":
                        total_done += 1
                        print(f"  ✓ [{total_processed}] {img['file_name']} "
                              f"→ 提取{result.get('extracted_count', 0)}个字段 "
                              f"({result['duration_ms']}ms)")
                    else:
                        total_failed += 1
                        print(f"  ✗ [{total_processed}] {img['file_name']} "
                              f"→ 失败: {result.get('error', '')[:80]}")
                except Exception as e:
                    total_processed += 1
                    total_failed += 1
                    print(f"  ✗ [{total_processed}] {img['file_name']} → 异常: {str(e)[:80]}")

        if batch_id:
            update_batch_progress(batch_id, extract_progress=total_processed)

    elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"Agent2 提取完成")
    print(f"  处理: {total_processed} 张")
    print(f"  成功: {total_done}")
    print(f"  失败: {total_failed}")
    print(f"  耗时: {elapsed:.1f}秒")
    print(f"  平均: {elapsed / max(total_processed, 1):.1f}秒/张")
    print(f"{'=' * 60}")

    if batch_id:
        status = "done" if total_failed == 0 else "partial"
        insert_pipeline_log(None, batch_id, "agent2_extract", status,
                            f"成功{total_done}, 失败{total_failed}",
                            duration_ms=int(elapsed * 1000))

    return {"total": total_processed, "done": total_done, "failed": total_failed,
            "elapsed": elapsed}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Agent2 字段提取管道")
    parser.add_argument("--batch-id", type=int, help="批次ID")
    parser.add_argument("--max", type=int, help="最大处理数量")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="并发数")
    args = parser.parse_args()

    run_extract(batch_id=args.batch_id, max_images=args.max, workers=args.workers)