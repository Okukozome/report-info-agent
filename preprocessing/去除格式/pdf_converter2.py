import os
import glob
import fitz  # PyMuPDF

def convert_pdf_to_image_pdf(input_path: str, output_path: str, zoom: float = 3.0) -> None:
    """
    使用 PyMuPDF (fitz) 将单个 PDF 转换为纯图像 PDF。
    这会彻底去除所有文本和矢量元素，只保留渲染后的像素图像。

    参数:
        input_path: 输入 PDF 路径
        output_path: 输出 PDF 路径
        zoom: 渲染缩放倍率 (3.0 ≈ 216 DPI, 推荐值以保证清晰度)
    """
    try:
        # 定义渲染矩阵
        mat = fitz.Matrix(zoom, zoom)
        
        # 加载输入 PDF
        doc = fitz.open(input_path)
        
        # 创建新的空 PDF
        new_doc = fitz.open()
        
        for page in doc:
            # 1. 获取原始页面尺寸（单位：points）
            rect = page.rect
            
            # 2. 以高分辨率渲染当前页面
            #    alpha=False 禁用透明通道
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # 3. 将渲染后的位图转换为 PNG 字节流
            img_bytes = pix.tobytes("png")
            
            # 4. 在新 PDF 中创建一页，尺寸与原始页面相同
            new_page = new_doc.new_page(width=rect.width, height=rect.height)
            
            # 5. 将图像插入新页面，并拉伸以填满整个页面
            new_page.insert_image(rect, stream=img_bytes)
        
        # 保存：压缩 + 清理元数据/垃圾对象
        new_doc.save(output_path, garbage=4, deflate=True, clean=True)
        
        # 6. 关闭文档
        new_doc.close()
        doc.close()
        
        print(f"转换成功: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")
        
    except Exception as e:
        print(f"转换失败 [{os.path.basename(input_path)}]: {str(e)}")

def main() -> None:
    INPUT_DIR = 'input'
    OUTPUT_DIR = 'output_PyMuPDF'
    ZOOM_FACTOR = 4.0  # 缩放因子

    # 确保 input 和 output 目录存在
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 查找所有PDF文件
    pdf_files = glob.glob(os.path.join(INPUT_DIR, '*.pdf'))
    
    if not pdf_files:
        print(f"未在 {INPUT_DIR}/ 目录下找到 PDF 文件。")
        return
    
    print(f"开始转换 {len(pdf_files)} 个文件 (使用 PyMuPDF 引擎)...")
    
    for pdf_file in pdf_files:
        input_path = pdf_file
        base_name = os.path.basename(pdf_file)
        output_path = os.path.join(OUTPUT_DIR, base_name)
        
        convert_pdf_to_image_pdf(input_path, output_path, zoom=ZOOM_FACTOR)

if __name__ == "__main__":
    try:
        import fitz
    except ImportError:
        print("错误：未检测到 PyMuPDF。请执行：")
        # 根据你的环境偏好，你可能想用 conda
        print("    pip install pymupdf") 
        exit(1)
    
    main()