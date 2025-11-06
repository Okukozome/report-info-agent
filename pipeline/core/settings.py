# pipeline/core/settings.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

# 定位到 .env 文件 (项目根目录)
BASE_DIR = Path(__file__).parent.parent # pipeline/ 目录
ENV_PATH = BASE_DIR.parent / '.env' # 根目录 / .env

class Settings(BaseSettings):
    """
    加载根目录 .env 文件中的环境变量
    """
    model_config = SettingsConfigDict(
        env_file=ENV_PATH, 
        env_file_encoding='utf-8', 
        extra='ignore'
    )
    
    # AI 聚合接口配置
    API_BASE_URL: str = Field(..., env="API_BASE_URL")
    API_KEY: str = Field(..., env="API_KEY")

    # 飞桨 PP-StructureV3 API 接口配置
    PP_API_URL: str = Field(..., env="PP_API_URL")
    PP_TOKEN: str = Field(..., env="PP_TOKEN")
    
    # LLM 模型配置
    LLM_MODEL: str = Field(default="gpt-5-mini", env="LLM_MODEL")
    LLM_TIMEOUT: int = Field(default=180, env="LLM_TIMEOUT")
    PP_TIMEOUT: int = Field(default=180, env="PP_TIMEOUT")

# 导出一个单例，供其他模块使用
try:
    settings = Settings()
except Exception as e:
    print(f"CRITICAL: 无法加载 .env 文件或配置不完整。")
    print(f"请确保 '.env' 文件存在于项目根目录 ( {ENV_PATH.resolve()} )，并包含所有必需的键。")
    print(f"错误: {e}")
    exit(1)