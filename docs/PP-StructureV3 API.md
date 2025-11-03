### 1\. 服务调用示例 (Python)

```python
# 请确保已安装 requests 库
# pip install requests
import base64
import os
import requests

API_URL = "<your url>"
TOKEN = "<access token>"
file_path = "<local file path>"

with open(file_path, "rb") as file:
    file_bytes = file.read()
    file_data = base64.b64encode(file_bytes).decode("ascii")

headers = {
    "Authorization": f"token {TOKEN}",
    "Content-Type": "application/json"
}

# 对于PDF文档，设置 `fileType` 为 0；对于图像，设置 `fileType` 为 1
payload = {"file": file_data, "fileType": <file type>}

response = requests.post(API_URL, json=payload, headers=headers)
print(response.status_code)
assert response.status_code == 200

result = response.json()["result"]
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

for i, res in enumerate(result["layoutParsingResults"]):
    md_filename = os.path.join(output_dir, f"doc_{i}.md")
    with open(md_filename, "w") as md_file:
        md_file.write(res["markdown"]["text"])
    print(f"Markdown document saved at {md_filename}")

    for img_path, img in res["markdown"]["images"].items():
        full_img_path = os.path.join(output_dir, img_path)
        os.makedirs(os.path.dirname(full_img_path), exist_ok=True)
        img_bytes = requests.get(img).content
        with open(full_img_path, "wb") as img_file:
            img_file.write(img_bytes)
        print(f"Image saved to: {full_img_path}")

    for img_name, img in res["outputImages"].items():
        img_response = requests.get(img)
        if img_response.status_code == 200:
            # 保存图片到本地
            filename = os.path.join(output_dir, f"{img_name}_{i}.jpg")
            with open(filename, "wb") as f:
                f.write(img_response.content)
            print(f"Image saved to: {filename}")
        else:
            print(f"Failed to download image, status code: {img_response.status_code}")
```

**服务操作：**

  * **HTTP 请求方法：** `POST`
  * **端点：** `/layout-parsing`
  * **请求体与响应体：** JSON 格式

-----

### 2\. 请求参数说明

| 名称 | 类型 | 含义 | 是否必填 |
| :--- | :--- | :--- | :--- |
| `file` | string | 服务器可访问的图像或PDF文件的URL，或文件内容的Base64编码。默认超10页的PDF只处理前10页。 | 是 |
| `fileType` | integer | null | 文件类型。`0` 表示PDF，`1` 表示图像。若不传，则根据URL推断。 | 否 |
| `useDocOrientationClassify` | boolean | null | 是否使用文档方向分类模块（自动矫正0°、90°、180°、270°的图片）。 | 否 |
| `useDocUnwarping` | boolean | null | 是否使用文本图像矫正模块（自动矫正扭曲、褶皱、倾斜等）。 | 否 |
| `useTextlineOrientation` | boolean | null | 是否使用文本行方向分类模块（自动矫正0° 和180° 的文本行）。 | 否 |
| `useSealRecognition` | boolean | null | 是否使用印章文本识别子产线（识别文档中的印章内容）。 | 否 |
| `useTableRecognition` | boolean | null | 是否使用表格识别子产线（将表格转换为HTML或Markdown）。 | 否 |
| `useFormulaRecognition` | boolean | null | 是否使用公式识别子产线（将数学公式转换为LaTeX代码）。 | 否 |
| `useChartRecognition` | boolean | null | 是否使用图表解析模块（将图表转为表格形式）。 | 否 |
| `useRegionDetection` | boolean | null | 是否使用文档区域检测模块（提高复杂排版文档的识别准确性）。 | 否 |
| `layoutThreshold` | number | object | null | 版面模型得分阈值（0-1之间，默认0.5）。 | 否 |
| `layoutNms` | boolean | null | 是否开启NMS后处理（移除重复或高度重叠的区域框）。 | 否 |
| `layoutUnclipRatio` | number | array | object | null | 版面区域检测框的扩张系数（大于0，默认1.0）。 | 否 |
| `layoutMergeBboxesMode` | string | object | null | 重叠框过滤方式 (`large`, `small`, `union`，默认 `large`)。 | 否 |
| `textDetLimitSideLen` | integer | null | 文本检测的图像边长限制（大于0，默认64）。 | 否 |
| `textDetLimitType` | string | null | 文本检测边长限制类型 (`min` 或 `max`，默认 `min`)。 | 否 |
| `textDetThresh` | number | null | 文本检测像素阈值（大于0，默认0.3）。 | 否 |
| `textDetBoxThresh` | number | null | 文本检测框阈值（大于0，默认0.6）。 | 否 |
| `textDetUnclipRatio` | number | null | 文本检测扩张系数（大于0，默认1.5）。 | 否 |
| `textRecScoreThresh` | number | null | 文本识别阈值（大于0，默认0.0，即不设阈值）。 | 否 |
| `sealDetLimitSideLen` | integer | null | 印章文本检测的图像边长限制（大于0，默认736）。 | 否 |
| `sealDetLimitType` | string | null | 印章文本检测的图像边长限制类型 (`min` 或 `max`，默认 `min`)。 | 否 |
| `sealDetThresh` | number | null | 印章检测像素阈值（大于0，默认0.2）。 | 否 |
| `sealDetBoxThresh` | number | null | 印章文本检测框阈值（大于0，默认0.6）。 | 否 |
| `sealDetUnclipRatio` | number | null | 印章文本检测扩张系数（大于0，默认0.5）。 | 否 |
| `sealRecScoreThresh` | number | null | 印章文本识别阈值（大于0，默认0.0）。 | 否 |
| `useWiredTableCellsTransToHtml` | boolean | 是否启用有线表单元格检测结果直转HTML。 | 否 |
| `useWirelessTableCellsTransToHtml` | boolean | 是否启用无线表单元格检测结果直转HTML。 | 否 |
| `useTableOrientationClassify` | boolean | 是否启用表格方向分类（矫正表格旋转）。 | 否 |
| `useOcrResultsWithTableCells` | boolean | 是否启用单元格切分OCR（避免文字缺失）。 | 否 |
| `useE2eWiredTableRecModel` | boolean | 是否启用有线表端到端表格识别模式。 | 否 |
| `useE2eWirelessTableRecModel` | boolean | 是否启用无线表端到端表格识别模式。 | 否 |
| `visualize` | boolean | null | 是否返回可视化结果图。 | 否 |

-----

### 3\. 响应体说明

#### 3.1 请求成功 (状态码 200)

响应体属性如下：

| 名称 | 类型 | 含义 |
| :--- | :--- | :--- |
| `logId` | string | 请求的UUID。 |
| `errorCode` | integer | 错误码。固定为 `0`。 |
| `errorMsg` | string | 错误说明。固定为 `"Success"`。 |
| `result` | object | 操作结果。 |

**`result` 对象属性：**

| 名称 | 类型 | 含义 |
| :--- | :--- | :--- |
| `layoutParsingResults` | array | 文档解析结果。数组，每个元素对应一页的结果。 |
| `dataInfo` | object | 输入数据信息。 |

**`layoutParsingResults` 数组元素属性：**

| 名称 | 类型 | 含义 |
| :--- | :--- | :--- |
| `prunedResult` | object | 简化的产线预测结果。 |
| `markdown` | object | Markdown结果。 |
| `outputImages` | object | null | 产线预测结果的图像（Base64编码）。 |
| `inputImage` | string | null | 输入图像（Base64编码）。 |

**`markdown` 对象属性：**

| 名称 | 类型 | 含义 |
| :--- | :--- | :--- |
| `text` | string | Markdown文本。 |
| `images` | object | Markdown图片相对路径和Base64编码图像的键值对。 |
| `isStart` | boolean | 当前页面第一个元素是否为段开始。 |
| `isEnd` | boolean | 当前页面最后一个元素是否为段结束。 |

#### 3.2 请求失败

响应体属性如下：

| 名称 | 类型 | 含义 |
| :--- | :--- | :--- |
| `logId` | string | 请求的UUID。 |
| `errorCode` | integer | 错误码（与响应状态码相同）。 |
| `errorMsg` | string | 错误说明。 |