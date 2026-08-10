from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import nsmap
from pptx.oxml import parse_xml
import os

# 项目路径
PROJECT_DIR = r"d:\pythonpro\ollama项目\审计OCR+CPA问答综合系统"
SCREENSHOT_DIR = os.path.join(PROJECT_DIR, "ppt_screenshots")
OUTPUT_PPT = os.path.join(PROJECT_DIR, "CPA知识图谱问答系统展示.pptx")

# 创建16:9演示文稿
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# 配色方案
DARK_BG = RGBColor(15, 25, 35)
ACCENT_BLUE = RGBColor(108, 155, 210)
ACCENT_PURPLE = RGBColor(118, 75, 162)
LIGHT_TEXT = RGBColor(240, 240, 240)
MUTED_TEXT = RGBColor(180, 190, 200)
WHITE = RGBColor(255, 255, 255)

def add_background(slide, color=DARK_BG):
    """添加纯色背景"""
    background = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height
    )
    background.fill.solid()
    background.fill.fore_color.rgb = color
    background.line.fill.background()
    # 移到最底层
    spTree = slide.shapes._spTree
    sp = background._element
    spTree.remove(sp)
    spTree.insert(2, sp)

def add_title_box(slide, title, subtitle=None, top=Inches(0.4)):
    """添加标题文本框"""
    title_box = slide.shapes.add_textbox(Inches(0.5), top, Inches(12.3), Inches(0.8))
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = LIGHT_TEXT
    p.alignment = PP_ALIGN.LEFT
    
    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.font.size = Pt(16)
        p2.font.color.rgb = MUTED_TEXT
        p2.alignment = PP_ALIGN.LEFT
        p2.space_before = Pt(6)
    return title_box

def add_bullet_text(slide, bullets, left, top, width, height, font_size=16):
    """添加要点文本"""
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    for i, text in enumerate(bullets):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = f"• {text}"
        p.font.size = Pt(font_size)
        p.font.color.rgb = LIGHT_TEXT
        p.space_after = Pt(10)
    return box

def add_image_slide(slide_num, title, subtitle, image_name, image_top=1.4, image_height=5.6):
    """添加带截图的幻灯片"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白布局
    add_background(slide)
    add_title_box(slide, title, subtitle)
    img_path = os.path.join(SCREENSHOT_DIR, image_name)
    if os.path.exists(img_path):
        # 计算图片宽度，保持16:9比例
        slide.shapes.add_picture(
            img_path,
            Inches(0.5),
            Inches(image_top),
            width=Inches(12.3)
        )
    return slide

# ========== 幻灯片 1: 标题页 ==========
slide1 = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide1)

# 大标题
title_box = slide1.shapes.add_textbox(Inches(0.5), Inches(2.2), Inches(12.3), Inches(1.2))
tf = title_box.text_frame
p = tf.paragraphs[0]
p.text = "CPA 知识图谱问答综合系统"
p.font.size = Pt(48)
p.font.bold = True
p.font.color.rgb = LIGHT_TEXT
p.alignment = PP_ALIGN.CENTER

# 副标题
sub_box = slide1.shapes.add_textbox(Inches(0.5), Inches(3.6), Inches(12.3), Inches(0.8))
tf2 = sub_box.text_frame
p2 = tf2.paragraphs[0]
p2.text = "基于图论与拓扑学的智能审计知识库问答平台"
p2.font.size = Pt(24)
p2.font.color.rgb = ACCENT_BLUE
p2.alignment = PP_ALIGN.CENTER

# 装饰线
line = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(4.5), Inches(4.5), Inches(4.3), Inches(0.05))
line.fill.solid()
line.fill.fore_color.rgb = ACCENT_BLUE
line.line.fill.background()

# 底部信息
info_box = slide1.shapes.add_textbox(Inches(0.5), Inches(6.3), Inches(12.3), Inches(0.6))
tf3 = info_box.text_frame
p3 = tf3.paragraphs[0]
p3.text = "知识图谱 · GraphRAG · 多模态检索 · 可视化分析"
p3.font.size = Pt(16)
p3.font.color.rgb = MUTED_TEXT
p3.alignment = PP_ALIGN.CENTER

# ========== 幻灯片 2: 项目概述 ==========
slide2 = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide2)
add_title_box(slide2, "项目概述", "面向注册会计师考试辅导的智能知识服务系统")

overview_points = [
    "整合 CPA 六科教材、审计准则、法律法规等专业知识",
    "构建包含 104 个实体、111 条关系、36 组易混概念的知识图谱",
    "支持向量检索、BM25、混合检索、GraphRAG 四种检索模式",
    "提供可视化知识图谱浏览器，支持实体关系展开与路径探索",
    "具备管理后台、数据仪表盘、API 配置等完整运维能力",
    "融合图论算法（BFS、双向BFS）与拓扑分析（社区发现、力导向布局）"
]
add_bullet_text(slide2, overview_points, 0.5, 1.4, 12.3, 5.5, font_size=18)

# ========== 幻灯片 3: 系统架构 ==========
slide3 = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide3)
add_title_box(slide3, "系统架构", "前后端分离 + 多源知识库 + 图谱可视化")

# 绘制架构图
layers = [
    ("前端交互层", ["CPA问答界面", "知识图谱浏览器", "管理后台", "数据仪表盘"], RGBColor(86, 119, 170)),
    ("应用服务层", ["Flask Web服务", "Socket.IO实时通信", "知识检索引擎", "GraphRAG"], RGBColor(108, 155, 210)),
    ("算法引擎层", ["BFS/双向BFS遍历", "社区发现", "力导向布局", "实体关系扩散"], RGBColor(118, 75, 162)),
    ("数据存储层", ["PostgreSQL", "pgvector向量库", "知识图谱表", "教材Chunk数据"], RGBColor(80, 100, 120))
]

y_start = 1.5
for i, (title, items, color) in enumerate(layers):
    y = y_start + i * 1.4
    # 层背景
    rect = slide3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0), Inches(y), Inches(11.3), Inches(1.15))
    rect.fill.solid()
    rect.fill.fore_color.rgb = color
    rect.line.fill.background()
    
    # 层标题
    tbox = slide3.shapes.add_textbox(Inches(1.2), Inches(y + 0.35), Inches(2.2), Inches(0.5))
    tf = tbox.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = WHITE
    
    # 模块项
    items_text = "  |  ".join(items)
    ibox = slide3.shapes.add_textbox(Inches(3.5), Inches(y + 0.3), Inches(8.6), Inches(0.6))
    itf = ibox.text_frame
    itf.word_wrap = True
    ip = itf.paragraphs[0]
    ip.text = items_text
    ip.font.size = Pt(13)
    ip.font.color.rgb = WHITE
    ip.alignment = PP_ALIGN.LEFT

# ========== 幻灯片 4: 技术栈 ==========
slide4 = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide4)
add_title_box(slide4, "核心技术栈", "Python后端 + 原生前端 + ECharts可视化")

stack_data = [
    ("后端框架", "Flask + Flask-SocketIO + SQLAlchemy", "RESTful API 与实时流式问答"),
    ("向量检索", "pgvector + sentence-transformers", "Embedding语义相似度匹配"),
    ("全文检索", "BM25 + PostgreSQL tsvector", "关键词精确匹配"),
    ("知识图谱", "NetworkX + 自定义GraphTraverser", "BFS/双向BFS/子图展开"),
    ("前端可视化", "ECharts 5.5 力导向图", "交互式知识网络展示"),
    ("文本处理", "jieba + openpyxl", "中文分词、文档解析")
]

for i, (cat, tech, desc) in enumerate(stack_data):
    row = i // 2
    col = i % 2
    x = 0.6 + col * 6.2
    y = 1.5 + row * 1.4
    
    card = slide4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(5.9), Inches(1.2))
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(30, 45, 60)
    card.line.color.rgb = ACCENT_BLUE
    
    cat_box = slide4.shapes.add_textbox(Inches(x + 0.15), Inches(y + 0.12), Inches(5.6), Inches(0.35))
    ctf = cat_box.text_frame
    cp = ctf.paragraphs[0]
    cp.text = cat
    cp.font.size = Pt(14)
    cp.font.bold = True
    cp.font.color.rgb = ACCENT_BLUE
    
    tech_box = slide4.shapes.add_textbox(Inches(x + 0.15), Inches(y + 0.45), Inches(5.6), Inches(0.35))
    ttf = tech_box.text_frame
    tp = ttf.paragraphs[0]
    tp.text = tech
    tp.font.size = Pt(13)
    tp.font.bold = True
    tp.font.color.rgb = LIGHT_TEXT
    
    desc_box = slide4.shapes.add_textbox(Inches(x + 0.15), Inches(y + 0.8), Inches(5.6), Inches(0.35))
    dtf = desc_box.text_frame
    dp = dtf.paragraphs[0]
    dp.text = desc
    dp.font.size = Pt(11)
    dp.font.color.rgb = MUTED_TEXT

# ========== 幻灯片 5-9: 功能截图 ==========
add_image_slide(5, "CPA 智能问答界面", "多角色选择 + 技能开关 + 检索模式 + 教材选择", "01_qa_home.png")
add_image_slide(6, "知识图谱可视化", "力导向布局展示 104 实体 / 111 关系 / 36 易混对", "02_kg_explorer.png")
add_image_slide(7, "实体详情与关系展开", "点击实体查看定义、章节、关联关系与易混概念", "03_kg_detail.png")
add_image_slide(8, "知识库管理后台", "教材知识库、历史问答、审计辅导、归档知识统一管理", "04_admin_panel.png")
add_image_slide(9, "审计数据仪表盘", "审计记录统计、风险等级分布、图片类型分布、知识库统计", "05_dashboard.png")

# ========== 幻灯片 10: 核心功能 ==========
slide10 = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide10)
add_title_box(slide10, "核心功能", "四大检索模式 + 图谱可视化 + 知识管理")

features = [
    ("🔍", "多模式检索", "向量语义、BM25关键词、混合RRF、GraphRAG图谱检索"),
    ("🧠", "知识图谱", "实体-关系-易混概念三元组，支持BFS多跳与最短路径"),
    ("💬", "流式问答", "Socket.IO实时输出，支持思考模式与上下文固定"),
    ("📚", "教材管理", "多教材选择、文件上传、AI做梦自动归档知识"),
    ("📊", "数据看板", "审计记录、风险分布、知识库统计可视化"),
    ("⚙️", "灵活配置", "API配置、角色提示词、技能开关等可定制")
]

for i, (emoji, title, desc) in enumerate(features):
    row = i // 3
    col = i % 3
    x = 0.5 + col * 4.2
    y = 1.5 + row * 2.5
    
    card = slide10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(3.95), Inches(2.1))
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(25, 40, 55)
    card.line.color.rgb = ACCENT_BLUE
    
    icon_box = slide10.shapes.add_textbox(Inches(x + 0.15), Inches(y + 0.15), Inches(0.6), Inches(0.5))
    itf = icon_box.text_frame
    ip = itf.paragraphs[0]
    ip.text = emoji
    ip.font.size = Pt(28)
    
    tbox = slide10.shapes.add_textbox(Inches(x + 0.15), Inches(y + 0.7), Inches(3.65), Inches(0.45))
    ttf = tbox.text_frame
    tp = ttf.paragraphs[0]
    tp.text = title
    tp.font.size = Pt(18)
    tp.font.bold = True
    tp.font.color.rgb = LIGHT_TEXT
    
    dbox = slide10.shapes.add_textbox(Inches(x + 0.15), Inches(y + 1.15), Inches(3.65), Inches(0.85))
    dtf = dbox.text_frame
    dtf.word_wrap = True
    dp = dtf.paragraphs[0]
    dp.text = desc
    dp.font.size = Pt(13)
    dp.font.color.rgb = MUTED_TEXT

# ========== 幻灯片 11: 图论与拓扑 ==========
slide11 = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide11)
add_title_box(slide11, "图论与拓扑学应用", "知识图谱背后的算法基础")

algo_points = [
    "图数据结构：有向图、加权图、异构图，使用邻接表存储",
    "广度优先搜索（BFS）：实现多跳知识检索与实体邻域展开",
    "双向BFS：高效查找两个实体间的最短路径",
    "社区发现：基于模块度识别知识聚类与学习模块",
    "力导向布局：ECharts模拟斥力/引力，自动排列知识网络",
    "GraphRAG：实体匹配 → 关系扩散 → Chunk收集，增强检索召回"
]
add_bullet_text(slide11, algo_points, 0.5, 1.4, 12.3, 5.5, font_size=18)

# ========== 幻灯片 12: 项目亮点 ==========
slide12 = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide12)
add_title_box(slide12, "项目亮点", "理论与实践结合，完整可运行的知识服务系统")

highlights = [
    "完整闭环：从数据上传、知识抽取、向量入库到问答应用一站式完成",
    "算法落地：图论算法不仅是理论，而是实际支撑检索与可视化的核心",
    "工程稳健：完善的异常处理、null保护、错误回退与缓存机制",
    "可扩展性：模块化架构，易于新增实体类型、关系类型与检索策略",
    "用户体验：响应式界面、实时流式输出、可视化知识导航"
]
add_bullet_text(slide12, highlights, 0.5, 1.4, 12.3, 5.5, font_size=20)

# ========== 幻灯片 13: 总结与展望 ==========
slide13 = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide13)
add_title_box(slide13, "总结与展望", "知识图谱驱动的下一代智能教育问答")

summary_box = slide13.shapes.add_textbox(Inches(0.5), Inches(2.0), Inches(12.3), Inches(3.5))
stf = summary_box.text_frame
stf.word_wrap = True
sp = stf.paragraphs[0]
sp.text = "本项目将 CPA 专业知识结构化、图谱化、可视化，结合大语言模型与多模态检索技术，为考试辅导提供了可解释、可探索、可管理的智能知识服务。"
sp.font.size = Pt(22)
sp.font.color.rgb = LIGHT_TEXT
sp.alignment = PP_ALIGN.CENTER

future_points = [
    "引入图神经网络（GNN）进行实体Embedding与关系推理",
    "支持多模态输入：图片、表格、PDF文档统一解析",
    "构建个性化学习路径推荐与薄弱知识点诊断",
    "对接LLM Agent实现主动式问答与知识讲解"
]
future_box = slide13.shapes.add_textbox(Inches(1.5), Inches(4.2), Inches(10.3), Inches(2.5))
ftf = future_box.text_frame
ftf.word_wrap = True
for i, text in enumerate(future_points):
    if i == 0:
        fp = ftf.paragraphs[0]
    else:
        fp = ftf.add_paragraph()
    fp.text = f"▸ {text}"
    fp.font.size = Pt(16)
    fp.font.color.rgb = ACCENT_BLUE
    fp.space_after = Pt(8)
    fp.alignment = PP_ALIGN.CENTER

# 保存
prs.save(OUTPUT_PPT)
print(f"PPT已生成: {OUTPUT_PPT}")
print(f"截图目录: {SCREENSHOT_DIR}")
