# ============================================================
# CPA 教材图片处理工具
# 功能: 将 MD 文件中的图片引用转为占位文本，
#       保留图片位置信息便于后续引用
# ============================================================

"""
MD图片处理工具
功能：
1. 将图片引用转为占位文本
2. 保留图片位置信息，便于后续引用
"""

import re
import os
from pathlib import Path

def process_images_in_md(content: str, md_file_path: str) -> str:
    """
    处理MD内容中的图片：
    - 将图片引用替换为描述性文本
    - 保留图片来源信息
    """
    
    def replace_image(match):
        alt_text = match.group(1)
        img_path = match.group(2)
        
        # 获取图片文件名
        img_name = os.path.basename(img_path)
        
        # 如果有alt文本，使用它；否则使用文件名
        if alt_text and alt_text.strip() and alt_text != 'image':
            description = alt_text.strip()
        else:
            description = img_name.replace('.jpg', '').replace('.png', '').replace('.gif', '')
        
        # 生成图片占位描述
        placeholder = f"【图片：{description}】"
        
        return placeholder
    
    # 匹配图片语法：![alt](path)
    pattern = r'!\[(.*?)\]\((.*?)\)'
    processed_content = re.sub(pattern, replace_image, content)
    
    return processed_content

def process_all_md_files(base_dir: str):
    """处理目录下所有MD文件中的图片"""
    md_files = list(Path(base_dir).rglob('*.md'))
    print(f'📁 找到 {len(md_files)} 个MD文件')
    
    for md_file in md_files:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否有图片
        if '![' in content:
            processed = process_images_in_md(content, str(md_file))
            
            # 生成处理后的文件
            processed_path = md_file.parent / f'{md_file.stem}_noimg.md'
            with open(processed_path, 'w', encoding='utf-8') as f:
                f.write(processed)
            
            print(f'✅ {md_file.name} -> {processed_path.name}')
        else:
            print(f'ℹ️ {md_file.name} 无图片')

if __name__ == '__main__':
    base_dir = r'd:\pythonpro\ollama项目\重构版\cpazs'
    process_all_md_files(base_dir)
    print('\n🎉 图片处理完成！')