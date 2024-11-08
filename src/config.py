from dataclasses import dataclass
from typing import Optional
import json
import os
from pathlib import Path

@dataclass
class ReflectionConfig:
    """反思引擎相關配置"""
    max_iterations: int = 7
    min_iterations: int = 3
    improvement_threshold: float = 0.2

@dataclass
class PromptConfig:
    """提示詞相關配置"""
    chatbot: str = "prompts/chatbot.txt"
    content_formatter: str = "prompts/content_formatter.txt"
    content_assistant: str = "prompts/content_assistant.txt"
    image_advisor: str = "prompts/image_advisor.txt"

class ConfigurationError(Exception):
    """配置相關錯誤的自定義異常類"""
    pass

class Config:
    """
    配置管理類，負責加載和管理應用程序的配置。
    
    支持從 JSON 文件加載配置，並提供合理的默認值。
    包含配置驗證和路徑解析功能。
    """

    DEFAULT_CONFIG_PATH = "config.json"
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器。

        Args:
            config_file: 配置文件路徑，如果為 None 則使用默認路徑

        Raises:
            ConfigurationError: 當配置加載或驗證失敗時
        """
        self.config_file = config_file or self.DEFAULT_CONFIG_PATH
        self.base_path = Path(os.path.dirname(os.path.abspath(self.config_file)))
        
        # 初始化配置屬性
        self.input_mode: str = "text"
        self.ppt_template: str = "templates/MasterTemplate.pptx"
        self.prompts = PromptConfig()
        self.reflection = ReflectionConfig()
        
        self.load_config()
        self.validate_config()

    def load_config(self) -> None:
        """
        從配置文件加載配置。

        Raises:
            ConfigurationError: 當配置文件不存在或格式錯誤時
        """
        try:
            if not os.path.exists(self.config_file):
                raise ConfigurationError(f"配置文件不存在: {self.config_file}")

            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 基礎配置
            self.input_mode = config.get('input_mode', self.input_mode)
            self.ppt_template = self._resolve_path(
                config.get('ppt_template', self.ppt_template)
            )

            # 提示詞配置
            self.prompts = PromptConfig(
                chatbot=self._resolve_path(config.get('chatbot_prompt', self.prompts.chatbot)),
                content_formatter=self._resolve_path(
                    config.get('content_formatter_prompt', self.prompts.content_formatter)
                ),
                content_assistant=self._resolve_path(
                    config.get('content_assistant_prompt', self.prompts.content_assistant)
                ),
                image_advisor=self._resolve_path(
                    config.get('image_advisor_prompt', self.prompts.image_advisor)
                )
            )

            # 反思引擎配置
            self.reflection = ReflectionConfig(
                max_iterations=config.get('reflection_max_iterations', 
                                       self.reflection.max_iterations),
                min_iterations=config.get('reflection_min_iterations', 
                                        self.reflection.min_iterations),
                improvement_threshold=config.get('reflection_improvement_threshold',
                                              self.reflection.improvement_threshold)
            )

        except json.JSONDecodeError as e:
            raise ConfigurationError(f"配置文件格式錯誤: {str(e)}")
        except Exception as e:
            raise ConfigurationError(f"加載配置時發生錯誤: {str(e)}")

    def validate_config(self) -> None:
        """
        驗證配置的有效性。

        Raises:
            ConfigurationError: 當配置驗證失敗時
        """
        # 驗證必要文件是否存在
        required_files = [
            self.ppt_template,
            self.prompts.chatbot,
            self.prompts.content_formatter,
            self.prompts.content_assistant,
            self.prompts.image_advisor
        ]

        for file_path in required_files:
            if not os.path.exists(file_path):
                raise ConfigurationError(f"必要文件不存在: {file_path}")

        # 驗證反思引擎配置的合理性
        if not (0 < self.reflection.min_iterations <= self.reflection.max_iterations):
            raise ConfigurationError("反思引擎迭代次數配置無效")

        if not (0 < self.reflection.improvement_threshold < 1):
            raise ConfigurationError("改進閾值必須在 0 到 1 之間")

    def _resolve_path(self, path: str) -> str:
        """
        解析相對路徑為絕對路徑。

        Args:
            path: 相對路徑或絕對路徑

        Returns:
            str: 解析後的絕對路徑
        """
        if os.path.isabs(path):
            return path
        return str(self.base_path / path)

    def get_prompt_path(self, prompt_type: str) -> str:
        """
        獲取指定類型的提示詞文件路徑。

        Args:
            prompt_type: 提示詞類型 ('chatbot', 'content_formatter', 
                        'content_assistant', 'image_advisor')

        Returns:
            str: 提示詞文件的絕對路徑

        Raises:
            ValueError: 當提示詞類型無效時
        """
        prompts_map = {
            'chatbot': self.prompts.chatbot,
            'content_formatter': self.prompts.content_formatter,
            'content_assistant': self.prompts.content_assistant,
            'image_advisor': self.prompts.image_advisor
        }

        if prompt_type not in prompts_map:
            raise ValueError(f"無效的提示詞類型: {prompt_type}")

        return prompts_map[prompt_type]

    def __str__(self) -> str:
        """返回配置的字符串表示"""
        return (
            f"Config(\n"
            f"  input_mode={self.input_mode},\n"
            f"  ppt_template={self.ppt_template},\n"
            f"  prompts={self.prompts},\n"
            f"  reflection={self.reflection}\n"
            f")"
        )
