import os
from pptx import Presentation
from pptx.util import Inches
from utils import remove_all_slides

def generate_presentation(powerpoint_data, template_path: str, output_path: str):
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file '{template_path}' does not exist.")

    prs = Presentation(template_path)
    remove_all_slides(prs)
    prs.core_properties.title = powerpoint_data.title

    for slide in powerpoint_data.slides:
        layout_idx = min(slide.layout, len(prs.slide_layouts) - 1)
        slide_layout = prs.slide_layouts[layout_idx]
        new_slide = prs.slides.add_slide(slide_layout)

        # 設置標題
        if hasattr(new_slide.shapes, 'title') and new_slide.shapes.title:
            new_slide.shapes.title.text = slide.content.title

        # 添加項目符號內容
        content_added = False
        for shape in new_slide.placeholders:
            if shape.has_text_frame and shape != new_slide.shapes.title:
                text_frame = shape.text_frame
                text_frame.clear()
                
                for point in slide.content.bullet_points:
                    p = text_frame.add_paragraph()
                    p.text = point
                    p.level = 0
                content_added = True
                break

        # 處理圖片
        if slide.content.image_path:
            image_full_path = os.path.join(os.getcwd(), slide.content.image_path)
            if os.path.exists(image_full_path):
                image_added = False
                
                # 方法1：嘗試使用預設圖片佔位符
                for shape in new_slide.placeholders:
                    if shape.placeholder_format.type in [18, 19]:  # 圖片佔位符類型
                        try:
                            shape.insert_picture(image_full_path)
                            image_added = True
                            break
                        except Exception as e:
                            print(f"Info: Could not insert image into placeholder: {str(e)}")

                # 方法2：嘗試使用內容佔位符
                if not image_added:
                    for shape in new_slide.placeholders:
                        if shape.placeholder_format.type == 15:  # 內容佔位符
                            try:
                                shape.insert_picture(image_full_path)
                                image_added = True
                                break
                            except Exception as e:
                                print(f"Info: Could not insert image into content placeholder: {str(e)}")

                # 方法3：如果前面都失敗了，直接在幻燈片上添加圖片
                if not image_added:
                    try:
                        # 獲取幻燈片的可用區域
                        slide_width = prs.slide_width
                        slide_height = prs.slide_height
                        
                        # 設置圖片大小（可以根據需要調整）
                        image_width = Inches(6)  # 預設寬度6英寸
                        left = (slide_width - image_width) / 2  # 水平居中
                        top = Inches(3)  # 從頂部3英寸開始
                        
                        new_slide.shapes.add_picture(
                            image_full_path,
                            left,
                            top,
                            width=image_width
                        )
                        image_added = True
                        print(f"Info: Image added directly to slide {len(prs.slides)}")
                    except Exception as e:
                        print(f"Warning: Failed to add image to slide {len(prs.slides)}: {str(e)}")

                if not image_added:
                    print(f"Warning: Could not add image to slide {len(prs.slides)} using any method")
            else:
                print(f"Warning: Image file not found: {image_full_path}")

    # 確保輸出目錄存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 保存文件
    try:
        prs.save(output_path)
        print(f"Presentation successfully saved to '{output_path}'")
    except Exception as e:
        print(f"Error saving presentation: {str(e)}")
