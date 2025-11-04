from pydantic import BaseModel, Field
from typing import List, Literal

class Person(BaseModel):
    """代表一位被提取的人员及其排序"""
    rank: int = Field(..., description="基于在原文中出现的先后顺序生成的排名（从1开始）")
    name: str = Field(..., description="人员的姓名（请进行归一化，去除不必要的空格）")
    role: str = Field(..., description="在原文中找到的该人员的完整职务")

class ConfidenceAssessment(BaseModel):
    """模型对本次提取任务的自我评估"""
    confidence_level: Literal["High", "Medium", "Low"] = Field(
        ..., 
        description=(
            "对本次提取结果的整体置信度。 "
            "High (非常确定), "
            "Medium (基本确定，但有疑点), "
            "Low (不确定，很可能漏报或错报)"
        )
    )
    doubts: List[str] = Field(
        ..., 
        description=(
            "一个疑虑点列表。明确说明在提取过程中遇到的任何不确定性、歧义或潜在的边缘情况。 "
            "例如：'表格跨页导致顺序可能不准', '张三的职务不明确', '文本中的XX人名似乎有OCR识别错误'。 "
            "如果没有疑虑，必须返回空列表 []。"
        )
    )

class CategoryExtractionResult(BaseModel):
    """针对单一类别（例如：董事）的完整提取结果与评估"""
    category: Literal["Directors", "Supervisors", "SeniorManagement"] = Field(
        ..., 
        description="本次提取的目标类别"
    )
    persons: List[Person] = Field(
        ..., 
        description="按原文出现顺序排序的人员列表"
    )
    assessment: ConfidenceAssessment = Field(
        ...,
        description="对本次提取任务的置信度评估"
    )