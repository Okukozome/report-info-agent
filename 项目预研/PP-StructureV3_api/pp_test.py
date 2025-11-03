import base64
import os
import requests

API_URL = "https://45h1iesc5ft5z4l1.aistudio-app.com/layout-parsing "
TOKEN = "4e42d1f33095f2d05b59c527eb07573e85a40a06"

file_path = "page2.pdf"  # 输入文件路径

with open(file_path, "rb") as file:
    file_bytes = file.read()
    file_data = base64.b64encode(file_bytes).decode("ascii")

headers = {
    "Authorization": f"token {TOKEN}",
    "Content-Type": "application/json"
}

# PDF文件设置fileType为0；图片设置为1
payload = {"file": file_data, "fileType": 0}

response = requests.post(API_URL, json=payload, headers=headers)
print(response.status_code)
assert response.status_code == 200
result = response.json()["result"]

# 修改输出目录为"result"
output_dir = "result"
os.makedirs(output_dir, exist_ok=True)  # 自动创建result目录（如果不存在）

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
        img_bytes = requests.get(img).content
        with open(full_img_path, "wb") as img_file:
            img_file.write(img_bytes)
        print(f"图片已保存至: {full_img_path}")
    
    # 输出图片保存到result目录下
    for img_name, img in res["outputImages"].items():
        img_response = requests.get(img)
        if img_response.status_code == 200:
            filename = os.path.join(output_dir, f"{img_name}_{i}.jpg")
            with open(filename, "wb") as f:
                f.write(img_response.content)
            print(f"图片已保存至: {filename}")
        else:
            print(f"图片下载失败，状态码: {img_response.status_code}")