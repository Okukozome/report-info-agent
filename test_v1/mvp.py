import os
import json
import requests
from pydantic import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv

# --- 1. 加载环境变量 ---
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# --- 2. 定义Pydantic数据结构 (Schema) ---
# 这是我们希望LLM返回的结构

class ExtractedPerson(BaseModel):
    """代表一位被提取的人员及其职务"""
    name: str = Field(..., description="人员的姓名")
    role: str = Field(..., description="人员的职务，例如：董事长, 独立董事, 监事会主席, 副总经理")

class ExtractionResult(BaseModel):
    """包含所有被提取人员的列表"""
    persons: List[ExtractedPerson] = Field(..., description="从文本中提取的董事、监事或高管的有序列表")

# --- 3. 核心提取函数 (保持不变) ---

def extract_info_from_text(text_content: str) -> Optional[ExtractionResult]:
    """
    使用聚合API的gpt-4o和Tool Use功能从文本中提取结构化信息。
    """
    
    api_base_url = os.getenv("API_BASE_URL")
    api_key = os.getenv("API_KEY")
    
    if not api_base_url or not api_key:
        print("错误：请在.env文件中设置 API_BASE_URL 和 API_KEY")
        return None
        
    api_url = f"{api_base_url}/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # --- 构造 Tool Use (Function Calling) ---
    
    # 1. 获取Pydantic模型的JSON Schema
    tools_schema = ExtractionResult.model_json_schema()
    
    # 2. 定义工具
    # 我们将强制模型调用这个名为 "save_extraction" 的工具
    tools_payload = [
        {
            "type": "function",
            "function": {
                "name": "save_extraction",
                "description": "保存提取到的董事、监事和高级管理人员信息",
                "parameters": tools_schema
            }
        }
    ]
    
    # 3. 构造请求数据
    system_prompt = (
        "你是一个专业的年报分析助手。"
        "你的任务是严格按照用户提供的文本内容，"
        "按出现的先后顺序，提取所有董事、监事和高级管理人员的姓名及其对应的职务。"
        "不要遗漏任何人，确保职务的准确性。"
    )

    user_prompt = f"请从以下文本中提取所需信息：\n\n---START OF TEXT---\n{text_content}\n---END OF TEXT---"

    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "tools": tools_payload,
        # 修正：强制模型必须调用这个工具
        "tool_choice": {"type": "function", "function": {"name": "save_extraction"}}
    }
    
    try:
        print("正在向API发送请求...")
        response = requests.post(api_url, headers=headers, json=data, timeout=60)
        
        if response.status_code == 200:
            print("API请求成功！")
            result = response.json()
            
            # --- 解析 Tool Use 返回的结果 ---
            tool_calls = result['choices'][0]['message'].get('tool_calls')
            
            if not tool_calls:
                print("错误：模型没有按预期调用工具。")
                return None
            
            # 提取第一个工具调用的参数
            tool_call = tool_calls[0]
            if tool_call['function']['name'] == "save_extraction":
                # 这是模型生成的JSON字符串
                arguments_json_str = tool_call['function']['arguments']
                
                print("成功获取模型返回的JSON，正在使用Pydantic验证...")
                
                # 使用 Pydantic 进行严格的验证和解析
                validated_result = ExtractionResult.model_validate_json(arguments_json_str)
                
                print("Pydantic格式验证通过！")
                return validated_result
            else:
                print(f"错误：模型调用了未知的工具 {tool_call['function']['name']}")
                return None

        else:
            print(f"API请求失败，状态码: {response.status_code}")
            print(f"错误信息: {response.text}")
            return None
            
    except Exception as e:
        print(f"发生异常: {e}")
        return None

# --- 4. 主执行逻辑：新增内容准确性校验 ---

def compare_results(extracted: ExtractionResult, golden: ExtractionResult) -> bool:
    """
    比较提取结果和黄金标准结果的内容是否完全一致（包括顺序）。
    """
    if len(extracted.persons) != len(golden.persons):
        print(f"❌ 数量不匹配：模型提取 {len(extracted.persons)} 人，黄金标准 {len(golden.persons)} 人。")
        return False
    
    # 逐个比对姓名和职务
    mismatches = []
    for i, (ext_p, gol_p) in enumerate(zip(extracted.persons, golden.persons)):
        is_match = (ext_p.name == gol_p.name) and (ext_p.role == gol_p.role)
        if not is_match:
            mismatches.append({
                "序号": i + 1,
                "期望姓名": gol_p.name,
                "期望职务": gol_p.role,
                "实际姓名": ext_p.name,
                "实际职务": ext_p.role
            })

    if mismatches:
        print(f"❌ 内容不匹配：发现 {len(mismatches)} 处错误。")
        print("\n--- 不匹配详情 ---")
        for m in mismatches:
            print(f"序号 {m['序号']}: 期望 ({m['期望姓名']} | {m['期望职务']}) vs 实际 ({m['实际姓名']} | {m['实际职务']})")
        return False
    
    print("✅ 内容完全匹配！姓名、职务和顺序均正确。")
    return True


def main():
    print("--- MVP 阶段一：格式与内容校验验证 ---")
    
    # 构造文件路径
    script_dir = os.path.dirname(__file__)
    sample_file_path = os.path.join(script_dir, 'sample.txt')
    golden_file_path = os.path.join(script_dir, 'sample_golden.json') # 新增的黄金标准文件
    
    # 1. 检查输入文本和黄金标准文件
    if not os.path.exists(sample_file_path):
        print(f"错误：未找到输入文本文件: {sample_file_path}")
        return
        
    if not os.path.exists(golden_file_path):
        print(f"错误：未找到黄金标准文件。请手动创建: {golden_file_path}")
        return

    try:
        # 读取输入文本
        with open(sample_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"已加载输入文本内容，共 {len(content)} 字符。")

        # 读取黄金标准
        golden_data = ExtractionResult.model_validate_json(open(golden_file_path, 'r', encoding='utf-8').read())
        print(f"已加载黄金标准，共 {len(golden_data.persons)} 人。")
        
        # 2. 执行提取
        extraction_data = extract_info_from_text(content)
        
        if extraction_data:
            # 3. 格式化输出 (保持原有逻辑)
            print("\n--- 提取结果 ---")
            max_name_len = max(len(p.name) for p in extraction_data.persons)
            max_role_len = max(len(p.role) for p in extraction_data.persons)
            
            print(f"{'序号':<4} | {'姓名':<{max_name_len}} | {'职务':<{max_role_len}}")
            print("-" * (10 + max_name_len + max_role_len))
            
            for i, person in enumerate(extraction_data.persons):
                print(f"{i+1:<4} | {person.name:<{max_name_len}} | {person.role:<{max_role_len}}")

            # 4. 准确性校验 (新增核心逻辑)
            print("\n--- 准确性校验 ---")
            is_accurate = compare_results(extraction_data, golden_data)
            
            if is_accurate:
                print("\n--- MVP 验收标准：格式正确 AND 内容准确达成！ ---")
            else:
                print("\n--- MVP 失败：格式正确，但内容不准确或顺序错误！ ---")
        
        else:
            print("\n--- MVP 失败：未能获取或解析提取结果 (格式检查失败) ---")

    except Exception as e:
        print(f"运行发生错误: {e}")

if __name__ == "__main__":
    main()