# -*- coding: utf-8 -*-
"""
医学论文 Word 模板生成器

生成符合医学期刊投稿要求的 Word 参考文档模板
用于 Pandoc 转换时应用统一样式
"""

import os
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Pt, Cm, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
    from docx.enum.style import WD_STYLE_TYPE
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    print("请先安装 python-docx: pip install python-docx")
    exit(1)


def set_chinese_font(run, font_name="宋体", font_name_ascii="Times New Roman"):
    """设置中英文字体"""
    run.font.name = font_name_ascii
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)


def create_medical_template(output_path: str = None):
    """
    创建医学论文 Word 模板

    符合大多数医学期刊的格式要求：
    - 正文：宋体/Times New Roman, 12pt, 1.5倍行距
    - 标题：黑体/Arial, 分级字号
    - 页边距：2.5cm
    - 首行缩进：2字符
    """

    doc = Document()

    # ========================================
    # 1. 设置页面布局
    # ========================================
    section = doc.sections[0]
    section.page_width = Cm(21)      # A4 宽度
    section.page_height = Cm(29.7)   # A4 高度
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)

    # ========================================
    # 2. 定义样式
    # ========================================
    styles = doc.styles

    # --- 正文样式 (Normal) ---
    normal_style = styles['Normal']
    normal_style.font.name = 'Times New Roman'
    normal_style.font.size = Pt(12)
    normal_style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    normal_style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    normal_style.paragraph_format.space_after = Pt(0)
    normal_style.paragraph_format.first_line_indent = Cm(0.74)  # 约2字符

    # --- 标题1样式 (Heading 1) - 一级标题 ---
    h1_style = styles['Heading 1']
    h1_style.font.name = 'Arial'
    h1_style.font.size = Pt(16)
    h1_style.font.bold = True
    h1_style._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    h1_style.paragraph_format.space_before = Pt(12)
    h1_style.paragraph_format.space_after = Pt(6)
    h1_style.paragraph_format.first_line_indent = Pt(0)
    h1_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # --- 标题2样式 (Heading 2) - 二级标题 ---
    h2_style = styles['Heading 2']
    h2_style.font.name = 'Arial'
    h2_style.font.size = Pt(14)
    h2_style.font.bold = True
    h2_style._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    h2_style.paragraph_format.space_before = Pt(10)
    h2_style.paragraph_format.space_after = Pt(4)
    h2_style.paragraph_format.first_line_indent = Pt(0)

    # --- 标题3样式 (Heading 3) - 三级标题 ---
    h3_style = styles['Heading 3']
    h3_style.font.name = 'Arial'
    h3_style.font.size = Pt(12)
    h3_style.font.bold = True
    h3_style._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    h3_style.paragraph_format.space_before = Pt(8)
    h3_style.paragraph_format.space_after = Pt(4)
    h3_style.paragraph_format.first_line_indent = Pt(0)

    # --- 标题样式 (Title) - 论文标题 ---
    title_style = styles['Title']
    title_style.font.name = 'Arial'
    title_style.font.size = Pt(18)
    title_style.font.bold = True
    title_style._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    title_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_style.paragraph_format.space_after = Pt(12)

    # ========================================
    # 3. 添加示例内容（Pandoc需要）
    # ========================================

    # 标题
    title = doc.add_paragraph('论文标题', style='Title')

    # 一级标题
    doc.add_paragraph('1 引言', style='Heading 1')
    doc.add_paragraph('这是正文内容示例。医学论文正文使用宋体或Times New Roman字体，'
                     '字号为小四（12pt），行距为1.5倍。段落首行缩进2字符。')

    # 二级标题
    doc.add_paragraph('1.1 研究背景', style='Heading 2')
    doc.add_paragraph('二级标题下的正文内容。')

    # 三级标题
    doc.add_paragraph('1.1.1 具体问题', style='Heading 3')
    doc.add_paragraph('三级标题下的正文内容。')

    # 更多章节
    doc.add_paragraph('2 材料与方法', style='Heading 1')
    doc.add_paragraph('方法部分的正文内容。')

    doc.add_paragraph('3 结果', style='Heading 1')
    doc.add_paragraph('结果部分的正文内容。')

    doc.add_paragraph('4 讨论', style='Heading 1')
    doc.add_paragraph('讨论部分的正文内容。')

    doc.add_paragraph('5 结论', style='Heading 1')
    doc.add_paragraph('结论部分的正文内容。')

    doc.add_paragraph('参考文献', style='Heading 1')
    doc.add_paragraph('[1] 作者. 文章标题[J]. 期刊名, 年份, 卷(期): 页码.')

    # ========================================
    # 4. 保存模板
    # ========================================
    if output_path is None:
        output_path = Path(__file__).parent / 'medical_template.docx'

    doc.save(output_path)
    print(f"医学论文模板已生成: {output_path}")
    return output_path


if __name__ == '__main__':
    create_medical_template()
