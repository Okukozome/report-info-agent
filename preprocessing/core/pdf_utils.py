import io
from pathlib import Path
from typing import List
from pypdf import PdfReader, PdfWriter

def get_pdf_page_count(pdf_path: Path) -> int:
    """获取 PDF 的总页数"""
    try:
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception as e:
        raise Exception(f"无法读取 PDF 文件 {pdf_path}: {e}")

def split_pdf_to_bytes(pdf_path: Path, max_pages: int) -> bytes:
    """
    分割 PDF 的前 N 页，并返回内存中的 bytes
    """
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    
    # 确保 max_pages 不超过总页数
    num_pages_to_add = min(len(reader.pages), max_pages)
    
    if num_pages_to_add == 0:
        return b""
        
    for i in range(num_pages_to_add):
        writer.add_page(reader.pages[i])
        
    # 写入内存
    with io.BytesIO() as bytes_stream:
        writer.write(bytes_stream)
        return bytes_stream.getvalue()

def get_pdf_page_by_index_to_bytes(pdf_path: Path, page_index: int) -> bytes:
    """
    获取指定索引（0-based）的单页 PDF，并返回内存中的 bytes
    """
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    
    if not (0 <= page_index < len(reader.pages)):
        raise IndexError(f"Page index {page_index} out of range (Total pages: {len(reader.pages)})")
        
    writer.add_page(reader.pages[page_index])
    
    with io.BytesIO() as bytes_stream:
        writer.write(bytes_stream)
        return bytes_stream.getvalue()

def crop_pdf(
    pdf_path: Path, 
    start_index: int, 
    end_index: int, 
    output_path: Path
):
    """
    根据物理索引（0-based）裁剪 PDF 并保存到文件
    """
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    
    total_pages = len(reader.pages)
    
    # 确保索引在有效范围内
    start_index = max(0, start_index)
    end_index = min(total_pages - 1, end_index)
    
    if start_index > end_index:
        raise ValueError(f"裁剪范围无效: start_index {start_index} > end_index {end_index}")

    for i in range(start_index, end_index + 1):
        writer.add_page(reader.pages[i])
        
    # 写入文件
    try:
        writer.write(output_path)
    except Exception as e:
        raise Exception(f"写入裁剪后的 PDF 失败: {e}")