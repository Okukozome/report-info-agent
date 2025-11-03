import base64
import os
import requests
import sys # 导入sys模块
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()
API_URL = os.getenv("PP_API_URL")
TOKEN = os.getenv("PP_TOKEN")

# 输入文件路径
file_path = "input/sample_page_split.pdf"

try:
    with open(file_path, "rb") as file:
        file_bytes = file.read()
        file_data = base64.b64encode(file_bytes).decode("ascii")
except FileNotFoundError:
    print(f"错误：未找到文件 {file_path}")
    sys.exit(1) # 文件不存在则退出

headers = {
    "Authorization": f"token {TOKEN}",
    "Content-Type": "application/json"
}

# PDF文件设置fileType为0；图片设置为1
file_type = 0

payload = {
        "file": file_data,
        "fileType": file_type,
        
        # --- 推荐的参数组合 ---
        "visualize": False,
        "useTableRecognition": True,
        "useChartRecognition": True,
        "useWiredTableCellsTransToHtml": True,
        "useWirelessTableCellsTransToHtml": True,
        "useOcrResultsWithTableCells": True,
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useTextlineOrientation": False,
        "useTableOrientationClassify": False,
    }

print(f"正在向 API 发送请求: {API_URL}")
response = requests.post(API_URL, json=payload, headers=headers)

if response.status_code != 200:
    print(f"API 请求失败，状态码: {response.status_code}")
    print("--- 原始响应内容 (可能包含错误信息) ---")
    try:
        # 尝试解析 JSON 并打印，如果不是 JSON 格式则打印文本
        print(response.json())
    except requests.exceptions.JSONDecodeError:
        print(response.text)
    print("------------------------------------------")
    sys.exit(1) # 请求失败则退出程序

# 请求成功，继续执行
print(f"API 请求成功，状态码: {response.status_code}")
result = response.json()["result"]

# 输出目录为"result"
output_dir = "result"
os.makedirs(output_dir, exist_ok=True)

for i, res in enumerate(result["layoutParsingResults"]):
    # Markdown文件保存到result目录下
    md_filename = os.path.join(output_dir, f"doc_{i}.md")
    with open(md_filename, "w") as md_file:
        md_file.write(res["markdown"]["text"])
    print(f"Markdown文档已保存至: {md_filename}")
    
    # 图片保存到result目录下
    for img_path, img in res["markdown"]["images"].items():
        full_img_path = os.path.join(output_dir, img_path)
        os.makedirs(os.path.dirname(full_img_path), exist_ok=True)
        # 使用requests.get(img).content下载图片
        try:
            img_bytes = requests.get(img).content
            with open(full_img_path, "wb") as img_file:
                img_file.write(img_bytes)
            print(f"图片已保存至: {full_img_path}")
        except requests.exceptions.RequestException as e:
            print(f"警告：下载图片 {img_path} 失败: {e}")
    
    # 输出图片保存到result目录下
    # 使用 .get("outputImages", {}) 来安全地获取
    # 如果 "outputImages" 键不存在, .get() 会返回一个空字典 {}
    # 遍历一个空字典是安全的（循环会直接跳过），不会引发错误。
    for img_name, img in res.get("outputImages", {}).items():
        img_response = requests.get(img)
        if img_response.status_code == 200:
            # Save image to local
            filename = os.path.join(output_dir, f"{img_name}_{i}.jpg")
            with open(filename, "wb") as f:
                f.write(img_response.content)
            print(f"Image saved to: {filename}")
        else:
            print(f"Failed to download image, status code: {img_response.status_code}")