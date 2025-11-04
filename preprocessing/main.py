import os
import logging
from pathlib import Path
import fitz  # PyMuPDF
# 移除了 openai 库
import requests # 引入 requests
from dotenv import load_dotenv
from tqdm import tqdm
import json
import re
from pydantic import BaseModel, Field
from typing import Optional

# --- 常量配置 ---
INPUT_DIR = Path("raw")
OUTPUT_DIR = Path("processed")
MANUAL_DIR = Path("manual_processing")
LOG_FILE = MANUAL_DIR / "failed_files.log"

# 配置LLM解析目录时读取的PDF最大页数
CATALOG_PAGE_LIMIT = 15

# --- 日志配置 ---
# (日志配置保持不变)
MANUAL_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger = logging.getLogger("PREPROCESSING")
logger.setLevel(logging.INFO)
logger.addHandler(console_handler)


# --- API 客户端初始化 (改为 Requests) ---
try:
    load_dotenv()
    # 严格按照 .env 文件读取
    API_BASE_URL = os.getenv("API_BASE_URL")
    API_KEY = os.getenv("API_KEY")
    
    if not API_BASE_URL or not API_KEY:
        raise ValueError("API_BASE_URL 和 API_KEY 未在 .env 文件中设置")
    
    # 遵循 test_schema_in_chat.py 的 URL 结构
    API_URL = f"{API_BASE_URL}/v1/chat/completions"
    HEADERS = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

except Exception as e:
    logger.error(f"API 客户端初始化失败: {e}")
    exit(1)


# --- Pydantic Schemas for LLM Output ---
# (Schema 定义保持不变)
class CatalogResult(BaseModel):
    """LLM解析的目录结果"""
    start_page: Optional[int] = Field(None, description="董监高章节的起始页码")
    end_page: Optional[int] = Field(None, description="董监高章节的结束页码 (即下一个章节的起始页码 - 1)")
    start_title: Optional[str] = Field(None, description="董监高章节的标题")
    next_chapter_title: Optional[str] = Field(None, description="下一个主要章节的标题")
    error: Optional[str] = Field(None, description="如果找不到章节或解析失败，则填写此字段")

class VerificationResult(BaseModel):
    """LLM页面验证结果"""
    is_match: bool = Field(..., description="页面内容是否与预期标题匹配")


def get_pdf_text_by_pages(pdf_doc: fitz.Document, start_page: int, end_page: int) -> str:
    """提取PDF指定页码范围（1-based）的文本"""
    # (此函数不变)
    text = ""
    start_idx = max(0, start_page - 1)
    end_idx = min(len(pdf_doc) - 1, end_page - 1)
    
    for i in range(start_idx, end_idx + 1):
        try:
            page = pdf_doc.load_page(i)
            text += page.get_text("text") + "\n--- (Page Break) ---\n"
        except Exception as e:
            logger.warning(f"无法提取 {pdf_doc.name} 第 {i+1} 页: {e}")
    return text

def parse_catalog_with_llm(catalog_text: str) -> dict:
    """使用LLM解析目录文本 (使用 Requests 和 Pydantic Schema)"""
    if not catalog_text.strip():
        return {"error": "目录文本为空（可能为纯图片PDF或无目录）"}

    system_prompt = """
你是A股年报分析助手。请严格解析以下PDF目录文本，找到“董事、监事、高级管理人员” (董监高) 相关章节。
章节标题可能包含 "董事、监事、高级管理人员和员工情况"、"董事、监事及高级管理人员持股情况" 或类似变体。
请根据解析结果调用 'output_catalog' 函数。
如果成功找到章节，请填充 'start_page', 'end_page', 'start_title', 'next_chapter_title'。
如果找不到“董监高”章节或无法解析，请在 'error' 字段中说明原因。
"""
    tools_schema = CatalogResult.model_json_schema()
    tools_payload = [
        {
            "type": "function",
            "function": {
                "name": "output_catalog",
                "description": "输出解析后的目录信息或错误",
                "parameters": tools_schema
            }
        }
    ]
    
    data = {
        "model": "gpt-4o", # 假设模型
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请解析以下目录：\n\n{catalog_text}"},
        ],
        "tools": tools_payload,
        "tool_choice": {"type": "function", "function": {"name": "output_catalog"}},
        "temperature": 0.0,
    }

    try:
        # 使用 requests.post
        response = requests.post(API_URL, headers=HEADERS, json=data, timeout=60)
        
        if response.status_code != 200:
            raise Exception(f"API请求失败，状态码: {response.status_code}, 详情: {response.text}")

        result = response.json()
        message = result['choices'][0]['message']
        
        if not message.get('tool_calls'):
            raise Exception(f"模型没有按预期调用工具。回复: {message.get('content')}")

        tool_call = message['tool_calls'][0]
        if tool_call['function']['name'] != 'output_catalog':
            raise Exception(f"模型调用了错误的工具: {tool_call['function']['name']}")

        arguments_json_str = tool_call['function']['arguments']
        validated_result = CatalogResult.model_validate_json(arguments_json_str)
        
        return validated_result.model_dump(exclude_none=True)
    
    except Exception as e:
        logger.error(f"LLM 解析目录失败: {e}")
        return {"error": f"LLM API 调用失败: {e}"}

def verify_page_content(pdf_doc: fitz.Document, page_num: int, expected_title: str) -> bool:
    """(关键步骤2) 验证指定页码是否为预期章节的开头 (使用 Requests 和 Pydantic Schema)"""
    try:
        page_text = get_pdf_text_by_pages(pdf_doc, page_num, page_num)
        if not page_text.strip():
            logger.warning(f"验证页 {page_num} 时未提取到文本 (可能为空白页或图片)")
            return False 

        clean_text = re.sub(r"(^\s*\d+\s*$)|(\s+\d+\s*$)", "", page_text, flags=re.MULTILINE)
        page_header = clean_text.strip()[:300]

        system_prompt = f"""
你是A股年报分析助手。请判断以下页面开头文本是否与章节标题 "{expected_title}" 匹配。
页眉、页脚或页码可能会干扰判断，请智能识别。
请调用 'output_verification' 函数并设置 'is_match' (true or false)。
"""
        
        tools_schema = VerificationResult.model_json_schema()
        tools_payload = [
            {
                "type": "function",
                "function": {
                    "name": "output_verification",
                    "description": "输出页面验证结果",
                    "parameters": tools_schema
                }
            }
        ]

        data = {
            "model": "gpt-4o", # 假设模型
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"页面开头文本：\n\n{page_header}"},
            ],
            "tools": tools_payload,
            "tool_choice": {"type": "function", "function": {"name": "output_verification"}},
            "temperature": 0.0,
        }

        # 使用 requests.post
        response = requests.post(API_URL, headers=HEADERS, json=data, timeout=60)

        if response.status_code != 200:
            raise Exception(f"API请求失败，状态码: {response.status_code}, 详情: {response.text}")
        
        result = response.json()
        message = result['choices'][0]['message']

        if not message.get('tool_calls'):
            raise Exception(f"模型没有按预期调用工具。回复: {message.get('content')}")

        tool_call = message['tool_calls'][0]
        arguments_json_str = tool_call['function']['arguments']
        validated_result = VerificationResult.model_validate_json(arguments_json_str)
        
        return validated_result.is_match
    
    except Exception as e:
        logger.error(f"LLM 验证页面 {page_num} 失败: {e}")
        return False

def split_pdf(pdf_doc: fitz.Document, start_page: int, end_page: int, output_path: Path):
    """根据1-based页码分割PDF"""
    # (此函数不变)
    try:
        new_doc = fitz.open()
        new_doc.insert_pdf(pdf_doc, from_page=start_page - 1, to_page=end_page - 1)
        new_doc.save(output_path)
        new_doc.close()
    except Exception as e:
        raise RuntimeError(f"PDF 分割失败: {e}")

def process_file(pdf_path: Path):
    """处理单个PDF文件的完整流水线"""
    # (此函数不变)
    output_path = OUTPUT_DIR / pdf_path.name
    
    if output_path.exists():
        logger.info(f"跳过已处理文件: {pdf_path.name}")
        return
        
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.error(f"[{pdf_path.name}] - 无法打开PDF文件: {e}")
        logging.error(f"[{pdf_path.name}] - 无法打开PDF文件: {e}")
        return

    catalog_text = get_pdf_text_by_pages(doc, 1, CATALOG_PAGE_LIMIT)
    catalog_result = parse_catalog_with_llm(catalog_text)

    if "error" in catalog_result:
        msg = f"[{pdf_path.name}] - 无法解析目录: {catalog_result['error']}"
        logger.error(msg)
        logging.error(msg)
        doc.close()
        return

    start_page = catalog_result.get("start_page")
    end_page = catalog_result.get("end_page")
    start_title = catalog_result.get("start_title")
    next_title = catalog_result.get("next_chapter_title")

    if not all([start_page, end_page, start_title, next_title]):
        msg = f"[{pdf_path.name}] - LLM返回的目录JSON不完整 (可能未找到或未返回必须字段): {catalog_result}"
        logger.error(msg)
        logging.error(msg)
        doc.close()
        return

    next_chapter_start_page = end_page + 1
    
    logger.info(f"[{pdf_path.name}] - 正在验证 '{(start_title or 'N/A')[:20]}...' (页码 {start_page})")
    start_page_ok = verify_page_content(doc, start_page, start_title)
    
    logger.info(f"[{pdf_path.name}] - 			正在验证 '{(next_title or 'N/A')[:20]}...' (页码 {next_chapter_start_page})")
    next_page_ok = verify_page_content(doc, next_chapter_start_page, next_title)

    if not (start_page_ok and next_page_ok):
        msg = (
            f"[{pdf_path.name}] - 页码验证失败 (目录页码与PDF页码不符)。"
            f"  '{start_title}' (页 {start_page}): {start_page_ok}."
            f"  '{next_title}' (页 {next_chapter_start_page}): {next_page_ok}."
        )
        logger.error(msg)
        logging.error(msg)
        doc.close()
        return

    try:
        logger.info(f"[{pdf_path.name}] - 验证通过。正在分割 {start_page} 页到 {end_page} 页...")
        split_pdf(doc, start_page, end_page, output_path)
        logger.info(f"[{pdf_path.name}] - 成功保存到 {output_path}")
    except Exception as e:
        msg = f"[{pdf_path.name}] - PDF分割时发生错误: {e}"
        logger.error(msg)
        logging.error(msg)
    finally:
        doc.close()


def main():
    # (此函数不变)
    logger.info("--- 开始执行预处理流水线 ---")
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    MANUAL_DIR.mkdir(exist_ok=True)

    pdf_files = list(INPUT_DIR.glob("*.pdf")) + list(INPUT_DIR.glob("*.PDF"))
    if not pdf_files:
        logger.warning(f"在 {INPUT_DIR} 中未找到任何 .pdf 文件。")
        return

    logger.info(f"在 {INPUT_DIR} 找到 {len(pdf_files)} 个PDF文件。")

    for pdf_path in tqdm(pdf_files, desc="正在处理PDF"):
        logger.info(f"--- 正在处理: {pdf_path.name} ---")
        process_file(pdf_path)

    logger.info("--- 预处理流水线执行完毕 ---")
    logger.info(f"成功的文件保存在: {OUTPUT_DIR}")
    logger.info(f"失败/需手动的日志保存在: {LOG_FILE}")

if __name__ == "__main__":
    main()