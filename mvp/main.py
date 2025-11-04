import os
import json
from pathlib import Path
from typing import Literal

try:
    from src.settings import settings
    from src.schemas import CategoryExtractionResult, CoreBlocksExtractionResult
    from src.pdf_parser import parse_pdf_to_markdown
    from src.llm_extractor import extract_category, extract_core_blocks
except ImportError as e:
    print(f"错误：导入模块失败。请确保你在 'mvp/' 目录下运行，并且 'src/' 目录结构正确。")
    print(f"详细信息: {e}")
    exit(1)

BASE_DIR = Path(__file__).parent
INPUT_FILE = BASE_DIR / "inputs" / "董事2split.pdf"
OUTPUT_DIR = BASE_DIR / "outputs"
MD_OUTPUT = OUTPUT_DIR / "intermediate.md"
CORE_BLOCKS_OUTPUT = OUTPUT_DIR / "core_blocks.json"

def main():
    """
    执行半自动化MVP流水线（包含核心块提取）
    """
    print("=" * 60)
    print(" 开始执行半自动化MVP流水线 (V2: 含核心块提取)")
    print("=" * 60)
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
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
        return 

    print(f"\n[步骤 1.5: LLM 核心块提取]")
    try:
        core_blocks_result = extract_core_blocks(markdown_content, settings)
        
        if not core_blocks_result:
            print("错误：核心块提取失败，无法继续。")
            return
        
        with open(CORE_BLOCKS_OUTPUT, "w", encoding="utf-8") as f:
            f.write(core_blocks_result.model_dump_json(indent=2, ensure_ascii=False))
        print(f"核心块提取结果已保存至: {CORE_BLOCKS_OUTPUT}")
        
        print(f"  提取到 {len(core_blocks_result.tables)} 个表格。")
        
        if core_blocks_result.employment_section:
            print(f"  提取到 '{core_blocks_result.employment_section.title}' 小节。")
        
        if not core_blocks_result.tables:
            print("警告：未提取到任何核心表格，后续提取可能失败或为空。")
            extraction_input_text = ""
        else:
            table_blocks = []
            for table in core_blocks_result.tables:
                table_blocks.append(f"### 表格：{table.description}\n\n{table.content}")
            
            extraction_input_text = "\n\n---\n\n".join(table_blocks)
            print("  已合并所有表格（含表名描述），准备进行分类提取。")

    except Exception as e:
        print(f"核心块提取时发生严重错误: {e}")
        return

    print(f"\n[步骤 2: LLM 信息提取 (共3次调用)]")
    
    categories_to_extract: list[Literal["Directors", "Supervisors", "SeniorManagement"]] = [
        "Directors", 
        "Supervisors", 
        "SeniorManagement"
    ]
    
    all_results = {}

    if not extraction_input_text.strip():
        print("输入为空（未找到核心表格），跳过信息提取步骤。")
    else:
        for category in categories_to_extract:
            print(f"\n--- 正在提取: {category} ---")
            try:
                result = extract_category(extraction_input_text, category, settings)
                
                if result:
                    all_results[category] = result
                    json_filename = f"{category.lower()}.json"
                    json_path = OUTPUT_DIR / json_filename
                    
                    with open(json_path, "w", encoding="utf-8") as f:
                        f.write(result.model_dump_json(indent=2, ensure_ascii=False))
                    print(f"结果已保存至: {json_path}")
                
                else:
                    print(f"提取 {category} 失败，未收到有效结果。")

            except Exception as e:
                print(f"提取 {category} 时发生严重错误: {e}")

    print("\n" + "=" * 60)
    print(" MVP 流水线执行完毕 - 结果汇总")
    print("=" * 60)
    
    if not all_results:
        print("未提取到任何结果。")
        
    for category, result in all_results.items():
        print(f"\n--- 类别: {category} ---")
        print(f"提取人数: {len(result.persons)}")
        print(f"置信度: {result.assessment.confidence_level}")
        
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