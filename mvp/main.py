import os
import json
from pathlib import Path
from typing import Literal

# 确保在顶层脚本中尽早加载设置
try:
    from src.settings import settings
    from src.schemas import CategoryExtractionResult
    from src.pdf_parser import parse_pdf_to_markdown
    from src.llm_extractor import extract_category
except ImportError as e:
    print(f"错误：导入模块失败。请确保你在 'mvp/' 目录下运行，并且 'src/' 目录结构正确。")
    print(f"详细信息: {e}")
    exit(1)

# --- 1. 定义路径 ---
# Path(__file__).parent 指向 main.py 所在的 mvp 目录
BASE_DIR = Path(__file__).parent
INPUT_FILE = BASE_DIR / "inputs" / "董事2split.pdf"
OUTPUT_DIR = BASE_DIR / "outputs"
MD_OUTPUT = OUTPUT_DIR / "intermediate.md"

def main():
    """
    执行半自动化MVP流水线
    """
    print("=" * 60)
    print(" 开始执行半自动化MVP流水线")
    print("=" * 60)
    
    # 确保输出目录存在
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # --- 步骤 1: PDF -> Markdown ---
    print(f"\n[步骤 1: PDF 解析]")
    print(f"输入文件: {INPUT_FILE}")
    
    if not INPUT_FILE.exists():
        print(f"错误：输入文件未找到！请确保 '{INPUT_FILE.name}' 存在于 'mvp/inputs/' 目录下。")
        return
        
    try:
        markdown_content = parse_pdf_to_markdown(str(INPUT_FILE), settings)
        with open(MD_OUTPUT, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(f"Markdown 中间文件已保存至: {MD_OUTPUT}")
    except Exception as e:
        print(f"PDF解析步骤失败: {e}")
        return # 如果第一步失败，则终止

    # --- 步骤 2: Markdown -> 结构化 JSON (分三次) ---
    print(f"\n[步骤 2: LLM 信息提取 (共3次调用)]")
    
    # 定义我们要提取的三个类别
    categories_to_extract: list[Literal["Directors", "Supervisors", "SeniorManagement"]] = [
        "Directors", 
        "Supervisors", 
        "SeniorManagement"
    ]
    
    all_results = {}

    for category in categories_to_extract:
        print(f"\n--- 正在提取: {category} ---")
        try:
            result = extract_category(markdown_content, category, settings)
            
            if result:
                all_results[category] = result
                # 保存独立的JSON文件
                json_filename = f"{category.lower()}.json"
                json_path = OUTPUT_DIR / json_filename
                
                with open(json_path, "w", encoding="utf-8") as f:
                    # ensure_ascii=False 确保中文正常显示
                    f.write(result.model_dump_json(indent=2, ensure_ascii=False))
                print(f"结果已保存至: {json_path}")
            
            else:
                print(f"提取 {category} 失败，未收到有效结果。")

        except Exception as e:
            print(f"提取 {category} 时发生严重错误: {e}")

    # --- 步骤 3: 结果汇总 ---
    print("\n" + "=" * 60)
    print(" MVP 流水线执行完毕 - 结果汇总")
    print("=" * 60)
    
    for category, result in all_results.items():
        print(f"\n--- 类别: {category} ---")
        print(f"提取人数: {len(result.persons)}")
        print(f"置信度: {result.assessment.confidence_level}")
        
        # 仅在有疑虑时打印疑虑点
        if result.assessment.doubts:
            print("!!! 发现疑虑点:")
            for doubt in result.assessment.doubts:
                print(f"  - {doubt}")
        else:
            print("疑虑点: 无")
            
        print("提取列表:")
        for p in result.persons:
            print(f"  Rank {p.rank:<2}: {p.name:<10} (职务: {p.role})")

if __name__ == "__main__":
    main()