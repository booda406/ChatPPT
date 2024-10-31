import os
import gradio as gr
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from input_parser import parse_input_text
from ppt_generator import generate_presentation
from template_manager import load_template
from layout_manager import LayoutManager
from config import Config
from logger import LOG

class ChatPPTInterface:
    def __init__(self):
        self.config = Config()
        self.layout_manager = LayoutManager(self.config.layout_mapping)
        self.prs = load_template(self.config.ppt_template)

        # 初始化搜索工具
        self.search_tool = DuckDuckGoSearchResults(
            api_wrapper=DuckDuckGoSearchAPIWrapper()
        )

        # 初始化 ChatOpenAI
        self.chat = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=2000
        )

        # 從文件讀取系統提示
        self.system_prompt = self._load_prompt_template()

        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}")
        ])

    def _load_prompt_template(self):
        """從文件讀取提示模板"""
        try:
            prompt_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "prompts",
                "formatter.txt"
            )
            with open(prompt_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except Exception as e:
            LOG.error(f"讀取提示詞模板時發生錯誤: {str(e)}")
            raise

    def _process_slide_content(self, slide_content):
        """處理單個幻燈片的內容"""
        lines = slide_content.strip().split('\n')
        if not lines:
            return slide_content

        # 獲取幻燈片標題
        title = lines[0].strip()

        # 尋找 need_image 和對應的描述
        image_description = None
        need_image_index = -1

        for i, line in enumerate(lines):
            if 'need_image' in line.lower():
                need_image_index = i
                # 尋找下一行的括號描述
                if i + 1 < len(lines) and lines[i + 1].strip().startswith('(') and lines[i + 1].strip().endswith(')'):
                    image_description = lines[i + 1].strip()[1:-1]  # 移除括號
                    break

        if need_image_index != -1:
            # 決定搜索關鍵詞
            search_query = image_description if image_description else title

            # 搜索相關圖片
            image_url = self._search_images(search_query)

            if image_url:
                LOG.info(f"找到圖片，開始插入圖片:\n{image_url}")
                # 移除 need_image 行和描述行
                new_lines = []
                skip_next = False
                for i, line in enumerate(lines):
                    if i == need_image_index or skip_next:
                        skip_next = False
                        continue
                    if 'need_image' in line.lower():
                        skip_next = True  # 跳過下一行（描述行）
                        continue
                    new_lines.append(line)

                # 在適當位置插入圖片
                image_line = f"![{search_query}]({image_url})"
                # 將圖片插入到標題之後
                new_lines.insert(1, image_line)

                return '\n'.join(new_lines)

        return slide_content

    def _search_images(self, query):
        """搜索相關圖片"""
        LOG.info(f"開始搜索:\n")
        try:
            # 添加更具體的搜索關鍵詞以提高相關性
            search_query = f"{query} image"
            results = self.search_tool.run(search_query)
            LOG.info(f"搜索結果:\n{results}")
            if results and isinstance(results, list) and len(results) > 0:
                # 假設結果中包含圖片 URL
                return results[0]  # 返回第一個搜索結果
            return None
        except Exception as e:
            LOG.error(f"搜索圖片時發生錯誤: {str(e)}")
            return None


    def _convert_to_markdown(self, user_input):
        try:
            # 獲取初始 Markdown 內容
            messages = self.prompt_template.format_messages(input=user_input)
            response = self.chat.invoke(messages)
            content = response.content
            LOG.info(f"生成的 初始 內容:\n{content}")

            # 處理每個幻燈片
            slides = content.split('##')
            processed_slides = []

            # 處理主標題（第一個部分）
            if slides[0].strip():
                processed_slides.append(slides[0].strip())

            # 處理其餘的幻燈片
            for slide in slides[1:]:
                if slide.strip():
                    processed_slide = self._process_slide_content(slide)
                    processed_slides.append(f"## {processed_slide}")

            # 組合處理後的內容
            return '\n\n'.join(processed_slides)

        except Exception as e:
            LOG.error(f"轉換為 Markdown 時發生錯誤: {str(e)}")
            raise

    def generate_ppt(self, user_input):
        try:
            # 將用戶輸入轉換為 Markdown
            LOG.info("正在將用戶輸入轉換為 Markdown 格式...")
            markdown_content = self._convert_to_markdown(user_input)

            LOG.info(f"生成的 Markdown 內容:\n{markdown_content}")

            # 解析 Markdown 內容
            powerpoint_data, presentation_title = parse_input_text(
                markdown_content,
                self.layout_manager
            )

            LOG.info(f"解析後的 PowerPoint 數據結構:\n{powerpoint_data}")

            # 確保輸出目錄存在
            os.makedirs("outputs", exist_ok=True)

            # 生成輸出文件路徑
            output_pptx = f"outputs/{presentation_title}.pptx"

            # 生成 PowerPoint 文件
            generate_presentation(
                powerpoint_data,
                self.config.ppt_template,
                output_pptx
            )

            return (
                f"成功生成 PowerPoint 文件：{output_pptx}\n\n"
                f"生成的 Markdown 內容：\n{markdown_content}",
                output_pptx
            )
        except Exception as e:
            LOG.error(f"生成 PowerPoint 時發生錯誤: {str(e)}")
            return f"錯誤：{str(e)}", None

def create_interface():
    chat_ppt = ChatPPTInterface()

    with gr.Blocks(title="ChatPPT - AI 簡報生成器") as interface:
        gr.Markdown("""
        # ChatPPT - AI 簡報生成器
        只需描述您的需求，AI 將幫您生成專業的 PowerPoint 演示文稿
        """)

        with gr.Row():
            with gr.Column(scale=2):
                # 用戶輸入區域
                input_text = gr.Textbox(
                    label="描述您的需求",
                    placeholder="例如：我需要一份關於人工智能發展歷史的演示文稿，包含主要里程碑和未來展望...",
                    lines=6
                )

                # 生成按鈕
                generate_btn = gr.Button("生成簡報", variant="primary")

            with gr.Column(scale=1):
                # 輸出區域
                output_message = gr.Textbox(
                    label="生成結果",
                    lines=10
                )
                output_file = gr.File(label="下載 PowerPoint")

        generate_btn.click(
            fn=chat_ppt.generate_ppt,
            inputs=[input_text],
            outputs=[output_message, output_file]
        )

    return interface

if __name__ == "__main__":
    # 確保設置了 OpenAI API 密鑰
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("請設置 OPENAI_API_KEY 環境變量")

    interface = create_interface()
    interface.launch(
        share=True,
        server_name="0.0.0.0",
        server_port=7860
    )
