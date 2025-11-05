# pipeline/core/llm_extractor.py
import requests
import json
import logging
from core.settings import Settings
from core.schemas import (
    CategoryExtractionResult, 
    CoreBlocksExtractionResult,
    NameVerificationResult, 
    ConfidenceAssessment
)
from typing import Literal, Optional, List

logger = logging.getLogger(__name__)

# --- 核心块提取 ---
def _get_core_block_system_prompt() -> str:
    """
    生成用于提取核心块（表格和文本）的系统提示词。
    """
    return (
        "你是一个专业的年报分析助手。你的任务是从用户提供的完整Markdown章节中，提取出两个最关键的部分：\n"
        "1. 【核心表格】：所有涉及'董事、监事和高级管理人员'的表格。\n"
        "2. 【任职情况小节】：标题为'任职情况'的完整文字段落。\n"
        "规则：\n"
        "A. 你必须调用 `save_core_blocks` 工具返回结果。\n"
        "B. **表格提取 (tables)**：\n"
        "   - 必须返回一个 `ExtractedTable` 对象列表。\n"
        "   - `description`：必须提取表格的标题或表名。若无标题，请根据内容生成一个（例如：'董事基本情况表'）。\n"
        "   - `content`：表格可能是HTML元素，除非存在跨页需要合并，否则提取时必须保持原始内容。\n"
        "   - **跨页合并**：如果Markdown中连续的表格是跨页的，必须将它们的 `content` 合并为**一个**字符串，并存入**一个** `ExtractedTable` 对象中。\n"
        "C. **任职情况小节 (employment_section)**：\n"
        "   - 如果找到，必须返回一个 `ExtractedTextSection` 对象。\n"
        "   - `title`：必须是准确的小节标题（例如 '任职情况'）。\n"
        "   - `content`：该小节的完整文字内容。\n"
        "D. 如果找不到表格，`tables` 列表必须返回空列表 `[]`。\n"
        "E. 如果找不到'任职情况'小节，`employment_section` 字段必须返回 `null`。"
    )

def extract_core_blocks(
    markdown_content: str, 
    settings: Settings) -> Optional[CoreBlocksExtractionResult]:
    """
    调用 LLM API，从完整 Markdown 中提取核心表格和'任职情况'文本。
    """
    api_url = f"{settings.API_BASE_URL.rstrip('/')}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.API_KEY}"
    }
    
    tools_schema = CoreBlocksExtractionResult.model_json_schema()
    
    tools_payload = [
        {
            "type": "function",
            "function": {
                "name": "save_core_blocks",
                "description": "保存提取到的核心表格和任职情况文本",
                "parameters": tools_schema
            }
        }
    ]
    
    system_prompt = _get_core_block_system_prompt()
    user_prompt = f"请从以下文本中提取所需的核心块：\n\n---START OF TEXT---\n{markdown_content}\n---END OF TEXT---"

    data = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "tools": tools_payload,
        "tool_choice": {"type": "function", "function": {"name": "save_core_blocks"}}
    }
    
    try:
        logger.info(f"  [LLM Extractor] 正在向 LLM API 发送请求 (提取核心块)...")
        response = requests.post(api_url, headers=headers, json=data, timeout=settings.LLM_TIMEOUT)
        
        if response.status_code == 200:
            logger.info(f"  [LLM Extractor] 核心块提取 API 请求成功。")
            result = response.json()
            
            tool_calls = result.get('choices', [{}])[0].get('message', {}).get('tool_calls')
            
            if not tool_calls:
                logger.error("错误：模型没有按预期调用 'save_core_blocks' 工具。")
                return None
            
            arguments_json_str = tool_calls[0]['function']['arguments']
            validated_result = CoreBlocksExtractionResult.model_validate_json(arguments_json_str)
            
            logger.info(f"  [LLM Extractor] 核心块 Pydantic 格式验证通过。")
            return validated_result
        
        else:
            logger.error(f"API请求失败，状态码: {response.status_code}")
            logger.error(f"错误信息: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"发生异常: {e}")
        return None

# --- 姓名核对 (Verification) ---

def _get_verification_system_prompt(target_names: List[str]) -> str:
    """
    生成用于核对姓名的系统提示词。
    """
    names_list_str = "\n".join([f"- {name}" for name in target_names])
    if not names_list_str:
        names_list_str = "(无)"

    return (
        "你是一个专业的年报审查助手。你的**唯一任务**是审查下方提供的【原文】，"
        "判断【标准名单】中的姓名**是否存在**于【原文】中。\n\n"
        f"**标准名单 (Target List):**\n{names_list_str}\n\n"
        "**核心规则：**\n"
        "1. 你**必须**严格按照【标准名单】进行核对。\n"
        "2. 你的任务**不是**分类。你的任务**仅仅是核对**。\n"
        "3. **格式容错：** 你必须能处理原文中的微小格式差异或OCR错误。例如：\n"
        "   - 空格/TAB: 原文中的 '张 三' 或 '张  三' 应匹配名单中的 '张三'。\n"
        "   - 常见OCR错字: 你可以适度容错，例如原文 '张兰'，如果上下文明显指向 '张三'，应匹配 '张三'。\n"
        "4. 你必须调用 `save_verification` 工具返回结果。\n"
        "5. `found_names` 列表必须只包含**在原文中被找到**的、且**属于【标准名单】**的姓名。\n"
        "6. 如果【标准名单】中的某个人在【原文】中**没有**被找到，则 `found_names` 列表中不应包含此人。\n"
        "7. 如果你对匹配(例如OCR错字)有任何不确定性，必须在 `doubts` 字段中说明。"
    )

def verify_name_presence(
    markdown_content: str, 
    target_names: List[str],
    settings: Settings
) -> Optional[NameVerificationResult]:
    """
    调用 LLM API，核对标准名单中的姓名是否在原文中存在。
    """
    
    if not target_names:
        logger.warning("  [LLM Verifier] 目标名单为空，跳过核对。")
        return NameVerificationResult(
            found_names=[],
            assessment=ConfidenceAssessment(
                confidence_level="High", 
                doubts=["标准名单为空，未执行核对。"]
            )
        )

    if not markdown_content.strip():
        logger.warning("  [LLM Verifier] 原文内容为空，跳过核对。")
        return NameVerificationResult(
            found_names=[],
            assessment=ConfidenceAssessment(
                confidence_level="High", 
                doubts=["原文内容为空，未执行核对。"]
            )
        )

    api_url = f"{settings.API_BASE_URL.rstrip('/')}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.API_KEY}"
    }
    
    tools_schema = NameVerificationResult.model_json_schema()
    tools_payload = [{
        "type": "function",
        "function": {
            "name": "save_verification",
            "description": "保存核对过的姓名列表",
            "parameters": tools_schema
        }
    }]
    
    system_prompt = _get_verification_system_prompt(target_names)
    user_prompt = f"请从以下文本中核对【标准名单】中的姓名：\n\n---START OF TEXT---\n{markdown_content}\n---END OF TEXT---"

    data = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "tools": tools_payload,
        "tool_choice": {"type": "function", "function": {"name": "save_verification"}}
    }
    
    try:
        logger.info(f"  [LLM Verifier] 正在向 LLM API 发送请求 (核对 {len(target_names)} 人)...")
        response = requests.post(api_url, headers=headers, json=data, timeout=settings.LLM_TIMEOUT)
        
        if response.status_code == 200:
            logger.info(f"  [LLM Verifier] API 请求成功。")
            result = response.json()
            tool_calls = result.get('choices', [{}])[0].get('message', {}).get('tool_calls')
            
            if not tool_calls:
                logger.error("错误：[Verifier] 模型没有按预期调用 'save_verification' 工具。")
                return None
            
            arguments_json_str = tool_calls[0]['function']['arguments']
            validated_result = NameVerificationResult.model_validate_json(arguments_json_str)
            
            logger.info(f"  [LLM Verifier] Pydantic 格式验证通过。")
            
            # 最终校验：确保模型没有返回名单之外的人
            validated_names = {name for name in validated_result.found_names}
            target_names_set = set(target_names)
            invalid_names = validated_names - target_names_set
            if invalid_names:
                logger.warning(f"!!! [Verifier] 模型幻觉：返回了名单之外的姓名: {invalid_names}")
                validated_result.found_names = [name for name in validated_result.found_names if name in target_names_set]
                validated_result.assessment.doubts.append(f"模型产生了幻觉，返回了名单外的姓名: {invalid_names}，已自动过滤。")
                validated_result.assessment.confidence_level = "Medium"

            return validated_result
        
        else:
            logger.error(f"[Verifier] API请求失败，状态码: {response.status_code}")
            logger.error(f"[Verifier] 错误信息: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"[Verifier] 发生异常: {e}")
        return None

def _get_category_specific_rules(
    category: Literal["Directors", "Supervisors", "SeniorManagement"]
) -> str:
    """返回类别特定的例外规则"""
    rules = {
        "Directors": "- 除了董事会秘书，含“董事”二字的都是董事\n- 董事会秘书不是董事，不参与排序，设 `rank: 0`",
        "SeniorManagement": "- 允许董事兼任高管，但不默认董事都属于高管，以原文为主\n- 监事不可兼任高管",
        "Supervisors": "- 含“监事”二字的都是监事"
    }
    return rules.get(category, "")

def _get_ranking_system_prompt(
    category: Literal["Directors", "Supervisors", "SeniorManagement"],
    target_names: List[str]
) -> str:
    
    names_list = "、".join(target_names) if target_names else "无"
    category_rules = _get_category_specific_rules(category)

    return f"""
[!!!] 注意：你的任务是对{category}在**原文**中的出现顺序进行排序，**而不是依据名单中出现的先后顺序进行排序**。

**处理规则：**
排序依据：rank=1:原文中首个出现的名单内人员，rank=2:第二个出现的名单内人员，以此类推
身份判据：
{category_rules}
- 离任人员应正常纳入排序
如果名单中的某个姓名未找到：rank 设为 -1，role 设为 'N/A'

输出要求：
- 必须包含名单中所有人员，不多不少不重复，同名多身份为兼任情况。
- role 字段填写原文中的完整职务
- 如有 rank -1 的情况，在 doubts 中说明

参考{category}名单（乱序）：
{names_list}
"""

def rank_names_from_text(
    markdown_content: str, 
    category: Literal["Directors", "Supervisors", "SeniorManagement"], 
    target_names: List[str],
    settings: Settings
) -> Optional[CategoryExtractionResult]:
    
    if not target_names:
        logger.warning(f"  [LLM Ranker] 类别 {category} 的标准名单为空，跳过提取。")
        return CategoryExtractionResult(
            category=category,
            persons=[],
            assessment=ConfidenceAssessment(
                confidence_level="High",
                doubts=["标准名单为空，未执行提取。"]
            )
        )

    api_url = f"{settings.API_BASE_URL.rstrip('/')}/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.API_KEY}"
    }
    
    tools_schema = CategoryExtractionResult.model_json_schema()
    
    tools_payload = [
        {
            "type": "function",
            "function": {
                "name": "save_extraction",
                "description": f"保存提取到的 {category} 排序信息及评估",
                "parameters": tools_schema
            }
        }
    ]
    
    system_prompt = _get_ranking_system_prompt(category, target_names)
    user_prompt = f"请从以下文本中找到并排序 【待排序名单】 中的人员：\n\n---START OF TEXT---\n{markdown_content}\n---END OF TEXT---"

    data = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "tools": tools_payload,
        "tool_choice": {"type": "function", "function": {"name": "save_extraction"}}
    }
    
    try:
        logger.info(f"  [LLM Ranker] -----------------------------------------------")
        logger.info(f"  [LLM Ranker] 正在向 LLM API 发送请求 (排序: {category})...")
        response = requests.post(api_url, headers=headers, json=data, timeout=settings.LLM_TIMEOUT)
        
        if response.status_code == 200:
            logger.info(f"  [LLM Ranker] API 请求成功 (排序: {category})。")
            result = response.json()
            
            tool_calls = result.get('choices', [{}])[0].get('message', {}).get('tool_calls')
            
            if not tool_calls:
                logger.error(f"错误：模型没有按预期调用 'save_extraction' 工具 ({category})。")
                return None
            
            arguments_json_str = tool_calls[0]['function']['arguments']
            validated_result = CategoryExtractionResult.model_validate_json(arguments_json_str)
            
            logger.info(f"  [LLM Ranker] Pydantic 格式验证通过 ({category})。")
            
            # --- 后处理和校验逻辑 ---
            validated_names_set = {p.name for p in validated_result.persons}
            target_names_set = set(target_names)
            
            # 1. 检查幻觉 (返回了名单之外的人)
            hallucinated_names = validated_names_set - target_names_set
            if hallucinated_names:
                logger.warning(f"!!! [Ranker] 模型幻觉：返回了名单之外的姓名: {hallucinated_names}")
                # 过滤掉幻觉姓名
                validated_result.persons = [p for p in validated_result.persons if p.name in target_names_set]
                validated_result.assessment.doubts.append(f"模型产生了幻觉，返回了名单外的姓名: {hallucinated_names}，已自动过滤。")
                validated_result.assessment.confidence_level = "Medium"
                # 更新 validated_names_set
                validated_names_set = {p.name for p in validated_result.persons}

            # 2. 检查遗漏 (模型未按要求返回足额名单，这是兜底)
            if len(validated_result.persons) != len(target_names_set):
                logger.warning(f"!!! [Ranker] 模型未遵循指令：应返回 {len(target_names_set)} 人，实际返回 {len(validated_result.persons)} 人。")
                missing_names_in_output = target_names_set - validated_names_set
                if missing_names_in_output:
                     logger.warning(f"!!! [Ranker] 模型彻底遗漏了: {missing_names_in_output}")
                     # 选择在这里手动补全 rank = -1 的人，以增强鲁棒性
                     for missing_name in missing_names_in_output:
                         validated_result.persons.append(
                             schemas.Person(rank=-1, name=missing_name, role="N/A")
                         )
                     validated_result.assessment.doubts.append(f"模型未返回足额名单，已自动补全 {len(missing_names_in_output)} 个 'rank: -1' 记录。")
                     validated_result.assessment.confidence_level = "Medium"
                else:
                     # 这种情况理论上不该发生（人数不匹配但名字都对上了）
                     validated_result.assessment.doubts.append(f"模型返回人数 ({len(validated_result.persons)}) 与目标 ({len(target_names_set)}) 不匹配，但姓名集合匹配。")
                     validated_result.assessment.confidence_level = "Medium"


            # 检查并记录 rank = -1 的人 (这是标准流程)
            not_found_persons = [p.name for p in validated_result.persons if p.rank == -1]
            if not_found_persons:
                logger.info(f"  [LLM Ranker] 模型报告 {len(not_found_persons)} 人未找到 (rank: -1): {not_found_persons}")
                # 检查 doubt 是否已包含此信息
                doubt_msg = f"名单中 {len(not_found_persons)} 人在原文中未找到 (rank: -1)"
                if not any(doubt_msg in d for d in validated_result.assessment.doubts):
                    validated_result.assessment.doubts.append(f"{doubt_msg}: {not_found_persons}")
                if validated_result.assessment.confidence_level == "High":
                    validated_result.assessment.confidence_level = "Medium"

            return validated_result
        
        else:
            logger.error(f"API请求失败，状态码: {response.status_code} ({category})")
            logger.error(f"错误信息: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"发生异常 ({category}): {e}")
        return None