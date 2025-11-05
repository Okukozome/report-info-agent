import os
import glob
import fitz  # PyMuPDF
import concurrent.futures

def convert_pdf_to_image_pdf(input_path: str, output_path: str, zoom: float = 3.0) -> None:
    """
    (此函数功能不变)
    使用 PyMuPDF (fitz) 将单个 PDF 转换为纯图像 PDF。
    """
    
    # <<<--- 添加这行 ---
    # 提前获取文件名，用于日志
    base_name = os.path.basename(input_path)
    print(f"开始处理: {base_name}")
    # <<<--- 添加结束 ---
    
    try:
        mat = fitz.Matrix(zoom, zoom)
        doc = fitz.open(input_path)
        new_doc = fitz.open()
        
        for page in doc:
            rect = page.rect
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            
            new_page = new_doc.new_page(width=rect.width, height=rect.height)
            new_page.insert_image(rect, stream=img_bytes)
        
        new_doc.save(output_path, garbage=4, deflate=True, clean=True)
        new_doc.close()
        doc.close()
        
        # 使用 base_name 变量
        print(f"转换成功: {base_name} -> {os.path.basename(output_path)}")
        
    except Exception as e:
        # 使用 base_name 变量
        print(f"转换失败 [{base_name}]: {str(e)}")

def main() -> None:
    INPUT_DIR = 'input'
    OUTPUT_DIR = 'output_PyMuPDF'
    ZOOM_FACTOR = 4.0

    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    pdf_files = glob.glob(os.path.join(INPUT_DIR, '*.pdf'))
    
    if not pdf_files:
        print(f"未在 {INPUT_DIR}/ 目录下找到 PDF 文件。")
        return

    # 使用 None 会默认使用所有可用的 CPU 核心
    max_workers = None
    
    print(f"开始并行转换 {len(pdf_files)} 个文件 (使用 {max_workers or '所有'} 个CPU核心)...")
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_file = {}
        for pdf_file in pdf_files:
            input_path = pdf_file
            base_name = os.path.basename(pdf_file)
            output_path = os.path.join(OUTPUT_DIR, base_name)
            
            future = executor.submit(convert_pdf_to_image_pdf, input_path, output_path, ZOOM_FACTOR)
            future_to_file[future] = input_path

        # 等待任务完成 (as_completed 会在任务完成时立即返回)
        for future in concurrent.futures.as_completed(future_to_file):
            input_path = future_to_file[future]
            try:
                # 检查是否有未被捕获的异常
                future.result()
            except Exception as e:
                print(f"文件 {input_path} 在工作进程中发生严重错误: {e}")
    
    print("所有转换任务已完成。")

if __name__ == "__main__":
    try:
        import fitz
    except ImportError:
        print("错误：未检测到 PyMuPDF。请执行：")
        print("    pip install pymupdf") 
        exit(1)
    
    main()