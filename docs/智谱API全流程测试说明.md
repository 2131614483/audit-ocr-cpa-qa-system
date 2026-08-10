# 审计OCR+CPA问答综合系统 - 智谱API全流程测试说明文档

## 一、系统概述

本系统基于智谱AI API（GLM-4.6V-FlashX）实现审计凭证的**自动分类**和**关键字段提取**，支持130种凭证类型的识别与结构化数据输出。

### 核心功能
- **Agent1 分类**：自动识别凭证类型（130种），归属10大类别
- **Agent2 提取**：按参考代码.py的JSON结构提取关键字段
- **自动整理**：按类别复制图片到文件夹，生成JSON结果文件

---

## 二、配置说明

### 2.1 智谱API配置

配置文件：`data/model_config.json`

```json
{
  "zhipu": {
    "name": "智谱AI API",
    "chat_api": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    "embed_api": "https://open.bigmodel.cn/api/paas/v4/embeddings",
    "api_key": "6fc16aaab7a24b93acd04f02942bf216.3XB3qLs03JoPNIaE",
    "models": {
      "main": "GLM-4.6V-FlashX",
      "fix": "GLM-4.7-FlashX",
      "embed": "embedding-3"
    },
    "vision_support": true
  }
}
```

### 2.2 数据库配置

```python
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "audit_pipeline_db",
    "user": "postgres",
    "password": "admin"
}
```

---

## 三、130种凭证类型与10大类别

### 3.1 类别分组

| 大类 | 包含类型数量 | 示例类型 |
|------|-------------|---------|
| 发票类 | 20 | 增值税专用发票、增值税普通发票、全电发票、餐饮发票、住宿发票等 |
| 差旅票据类 | 5 | 航空运输电子客票、铁路车票、出租车发票、过路费发票、停车费发票 |
| 银行金融类 | 10 | 银行回单、电子回单、银行对账单、银行承兑汇票、现金支票等 |
| 函证审计类 | 5 | 企业询证函、银行询证函、往来款项对账函、催款函、对账函 |
| 出入库类 | 5 | 入库单、出库单、送货单、验收单、领料单 |
| 报销付款类 | 5 | 借款单、报销单、付款申请单、差旅费报销单、费用报销单 |
| 薪酬社保类 | 5 | 工资表、工资条、社保缴费凭证、公积金缴费凭证、个人所得税纳税记录 |
| 记账凭证类 | 6 | 记账凭证、原始凭证、汇总凭证、转账凭证、收款凭证、付款凭证 |
| 账簿类 | 5 | 总账、明细账、日记账、多栏账、辅助账 |
| 财务报表类 | 5 | 资产负债表、利润表、现金流量表、所有者权益变动表、财务报表附注 |
| 审计报告类 | 5 | 审计报告、专项审计报告、审计工作底稿、验资报告、资产评估报告 |
| 证照资质类 | 5 | 营业执照、开户许可证、税务登记证、组织机构代码证、资质证书 |
| 合同协议类 | 5 | 合同、协议、租赁合同、采购合同、销售合同 |
| 海关税务类 | 5 | 完税凭证、税收缴款书、印花税票、海关单据、报关单 |
| 担保信用类 | 5 | 保函、信用证、担保合同、抵押合同、质押合同 |
| 审批决议类 | 5 | 股东会决议、董事会决议、会议纪要、立项审批表、签字页 |
| 资产管理类 | 5 | 固定资产增加单、固定资产减少单、固定资产盘点表、资产转移单、资产报废单 |
| 计算分配类 | 5 | 折旧计算表、摊销计算表、成本计算表、费用分配表、利润计算表 |
| 收据结算类 | 5 | 会费收据、捐赠收据、押金收据、违约金收据、结算单 |
| 税务管理类 | 5 | 个人所得税纳税记录、企业所得税汇算清缴、税务事项通知书等 |

---

## 四、JSON输出结构

### 4.1 完整JSON模板（参考参考代码.py）

```json
{
  "file_name": "付款申请单_0002.jpeg",
  "file_path": "D:\\pythonpro\\ollama项目\\审计OCR+CPA问答综合系统\\pic_claw\\downloaded\\付款申请单\\付款申请单_0002.jpeg",
  "classify_result": {
    "type_name": "付款申请单",
    "category": "报销付款类",
    "duration_s": 1.3
  },
  "extract_result": {
    "image_type": "付款申请单",
    "ocr_extract": {
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
      "seal_info": {
        "seal_type": "印章类型或N/A",
        "seal_number": "印章编号或N/A",
        "seal_clarity": "印章清晰度(清晰/模糊/无)或N/A",
        "joint_seal": "是否联合盖章(是/否)或N/A"
      },
      "license_info": {
        "unified_social_credit_code": "统一社会信用代码或N/A",
        "legal_person": "法定代表人或N/A",
        "valid_period": "有效期限或N/A"
      },
      "asset_info": {
        "asset_tag": "资产标签或N/A",
        "asset_name": "资产名称或N/A",
        "location": "位置或N/A",
        "quantity": "数量或N/A",
        "progress": "进度或N/A"
      },
      "internal_control_info": {
        "signer": "签字人或N/A",
        "approval_level": "审批级别或N/A",
        "attachment_complete": "附件是否完整(是/否)或N/A"
      },
      "other_info": "其他信息或N/A"
    },
    "validation_result": {
      "date_valid": true,
      "amount_valid": true,
      "code_format_valid": true,
      "no_missing_field": true,
      "image_normal": true,
      "no_duplicate": true,
      "consistent_info": true,
      "compliance": true,
      "no_fraud": true
    },
    "risk_rating": "高风险/中风险/低风险",
    "risk_description": "风险说明",
    "audit_conclusion": "通过/不通过/人工复核",
    "reason": "审计说明",
    "audit_value": "数字化审计留痕，可核对、可预警",
    "_confidence": 0.95,
    "_summary": "简要描述该凭证的核心内容（20字以内）"
  },
  "process_time": "2026-05-17 11:55:12",
  "total_duration_s": 13.1,
  "output_path": "D:\\pythonpro\\ollama项目\\审计OCR+CPA问答综合系统\\pic_claw\\分类结果_智谱\\报销付款类\\付款申请单\\付款申请单_0002.jpeg"
}
```

### 4.2 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `file_name` | string | 原始文件名 |
| `file_path` | string | 原始文件路径 |
| `classify_result.type_name` | string | 分类结果：凭证类型名称 |
| `classify_result.category` | string | 分类结果：所属大类 |
| `classify_result.duration_s` | float | 分类耗时（秒） |
| `extract_result.image_type` | string | 提取确认的凭证类型 |
| `ocr_extract.*` | object | OCR提取的所有字段（见下方详细说明） |
| `validation_result.*` | object | 数据校验结果（9项布尔值） |
| `risk_rating` | string | 风险评级：高风险/中风险/低风险 |
| `audit_conclusion` | string | 审计结论：通过/不通过/人工复核 |
| `_confidence` | float | 置信度（0.0-1.0） |
| `_summary` | string | 凭证摘要（20字以内） |

### 4.3 ocr_extract 字段详解

| 字段 | 说明 | 示例值 |
|------|------|--------|
| `invoice_code` | 发票代码 | "3100213410" |
| `invoice_number` | 发票号码 | "12345678" |
| `date` | 日期（YYYY-MM-DD） | "2024-03-15" |
| `total_amount` | 总金额（纯数字） | 113000.00 |
| `relevant_party` | 相关方名称 | "上海华兴科技有限公司" |
| `tax_rate` | 税率 | "13%" |
| `tax_id` | 纳税人识别号 | "91310115MA7XXXXXX" |
| `bank_info` | 银行信息 | "工商银行上海分行" |
| `serial_number` | 流水号 | "202403150001" |
| `details` | 摘要/备注 | "办公用品采购" |

### 4.4 seal_info 印章信息

| 字段 | 说明 | 可选值 |
|------|------|--------|
| `seal_type` | 印章类型 | "发票专用章"/"财务章"/"公章"/"法人章" |
| `seal_number` | 印章编号 | 印章上的编号 |
| `seal_clarity` | 印章清晰度 | "清晰"/"模糊"/"无" |
| `joint_seal` | 是否联合盖章 | "是"/"否" |

### 4.5 license_info 证照信息

| 字段 | 说明 | 示例值 |
|------|------|--------|
| `unified_social_credit_code` | 统一社会信用代码 | "91310115MA7XXXXXX" |
| `legal_person` | 法定代表人 | "张三" |
| `valid_period` | 有效期限 | "2024-01-01至2034-12-31" |

### 4.6 asset_info 资产信息

| 字段 | 说明 | 示例值 |
|------|------|--------|
| `asset_tag` | 资产标签 | "ZC-2024-001" |
| `asset_name` | 资产名称 | "笔记本电脑" |
| `location` | 位置 | "财务部办公室" |
| `quantity` | 数量 | "5" |
| `progress` | 进度 | "80%" |

### 4.7 internal_control_info 内控信息

| 字段 | 说明 | 示例值 |
|------|------|--------|
| `signer` | 签字人 | "李四" |
| `approval_level` | 审批级别 | "部门经理审批" |
| `attachment_complete` | 附件是否完整 | "是"/"否" |

### 4.8 validation_result 校验结果

| 字段 | 说明 |
|------|------|
| `date_valid` | 日期是否有效（不超过当前日期） |
| `amount_valid` | 金额是否有效（正数、格式正确） |
| `code_format_valid` | 代码格式是否有效（发票代码/号码格式） |
| `no_missing_field` | 是否有缺失字段 |
| `image_normal` | 图片是否正常（非模糊/遮挡） |
| `no_duplicate` | 是否无重复凭证 |
| `consistent_info` | 信息是否一致（金额/名称等） |
| `compliance` | 是否合规 |
| `no_fraud` | 是否无欺诈嫌疑 |

---

## 五、输出目录结构

```
分类结果_智谱/
├── 发票类/
│   ├── 增值税专用发票/
│   │   ├── 增值税专用发票_0001.jpeg
│   │   └── 增值税专用发票_0001_result.json
│   ├── 增值税普通发票/
│   │   ├── 增值税普通发票_0001.jpeg
│   │   └── 增值税普通发票_0001_result.json
│   └── ...
├── 报销付款类/
│   ├── 付款申请单/
│   │   ├── 付款申请单_0002.jpeg
│   │   └── 付款申请单_0002_result.json
│   └── ...
├── 银行金融类/
│   └── ...
└── 汇总结果.json
```

### 汇总结果.json 结构

```json
{
  "process_time": "2026-05-17 11:55:12",
  "total_images": 10,
  "success_count": 9,
  "error_count": 1,
  "results": [
    { ... },  // 每张图片的完整结果
    { ... }
  ]
}
```

---

## 六、使用方法

### 6.1 单张测试

```bash
python pic_claw/_test_zhipu_full.py
```

**功能**：从数据库取1张待处理图片，执行分类+提取，输出JSON结果并复制到类别文件夹。

### 6.2 批量处理（修改脚本中的LIMIT参数）

编辑 `_test_zhipu_full.py` 中的SQL语句：

```python
# 改为批量处理（如10张）
cur.execute("""
    SELECT id, file_path, file_name, doc_type_name, category_name
    FROM voucher_images
    WHERE batch_id = 4 AND classify_status = 'pending'
    ORDER BY id
    LIMIT 10  -- 修改此处数字控制处理数量
""")
```

### 6.3 重置状态重新处理

```bash
python pic_claw/_reset_and_test.py
```

**功能**：重置batch=4的所有图片状态为pending，清空已提取字段和agent日志。

---

## 七、API调用说明

### 7.1 分类Prompt

```
请识别这张图片的凭证类型，从以下列表中选择最匹配的一项：

- 增值税专用发票
- 增值税普通发票
- ...（130种类型）

如果图片内容模糊、无关或不在列表中，请回复"其他"。

只输出类型名称，不要输出其他内容。
```

### 7.2 提取Prompt

```
你是一位专业的审计凭证信息提取专家。请从这张图片中提取所有可见的关键字段信息。

凭证类型：{type_name}
所属大类：{category}

请严格按照以下JSON格式输出（只输出JSON，不要包含任何其他文字）：
{
    "image_type": "{type_name}",
    "ocr_extract": { ... },
    "validation_result": { ... },
    "risk_rating": "高风险/中风险/低风险",
    ...
}
```

---

## 八、注意事项

### 8.1 图片质量问题
- 部分图片从百度搜索，可能包含无关场景图
- 模糊、遮挡、非凭证类图片可能分类不准确
- 建议在`_summary`字段中标注图片质量问题

### 8.2 费用控制
- 智谱API按token计费
- 建议先用少量图片测试（1-10张）
- 可通过修改`LIMIT`参数控制处理数量

### 8.3 字段提取规则
- 不存在的字段填`"N/A"`
- 金额只填数字，去掉货币符号（¥、$等）
- 日期统一为`YYYY-MM-DD`格式
- 布尔值填`true`或`false`（小写）

### 8.4 错误处理
- 分类失败：返回`{"error": "分类失败: 错误信息"}`
- 提取失败：返回`{"error": "JSON解析失败", "raw": "原始响应"}`
- 网络超时：120秒超时，可调整`timeout`参数

---

## 九、测试记录

### 9.1 单张测试结果

| 项目 | 结果 |
|------|------|
| 文件名 | 付款申请单_0002.jpeg |
| 分类结果 | 付款申请单（报销付款类）✅ |
| 分类耗时 | 1.3秒 |
| 提取字段数 | 7个 |
| 提取耗时 | 11.8秒 |
| 总耗时 | 13.1秒 |
| 风险评级 | 中风险 |
| 审计结论 | 不通过（信息填写不完整） |

### 9.2 输出文件

```
分类结果_智谱/
└── 报销付款类/
    └── 付款申请单/
        ├── 付款申请单_0002.jpeg
        └── 付款申请单_0002_result.json
```

---

## 十、文件清单

| 文件 | 说明 |
|------|------|
| `pic_claw/_test_zhipu_full.py` | 智谱API全流程测试脚本（分类+提取+整理） |
| `pic_claw/_reset_and_test.py` | 重置数据库状态并测试API连接 |
| `pic_claw/_check_db.py` | 检查数据库图片状态 |
| `data/model_config.json` | 模型配置文件（含智谱API密钥） |
| `pic_claw/分类结果_智谱/` | 输出目录（按类别整理） |

---

## 十一、后续优化建议

1. **增加图片质量校验**：在分类前增加图片清晰度检测
2. **优化分类Prompt**：为130种类型增加视觉特征描述
3. **字段模板优化**：按凭证类型提供专属字段模板
4. **批量并发处理**：使用ThreadPoolExecutor提升处理速度
5. **结果可视化**：生成HTML报告展示分类/提取结果

---

**文档版本**: v1.0  
**更新日期**: 2026-05-17  
**测试模型**: GLM-4.6V-FlashX（智谱AI）