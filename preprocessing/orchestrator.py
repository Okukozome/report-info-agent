import logging
import re
import shutil
from pathlib import Path
from typing import Literal, List

# 假设在 main.py 同级，core 是兄弟目录
from core.settings import Settings
from core import schemas
from core import llm_clients
from core import pdf_utils

logger = logging.getLogger("Orchestrator")

# 步骤 4.1：编译"目录"正则表达式
TOC_REGEX = re.compile(r"目\s*录")

# 步骤 6.1：定义最大重试次数
VERIFICATION_MAX_RETRIES = 10

def process_file(
    pdf_path: Path, 
    output_path: Path, 
    settings: Settings,
    debug_dir: Path
) -> str:
    """
    对单个 PDF 文件执行完整的预处理流水线
    """
    
    # --- Debug 文件保存辅助函数 ---
    def save_debug_markdowns(page_markdowns: list):
        task_debug_dir = debug_dir / pdf_path.stem
        task_debug_dir.mkdir(parents=True, exist_ok=True)
        for i, md_content in enumerate(page_markdowns):
            page_num = i + 1
            debug_file_path = task_debug_dir / f"page_{page_num:02d}.md"
            try:
                with open(debug_file_path, "w", encoding="utf-8") as f:
                    f.write(f"--- [DEBUG] 原始文件名: {pdf_path.name}\n")
                    f.write(f"--- [DEBUG] 物理页码: {page_num}\n")
                    f.write("---\n\n")
                    f.write(md_content)
            except Exception as e:
                logger.error(f"[{pdf_path.name}] 保存 debug page {page_num} 失败: {e}")
        logger.info(f"[{pdf_path.name}] 已保存 {len(page_markdowns)} 页 debug markdown 到 {task_debug_dir}")
    # ---

    # 步骤 1: 检查总页数
    try:
        total_pages = pdf_utils.get_pdf_page_count(pdf_path)
    except Exception as e:
        return f"FAILED (无法读取PDF: {e})"

    if total_pages < settings.TOC_SEARCH_PAGES:
        # 文件太短，可能没有目录，直接复制
        shutil.copy(pdf_path, output_path)
        return f"SKIPPED (页数 < {settings.TOC_SEARCH_PAGES}，已完整复制)"

    # 步骤 2: 分割前 N 页用于目录搜索
    logger.info(f"[{pdf_path.name}] 步骤 2: 提取前 {settings.TOC_SEARCH_PAGES} 页...")
    try:
        toc_pdf_bytes = pdf_utils.split_pdf_to_bytes(pdf_path, max_pages=settings.TOC_SEARCH_PAGES)
    except Exception as e:
        return f"FAILED (PDF分割失败: {e})"

    # 步骤 3: 调用 PP-StructureV3 获取前 N 页的 Markdown
    logger.info(f"[{pdf_path.name}] 步骤 3: 调用 PP-StructureV3...")
    try:
        page_markdowns = llm_clients.call_pp_structure_api(toc_pdf_bytes, settings)
    except Exception as e:
        return f"FAILED (PP-StructureV3 API 失败: {e})"

    # --- 保存 Debug 文件 ---
    save_debug_markdowns(page_markdowns)
    # ---

    # 步骤 4: 查找"目录"并拼接 Prompt
    logger.info(f"[{pdf_path.name}] 步骤 4: 查找'目录'...")
    toc_content_list = []
    for i, md in enumerate(page_markdowns):
        if TOC_REGEX.search(md):
            toc_content_list.append(f"\n--- [PDF 物理页: {i + 1}] ---\n{md}")
            
    if not toc_content_list:
        return f"FAILED (在前 {settings.TOC_SEARCH_PAGES} 页中未找到'目录'关键字)"
    
    toc_full_markdown = "\n".join(toc_content_list)

    # 步骤 5: AI 步骤 1 - 分析目录
    logger.info(f"[{pdf_path.name}] 步骤 5: AI分析目录...")
    try:
        toc_result = llm_clients.find_dgs_chapter_in_toc(toc_full_markdown, settings)
        
        if (toc_result.start_page == -1 or 
            toc_result.end_page == -1 or 
            not toc_result.title):
            return "FAILED (AI未能在目录中定位DGS章节)"
        
        if toc_result.end_page < toc_result.start_page:
             return "FAILED (AI返回的结束页码小于起始页码)"
            
    except Exception as e:
        return f"FAILED (AI 步骤 1 失败: {e})"

    logger.info(f"[{pdf_path.name}] 目录分析成功: "
                f"章节='{toc_result.title}', "
                f"目录页码=[{toc_result.start_page}-{toc_result.end_page}]")

    # 步骤 6: AI 步骤 2 - 迭代验证起始页（解决页码偏移）
    logger.info(f"[{pdf_path.name}] 步骤 6: 迭代验证起始页...")
    
    target_title = toc_result.title
    doc_start_page = toc_result.start_page
    doc_end_page = toc_result.end_page
    chapter_length = doc_end_page - doc_start_page + 1

    # 初始猜测：目录页码 = 物理页码索引 + 1
    current_pdf_index = doc_start_page - 1
    found_pdf_index = -1
    
    visited_indexes = set()
    
    # 初始化历史列表
    verification_history: List[str] = []

    for i in range(VERIFICATION_MAX_RETRIES):
        logger.info(f"[{pdf_path.name}]  验证循环 {i+1}/{VERIFICATION_MAX_RETRIES}: "
                    f"尝试物理索引 {current_pdf_index} (页码 {current_pdf_index + 1})")

        # 0. 检查边界和循环
        if not (0 <= current_pdf_index < total_pages):
            logger.warning(f"[{pdf_path.name}]  索引 {current_pdf_index} 超出范围 [0, {total_pages - 1}]")
            break
        if current_pdf_index in visited_indexes:
            logger.warning(f"[{pdf_path.name}]  索引 {current_pdf_index} 已访问，停止循环。")
            break
        visited_indexes.add(current_pdf_index)

        # 1. 提取单页
        try:
            page_bytes = pdf_utils.get_pdf_page_by_index_to_bytes(pdf_path, current_pdf_index)
            # PP-StructureV3 预期是列表
            md_content_list = llm_clients.call_pp_structure_api(page_bytes, settings)
            if not md_content_list:
                raise Exception("PP-StructureV3 返回空内容")
            page_markdown = md_content_list[0]
            
        except Exception as e:
            logger.error(f"[{pdf_path.name}]  在索引 {current_pdf_index} 获取页面内容失败: {e}")
            break # 提取失败，终止循环

        # 2. AI 验证
        try:
            verify_result = llm_clients.verify_chapter_start_page(
                page_markdown, target_title, settings, verification_history
            )
            logger.info(f"[{pdf_path.name}]  AI 验证结果: {verify_result.status} ({verify_result.reason})")
            
            # 记录本次历史以备下次使用
            history_entry = (
                f"Attempt {i+1}: Tested physical index {current_pdf_index} (Page {current_pdf_index + 1}). "
                f"AI result was '{verify_result.status}'. "
                f"AI reason: \"{verify_result.reason}\""
            )
            verification_history.append(history_entry)

            # 3. 决策
            if verify_result.status == "match":
                found_pdf_index = current_pdf_index
                break
            elif verify_result.status == "too_early":
                current_pdf_index += 1 # 还没到，下一页
            elif verify_result.status == "too_late":
                current_pdf_index -= 1 # 翻过了，上一页
            elif verify_result.status == "fail":
                break # AI 认为无法判断，终止
                
        except Exception as e:
            logger.error(f"[{pdf_path.name}]  AI 步骤 2 失败: {e}")
            break # AI 失败，终止循环

    if found_pdf_index == -1:
        return f"FAILED (迭代 {VERIFICATION_MAX_RETRIES} 次后仍未找到起始页)"

    logger.info(f"[{pdf_path.name}] 验证成功! "
                f"物理起始索引: {found_pdf_index} (页码 {found_pdf_index + 1})")

    # 步骤 7: 最终裁剪
    start_index = found_pdf_index
    # 计算结束索引，并确保不越界
    end_index = min(found_pdf_index + chapter_length - 1, total_pages - 1)

    logger.info(f"[{pdf_path.name}] 步骤 7: 裁剪 PDF 范围 "
                f"[{start_index} - {end_index}] (共 {end_index - start_index + 1} 页)")

    try:
        pdf_utils.crop_pdf(pdf_path, start_index, end_index, output_path)
    except Exception as e:
        return f"FAILED (最终裁剪失败: {e})"

    return f"SUCCESS (裁剪 {start_index}-{end_index})"