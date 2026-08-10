#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
审计票据 & 凭证识别 — VLM 微调数据集生成脚本

功能：从原始图片文件夹中采样、复制到新目录，并生成结构化 JSONL 训练数据

用法：
    python generate_vlm_dataset.py --max_per_category 100 --output_dir ../dataset --train_split 0.9
"""

import os
import sys
import json
import random
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# ============================================================
# 全局配置
# ============================================================

INSTRUCTION = (
    "你是一名专业的审计员。请准确识别并描述这张票据/凭证中的所有关键信息，"
    "包括但不限于：票据类型、日期、金额、相关方、编号、摘要等。"
)

IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')

# ============================================================
# 随机数据生成辅助函数
# ============================================================

def random_date(start_year=2020, end_year=2025):
    """生成随机日期"""
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return (start + timedelta(days=random_days)).strftime('%Y-%m-%d')

def random_amount(min_val=100, max_val=500000):
    """生成随机金额（带两位小数）"""
    val = random.uniform(min_val, max_val)
    return f"¥{val:,.2f}"

def random_company():
    """生成随机公司名称"""
    cities = ['北京', '上海', '深圳', '广州', '杭州', '苏州', '成都', '武汉', '南京', '天津']
    industries = ['科技', '贸易', '电子', '建筑', '咨询', '物流', '制造', '软件', '金融', '医药']
    suffixes = ['有限公司', '股份有限公司', '有限责任公司', '集团有限公司']
    return f"{random.choice(cities)}市{random.choice(industries)}{random.choice(suffixes)}"

def random_bank():
    """生成随机银行名称"""
    banks = ['中国工商银行', '中国建设银行', '中国农业银行', '中国银行', '招商银行',
             '交通银行', '中信银行', '浦发银行', '光大银行', '民生银行']
    return random.choice(banks)

def random_tax_id():
    """生成随机税号"""
    return ''.join([str(random.randint(0, 9)) for _ in range(18)])

def random_invoice_code():
    """生成随机发票代码"""
    return ''.join([str(random.randint(0, 9)) for _ in range(10)])

def random_invoice_number():
    """生成随机发票号码"""
    return ''.join([str(random.randint(0, 9)) for _ in range(8)])

def random_account():
    """生成随机账号"""
    return ''.join([str(random.randint(0, 9)) for _ in range(16)])

def random_phone():
    """生成随机手机号"""
    prefix = random.choice(['138', '139', '137', '136', '135', '150', '151', '152', '186', '185'])
    return prefix + ''.join([str(random.randint(0, 9)) for _ in range(8)])

# ============================================================
# 按文档类型分组的 caption 生成器
# ============================================================

def caption_vat_invoice(category):
    """增值税发票类（专用/普通/电子）"""
    amt = random_amount(1000, 500000)
    tax = random_amount(100, 80000)
    total = random_amount(2000, 600000)
    return (
        f"{category}，"
        f"发票代码：{random_invoice_code()}，"
        f"发票号码：{random_invoice_number()}，"
        f"开票日期：{random_date()}，"
        f"购买方：{random_company()}，"
        f"购买方税号：{random_tax_id()}，"
        f"销售方：{random_company()}，"
        f"销售方税号：{random_tax_id()}，"
        f"金额合计：{amt}，"
        f"税率：{random.choice(['6%', '9%', '13%'])}，"
        f"税额：{tax}，"
        f"价税合计：{total}，"
        f"备注：{random.choice(['货款', '服务费', '材料费', '工程款', '咨询费'])}。"
    )

def caption_electronic_invoice(category):
    """全电发票 / 电子发票"""
    amt = random_amount(500, 200000)
    return (
        f"{category}，"
        f"发票号码：{random_invoice_number()}，"
        f"开票日期：{random_date()}，"
        f"购买方：{random_company()}，"
        f"销售方：{random_company()}，"
        f"金额：{amt}，"
        f"备注：{random.choice(['电子发票', '线上交易', '服务收入'])}。"
    )

def caption_general_invoice(category):
    """普通发票类（住宿、餐饮、交通、运输等）"""
    amt = random_amount(50, 10000)
    return (
        f"{category}，"
        f"发票号码：{random_invoice_number()}，"
        f"开票日期：{random_date()}，"
        f"付款方：{random_company()}，"
        f"金额：{amt}，"
        f"备注：{random.choice(['住宿费', '餐饮费', '交通费', '运输费', '水电费'])}。"
    )

def caption_transport_ticket(category):
    """交通票据（出租车、船票、火车票、航空票）"""
    amt = random_amount(50, 5000)
    return (
        f"{category}，"
        f"票号：{random_invoice_number()}，"
        f"日期：{random_date()}，"
        f"出发地：{random.choice(['北京', '上海', '广州', '深圳', '成都'])}，"
        f"目的地：{random.choice(['北京', '上海', '广州', '深圳', '杭州'])}，"
        f"金额：{amt}，"
        f"乘客/托运人：{random.choice(['张三', '李四', '王五', '赵六'])}。"
    )

def caption_bank_receipt(category):
    """银行回单/银行进账单/电汇凭证"""
    amt = random_amount(1000, 500000)
    return (
        f"{category}，"
        f"交易日期：{random_date()}，"
        f"付款方：{random_company()}，"
        f"付款账号：{random_account()}，"
        f"收款方：{random_company()}，"
        f"收款账号：{random_account()}，"
        f"开户银行：{random_bank()}，"
        f"金额：{amt}，"
        f"摘要：{random.choice(['货款', '服务费', '借款', '还款', '工资'])}，"
        f"交易流水号：{random_invoice_number()}{random_invoice_number()}。"
    )

def caption_bank_check(category):
    """支票类（转账支票、现金支票）"""
    amt = random_amount(1000, 100000)
    return (
        f"{category}，"
        f"出票日期：{random_date()}，"
        f"付款行：{random_bank()}，"
        f"出票人账号：{random_account()}，"
        f"收款人：{random_company()}，"
        f"金额：{amt}，"
        f"用途：{random.choice(['货款', '备用金', '差旅费', '工资'])}。"
    )

def caption_loan_receipt(category):
    """贷款借据/贴现凭证/还款凭证"""
    amt = random_amount(100000, 5000000)
    return (
        f"{category}，"
        f"日期：{random_date()}，"
        f"借款人/还款人：{random_company()}，"
        f"贷款银行：{random_bank()}，"
        f"金额：{amt}，"
        f"期限：{random.choice(['6个月', '1年', '3年', '5年'])}，"
        f"利率：{random.uniform(3.5, 6.5):.2f}%。"
    )

def caption_cash_doc(category):
    """现金缴款单/现金盘点表"""
    amt = random_amount(1000, 500000)
    return (
        f"{category}，"
        f"日期：{random_date()}，"
        f"缴款单位/盘点部门：{random_company()}，"
        f"金额：{amt}，"
        f"币种：人民币，"
        f"缴款人/盘点人：{random.choice(['张三', '李四', '王五'])}。"
    )

def caption_accounting_voucher(category):
    """会计凭证（付款/收款/转账/记账/原始）"""
    amt = random_amount(500, 100000)
    return (
        f"{category}，"
        f"凭证日期：{random_date()}，"
        f"凭证号：记-{random.randint(1, 999)}-{random.randint(1, 99)}，"
        f"摘要：{random.choice(['支付货款', '收到服务费', '转账备用金', '计提折旧', '工资发放'])}，"
        f"借方科目：{random.choice(['银行存款', '库存现金', '管理费用', '销售费用', '应收账款'])}，"
        f"贷方科目：{random.choice(['应付账款', '主营业务收入', '银行存款', '累计折旧'])}，"
        f"金额：{amt}。"
    )

def caption_expense_reimbursement(category):
    """费用报销单/差旅费报销单"""
    total = random_amount(500, 20000)
    return (
        f"{category}，"
        f"报销日期：{random_date()}，"
        f"报销人：{random.choice(['张三', '李四', '王五', '赵六', '陈七'])}，"
        f"部门：{random.choice(['财务部', '销售部', '技术部', '行政部', '市场部'])}，"
        f"金额合计：{total}，"
        f"事由：{random.choice(['北京出差', '客户招待', '办公采购', '培训费用', '市场调研'])}，"
        f"审批人：{random.choice(['部门经理', '财务总监', '总经理'])}。"
    )

def caption_application_form(category):
    """付款/采购/借款申请单"""
    amt = random_amount(1000, 500000)
    return (
        f"{category}，"
        f"申请日期：{random_date()}，"
        f"申请部门：{random.choice(['财务部', '采购部', '技术部', '行政部'])}，"
        f"申请人：{random.choice(['张三', '李四', '王五'])}，"
        f"金额：{amt}，"
        f"事由：{random.choice(['支付货款', '采购设备', '备用金借款', '项目支出'])}，"
        f"审批状态：{random.choice(['待审批', '已审批', '已支付'])}。"
    )

def caption_payroll(category):
    """工资单/加班工资表/年终奖金表/劳务费/福利费"""
    total = random_amount(20000, 500000)
    net = random_amount(18000, 450000)
    return (
        f"{category}，"
        f"月份/期间：2025年{random.randint(1, 12)}月，"
        f"部门：{random.choice(['技术部', '销售部', '财务部', '行政部', '全公司'])}，"
        f"人数：{random.randint(5, 200)}人，"
        f"应发合计：{total}，"
        f"实发合计：{net}，"
        f"扣款合计：{random_amount(1000, 50000)}，"
        f"制表人：{random.choice(['张三', '李四', '王五'])}。"
    )

def caption_attendance(category):
    """考勤表/公积金/社保/个税记录"""
    return (
        f"{category}，"
        f"月份：2025年{random.randint(1, 12)}月，"
        f"部门/单位：{random_company()}，"
        f"人数：{random.randint(5, 200)}人，"
        f"应出勤天数：{random.randint(20, 22)}天，"
        f"备注：{random.choice(['正常', '缺勤1天', '迟到2次'])}。"
    )

def caption_contract(category):
    """合同/协议类"""
    amt = random_amount(100000, 5000000)
    return (
        f"{category}，"
        f"合同编号：HT-{random.randint(2020, 2025)}-{random.randint(1, 999):03d}，"
        f"甲方：{random_company()}，"
        f"乙方：{random_company()}，"
        f"合同金额：{amt}，"
        f"签订日期：{random_date()}，"
        f"有效期：{random.choice(['1年', '2年', '3年', '5年'])}，"
        f"付款方式：{random.choice(['月结', '季度结', '一次性付清', '分期付款'])}。"
    )

def caption_financial_report(category):
    """财务报表（资产负债表、利润表、现金流量表等）"""
    return (
        f"{category}，"
        f"报表期间：2025年{random.randint(1, 4)}季度，"
        f"编制单位：{random_company()}，"
        f"编制日期：{random_date()}，"
        f"主要科目包括：{random.choice(['资产、负债、所有者权益', '营业收入、营业成本、净利润', '现金流入、现金流出、净现金流'])}，"
        f"金额单位：人民币元。"
    )

def caption_tax_report(category):
    """税务报表/申报表"""
    amt = random_amount(10000, 500000)
    return (
        f"{category}，"
        f"所属期：2025年{random.randint(1, 12)}月，"
        f"纳税人名称：{random_company()}，"
        f"纳税人识别号：{random_tax_id()}，"
        f"应纳税额：{amt}，"
        f"申报日期：{random_date()}，"
        f"主管税务机关：{random.choice(['北京市税务局', '上海市税务局', '深圳市税务局'])}。"
    )

def caption_audit_report(category):
    """审计报告/验资报告/内控报告/底稿"""
    return (
        f"{category}，"
        f"报告期间：2025年{random.randint(1, 4)}季度，"
        f"被审计单位：{random_company()}，"
        f"审计日期：{random_date()}，"
        f"审计意见：{random.choice(['无保留意见', '保留意见', '带强调事项段'])}，"
        f"审计机构：{random_company()}，"
        f"注册会计师：{random.choice(['CPA张三', 'CPA李四', 'CPA王五'])}。"
    )

def caption_confirmation_letter(category):
    """询证函/对账函/催款函/保函/信用证"""
    amt = random_amount(10000, 1000000)
    return (
        f"{category}，"
        f"函件日期：{random_date()}，"
        f"发函方：{random_company()}，"
        f"收函方：{random_company()}，"
        f"函证金额/事项：{amt}，"
        f"截止日期：{random_date()}，"
        f"函证类型：{random.choice(['积极式', '消极式', '普通'])}。"
    )

def caption_inventory_doc(category):
    """出入库单/调拨单/领料单/验收单/送货单"""
    amt = random_amount(1000, 100000)
    return (
        f"{category}，"
        f"日期：{random_date()}，"
        f"单号：{random.choice(['RK', 'CK', 'DB', 'LL', 'YS', 'SH'])}{random.randint(1000, 9999)}，"
        f"部门：{random.choice(['仓库', '生产部', '采购部', '技术部'])}，"
        f"金额：{amt}，"
        f"经办人：{random.choice(['张三', '李四', '王五'])}，"
        f"审批人：{random.choice(['部门经理', '仓库主管'])}。"
    )

def caption_fixed_asset(category):
    """固定资产相关（卡片、增加单、报废单、调拨单、台账）"""
    amt = random_amount(5000, 500000)
    return (
        f"{category}，"
        f"日期：{random_date()}，"
        f"资产编号：ZC-{random.randint(1000, 9999)}，"
        f"资产名称：{random.choice(['电脑', '打印机', '服务器', '办公桌椅', '车辆'])}，"
        f"使用部门：{random.choice(['财务部', '技术部', '行政部'])}，"
        f"原值：{amt}，"
        f"使用人：{random.choice(['张三', '李四', '王五'])}。"
    )

def caption_cost_depreciation(category):
    """成本计算单/折旧计算表"""
    amt = random_amount(10000, 500000)
    return (
        f"{category}，"
        f"月份：2025年{random.randint(1, 12)}月，"
        f"部门：{random.choice(['生产部', '技术部', '全公司'])}，"
        f"计算金额：{amt}，"
        f"计算方法：{random.choice(['直线法', '工作量法', '双倍余额递减法'])}，"
        f"制表人：{random.choice(['张三', '李四', '王五'])}。"
    )

def caption_certificate(category):
    """证照/证件类（营业执照、税务登记等）"""
    return (
        f"{category}，"
        f"企业名称：{random_company()}，"
        f"统一社会信用代码/注册号：{random_tax_id()}，"
        f"法定代表人：{random.choice(['张三', '李四', '王五', '赵六'])}，"
        f"成立日期：{random_date(2010, 2020)}，"
        f"发证机关：{random.choice(['北京市市场监督管理局', '上海市市场监督管理局', '深圳市市场监督管理局'])}。"
    )

def caption_receipt(category):
    """收据/捐赠/会费/非税收入票据"""
    amt = random_amount(100, 50000)
    return (
        f"{category}，"
        f"日期：{random_date()}，"
        f"收款单位：{random_company()}，"
        f"付款单位：{random_company()}，"
        f"金额：{amt}，"
        f"收款事由：{random.choice(['服务费', '捐赠款', '会费', '培训费', '材料费'])}，"
        f"收款人：{random.choice(['张三', '李四', '王五'])}。"
    )

def caption_generic(category):
    """通用 fallback 模板"""
    return (
        f"{category}，"
        f"日期：{random_date()}，"
        f"相关方：{random_company()}，"
        f"金额：{random_amount()}，"
        f"编号：{random_invoice_number()}，"
        f"备注：{random.choice(['正常业务', '常规交易', '标准流程'])}。"
    )

# ============================================================
# 类别 → 生成器 映射表
# ============================================================

CATEGORY_GENERATORS = {
    # 增值税发票类
    '增值税专用发票': caption_vat_invoice,
    '增值税普通发票': caption_vat_invoice,
    '增值税电子专用发票': caption_vat_invoice,
    '增值税电子普通发票': caption_vat_invoice,
    '增值税发票汇总表': caption_vat_invoice,
    '全电发票': caption_electronic_invoice,
    '红字发票': caption_vat_invoice,
    '海关进口增值税缴款书': caption_vat_invoice,
    
    # 其他发票类
    '住宿发票': caption_general_invoice,
    '餐饮发票': caption_general_invoice,
    '交通运输业发票': caption_general_invoice,
    '二手车销售发票': caption_general_invoice,
    '机动车销售发票': caption_general_invoice,
    '建筑安装业发票': caption_general_invoice,
    '服务业发票': caption_general_invoice,
    '水电费发票': caption_general_invoice,
    '物业费发票': caption_general_invoice,
    '保险费发票': caption_general_invoice,
    '农产品收购发票': caption_general_invoice,
    '非税收入票据': caption_general_invoice,
    '通用机打发票': caption_general_invoice,
    '出租车发票': caption_transport_ticket,
    '船票': caption_transport_ticket,
    '铁路车票': caption_transport_ticket,
    '航空运输电子客票': caption_transport_ticket,
    '航空运输货运单': caption_transport_ticket,
    '汽车客运票': caption_transport_ticket,
    '过路费发票': caption_transport_ticket,
    '停车费发票': caption_transport_ticket,
    '印花税票': caption_general_invoice,
    '医疗收费票据': caption_general_invoice,
    '捐赠收据': caption_receipt,
    '商业承兑汇票': caption_bank_check,
    '银行承兑汇票': caption_bank_check,
    '原始凭证': caption_accounting_voucher,
    '车辆购置税发票': caption_general_invoice,
    
    # 银行凭证类
    '银行回单': caption_bank_receipt,
    '银行存款余额调节表': caption_bank_receipt,
    '银行对账单': caption_bank_receipt,
    '银行进账单': caption_bank_receipt,
    '电汇凭证': caption_bank_receipt,
    '手续费回单': caption_bank_receipt,
    '利息单': caption_bank_receipt,
    '结汇水单': caption_bank_receipt,
    '转账支票': caption_bank_check,
    '现金支票': caption_bank_check,
    '贷款借据': caption_loan_receipt,
    '贴现凭证': caption_loan_receipt,
    '还款凭证': caption_loan_receipt,
    '现金缴款单': caption_cash_doc,
    '现金盘点表': caption_cash_doc,
    
    # 会计凭证类
    '付款凭证': caption_accounting_voucher,
    '收款凭证': caption_accounting_voucher,
    '转账凭证': caption_accounting_voucher,
    '记账凭证': caption_accounting_voucher,
    '内部转账单': caption_accounting_voucher,
    
    # 报销/申请单类
    '费用报销单': caption_expense_reimbursement,
    '差旅费报销单': caption_expense_reimbursement,
    '付款申请单': caption_application_form,
    '采购申请单': caption_application_form,
    '借款单': caption_application_form,
    '出差申请单': caption_application_form,
    
    # 工资/福利类
    '工资单': caption_payroll,
    '加班工资表': caption_payroll,
    '年终奖金表': caption_payroll,
    '劳务费发放表': caption_payroll,
    '福利费发放表': caption_payroll,
    '考勤表': caption_attendance,
    '公积金缴存凭证': caption_attendance,
    '社保缴费凭证': caption_attendance,
    '个人所得税纳税记录': caption_attendance,
    
    # 合同类
    '劳动合同': caption_contract,
    '劳务合同': caption_contract,
    '购销合同': caption_contract,
    '租赁合同': caption_contract,
    '国际汇款申请书': caption_application_form,
    
    # 财务报表类
    '资产负债表': caption_financial_report,
    '利润表': caption_financial_report,
    '现金流量表': caption_financial_report,
    '所有者权益变动表': caption_financial_report,
    '总账': caption_financial_report,
    '明细账': caption_financial_report,
    '日记账': caption_financial_report,
    
    # 税务报表类
    '企业所得税汇算清缴': caption_tax_report,
    '房产税申报表': caption_tax_report,
    '出口退税申报表': caption_tax_report,
    '纳税申报表': caption_tax_report,
    '税收缴款书': caption_tax_report,
    '税务事项通知书': caption_tax_report,
    '税务登记证': caption_certificate,
    
    # 审计文档类
    '审计报告': caption_audit_report,
    '专项审计报告': caption_audit_report,
    '内部控制审计报告': caption_audit_report,
    '审计工作底稿': caption_audit_report,
    '审计业务约定书': caption_audit_report,
    '管理层声明书': caption_audit_report,
    '验资报告': caption_audit_report,
    
    # 询证/函件类
    '企业询证函': caption_confirmation_letter,
    '存货询证函': caption_confirmation_letter,
    '应收账款询证函': caption_confirmation_letter,
    '应付账款询证函': caption_confirmation_letter,
    '银行询证函': caption_confirmation_letter,
    '对账函': caption_confirmation_letter,
    '催款函': caption_confirmation_letter,
    '保函': caption_confirmation_letter,
    '信用证': caption_confirmation_letter,
    
    # 出入库/调拨类
    '入库单': caption_inventory_doc,
    '出库单': caption_inventory_doc,
    '材料领用单': caption_inventory_doc,
    '调拨单': caption_inventory_doc,
    '比价单': caption_inventory_doc,
    '验收单': caption_inventory_doc,
    '送货单': caption_inventory_doc,
    '固定资产调拨单': caption_fixed_asset,
    
    # 固定资产/资产类
    '固定资产卡片': caption_fixed_asset,
    '固定资产增加单': caption_fixed_asset,
    '固定资产报废单': caption_fixed_asset,
    '无形资产台账': caption_fixed_asset,
    '折旧计算表': caption_cost_depreciation,
    '成本计算表': caption_cost_depreciation,
    
    # 证照类
    '营业执照': caption_certificate,
    '组织机构代码证': caption_certificate,
    '开户许可证': caption_certificate,
    
    # 通用收据类
    '收据': caption_receipt,
    '会费收据': caption_receipt,
}

# ============================================================
# 主函数
# ============================================================

def get_all_categories(source_dir):
    """获取所有类别文件夹及其图片数量"""
    categories = {}
    for item in sorted(os.listdir(source_dir)):
        item_path = os.path.join(source_dir, item)
        if os.path.isdir(item_path) and not item.startswith('_') and not item.startswith('.'):
            image_files = [f for f in os.listdir(item_path)
                           if f.lower().endswith(IMAGE_EXTS)]
            if image_files:
                categories[item] = sorted(image_files)
    return categories


def generate_dataset(source_dir, output_dir, max_per_category=100, train_split=0.9, seed=42):
    """
    生成 VLM 训练数据集

    参数:
        source_dir: 原始图片文件夹路径
        output_dir: 输出数据集路径
        max_per_category: 每个类别最多采样的图片数
        train_split: 训练集比例
        seed: 随机种子
    """
    random.seed(seed)

    # 创建输出目录
    images_dir = os.path.join(output_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)

    print(f"{'='*60}")
    print(f"审计票据 VLM 训练数据集生成")
    print(f"{'='*60}")
    print(f"源目录: {source_dir}")
    print(f"输出目录: {output_dir}")
    print(f"每类最大采样: {max_per_category}")
    print(f"训练集比例: {train_split:.0%}")
    print(f"{'='*60}")

    # 获取所有类别
    categories = get_all_categories(source_dir)
    total_cats = len(categories)
    print(f"\n发现 {total_cats} 个类别")

    # 收集所有数据条目
    all_entries = []
    copied_count = 0
    skipped_count = 0

    for cat_idx, (category, image_files) in enumerate(categories.items(), 1):
        # 确定采样数量
        sample_count = min(max_per_category, len(image_files))
        sampled_files = random.sample(image_files, sample_count)

        # 获取 caption 生成器
        generator = CATEGORY_GENERATORS.get(category, caption_generic)

        for img_idx, filename in enumerate(sampled_files, 1):
            src_path = os.path.join(source_dir, category, filename)

            # 确定目标文件名（标准化命名）
            ext = os.path.splitext(filename)[1].lower()
            if ext == '.jpeg':
                ext = '.jpg'
            new_filename = f"{category}_{img_idx:04d}{ext}"
            dst_path = os.path.join(images_dir, new_filename)

            # 复制文件
            try:
                shutil.copy2(src_path, dst_path)
                copied_count += 1
            except Exception as e:
                print(f"  警告: 复制失败 {src_path} -> {e}")
                skipped_count += 1
                continue

            # 生成 caption
            caption = generator(category)

            # 构建 JSONL 条目
            entry = {
                "image": f"images/{new_filename}",
                "caption": caption,
                "instruction": INSTRUCTION,
                "category": category,
                "label": 0
            }
            all_entries.append(entry)

        # 打印进度
        print(f"  [{cat_idx}/{total_cats}] {category}: {sample_count} 张")

    print(f"\n{'='*60}")
    print(f"图片复制完成: {copied_count} 张成功, {skipped_count} 张失败")
    print(f"总条目数: {len(all_entries)}")
    print(f"{'='*60}")

    # 划分训练集和验证集
    random.shuffle(all_entries)
    split_idx = int(len(all_entries) * train_split)
    train_entries = all_entries[:split_idx]
    val_entries = all_entries[split_idx:]

    print(f"训练集: {len(train_entries)} 条")
    print(f"验证集: {len(val_entries)} 条")

    # 写入 JSONL 文件
    train_path = os.path.join(output_dir, 'train.jsonl')
    val_path = os.path.join(output_dir, 'val.jsonl')
    meta_path = os.path.join(output_dir, 'meta.json')

    with open(train_path, 'w', encoding='utf-8') as f:
        for entry in train_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    with open(val_path, 'w', encoding='utf-8') as f:
        for entry in val_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    # 生成元数据
    meta = {
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_entries': len(all_entries),
        'train_entries': len(train_entries),
        'val_entries': len(val_entries),
        'categories': list(categories.keys()),
        'category_count': total_cats,
        'max_per_category': max_per_category,
        'train_split': train_split,
        'instruction': INSTRUCTION
    }

    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n输出文件:")
    print(f"  - {train_path}")
    print(f"  - {val_path}")
    print(f"  - {meta_path}")
    print(f"  - {images_dir}/")
    print(f"\n{'='*60}")
    print("数据集生成完成!")
    print(f"{'='*60}")

    return len(train_entries), len(val_entries)


# ============================================================
# 命令行入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='生成审计票据 VLM 训练数据集')
    parser.add_argument('--source_dir', type=str, default='../downloaded',
                        help='原始图片文件夹路径 (默认: ../downloaded)')
    parser.add_argument('--output_dir', type=str, default='../dataset',
                        help='输出数据集路径 (默认: ../dataset)')
    parser.add_argument('--max_per_category', type=int, default=100,
                        help='每个类别最多采样的图片数 (默认: 100)')
    parser.add_argument('--train_split', type=float, default=0.9,
                        help='训练集比例 (默认: 0.9)')
    parser.add_argument('--seed', type=int, default=42,
                        help='随机种子 (默认: 42)')

    args = parser.parse_args()

    # 解析为绝对路径
    source_dir = os.path.abspath(args.source_dir)
    output_dir = os.path.abspath(args.output_dir)

    if not os.path.exists(source_dir):
        print(f"错误: 源目录不存在: {source_dir}")
        sys.exit(1)

    generate_dataset(
        source_dir=source_dir,
        output_dir=output_dir,
        max_per_category=args.max_per_category,
        train_split=args.train_split,
        seed=args.seed
    )


if __name__ == '__main__':
    main()
