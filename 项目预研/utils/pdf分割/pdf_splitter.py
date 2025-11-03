import os
import sys
from PyPDF2 import PdfReader, PdfWriter

def split_pdf(pdf_path: str, start_page: int, end_page: int, output_path: str):
    """
    分割 PDF 文件中的指定页码范围。

    :param pdf_path: 待分割的 PDF 文件路径。
    :param start_page: 起始页码（基于 1）。
    :param end_page: 结束页码（包含在内，基于 1）。
    :param output_path: 输出的 PDF 文件路径。
    """
    try:
        # 打开原始 PDF 文件
        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        total_pages = len(reader.pages)

        # 检查页码范围是否有效
        if not (1 <= start_page <= end_page <= total_pages):
            print(f"错误：页码范围无效或超出文件范围 (1 - {total_pages})。")
            return

        # PyPDF2 的页码是从 0 开始计数的，所以需要 -1
        # range(start, stop) 是 [start, stop)
        for i in range(start_page - 1, end_page):
            writer.add_page(reader.pages[i])

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 写入新的 PDF 文件
        with open(output_path, "wb") as output_pdf:
            writer.write(output_pdf)

        print(f"成功：已将 '{pdf_path}' 的第 {start_page} 至 {end_page} 页保存到 '{output_path}'。")

    except FileNotFoundError:
        print(f"错误：文件未找到：'{pdf_path}'")
    except Exception as e:
        # 仅捕获通用异常，避免过度处理
        print(f"发生错误：{e}")


def main():
    # 硬编码输入/输出路径
    INPUT_DIR = "input"
    OUTPUT_DIR = "output"
    
    # 示例文件名
    INPUT_FILENAME = "sample.pdf"
    OUTPUT_FILENAME = "sample_page_split.pdf"  # 根据需要修改输出文件名

    # 完整路径
    input_pdf_path = os.path.join(INPUT_DIR, INPUT_FILENAME)
    output_pdf_path = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)

    # 分割页码范围（基于 1 起始）
    START_PAGE = 42
    END_PAGE = 48

    # 示例：创建目录和空文件以便测试 (可选，手动创建也行)
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # 假设 'input/sample.pdf' 存在并有足够页数

    print(f"正在尝试分割文件: {input_pdf_path}")
    print(f"页码范围: {START_PAGE} - {END_PAGE}")
    print(f"输出到: {output_pdf_path}\n")

    # 调用分割函数
    split_pdf(
        pdf_path=input_pdf_path,
        start_page=START_PAGE,
        end_page=END_PAGE,
        output_path=output_pdf_path
    )


if __name__ == "__main__":
    main()