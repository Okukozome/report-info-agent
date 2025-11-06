import requests
import json
import base64
import logging
from typing import List, Optional, Dict, Any, Type

from pydantic import BaseModel

# 假定 settings.py 在父级目录的 core/ 中
from .settings import Settings
from .schemas import TocAnalysisResult, PageVerificationResult

logger = logging.getLogger("ApiClient")

# --- 1. PP-StructureV3 客户端 ---

def call_pp_structure_api(
    pdf_bytes: bytes, 
    settings: Settings
) -> List[str]:
    """
    调用 PP-StructureV3 API，将 PDF 字节（可以是多页）转换为 Markdown 列表。
    使用优化后的参数组合。
    """
    
    file_data_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    headers = {
        "Authorization": f"token {settings.PP_TOKEN}",
        "Content-Type": "application/json"
    }

    # 使用推荐的优化参数组合
    payload = {
        "file": file_data_b64, 
        "fileType": 0, # 0 = PDF
        
        # 推荐的参数组合
        "visualize": False,
        "useTableRecognition": True,
        "useChartRecognition": True,
        "useWiredTableCellsTransToHtml": True,
        "useWirelessTableCellsTransToHtml": True,
        "useRegionDetection": True,
        "textDetThresh": 0.1,
        "useOcrResultsWithTableCells": True, # 确保表格识别同时包含 OCR 结果
        "useDocOrientationClassify": False, # 关闭旋转矫正
        "useDocUnwarping": False, # 关闭文本扭曲矫正
        "useTextlineOrientation": False, # 关闭文本行方向矫正
        "useTableOrientationClassify": False, # 关闭表格方向矫正
    }

    logger.debug(f"向 PP-StructureV3 API ({settings.PP_API_URL}) 发送请求...")
    
    try:
        response = requests.post(
            settings.PP_API_URL, 
            json=payload, 
            headers=headers,
            timeout=settings.API_TIMEOUT
        )
        response.raise_for_status() # 4xx, 5xx 抛出异常
        
        result = response.json()

        if result.get("errorCode") != 0:
            raise Exception(f"API返回错误: {result.get('errorMsg', '未知错误')}")
            
        layout_results = result.get("result", {}).get("layoutParsingResults", [])
        if not layout_results:
            # 即使 API 成功返回，如果解析结果为空，也认为是失败
            raise Exception("API 未返回有效的 'layoutParsingResults' (可能内容无法识别)")

        # 提取每一页的 markdown
        markdown_pages = [
            page_res.get("markdown", {}).get("text", "") 
            for page_res in layout_results
        ]
        
        logger.debug(f"PP-StructureV3 成功返回 {len(markdown_pages)} 页内容。")
        return markdown_pages

    except requests.exceptions.RequestException as e:
        logger.error(f"PP-StructureV3 API 请求失败: {e}")
        raise
    except Exception as e:
        logger.error(f"PP-StructureV3 响应处理失败: {e}")
        raise

# --- 2. LLM (Tool-Calling) 客户端 ---

def _call_llm_api_with_tools(
    system_prompt: str,
    user_prompt: str,
    schema_cls: Type[BaseModel],
    tool_name: str,
    settings: Settings
) -> BaseModel:
    """
    封装的 LLM Tool-Calling API
    """
    
    api_url = f"{settings.API_BASE_URL.rstrip('/')}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.API_KEY}"
    }
    
    tools_payload = [{
        "type": "function",
        "function": {
            "name": tool_name,
            "description": f"保存 {schema_cls.__name__} 的提取结果",
            "parameters": schema_cls.model_json_schema()
        }
    }]
    
    data = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "tools": tools_payload,
        "tool_choice": {"type": "function", "function": {"name": tool_name}}
    }
    
    logger.debug(f"向 LLM API ({settings.API_BASE_URL}) 发送请求 (Tool: {tool_name})...")

    try:
        response = requests.post(
            api_url, 
            headers=headers, 
            json=data, 
            timeout=settings.API_TIMEOUT
        )
        response.raise_for_status()
        
        result = response.json()
        
        tool_calls = result.get('choices', [{}])[0].get('message', {}).get('tool_calls')
        if not tool_calls:
            raise Exception("模型没有按预期调用工具")
            
        arguments_json_str = tool_calls[0]['function']['arguments']
        
        # 验证并返回 Pydantic 实例
        validated_result = schema_cls.model_validate_json(arguments_json_str)
        logger.debug(f"LLM API Tool-Calling 验证成功。")
        return validated_result

    except requests.exceptions.RequestException as e:
        logger.error(f"LLM API 请求失败: {e}")
        raise
    except Exception as e:
        logger.error(f"LLM 响应处理或验证失败: {e}")
        raise

# --- 3. 封装的 AI 步骤 ---

def find_dgs_chapter_in_toc(
    toc_markdown: str, 
    settings: Settings
) -> TocAnalysisResult:
    """
    AI 步骤 1: 分析目录
    """
    system_prompt = (
"""
你是一个年报目录分析助手。
请从【目录】文本中，找出介绍【董事、监事、高级管理人员】（DGS）的章节。并提取其【起始页码】、【结束页码】（下一章页码起始-1）和【章节标题】。

主要线索（按优先级排序）：
1. '董事、监事、高级管理人员'
2. '公司治理结构'
3. '人力资源情况'

如果未找到确信的章节，返回 -1, -1, ''。
调用 `save_toc_analysis` 工具返回结果。
"""
    )
    user_prompt = f"请分析以下目录内容，提取DGS章节信息：\n\n--- 目录开始 ---\n{toc_markdown}\n--- 目录结束 ---"
    
    result = _call_llm_api_with_tools(
        system_prompt, 
        user_prompt, 
        TocAnalysisResult, 
        "save_toc_analysis", 
        settings
    )
    return result

def verify_chapter_start_page(
    page_markdown: str, 
    target_title: str, 
    settings: Settings,
    verification_history: List[str]
) -> PageVerificationResult:
    """
    AI 步骤 2: 验证章节首页
    """
    system_prompt = (
"""
你是一个章节验证助手。
请判断【页面内容】是否是【目标章节标题】的【起始页】。

调用 `save_page_verification` 工具返回你的判断，状态必须是以下之一：
- 'match': 页面以此标题为开头，是该章节的第一页。
- 'too_early': 页面内容可能仍在目标章节之前。
- 'too_late': 页面内容已在目标章节第一页之后。
- 'fail': 页面内容难以分析和得出结论，例如乱码、空白等。
"""
    )
    
    history_prompt_section = ""
    if verification_history:
        history_prompt_section = (
            "--- 历史尝试开始 ---\n"
            "你之前的尝试和判断如下：\n" +
            "\n".join(verification_history) +
            "\n--- 历史尝试结束 ---\n\n"
        )

    user_prompt = (
        f"【目标章节标题】: \"{target_title}\"\n\n"
        f"{history_prompt_section}"
        f"--- 页面内容开始 ---\n{page_markdown}\n--- 页面内容结束 ---"
    )

    result = _call_llm_api_with_tools(
        system_prompt,
        user_prompt,
        PageVerificationResult,
        "save_page_verification",
        settings
    )
    return result