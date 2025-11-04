import requests
import json
from .settings import Settings
from .schemas import CategoryExtractionResult
from typing import Literal, Optional

def _get_system_prompt(category: Literal["Directors", "Supervisors", "SeniorManagement"]) -> str:
    """
    根据客户需求（设计草案.md）生成分类提示词。
    """
    base_prompt = (
        "你是一个专业的年报分析助手。你的任务是严格按照用户提供的 Markdown 文本内容，"
        "按出现的先后顺序，提取人员信息。\n"
        "你必须严格遵守排序，原文中先出现的人，rank就必须靠前。\n"
        "你必须调用 `save_extraction` 工具，并提供提取的列表和你的置信度评估。\n"
        "如果原文中没有找到表格，请尝试从'任职情况'相关的文本中提取。"
    )
    
    if category == "Directors":
        return base_prompt + (
            "\n**提取目标：仅提取所有董事**。\n"
            "**分类规则：** 带‘董事’两个字的人员（例如：董事长, 副董事长, 董事, 独立董事）都是董事。\n"
            "**关键例外：** ‘董事会秘书’ **不**属于董事，请忽略。"
        )
    
    if category == "Supervisors":
        return base_prompt + (
            "\n**提取目标：仅提取所有监事**。\n"
            "**分类规则：** 带‘监事’两个字的人员（例如：监事会主席, 监事）都是监事。"
        )
        
    if category == "SeniorManagement":
        return base_prompt + (
            "\n**提取目标：仅提取所有高级管理人员**。\n"
            "**分类规则：** **不属于**董事和监事的**其他所有高管**都属于高级管理人员。\n"
            "**关键例外：** ‘董事会秘书’ **必须**被归类为高级管理人员。\n"
            "**常见职务：** 总经理, 副总经理, 财务总监, 董事会秘书, 总工程师等。"
        )
    
    # 这是一个兜底，理论上不会被触发
    raise ValueError(f"未知的分类: {category}")


def extract_category(
    markdown_content: str, 
    category: Literal["Directors", "Supervisors", "SeniorManagement"], 
    settings: Settings
) -> Optional[CategoryExtractionResult]:
    """
    调用 LLM API，根据指定分类提取人员信息。
    """
    
    api_url = f"{settings.API_BASE_URL.rstrip('/')}/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.API_KEY}"
    }
    
    # 1. 获取 Pydantic 模型的 JSON Schema
    tools_schema = CategoryExtractionResult.model_json_schema()
    
    # 2. 定义工具
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
    
    # 3. 构造请求数据
    system_prompt = _get_system_prompt(category)
    user_prompt = f"请从以下文本中提取所需信息：\n\n---START OF TEXT---\n{markdown_content}\n---END OF TEXT---"

    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "tools": tools_payload,
        # 强制模型必须调用这个工具
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
            
            # 提取模型生成的JSON字符串
            arguments_json_str = tool_calls[0]['function']['arguments']
            
            # 使用 Pydantic 进行严格的验证和解析
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