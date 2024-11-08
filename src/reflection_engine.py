import json
import re
from typing import Dict, Optional
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from config import Config
from logger import LOG

class ReflectionState(BaseModel):
    """反思過程的狀態模型"""
    content: str = Field(default="", description="當前內容")
    analysis: Optional[Dict] = Field(default=None, description="內容分析結果")
    improved_content: Optional[str] = Field(default=None, description="改進後的內容")
    evaluation: Optional[Dict] = Field(default=None, description="評估結果")
    iterations: int = Field(default=0, description="當前迭代次數")
    previous_score: float = Field(default=0.0, description="上一次評分")

class ReflectionOutput(BaseModel):
    """反思過程的輸出模型"""
    final_content: str = Field(description="最終改進的內容")
    iterations: int = Field(description="總迭代次數")
    final_score: float = Field(description="最終評分")

class ReflectionEngine:
    def __init__(self, config: Optional[Config] = None):
        """初始化 ReflectionEngine"""
        self.config = config or Config()
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.5,
            max_tokens=4096
        )
        self.max_iterations = self.config.reflection.max_iterations
        self.min_iterations = self.config.reflection.min_iterations
        self.improvement_threshold = self.config.reflection.improvement_threshold
        LOG.info(f"ReflectionEngine initialized with max_iterations={self.max_iterations}, "
                 f"min_iterations={self.min_iterations}, improvement_threshold={self.improvement_threshold}")

    def create_graph(self) -> StateGraph:
        """創建並返回工作流圖"""
        LOG.info("Creating reflection workflow graph")
        workflow = StateGraph(ReflectionState)

        workflow.add_node("analyze", self._analyze_content)
        workflow.add_node("improve", self._improve_content)
        workflow.add_node("evaluate", self._evaluate_improvement)

        workflow.set_entry_point("analyze")

        workflow.add_edge("analyze", "improve")
        workflow.add_edge("improve", "evaluate")

        workflow.add_conditional_edges(
            "evaluate",
            self._should_continue,
            {
                True: "analyze",
                False: END
            }
        )

        LOG.info("Reflection workflow graph created successfully")
        return workflow.compile()

    def reflect_and_improve(self, initial_content: str) -> ReflectionOutput:
        """執行反思和改進過程"""
        LOG.info("Starting reflection and improvement process")
        graph = self.create_graph()
        initial_state = ReflectionState(content=initial_content, iterations=0)

        try:
            final_state = initial_state
            for output in graph.stream(initial_state):
                LOG.debug(f"output['iterations'] is {output['analyze']['iterations']}")
                LOG.debug(f"output['previous_score'] is {output['analyze']['previous_score']}")
                if isinstance(output, dict):
                    if 'state' in output:
                        final_state = ReflectionState(**output['state'])
                        LOG.debug(f"Updated state: iterations={final_state.iterations}, content_length={len(final_state.content)}")
                    if output.get('end'):
                        LOG.info("Reflection process completed")
                        break
                # Log the state after each stream output
                LOG.debug(f"Intermediate state: iterations={final_state.iterations}, content_length={len(final_state.content)}")
            LOG.info("Reflection process completed successfully")
            LOG.debug(f"Final state: iterations={final_state.iterations}, content_length={len(final_state.content)}")
        except Exception as e:
            LOG.error(f"Reflection process failed: {str(e)}")
            import traceback
            LOG.error(traceback.format_exc())
        
        return self._extract_result(final_state)


    def _extract_result(self, state: ReflectionState) -> ReflectionOutput:
        """從最終狀態提取結果"""
        final_score = 0.0
        if hasattr(state, 'evaluation') and isinstance(state.evaluation, dict):
            final_score = float(state.evaluation.get('score', 0.0))
        
        LOG.info(f"Extracting final result: content length={len(state.content)}, "
                 f"iterations={state.iterations}, final_score={final_score}")
        return ReflectionOutput(
            final_content=state.content,
            iterations=state.iterations,
            final_score=final_score
        )

    def _should_continue(self, state: ReflectionState) -> bool:
        """決定是否繼續迭代"""
        if state.iterations >= self.max_iterations:
            LOG.info(f"Stopping: Maximum iterations ({self.max_iterations}) reached")
            return False
        
        if state.evaluation:
            current_score = float(state.evaluation['score'])
            LOG.debug(f"Current score: {current_score}, Previous score: {state.previous_score}")

            if current_score >= 9:
                LOG.info(f"Stopping: High quality achieved (score: {current_score})")
                return False
            if state.iterations >= self.min_iterations:
                if current_score - state.previous_score < self.improvement_threshold:
                    LOG.info(f"Stopping: No significant improvement (threshold: {self.improvement_threshold})")
                    return False
            
            state.previous_score = current_score
            LOG.debug(f"Updated previous score to: {state.previous_score}")
            LOG.info(f"Continuing to next iteration. Current score: {current_score}")
        elif state.iterations > 0:
            LOG.warning("No evaluation available, but continuing")
        
        return True


    def _analyze_content(self, state: ReflectionState) -> ReflectionState:
        """分析當前內容"""
        LOG.debug(f"Analyzing content (iteration {state.iterations + 1})")
        prompt = ChatPromptTemplate.from_messages([
            HumanMessage(content=self._get_analysis_template().format(content=state.content))
        ])
        messages = prompt.format_messages(content=state.content)
        analysis = self.llm.invoke(messages)
        
        try:
            cleaned_content = self._clean_json_string(analysis.content)
            state.analysis = json.loads(cleaned_content)
            LOG.debug(f"Analysis result: {state.analysis}")
        except json.JSONDecodeError as e:
            LOG.error(f"Failed to parse analysis JSON: {analysis.content}")
            LOG.error(f"JSON parse error: {str(e)}")
            state.analysis = {"error": "Failed to parse JSON", "raw_content": analysis.content}
        
        LOG.debug(f"Content analysis completed for iteration {state.iterations + 1}")
        return state


    def _improve_content(self, state: ReflectionState) -> ReflectionState:
        """根據分析結果改進內容"""
        LOG.debug(f"Improving content (iteration {state.iterations + 1})")
        prompt = ChatPromptTemplate.from_messages([
            HumanMessage(content=self._get_improvement_template().format(
                content=state.content, analysis=state.analysis))
        ])
        messages = prompt.format_messages(content=state.content, analysis=state.analysis)
        improved = self.llm.invoke(messages)
        
        try:
            cleaned_content = self._clean_json_string(improved.content)
            improvement_data = json.loads(cleaned_content)
            state.improved_content = improvement_data.get('improved_content', '')
            LOG.debug(f"Improvement changes: {improvement_data.get('changes', [])}")
        except json.JSONDecodeError as e:
            LOG.error(f"Failed to parse improvement JSON: {improved.content}")
            LOG.error(f"JSON parse error: {str(e)}")
            state.improved_content = improved.content
        
        LOG.debug(f"Content improvement completed for iteration {state.iterations + 1}")
        return state

    def _evaluate_improvement(self, state: ReflectionState) -> ReflectionState:
        """評估改進的效果"""
        LOG.debug(f"Evaluating improvement (iteration {state.iterations + 1})")
        prompt = ChatPromptTemplate.from_messages([
            HumanMessage(content=self._get_evaluation_template().format(
                original=state.content, improved=state.improved_content))
        ])
        messages = prompt.format_messages(original=state.content, improved=state.improved_content)
        evaluation = self.llm.invoke(messages)
        
        try:
            cleaned_content = self._clean_json_string(evaluation.content)
            state.evaluation = json.loads(cleaned_content)
            LOG.debug(f"Evaluation result: {state.evaluation}")            
        except json.JSONDecodeError as e:
            LOG.error(f"Failed to parse evaluation JSON: {evaluation.content}")
            LOG.error(f"JSON parse error: {str(e)}")
            state.evaluation = {"error": "Failed to parse JSON", "raw_content": evaluation.content}
        
        state.iterations += 1
        state.content = state.improved_content
        LOG.info(f"Iteration {state.iterations} completed. Evaluation: {state.evaluation}")
        return state


    @staticmethod
    def _clean_json_string(json_string: str) -> str:
        """清理 JSON 字符串，移除 Markdown 格式和多餘的空白"""
        # 移除 Markdown 代碼塊標記
        cleaned = re.sub(r'```json\s*|\s*```', '', json_string)
        # 移除開頭和結尾的空白字符
        cleaned = cleaned.strip()
        return cleaned

    @staticmethod
    def _get_analysis_template() -> str:
        return """
        你是一位專業的內容分析師，擅長深入分析文本並提供建設性的反饋。請仔細分析以下內容，並以JSON格式返回詳細的分析結果：

        {content}

        請確保您的回答是一個有效的JSON對象，包含以下鍵：
        - strengths: 列出內容的優點，包括但不限於結構、邏輯、語言表達、信息豐富度等方面
        - weaknesses: 指出內容的不足之處，包括但不限於邏輯漏洞、表達不清晰、信息缺失等問題
        - suggestions: 提供具體且可操作的改進建議，每個建議應包含改進點和相應的實施方法
        - key_points: 總結內容的核心要點，確保不遺漏重要信息
        - audience_impact: 評估內容對目標受眾的潛在影響和吸引力

        在分析過程中，請特別注意：
        1. 內容是否符合原始的演示主題和目的
        2. 各個幻燈片之間的連貫性和邏輯流程
        3. 是否有足夠的細節和例子支持主要論點
        4. 語言表達是否清晰、簡潔且有說服力
        5. 內容結構是否合理，便於聽眾理解和記憶

        請提供深入、客觀且有建設性的分析，以幫助作者顯著提升內容質量。
        """


    @staticmethod
    def _get_improvement_template() -> str:
        return """
        你是一位經驗豐富的內容優化專家，擅長根據分析結果改進文本內容。請根據以下分析結果，對給定的內容進行全面的改進和優化：

        原始內容：
        {content}

        分析結果：
        {analysis}

        請按照以下步驟進行改進：
        1. 仔細閱讀原始內容和分析結果
        2. 根據分析中指出的優點，進一步強化這些方面
        3. 針對分析中提到的弱點，進行有針對性的修改和完善
        4. 參考改進建議，對內容進行具體的優化
        5. 確保改進後的內容保持原有的核心信息，同時提升整體質量和表現力
        6. 注意保持各個幻燈片之間的連貫性和邏輯流程
        7. 適當增加細節、例子或數據來支持主要論點
        8. 優化語言表達，使其更加清晰、簡潔且有說服力
        9. 調整內容結構，使其更易於理解和記憶

        請提供改進後的內容，並確保您的回答是一個有效的JSON對象，包含以下鍵：
        - improved_content: 完整的改進後內容
        - changes: 詳細列出所做的主要更改，包括每項更改的原因和預期效果
        - improvement_summary: 簡要總結改進的重點和整體提升效果

        在改進過程中，請確保：
        1. 保持原有的演示風格和tone of voice
        2. 改進內容符合原始的演示主題和目的
        3. 優化後的內容對目標受眾更具吸引力和影響力
        4. 每個幻燈片都有清晰的主題和豐富的內容
        5. 整體演示結構更加合理，邏輯更加清晰

        請提供高質量的改進，確保內容在各個方面都有顯著提升。
        """


    @staticmethod
    def _get_evaluation_template() -> str:
        return """
        你是一位嚴格的內容評估專家，擅長客觀評估內容質量並提供詳細反饋。請仔細評估原始內容和改進後的內容，並提供全面的評估報告：

        原始內容：
        {original}

        改進後的內容：
        {improved}

        請按照以下標準進行評估，並確保您的回答是一個有效的JSON對象，包含以下鍵：
        - score: 1-10的評分，表示改進的整體程度（1分表示幾乎沒有改進，10分表示顯著改進）
        - criteria_scores: 對各個評估標準的單獨評分（1-10分），包括：
          - content_quality: 內容質量和深度
          - structure: 結構和邏輯流程
          - clarity: 表達清晰度
          - engagement: 吸引力和說服力
          - relevance: 與主題和目標受眾的相關性
        - improvements: 詳細說明改進的具體方面和效果
        - remaining_issues: 指出仍需進一步改進的地方
        - overall_assessment: 對改進效果的總體評價
        - recommendations: 為進一步提升內容質量提供建議

        評估過程中，請特別注意：
        1. 改進是否解決了原始內容中的主要問題
        2. 新增的內容或修改是否增加了價值
        3. 整體結構和邏輯流程是否有所優化
        4. 語言表達是否更加清晰、簡潔且有說服力
        5. 內容是否更好地符合演示主題和目的
        6. 是否更有效地吸引和影響目標受眾

        請提供客觀、全面且有建設性的評估，以幫助進一步改進內容質量。如果評分低於8分，請詳細解釋原因並提供具體的改進建議。
        """


# 使用示例
if __name__ == "__main__":
    initial_content = "這是一個初始內容，需要進行改進和優化。"
    engine = ReflectionEngine()
    LOG.info(f"Initial content: {initial_content}")
    result = engine.reflect_and_improve(initial_content)
    
    LOG.info(f"Final content: {result.final_content}")
    LOG.info(f"Total iterations: {result.iterations}")
    LOG.info(f"Final score: {result.final_score}")
    LOG.info("ReflectionEngine demo completed")