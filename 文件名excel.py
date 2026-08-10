import os
import re
import pandas as pd

# -------------------------- 配置（已填好你的路径）--------------------------
target_folder = r"C:\Users\he\Desktop\实习\天猫"
save_excel_path = r"C:\Users\he\Desktop\天猫订单数字清单.xlsx"

# -------------------------- 自动提取数字+导出Excel --------------------------
data = []

# 遍历文件夹所有文件
for name in os.listdir(target_folder):
    full_path = os.path.join(target_folder, name)
    if os.path.isfile(full_path):
        # 核心：正则表达式提取文件名中的所有数字
        number_list = re.findall(r'\d+', name)  # 匹配所有连续数字
        order_number = ''.join(number_list)     # 拼接成完整数字
        data.append([name, order_number])       # 保存原文件名+提取的数字

# 生成Excel（两列：原文件名、提取的数字）
df = pd.DataFrame(data, columns=["原文件名", "提取的订单数字"])
df.to_excel(save_excel_path, index=False, engine="openpyxl")

# 完成提示
print(f"✅ 提取成功！")
print(f"🔢 共处理 {len(data)} 个文件")
print(f"📄 Excel文件位置：{save_excel_path}")