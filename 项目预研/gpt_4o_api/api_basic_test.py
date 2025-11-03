import os
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def test_api():
    # 从环境变量读取配置
    api_base_url = os.getenv("API_BASE_URL")
    api_key = os.getenv("API_KEY")
    
    api_url = f"{api_base_url}/v1/chat/completions"
    
    # 请求头
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # 请求数据
    data = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "你是谁？"}],
        "temperature": 0.7
    }
    
    try:
        # 发送请求
        response = requests.post(api_url, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            print("API请求成功！")
            print(f"助手回复: {result['choices'][0]['message']['content']}")
            print(f"Token使用: {result['usage']}")
        else:
            print(f"API请求失败，状态码: {response.status_code}")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"发生异常: {e}")

if __name__ == "__main__":
    test_api()