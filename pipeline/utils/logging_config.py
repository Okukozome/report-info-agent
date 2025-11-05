# pipeline/utils/logging_config.py
import logging
import sys

def setup_global_logger():
    """
    配置全局 (main) 日志记录器，仅输出到控制台。
    任务相关的日志由 orchestrator 单独处理。
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [MAIN] - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # 调低 requests 和 pypdf 的日志级别，避免刷屏
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pypdf").setLevel(logging.WARNING)