import os
import sys
from pdf2image import convert_from_path


def pdf_to_jpgs(pdf_path: str, start_page: int, end_page: int, output_dir: str):
    """
    将 PDF 文件中指定页码范围的每一页转换为单独的 JPG 图片。

    :param pdf_path: 待转换的 PDF 文件路径。
    :param start_page: 起始页码（基于 1）。
    :param end_page: 结束页码（包含在内，基于 1）。
    :param output_dir: 存放 JPG 图片的输出目录。
    """
    try:
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 使用 300 DPI 保证图片质量，指定页码范围并转换为 JPEG 格式
        images = convert_from_path(
            pdf_path, 
            dpi=300, 
            first_page=start_page, 
            last_page=end_page, 
            fmt='jpeg'
        )

        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        # 逐页保存为 JPG 文件
        for i, image in enumerate(images):
            # i 从 0 开始，所以实际页码是 start_page + i
            page_num = start_page + i
            output_file = os.path.join(output_dir, f"{base_name}_page_{page_num}.jpg")
            image.save(output_file, 'JPEG')

        print(f"成功：已将 '{pdf_path}' 的第 {start_page} 至 {end_page} 页转换为 JPG 图片，保存在 '{output_dir}'。")

    except FileNotFoundError:
        print(f"错误：文件未找到：'{pdf_path}'")
    except Exception as e:
        # 捕获其他通用异常，例如 Poppler 路径配置错误
        print(f"转换发生错误，请检查 Poppler 是否正确安装和配置：{e}")


def main():
    # --- 配置参数 ---
    INPUT_DIR = "input"
    OUTPUT_DIR = "output_jpgs"
    
    # 示例文件名 (确保此文件在 input 目录下存在)
    INPUT_FILENAME = "sample.pdf"

    # 完整输入路径
    input_pdf_path = os.path.join(INPUT_DIR, INPUT_FILENAME)
    output_images_dir = os.path.join(OUTPUT_DIR, os.path.splitext(INPUT_FILENAME)[0])

    # 转换的页码范围（基于 1 起始）
    START_PAGE = 42
    END_PAGE = 43
    # --- 配置参数结束 ---

    # 示例：创建输入目录（假设 sample.pdf 已手动放入）
    os.makedirs(INPUT_DIR, exist_ok=True)

    print(f"正在尝试转换文件: {input_pdf_path}")
    print(f"页码范围: {START_PAGE} - {END_PAGE}")
    print(f"图片输出到: {output_images_dir}\n")

    # 调用转换函数
    pdf_to_jpgs(
        pdf_path=input_pdf_path,
        start_page=START_PAGE,
        end_page=END_PAGE,
        output_dir=output_images_dir
    )


if __name__ == "__main__":
    main()
