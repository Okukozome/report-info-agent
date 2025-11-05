# pipeline/main.py
import argparse
import re
import sys
from pathlib import Path
from typing import Dict
from orchestrator import process_task
from utils.logging_config import setup_global_logger
import logging
from collections import Counter

# --- 配置 ---
BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "preprocessed_reports"
# 匹配文件名格式: 000014_2014_... .pdf
FILENAME_REGEX = re.compile(r"(\d{6})_(\d{4})_.*\.pdf")
# ---

def find_tasks() -> Dict[str, Path]:
    """
    扫描 preprocessed_reports 目录，建立 任务ID -> PDF路径 的映射
    """
    logger = logging.getLogger(__name__) # 获取 main logger
    logger.info(f"正在扫描目录: {REPORTS_DIR}")
    
    tasks = {}
    
    for pdf_file in REPORTS_DIR.glob("*.pdf"):
        match = FILENAME_REGEX.match(pdf_file.name)
        if match:
            stkcd = match.group(1)
            year = match.group(2)
            task_id = f"{stkcd}_{year}"
            
            if task_id in tasks:
                logger.warning(f"发现重复的任务ID: {task_id}。将使用 {pdf_file.name}，覆盖之前的。")
            tasks[task_id] = pdf_file
        else:
            logger.warning(f"忽略格式不匹配的文件: {pdf_file.name}")
            
    logger.info(f"共找到 {len(tasks)} 个有效任务。")
    return tasks

def main():
    # 1. 设置全局日志
    setup_global_logger()
    main_logger = logging.getLogger(__name__)

    # 2. 解析命令行参数
    parser = argparse.ArgumentParser(description="董监高(DGS)信息提取流水线")
    parser.add_argument(
        "--tasks", 
        nargs="+", 
        help="指定要处理的一个或多个任务ID (例如 '000014_2014')。 "
             "如果提供 'all'，则处理 'preprocessed_reports' 目录中的所有文件。 "
             "如果为空，则不执行任何操作。"
    )
    
    args = parser.parse_args()
    
    if not args.tasks:
        main_logger.info("未指定任何任务。请使用 --tasks [task_id...] 或 --tasks all。")
        parser.print_help()
        sys.exit(0)

    # 3. 查找所有可用任务
    try:
        all_available_tasks = find_tasks()
        if not all_available_tasks:
            main_logger.error(f"在 {REPORTS_DIR} 中未找到任何有效的 PDF 文件。")
            sys.exit(1)
    except Exception as e:
        main_logger.error(f"扫描任务文件时出错: {e}")
        sys.exit(1)

    # 4. 确定要运行的任务
    tasks_to_run: Dict[str, Path] = {}
    if "all" in args.tasks:
        tasks_to_run = all_available_tasks
        main_logger.info(f"--- 准备执行全部 {len(tasks_to_run)} 个任务 ---")
    else:
        for task_id in args.tasks:
            if task_id in all_available_tasks:
                tasks_to_run[task_id] = all_available_tasks[task_id]
            else:
                main_logger.warning(f"未找到任务 '{task_id}' 对应的 PDF 文件，已跳过。")
        main_logger.info(f"--- 准备执行 {len(tasks_to_run)} 个指定任务 ---")

    if not tasks_to_run:
        main_logger.error("没有要执行的任务。")
        sys.exit(0)
        
    # 5. 执行任务
    summary = Counter()
    total = len(tasks_to_run)
    
    for i, (task_id, pdf_path) in enumerate(tasks_to_run.items()):
        main_logger.info(f"--- ( {i+1} / {total} ) ---")
        try:
            status = process_task(task_id, pdf_path)
            summary[status] += 1
        except Exception as e:
            # 这是为了捕捉 orchestrator 本身的意外崩溃
            main_logger.error(f"!!! 任务 {task_id} 遭遇无法恢复的严重错误: {e}", exc_info=True)
            summary["failed"] += 1

    # 6. 打印总结
    main_logger.info("--- 批量处理完成 ---")
    main_logger.info(f"总计: {total} 个任务")
    main_logger.info(f"  成功 (Success): {summary['success']}")
    main_logger.info(f"  需审查 (Review):  {summary['review']}")
    main_logger.info(f"  失败 (Failed):  {summary['failed']}")
    main_logger.info("---")

if __name__ == "__main__":
    main()