import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 确保 .env 文件被加载
# 我们指向 mvp 目录的父目录（即项目根目录）或当前目录下的 .env
# 假设 .env 文件放在 mvp 目录中
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')

if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    # 兼容 .env 文件在项目根目录的情况
    env_path_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    if os.path.exists(env_path_root):
        load_dotenv(env_path_root)
    else:
        print("警告：未找到 .env 文件。请确保在 'mvp/' 或项目根目录创建 .env 文件。")


class Settings(BaseSettings):
    """加载环境变量"""
    API_BASE_URL: str
    API_KEY: str
    PP_API_URL: str
    PP_TOKEN: str

    class Config:
        # Pydantic-Settings V2 推荐使用 env_file 和 env_file_encoding
        # 但由于我们已使用 load_dotenv，它会自动从环境中读取
        env_file_encoding = "utf-8"

try:
    settings = Settings()
except Exception as e:
    print(f"错误：环境变量加载失败。请检查 .env 文件是否完整。")
    print(f"详细信息: {e}")
    exit(1)