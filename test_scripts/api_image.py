import os
import base64
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class ImageAnalyzer:
    def __init__(self):
        self.api_base_url = os.getenv("API_BASE_URL", "https://api2.aigcbest.top")
        self.api_key = os.getenv("API_KEY")
        
        if not self.api_key:
            raise ValueError("请设置 API_KEY 环境变量")
    
    def encode_image_to_base64(self, image_path):
        """将图片文件编码为base64"""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def analyze_local_image(self, image_path, prompt="请详细描述这张图片的内容"):
        """分析本地图片"""
        try:
            # 编码图片为base64
            base64_image = self.encode_image_to_base64(image_path)
            
            # 构建请求
            api_url = f"{self.api_base_url}/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.7
            }
            
            print(f"正在分析图片: {image_path}")
            print(f"提问: {prompt}")
            print("请求中...")
            
            # 发送请求
            response = requests.post(api_url, headers=headers, json=data)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                usage = result['usage']
                
                print("图片分析成功！")
                print("AI回复:")
                print("-" * 50)
                print(content)
                print("-" * 50)
                print(f"Token使用: {usage}")
                
                return content
            else:
                print(f"API请求失败，状态码: {response.status_code}")
                print(f"错误信息: {response.text}")
                return None
                
        except Exception as e:
            print(f"发生异常: {e}")
            return None

def main():
    """主函数"""
    try:
        analyzer = ImageAnalyzer()
        
        # 测试本地图片
        local_image = "test.jpg"
        
        if os.path.exists(local_image):
            print("=" * 60)
            print("测试本地图片识别")
            print("=" * 60)
            
            # 可以自定义提问
            prompts = [
                "请详细描述这张图片的内容",
                "这张图片中有什么物体或场景？",
                "分析图片的色彩、构图和风格"
            ]
            
            for prompt in prompts:
                analyzer.analyze_local_image(local_image, prompt)
                print("\n" + "=" * 60 + "\n")
        
        else:
            print(f"本地图片 {local_image} 不存在，请准备测试图片")
        
    except ValueError as e:
        print(e)
    except Exception as e:
        print(f"程序异常: {e}")

if __name__ == "__main__":
    main()

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