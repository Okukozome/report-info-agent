# pipeline/orchestrator.py
import logging
import io
import json
from pathlib import Path
from typing import Dict, Tuple, Literal, List, Set

# 导入核心模块 (使用绝对路径)
from core import settings, schemas, pdf_parser, llm_extractor
from data_loader import get_target_lists
from utils.file_utils import save_debug_files, save_results_csv

# 辅助函数：执行三次 LLM 排序
def _run_ranking(
    source_text: str,
    target_lists: Dict[str, List[str]],
    cfg: settings.Settings,
    logger: logging.Logger
) -> Tuple[Dict[str, schemas.CategoryExtractionResult], int]:
    
    results: Dict[str, schemas.CategoryExtractionResult] = {}
    total_found_count = 0  # 统计所有 rank >= 0 的人
    
    if not source_text.strip():
         logger.warning("  [Ranker] 排序的原文内容为空，跳过所有排序。")
         return results, 0
    
    for category in ["Directors", "Supervisors", "SeniorManagement"]:
        target_names = target_lists.get(category, [])
        target_names_set = set(target_names)
        
        if not target_names:
            logger.info(f"  [{category}] 标准名单为空，跳过。")
            continue
            
        logger.info(f"  正在排序 [{category}] (目标 {len(target_names)} 人)...")
        result = llm_extractor.rank_names_from_text(
            markdown_content=source_text,
            category=category,
            target_names=target_names,
            settings=cfg
        )
        
        if result:
            results[category] = result
            
            # 统计所有被找到的人 (rank >= 0, 包括 1...N 和 0)
            found_persons = [p for p in result.persons if p.rank >= 0]
            found_count = len(found_persons)
            total_found_count += found_count
            
            # 检查未找到的人 (rank == -1)
            not_found_persons = [p for p in result.persons if p.rank == -1]
            not_found_count = len(not_found_persons)

            # 健全性检查：是否有未找到的人员 (rank: -1)
            if not_found_count > 0:
                logger.warning(f"  [{category}] 排序后名单不全: 找到 {found_count} / {len(target_names)} 人。")
                missing_names_from_result = {p.name for p in not_found_persons}
                logger.warning(f"  [{category}] 模型报告未找到 (rank: -1): {missing_names_from_result}")
                
                # 在评估中补充疑虑，并降低置信度
                doubt_msg = f"名单中 {not_found_count} 人未在原文中找到"
                # 避免重复添加
                doubt_exists = any(doubt_msg in d for d in result.assessment.doubts)
                if not doubt_exists:
                     result.assessment.doubts.append(f"{doubt_msg}: {missing_names_from_result}")
                if result.assessment.confidence_level == "High":
                    result.assessment.confidence_level = "Medium"
            
            # 兜底检查：返回的总人数是否与目标名单人数一致
            if len(result.persons) != len(target_names_set):
                logger.error(f"  [{category}] 严重逻辑错误：模型返回的人数 ({len(result.persons)}) 与标准名单人数 ({len(target_names_set)}) 不匹配！")
                result.assessment.doubts.append(f"严重错误：返回总人数 {len(result.persons)} != 名单人数 {len(target_names_set)}")
                result.assessment.confidence_level = "Low"
                
        else:
            logger.error(f"  [{category}] LLM 排序失败，返回 None。")
            
    return results, total_found_count


# 辅助函数：执行一次 LLM 验证
def _run_verification(
    source_text: str,
    combined_target_names: List[str],
    cfg: settings.Settings,
    logger: logging.Logger
) -> Tuple[Set[str], schemas.ConfidenceAssessment]:
    """
    调用 LLM 核对函数，返回找到的姓名集合和评估
    """
    if not source_text or not source_text.strip():
        logger.warning("  [Verifier] 原文内容为空，无法核对。")
        return set(), schemas.ConfidenceAssessment(
            confidence_level="Low", 
            doubts=["核对的原文内容为空。"]
        )
    
    verification_result = llm_extractor.verify_name_presence(
        source_text,
        combined_target_names,
        cfg,
    )
    
    if not verification_result:
        logger.error("  [Verifier] LLM 核对失败，返回 None。")
        raise Exception("LLM Verifier failed (returned None), likely due to API error or timeout.")
        
    found_names_set = set(verification_result.found_names)
    logger.info(f"  [Verifier] 核对完成。在原文中找到 {len(found_names_set)} / {len(combined_target_names)} 个姓名。")
    
    # 将核对的疑虑点也返回
    return found_names_set, verification_result.assessment

# 主流程
def process_task(task_id: str, pdf_path: Path) -> Literal["success", "failed", "review"]:
    """
    执行单个任务的完整流水线
    """
    
    # 1. 设置任务专用日志记录器
    log_stream = io.StringIO()
    task_logger = logging.getLogger(task_id)
    task_logger.setLevel(logging.INFO)
    
    if task_logger.hasHandlers():
        task_logger.handlers.clear()
    formatter = logging.Formatter(f'%(asctime)s - [{task_id}] - %(levelname)s - %(message)s')
    stream_handler = logging.StreamHandler(log_stream)
    stream_handler.setFormatter(formatter)
    task_logger.addHandler(stream_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    task_logger.addHandler(console_handler)

    status: Literal["success", "failed", "review"] = "failed"
    debug_files: Dict[str, str] = {}
    
    try:
        task_logger.info(f"=== 开始处理任务: {task_id} ===")
        task_logger.info(f"PDF 路径: {pdf_path}")
        
        stkcd, year = task_id.split('_')
        cfg = settings.settings
        
        # 步骤 0: 加载标准名单
        task_logger.info("步骤 0: 正在加载标准名单...")
        target_lists = get_target_lists(stkcd, year)
        debug_files['0_target_lists.json'] = json.dumps(target_lists, ensure_ascii=False, indent=2)
        
        # 创建一个包含所有董监高姓名的总名单，用于一次性核对
        combined_target_list = list(
            set(target_lists.get("Directors", [])) |
            set(target_lists.get("Supervisors", [])) |
            set(target_lists.get("SeniorManagement", []))
        )
        total_target_count = len(combined_target_list)
        
        if total_target_count == 0:
            task_logger.warning("所有类别的标准名单均为空。任务将标记为成功，但结果为空。")
            status = "success"
            raise StopIteration("标准名单为空，无需处理。") # 使用 StopIteration 提前跳出
        else:
            task_logger.info(f"标准名单加载完毕 (共 {total_target_count} 人)。")

        # 步骤 1: PDF 解析
        task_logger.info("步骤 1: 正在解析 PDF -> Markdown...")
        md_content = pdf_parser.parse_pdf_to_markdown(str(pdf_path), cfg)
        debug_files['1_intermediate.md'] = md_content
        if not md_content.strip():
            raise Exception("PDF 解析结果为空，无法继续。")

        # 步骤 1+: 核心块提取
        task_logger.info("步骤 1+: 正在提取核心块 (表格/任职情况)...")
        core_blocks = llm_extractor.extract_core_blocks(md_content, cfg)
        if not core_blocks:
            raise Exception("核心块提取失败 (LLM 返回 None)。")
        debug_files['2_core_blocks.json'] = core_blocks.model_dump_json(indent=2, ensure_ascii=False)

        # 步骤 2 & 3: 核对、回退与决策
        task_logger.info("步骤 2/3: 开始核对 P1 (表格)...")
        
        p1_source_text = ""
        if core_blocks.tables:
            p1_source_text = "\n\n---\n\n".join([t.content for t in core_blocks.tables])
            debug_files['3_p1_source_text.md'] = p1_source_text
        else:
            task_logger.warning("P1: 未提取到任何核心表格。")

        # --- 执行 P1 (表格) 核对 ---
        p1_found_names, p1_assessment = _run_verification(p1_source_text, combined_target_list, cfg, task_logger)
        p1_found_count = len(p1_found_names)
        debug_files['3_p1_verification.json'] = json.dumps({
            "found_count": p1_found_count,
            "assessment": p1_assessment.model_dump(),
            "found_names": list(p1_found_names)
        }, indent=2, ensure_ascii=False)

        final_source_text = ""
        source_type = "N/A"
        verification_doubts = p1_assessment.doubts # 记录核对阶段的疑虑
        
        # --- 决策 ---
        if p1_found_count == total_target_count:
            task_logger.info(f"P1 成功: 表格中核对到全部 {total_target_count} 人。")
            final_source_text = p1_source_text
            source_type = "Tables (P1)"
        else:
            task_logger.warning(f"P1 名单不全: 表格中仅核对到 {p1_found_count} / {total_target_count} 人。")
            task_logger.info("P2: 启动回退，核对 '任职情况' 小节...")
            
            p2_source_text = ""
            if core_blocks.employment_section:
                p2_source_text = core_blocks.employment_section.content
                debug_files['3_p2_source_text.md'] = p2_source_text
            else:
                task_logger.warning("P2: 未提取到 '任职情况' 小节。")

            # --- 执行 P2 (任职情况) 核对 ---
            p2_found_names, p2_assessment = _run_verification(p2_source_text, combined_target_list, cfg, task_logger)
            p2_found_count = len(p2_found_names)
            debug_files['3_p2_verification.json'] = json.dumps({
                "found_count": p2_found_count,
                "assessment": p2_assessment.model_dump(),
                "found_names": list(p2_found_names)
            }, indent=2, ensure_ascii=False)
            
            # 最终决策：P1 还是 P2？
            if p2_found_count > p1_found_count:
                task_logger.info(f"P2 优于 P1 (找到 {p2_found_count} 人 > {p1_found_count} 人)。选择 P2。")
                final_source_text = p2_source_text
                source_type = "EmploymentSection (P2)"
                verification_doubts = p2_assessment.doubts # 替换为P2的核对疑虑
            else:
                task_logger.info(f"P1 优于或等于 P2 (找到 {p1_found_count} 人 >= {p2_found_count} 人)。选择 P1。")
                final_source_text = p1_source_text
                source_type = f"Tables (P1 - Incomplete, {p1_found_count}/{total_target_count})"
                # 保留 P1 的核对疑虑 (已在前面赋值)
                
        if not final_source_text.strip():
             raise Exception(f"P1 和 P2 均未找到可用文本或未找到任何姓名。来源: {source_type}")

        # 步骤 4: 执行排序
        task_logger.info(f"步骤 4: 最终结果来源: {source_type}。开始执行排序...")
        final_results, final_found_count = _run_ranking(
            final_source_text, 
            target_lists, 
            cfg, 
            task_logger
        )
        
        # 步骤 5: 确定状态并保存
        task_logger.info("步骤 5: 正在确定最终状态...")
        
        status = "success" # 默认为成功
        if not final_results:
            task_logger.warning("最终无任何排序结果。")
            if total_target_count > 0:
                status = "failed" # 有名单，但没结果

        # 检查是否需要人工审查
        needs_review = False
        
        # 1. 检查核对阶段的疑虑
        if verification_doubts:
             needs_review = True
             task_logger.warning(f"[Verifier] 核对阶段发现疑虑，标记审查: {verification_doubts}")

        for category, result in final_results.items():
            # 2. 检查排序阶段的疑虑 (rank: -1 会自动导致 Medium/Low 和 doubt)
            if result.assessment.confidence_level != "High" or result.assessment.doubts:
                needs_review = True
                task_logger.warning(f"[{category}] 排序阶段需要审查 (置信度: {result.assessment.confidence_level}, 疑虑: {result.assessment.doubts})")
            
            # 3. 将核对阶段的疑虑附加到排序结果中，以便审查
            if verification_doubts:
                # 避免重复添加
                new_doubts = [f"[Verifier Doubt] {d}" for d in verification_doubts if f"[Verifier Doubt] {d}" not in result.assessment.doubts and d not in result.assessment.doubts]
                result.assessment.doubts.extend(new_doubts)

            # 保存最终结果 (只保存被找到且排名的人)
            # 只保存 rank >= 0 的人到 CSV
            ranked_persons_only = [p for p in result.persons if p.rank >= 0]
            save_results_csv(task_id, category, ranked_persons_only)
            
            # 保存 debug JSON (保存完整结果，包括 rank: -1)
            debug_files[f'4_{category.lower()}_extraction.json'] = result.model_dump_json(indent=2, ensure_ascii=False)
        
        if needs_review:
            status = "review"
        
        # 4. 额外检查：如果核对是完整的，但排序是不完整的，也需要审查
        if (p1_found_count == total_target_count) and (final_found_count < total_target_count) and (status == "success"):
            status = "review"
            task_logger.warning(f"状态降级: P1 核对完整，但排序不完整 ({final_found_count}/{total_target_count})。")
        if status == "success":
             task_logger.info("任务状态: success (全部高置信度且完整)")
    
    except StopIteration as e: # 用于处理 "标准名单为空" 的情况
        task_logger.info(f"任务提前终止: {e}")
        # 状态已在抛出前设置为 "success"

    except Exception as e:
        status = "failed"
        task_logger.error(f"任务 {task_id} 遭遇致命错误: {e}", exc_info=True)
        
    finally:
        # 步骤 6: 保存日志文件
        task_logger.info(f"=== 任务 {task_id} 结束，最终状态: {status} ===")
        log_content = log_stream.getvalue()
        debug_files[f'5_{task_id}.log'] = log_content
        
        save_debug_files(task_id, status, debug_files)
        
        # 清理日志句柄
        log_stream.close()
        task_logger.removeHandler(stream_handler)
        task_logger.removeHandler(console_handler)

    return status