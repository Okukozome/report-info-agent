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
        
        # --- 推荐的参数组合 ---
        "visualize": False,
        "useTableRecognition": True,
        "useChartRecognition": True,
        "useWiredTableCellsTransToHtml": True,
        "useWirelessTableCellsTransToHtml": True,
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
        "你是一个专业的年报目录分析助手。\n"
        "你的任务是严格从用户提供的【目录】文本中，找出专门介绍【董事、监事、高级管理人员】（简称DGS）情况的那个核心章节。\n"
        "你需要提取该章节的【起始页码】、【结束页码】和完整的【章节标题】。\n"
        "规则：\n"
        "1. 搜索目标是专门介绍DGS情况的章节。根据《年报准则》，这个章节的名称可能存在多种变体。\n"
        "2. **优先寻找**最标准的名称，例如：'董事、监事、高级管理人员和员工情况' 或简化版 '董事、监事和高级管理人员'。\n"
        "3. 如果找不到上述标准名称，**其次寻找** '公司治理' 或 '公司治理结构和运作情况' 章节，因为DGS信息也常包含在这些章节中。\n"
        "4. **注意**：不要选择 '董事会报告'、'重要事项' 或 '人力资源情况'/'员工情况'。这些章节虽然可能间接相关，但不是我们要找的那个专门披露DGS个人情况的核心章节。\n"
        "5. 章节标题必须是目录中的原文。\n"
        "6. 页码必须是目录中标记的数字。\n"
        "7. 如果目录中没有符合上述目标的章节，或输入内容与目录完全无关，必须返回 -1, -1, ''。\n"
        "8. 你必须调用 `save_toc_analysis` 工具返回结果。"
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
    settings: Settings
) -> PageVerificationResult:
    """
    AI 步骤 2: 验证章节首页
    """
    system_prompt = (
        "你是一个章节验证助手。\n"
        "你的任务是判断所给的【页面内容】是否为目标【章节标题】的【第一页】。\n"
        "判据：【第一页】必须包含与【章节标题】高度匹配的标题文本。\n"
        "返回状态：\n"
        "1. 'match': 明确找到了标题，这是第一页。\n"
        "2. 'too_early': 还没到，内容是上一章的，应 '下一页'。\n"
        "3. 'too_late': 已经翻过了，内容是DGS章的非首页，应 '上一页'。\n"
        "4. 'fail': 内容完全无关（例如附录、空白页），无法判断。\n"
        "你必须调用 `save_page_verification` 工具返回结果。"
    )
    
    user_prompt = (
        f"【目标章节标题】: \"{target_title}\"\n\n"
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