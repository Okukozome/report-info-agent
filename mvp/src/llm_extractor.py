import requests
import json
from .settings import Settings
from .schemas import (
    CategoryExtractionResult, 
    CoreBlocksExtractionResult, 
    ConfidenceAssessment,
    ExtractedTable,
    ExtractedTextSection
)
from typing import Literal, Optional

def _get_system_prompt(category: Literal["Directors", "Supervisors", "SeniorManagement"]) -> str:
    """
    根据客户需求（设计草案.md）生成分类提示词。
    """
    base_prompt = (
        "你是一个专业的年报分析助手。你的任务是严格按照用户提供的文本内容，"
        "按出现的先后顺序，提取人员信息。\n"
        "你必须严格遵守排序，原文中先出现的人，rank就必须靠前。\n"
        "你必须调用 `save_extraction` 工具，并提供提取的列表和你的置信度评估。\n"
    )
    
    if category == "Directors":
        return base_prompt + (
            "\n**提取目标：仅提取所有董事**。\n"
            "**分类规则：** 带‘董事’两个字的人员（例如：董事长, 副董事长, 董事, 独立董事）都是董事。\n"
            "**关键例外：** ‘董事会秘书’ **不**属于董事，请忽略。\n"
            "**特别注意1：** ‘离职’状态的董事也必须被提取出来。\n"
            "**特别注意2：** 不存在同名董事的可能性，如果出现多职位同名则是兼任情况，请使用顿号隔开。\n"
        )
    
    if category == "Supervisors":
        return base_prompt + (
            "\n**提取目标：仅提取所有监事**。\n"
            "**分类规则：** 带‘监事’两个字的人员（例如：监事会主席, 监事）都是监事。\n"
            "**特别注意1：** ‘离职’状态的监事也必须被提取出来。\n"
            "**特别注意2：** 不存在同名监事的可能性，如果出现多职位同名则是兼任情况，请使用顿号隔开。\n"
        )
        
    if category == "SeniorManagement":
        return base_prompt + (
            "\n**提取目标：仅提取所有高级管理人员**。\n"
            "**分类规则：** **不属于**董事和监事的**其他所有高管**都属于高级管理人员。\n"
            "**关键例外：** ‘董事会秘书’ **必须**被归类为高级管理人员。\n"
            "**常见职务：** 总经理, 副总经理, 财务总监, 董事会秘书, 总工程师等。"
            "**特别注意1：** ‘离职’状态的高管也必须被提取出来。\n"
            "**特别注意2：** 高级管理人员也可能由董事兼任，但不可能由监事兼任。\n"
            "**特别注意3：** 不存在同名高级管理人员的可能性，如果出现多职位同名则是兼任情况，请使用顿号隔开。\n"
        )
    
    raise ValueError(f"未知的分类: {category}")

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
        "   - `content`：表格可能是HTML元素，提取时应保持原始内容。\n"
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
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "tools": tools_payload,
        "tool_choice": {"type": "function", "function": {"name": "save_core_blocks"}}
    }
    
    try:
        print(f"  [LLM Extractor] 正在向 LLM API 发送请求 (提取核心块)...")
        response = requests.post(api_url, headers=headers, json=data, timeout=120)
        
        if response.status_code == 200:
            print(f"  [LLM Extractor] 核心块提取 API 请求成功。")
            result = response.json()
            
            tool_calls = result.get('choices', [{}])[0].get('message', {}).get('tool_calls')
            
            if not tool_calls:
                print("错误：模型没有按预期调用 'save_core_blocks' 工具。")
                return None
            
            arguments_json_str = tool_calls[0]['function']['arguments']
            validated_result = CoreBlocksExtractionResult.model_validate_json(arguments_json_str)
            
            print(f"  [LLM Extractor] 核心块 Pydantic 格式验证通过。")
            return validated_result
        
        else:
            print(f"API请求失败，状态码: {response.status_code}")
            print(f"错误信息: {response.text}")
            return None
            
    except Exception as e:
        print(f"发生异常: {e}")
        return None

def extract_category(
    markdown_content: str, 
    category: Literal["Directors", "Supervisors", "SeniorManagement"], 
    settings: Settings) -> Optional[CategoryExtractionResult]:
    """
    调用 LLM API，根据指定分类提取人员信息。
    """
    
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
                "description": f"保存提取到的 {category} 信息及评估",
                "parameters": tools_schema
            }
        }
    ]
    
    system_prompt = _get_system_prompt(category)
    user_prompt = f"请从以下文本中提取所需信息：\n\n---START OF TEXT---\n{markdown_content}\n---END OF TEXT---"

    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "tools": tools_payload,
        "tool_choice": {"type": "function", "function": {"name": "save_extraction"}}
    }
    
    try:
        print(f"  [LLM Extractor] 正在向 LLM API 发送请求 (分类: {category})...")
        response = requests.post(api_url, headers=headers, json=data, timeout=120)
        
        if response.status_code == 200:
            print(f"  [LLM Extractor] API 请求成功。")
            result = response.json()
            
            tool_calls = result.get('choices', [{}])[0].get('message', {}).get('tool_calls')
            
            if not tool_calls:
                print("错误：模型没有按预期调用工具。")
                return None
            
            arguments_json_str = tool_calls[0]['function']['arguments']
            validated_result = CategoryExtractionResult.model_validate_json(arguments_json_str)
            
            print(f"  [LLM Extractor] Pydantic 格式验证通过。")
            return validated_result
        
        else:
            print(f"API请求失败，状态码: {response.status_code}")
            print(f"错误信息: {response.text}")
            return None
            
    except Exception as e:
        print(f"发生异常: {e}")
        return None