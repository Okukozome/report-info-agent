import os
import glob
from io import BytesIO
import pypdfium2 as pdfium
from PIL import Image

def convert_pdf_to_image_pdf(input_path: str, output_path: str, zoom: float = 3.0) -> None:
    """
    使用 pypdfium2 (Google PDFium) 将单个 PDF 转换为纯图像 PDF。
    这会彻底去除所有文本和矢量元素，只保留渲染后的像素图像。

    参数:
        input_path: 输入 PDF 路径
        output_path: 输出 PDF 路径
        zoom: 渲染缩放倍率 (3.0 ≈ 216 DPI, 推荐值以保证清晰度)
    """
    try:
        # 加载输入 PDF
        doc = pdfium.PdfDocument(input_path)
        
        # 创建新的空 PDF
        new_doc = pdfium.PdfDocument.new()
        
        for page in doc:
            # 1. 获取原始页面尺寸（单位：points）
            width, height = page.get_size()
            
            # 2. 以高分辨率渲染当前页面
            bitmap = page.render(
                scale=zoom,
                rotation=0
            )
            
            # 3. 将位图转换为 PIL 图像
            pil_img = bitmap.to_pil()
            
            # 4. 在新 PDF 中创建一页，尺寸与原始页面相同
            new_page = new_doc.new_page(width, height)
            
            # 5. 创建 PdfImage 对象并设置位图
            image = pdfium.PdfImage.new(new_doc)
            new_bitmap = pdfium.PdfBitmap.from_pil(pil_img)  # 从 PIL 创建新位图
            image.set_bitmap(new_bitmap)
            
            # 6. 设置变换矩阵以拉伸图像填满页面
            matrix = pdfium.PdfMatrix().scale(width, height)
            image.set_matrix(matrix)
            
            # 7. 插入图像到新页面并生成内容
            new_page.insert_obj(image)
            new_page.gen_content()
            
            # 8. 及时关闭资源以释放内存
            pil_img.close()
            new_bitmap.close()
            bitmap.close()
            page.close()
        
        # 保存新 PDF（pypdfium2 会自动压缩）
        new_doc.save(output_path, version=17)  # 使用 PDF 1.7 标准
        
        # 关闭文档
        new_doc.close()
        doc.close()
        
        print(f"转换成功: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")
        
    except Exception as e:
        print(f"转换失败 [{os.path.basename(input_path)}]: {str(e)}")

def main() -> None:
    INPUT_DIR = 'input'
    OUTPUT_DIR = 'output'
    ZOOM_FACTOR = 3.0  # 缩放因子，3.0 提供了很好的清晰度

    # 确保 input 和 output 目录存在
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 查找所有 PDF 文件
    pdf_files = glob.glob(os.path.join(INPUT_DIR, '*.pdf'))
    
    if not pdf_files:
        print(f"未在 {INPUT_DIR}/ 目录下找到 PDF 文件。")
        return
    
    print(f"开始转换 {len(pdf_files)} 个文件 (使用 PDFium 引擎)...")
    
    for pdf_file in pdf_files:
        input_path = pdf_file
        base_name = os.path.basename(pdf_file)
        output_path = os.path.join(OUTPUT_DIR, base_name)
        
        convert_pdf_to_image_pdf(input_path, output_path, zoom=ZOOM_FACTOR)

if __name__ == "__main__":
    try:
        import pypdfium2 as pdfium
    except ImportError:
        print("错误：未检测到 pypdfium2。请执行：")
        print("    pip install pypdfium2") 
        exit(1)
    
    try:
        from PIL import Image
    except ImportError:
        print("错误：未检测到 Pillow。请执行：")
        print("    pip install Pillow") 
        exit(1)
    
    main()