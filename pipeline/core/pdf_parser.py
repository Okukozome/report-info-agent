# pipeline/core/pdf_parser.py
import base64
import requests
import logging
from core.settings import Settings

logger = logging.getLogger(__name__)

def parse_pdf_to_markdown(file_path: str, settings: Settings) -> str:
    """
    调用 PP-StructureV3 API 将 PDF 文件转换为 Markdown 文本。
    """
    logger.info(f"  [PDF Parser] 正在读取文件: {file_path}")
    try:
        with open(file_path, "rb") as file:
            file_bytes = file.read()
            file_data = base64.b64encode(file_bytes).decode("ascii")
    except FileNotFoundError:
        logger.error(f"错误：未找到文件 {file_path}")
        raise
    except Exception as e:
        logger.error(f"读取文件时出错: {e}")
        raise

    headers = {
        "Authorization": f"token {settings.PP_TOKEN}",
        "Content-Type": "application/json"
    }

    # 使用推荐参数
    payload = {
        "file": file_data,
        "fileType": 0, # 0 表示PDF
        "visualize": False,
        "useTableRecognition": True,
        "useChartRecognition": True,
        "useWiredTableCellsTransToHtml": True,
        "useWirelessTableCellsTransToHtml": True,
        "useOcrResultsWithTableCells": True,
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useTextlineOrientation": False,
        "useTableOrientationClassify": False,
    }

    logger.info(f"  [PDF Parser] 正在向 PP-StructureV3 API 发送请求...")
    try:
        response = requests.post(
            settings.PP_API_URL, 
            json=payload, 
            headers=headers, 
            timeout=settings.PP_TIMEOUT
        )
        
        if response.status_code != 200:
            logger.error(f"PP API 请求失败，状态码: {response.status_code}")
            logger.error(f"PP API 错误信息: {response.text}")
            raise Exception(f"API 请求失败，状态码: {response.status_code} - {response.text}")

        logger.info(f"  [PDF Parser] API 请求成功。")
        result = response.json().get("result", {})
        
        md_parts = []
        page_count = len(result.get("layoutParsingResults", []))
        # 拼接所有页面的 Markdown 结果
        for i, res in enumerate(result.get("layoutParsingResults", [])):
            md_text = res.get("markdown", {}).get("text", "")
            md_parts.append(md_text)
            if (i + 1) % 10 == 0 or (i + 1) == page_count:
                 logger.info(f"  [PDF Parser] 已处理页面 {i+1}/{page_count}")
        
        full_markdown = "\n\n".join(md_parts)
        if not full_markdown.strip():
            logger.warning("PP-StructureV3 返回了空的 Markdown 内容。")
            
        return full_markdown

    except requests.exceptions.RequestException as e:
        logger.error(f"PP API 请求异常: {e}")
        raise
    except Exception as e:
        logger.error(f"解析PP响应时出错: {e}")
        raise