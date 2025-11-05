# pipeline/core/schemas.py
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class Person(BaseModel):
    """代表一位被提取的人员及其排序"""
    rank: int = Field(..., description="基于在原文中出现的先后顺序生成的排名（从1开始）")
    name: str = Field(..., description="人员的姓名（必须来自标准名单）。注意：不可能同名异人，如果存在同名多个职务，则属于兼任情况。")
    role: str = Field(..., description="在原文中找到的该人员的完整职务，多职兼任时用顿号隔开")

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

class ExtractedTable(BaseModel):
    """代表一个被提取的、带有描述的表格"""
    description: str = Field(
        ..., 
        description=(
            "提取到的表格的标题或表名。如果表格在原文中没有明确标题，"
            "模型应根据其内容生成一个简短描述（例如：'董事基本情况表'）。"
        )
    )
    content: str = Field(
        ...,
        description="完整的表格内容（Markdown或HTML字符串）。跨页表格必须被合并为单个字符串。"
    )

class ExtractedTextSection(BaseModel):
    """代表一个被提取的、有标题的文本小节"""
    title: str = Field(
        ..., 
        description="提取到的文字小节的准确标题（例如：'任职情况'）。"
    )
    content: str = Field(
        ...,
        description="该小节的完整文字内容。"
    )

class CoreBlocksExtractionResult(BaseModel):
    """
    保存从完整Markdown中提取出的核心数据块（表格和文本）
    """
    tables: List[ExtractedTable] = Field(
        ...,
        description="董监高相关的核心表格对象列表。应按在原文中的出现顺序排列。"
    )
    employment_section: Optional[ExtractedTextSection] = Field(
        default=None,
        description="完整的'任职情况'文字小节（包含其标题和内容）。如果未找到，则为 null。"
    )
    assessment: ConfidenceAssessment = Field(
        ...,
        description="对本次核心块提取的置信度评估"
    )

# --- [新增] 用于核对步骤的模型 ---
class NameVerificationResult(BaseModel):
    """保存对标准名单的核验结果"""
    found_names: List[str] = Field(
        ...,
        description="在原文中明确找到的、且属于标准名单的姓名列表。"
    )
    assessment: ConfidenceAssessment = Field(
        ...,
        description="对本次核验任务的置信度评估"
    )