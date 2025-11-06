import logging
import sys
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm

# 确保 core 模块可以被导入
# 假设 main.py 在 preprocessing/ 目录下运行
sys.path.append(str(Path(__file__).parent))

try:
    from core.settings import Settings
    from orchestrator import process_file
except ImportError:
    print("错误：无法导入核心模块。请确保在 'preprocessing' 目录下运行此脚本。", file=sys.stderr)
    sys.exit(1)

# --- 配置 ---
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("PreprocessingMain")

# 配置路径
BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "raw"
PREPROCESSED_DIR = BASE_DIR / "preprocessed"
DEBUG_DIR = BASE_DIR / "debug"  # Debug 目录
# ---

def main():
    """
    预处理流水线主函数
    """
    logger.info("--- 开始执行预处理流水线 ---")
    
    # 1. 加载环境变量
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        logger.warning(f"未找到 .env 文件 (应位于 {env_path})，尝试从环境变量加载。")
    load_dotenv(dotenv_path=env_path)

    # 2. 加载配置
    try:
        settings = Settings()
    except Exception as e:
        logger.error(f"加载配置失败 (请检查 .env 文件或环境变量): {e}")
        return

    # 3. 确保目录存在
    RAW_DIR.mkdir(exist_ok=True)
    PREPROCESSED_DIR.mkdir(exist_ok=True)
    DEBUG_DIR.mkdir(exist_ok=True)  # 创建 Debug 目录
    logger.info(f"输入目录: {RAW_DIR}")
    logger.info(f"输出目录: {PREPROCESSED_DIR}")
    logger.info(f"调试目录: {DEBUG_DIR}")

    # 4. 查找任务
    pdf_files = list(RAW_DIR.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"在 {RAW_DIR} 中未找到任何 .pdf 文件。")
        return

    logger.info(f"共找到 {len(pdf_files)} 个 PDF 文件待处理。")

    # 5. 执行任务
    summary = {"SUCCESS": 0, "SKIPPED": 0, "FAILED": 0}
    
    for pdf_path in tqdm(pdf_files, desc="Processing PDFs"):
        output_name = f"{pdf_path.stem}_split.pdf"
        output_path = PREPROCESSED_DIR / output_name
        
        task_id = pdf_path.name
        
        # 检查文件是否已处理
        if output_path.exists():
            logger.info(f"[{task_id}] -> SKIPPED (已存在 {output_name})")
            summary["SKIPPED"] += 1
            continue  # 跳过此文件

        try:
            # 传入 DEBUG_DIR
            status = process_file(pdf_path, output_path, settings, DEBUG_DIR) 
            
            if "SUCCESS" in status:
                summary["SUCCESS"] += 1
            elif "SKIPPED" in status:
                summary["SKIPPED"] += 1
            else:
                summary["FAILED"] += 1
            logger.info(f"[{task_id}] -> {status}")
            
        except Exception as e:
            logger.error(f"[{task_id}] 遭遇致命错误: {e}", exc_info=True)
            summary["FAILED"] += 1

    # 6. 打印总结
    logger.info("--- 预处理流水线执行完毕 ---")
    logger.info(f"成功: {summary['SUCCESS']}")
    logger.info(f"跳过: {summary['SKIPPED']} (例如页数过短或已存在)")
    logger.info(f"失败: {summary['FAILED']}")
    logger.info("---")

if __name__ == "__main__":
    main()