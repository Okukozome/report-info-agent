import os
import json
import requests
from pydantic import BaseModel, Field
from typing import List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# --- 定义Schema数据结构 ---
class FruitInfo(BaseModel):
    """代表一种水果及其健康理由"""
    name: str = Field(..., description="水果名称")
    reason: str = Field(..., description="对健康有益的理由")

class FruitList(BaseModel):
    """包含所有水果信息的列表"""
    fruits: List[FruitInfo] = Field(..., description="水果及其健康理由的列表")

def test_mixed_api_usage():
    """
    测试混合使用自由对话和强制Schema调用
    第一轮：自由对话
    第二轮：强制Schema输出
    """
    # 从环境变量读取配置
    api_base_url = os.getenv("API_BASE_URL")
    api_key = os.getenv("API_KEY")
    
    if not api_base_url or not api_key:
        print("错误：请在.env文件中设置 API_BASE_URL 和 API_KEY")
        return
    
    api_url = f"{api_base_url}/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # 存储对话历史
    conversation_history = []
    
    print("=== 混合API调用测试 ===\n")
    
    try:
        # --- 第一轮：自由对话 ---
        print("第一轮：自由对话模式")
        print("用户：举例一些有利于健康的水果")
        
        first_round_data = {
            "model": "gpt-4o",
            "messages": [
                {"role": "user", "content": "举例一些有利于健康的水果"}
            ],
            "temperature": 0.7
        }
        
        response1 = requests.post(api_url, headers=headers, json=first_round_data, timeout=60)
        
        if response1.status_code == 200:
            result1 = response1.json()
            assistant_reply1 = result1['choices'][0]['message']['content']
            print(f"助手：{assistant_reply1}")
            
            # 保存对话历史
            conversation_history.extend([
                {"role": "user", "content": "举例一些有利于健康的水果"},
                {"role": "assistant", "content": assistant_reply1}
            ])
        else:
            print(f"第一轮API请求失败，状态码: {response1.status_code}")
            return
        
        print("\n" + "="*50 + "\n")
        
        # --- 第二轮：强制Schema调用 ---
        print("第二轮：强制Schema模式")
        print("用户：请将上述提到过的水果，按照{水果名: 理由}的格式，用JSON格式输出")
        
        # 准备Schema工具定义
        tools_schema = FruitList.model_json_schema()
        
        tools_payload = [
            {
                "type": "function",
                "function": {
                    "name": "output_fruits",
                    "description": "输出水果列表和理由",
                    "parameters": tools_schema
                }
            }
        ]
        
        # 构建第二轮消息（包含历史记录）
        second_round_messages = conversation_history + [
            {"role": "user", "content": "请将上述提到过的水果，按照水果名和理由的格式，用JSON格式输出"}
        ]
        
        second_round_data = {
            "model": "gpt-4o",
            "messages": second_round_messages,
            "tools": tools_payload,
            # 关键：强制调用工具
            "tool_choice": {"type": "function", "function": {"name": "output_fruits"}},
            "temperature": 0.1  # 降低温度以获得更稳定的输出
        }
        
        response2 = requests.post(api_url, headers=headers, json=second_round_data, timeout=60)
        
        if response2.status_code == 200:
            result2 = response2.json()
            message2 = result2['choices'][0]['message']
            
            # 检查是否有工具调用
            if 'tool_calls' in message2:
                tool_call = message2['tool_calls'][0]
                if tool_call['function']['name'] == 'output_fruits':
                    arguments_json_str = tool_call['function']['arguments']
                    
                    print("✅ Schema调用成功！")
                    print("获取到的结构化数据：")
                    
                    # 使用Pydantic验证和解析
                    validated_result = FruitList.model_validate_json(arguments_json_str)
                    
                    # 格式化输出结果
                    print("\n--- 结构化输出结果 ---")
                    for i, fruit in enumerate(validated_result.fruits, 1):
                        print(f"{i}. {fruit.name}: {fruit.reason}")
                    
                    # 原始JSON输出
                    print("\n--- 原始JSON数据 ---")
                    print(json.dumps(json.loads(arguments_json_str), ensure_ascii=False, indent=2))
                    
                else:
                    print(f"❌ 模型调用了未知的工具: {tool_call['function']['name']}")
            else:
                print("❌ 模型没有按预期调用工具")
                print(f"助手回复: {message2.get('content', '无内容')}")
                
        else:
            print(f"第二轮API请求失败，状态码: {response2.status_code}")
            print(f"错误信息: {response2.text}")
            
    except Exception as e:
        print(f"发生异常: {e}")

def test_schema_only():
    """
    纯Schema模式测试，用于对比
    """
    api_base_url = os.getenv("API_BASE_URL")
    api_key = os.getenv("API_KEY")
    
    api_url = f"{api_base_url}/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # 准备Schema
    tools_schema = FruitList.model_json_schema()
    
    tools_payload = [
        {
            "type": "function",
            "function": {
                "name": "output_fruits",
                "description": "输出水果列表和理由",
                "parameters": tools_schema
            }
        }
    ]
    
    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "请列举3种有利于健康的水果，并说明理由，用JSON格式输出"}
        ],
        "tools": tools_payload,
        "tool_choice": {"type": "function", "function": {"name": "output_fruits"}},
        "temperature": 0.1
    }
    
    try:
        print("\n=== 纯Schema模式对比测试 ===")
        response = requests.post(api_url, headers=headers, json=data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            message = result['choices'][0]['message']
            
            if 'tool_calls' in message:
                tool_call = message['tool_calls'][0]
                arguments_json_str = tool_call['function']['arguments']
                
                validated_result = FruitList.model_validate_json(arguments_json_str)
                print("✅ 纯Schema模式成功！")
                for i, fruit in enumerate(validated_result.fruits, 1):
                    print(f"{i}. {fruit.name}: {fruit.reason}")
            else:
                print("❌ 纯Schema模式失败")
        else:
            print(f"纯Schema测试失败，状态码: {response.status_code}")
            
    except Exception as e:
        print(f"纯Schema测试异常: {e}")

if __name__ == "__main__":
    # 运行混合测试
    test_mixed_api_usage()
    
    # 运行纯Schema对比测试
    test_schema_only()
    
    print("\n=== 测试总结 ===")
    print("如果混合测试和纯Schema测试都成功，说明你的API提供商支持混用模式")
    print("如果只有纯Schema测试成功，说明可能需要在同一会话中保持状态")