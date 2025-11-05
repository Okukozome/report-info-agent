# pipeline/utils/file_utils.py
import pandas as pd
from pathlib import Path
from typing import Dict, Literal, List
import logging
from core.schemas import Person

BASE_DIR = Path(__file__).parent.parent # pipeline/ 目录
RESULTS_DIR = BASE_DIR / "results"
DEBUG_DIR = BASE_DIR / "debug_logs"

logger = logging.getLogger(__name__)

def save_debug_files(
    task_id: str, 
    status: Literal["success", "failed", "review"], 
    files_to_save: Dict[str, str]
):
    """
    将所有中间文件和日志保存到指定的 debug 目录
    """
    try:
        log_dir = DEBUG_DIR / status / task_id
        log_dir.mkdir(parents=True, exist_ok=True)
        
        for filename, content in files_to_save.items():
            try:
                (log_dir / filename).write_text(content, encoding='utf-8')
            except Exception as e:
                logger.error(f"写入 debug 文件 {filename} 失败: {e}")
                
    except Exception as e:
        logger.error(f"创建 debug 目录 {log_dir} 失败: {e}")

def save_results_csv(
    task_id: str, 
    category: Literal["Directors", "Supervisors", "SeniorManagement"], 
    persons: List[Person]
):
    """
    将最终的排序结果保存为 CSV
    """
    try:
        results_dir = RESULTS_DIR / task_id
        results_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = results_dir / f"{category.lower()}_ranked.csv"
        
        if not persons:
            # 如果列表为空，也创建一个带表头的空文件
            df = pd.DataFrame(columns=["rank", "name", "role"])
        else:
            df = pd.DataFrame([p.model_dump() for p in persons])
        
        # 按 rank 排序后保存
        df.sort_values(by="rank").to_csv(output_path, index=False, encoding='utf-8')
        
    except Exception as e:
        logger.error(f"保存结果 CSV {output_path} 失败: {e}")