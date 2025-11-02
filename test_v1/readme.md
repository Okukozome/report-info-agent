阶段一：MVP (核心提取器验证)
目标： Prompt和Schema是否能从理想的、干净的上下文中提取出正确信息。
步骤：
手动挑选一份PDF。
手动找到“董监高”名单的那几页，手动把它们复制粘贴到一个.txt文件中。
忽略 RAG、Reranker、unstructured.io。
编写一个Python脚本，读取这个.txt文件内容，将其作为content，调用gpt-4o。
使用 Q1 中的 Tool Use 方法，强制gpt-4o返回您定义的Pydantic模型的JSON。
验收标准： 能够稳定、准确地解析出这份“黄金标准”文本中的所有人员和角色。