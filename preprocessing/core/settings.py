import pydantic_settings
from pydantic import Field

class Settings(pydantic_settings.BaseSettings):
    """
    配置模型，从 .env 文件或环境变量加载
    """
    
    # LLM API
    API_KEY: str = Field(..., description="LLM API 密钥")
    API_BASE_URL: str = Field(..., description="LLM API 的 Base URL")
    LLM_MODEL: str = Field(..., description="用于分析的 LLM 模型")

    # PP-StructureV3 API
    PP_API_URL: str = Field(..., description="PP-StructureV3 API 端点")
    PP_TOKEN: str = Field(..., description="PP-StructureV3 API 令牌")

    # Pipeline 常量
    TOC_SEARCH_PAGES: int = Field(10, description="用于搜索目录的最大页数")
    API_TIMEOUT: int = Field(120, description="所有 API 请求的超时时间（秒）")

    class Config:
        # Pydantic-settings v2+ a.k.a .env loading
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

# 导出一个单例，以便在模块中共享
try:
    settings = Settings()
except Exception as e:
    print(f"无法加载配置: {e}。请确保 .env 文件存在或已设置环境变量。", flush=True)
    # 允许在 main.py 中捕获并处理
    raise