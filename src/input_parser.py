import re
from typing import Optional

from data_structures import PowerPoint
from slide_builder import SlideBuilder
from layout_manager import LayoutManager
from logger import LOG  # 引入日志模块

# 解析输入文本，生成 PowerPoint 数据结构
def parse_input_text(input_text: str, layout_manager: LayoutManager) -> PowerPoint:
    """
    解析输入的文本并转换为 PowerPoint 数据结构。自动为每张幻灯片分配适当的布局。
    """
    lines = input_text.split('\n')  # 按行拆分文本
    presentation_title = ""  # PowerPoint 的主标题
    slides = []  # 存储所有幻灯片
    slide_builder: Optional[SlideBuilder] = None  # 当前幻灯片的构建器

    # 正则表达式，用于匹配幻灯片标题、要点和图片
    slide_title_pattern = re.compile(r'^##\s+(.*)')
    bullet_pattern = re.compile(r'^-\s+(.*)')
    image_pattern = re.compile(r'!\[(.*?)\]\((.*?)\)')

    for line in lines:
        line = line.strip()  # 去除空格
        
        # 跳过空行
        if not line:
            continue

        # 主标题 (用作 PowerPoint 的标题和文件名)
        if line.startswith('# ') and not line.startswith('##'):
            presentation_title = line[2:].strip()

            # 创建第一张幻灯片，使用 "Title Only" 布局
            first_slide_builder = SlideBuilder(layout_manager)
            first_slide_builder.set_title(presentation_title)
            slides.append(first_slide_builder.finalize())

        # 幻灯片标题
        elif line.startswith('## '):
            match = slide_title_pattern.match(line)
            if match:
                title = match.group(1).strip()

                # 如果有当前幻灯片，生成并添加到幻灯片列表中
                if slide_builder:
                    slides.append(slide_builder.finalize())

                # 创建新的 SlideBuilder
                slide_builder = SlideBuilder(layout_manager)
                slide_builder.set_title(title)

        # 处理行内容
        elif slide_builder:
            # 检查是否包含图片
            image_match = image_pattern.search(line)  # 使用 search 而不是 match
            if image_match:
                image_description = image_match.group(1)
                image_url = image_match.group(2)
                LOG.info(f"找到图片: {image_url}")
                slide_builder.set_image(image_url)
                
                # 如果这行还包含项目符号内容，提取并添加（去除图片部分）
                line_without_image = line.split('![')[0].strip()
                if line_without_image.startswith('- '):
                    bullet = line_without_image[2:].strip()
                    if bullet:  # 确保不是空字符串
                        slide_builder.add_bullet_point(bullet)
            
            # 如果是普通项目符号
            elif line.startswith('- '):
                bullet = line[2:].strip()
                if bullet:  # 确保不是空字符串
                    slide_builder.add_bullet_point(bullet)

    # 为最后一张幻灯片分配布局并添加到列表中
    if slide_builder:
        slides.append(slide_builder.finalize())

    # 返回 PowerPoint 数据结构以及演示文稿标题
    return PowerPoint(title=presentation_title, slides=slides), presentation_title
