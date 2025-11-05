from pydantic import BaseModel, Field
from typing import Literal

class TocAnalysisResult(BaseModel):
    """
    用于保存从目录中提取的DGS章节信息
    """
    start_page: int = Field(
        ..., 
        description="DGS章节在目录中标记的起始页码。如果未找到或无法确定，必须返回-1。"
    )
    end_page: int = Field(
        ..., 
        description="DGS章节在目录中标记的结束页码。如果未找到或无法确定，必须返回-1。"
    )
    title: str = Field(
        ..., 
        description="DGS章节的完整官方标题。如果未找到，必须返回空字符串 ''。"
    )

class PageVerificationResult(BaseModel):
    """
    用于验证页面是否为章节首页
    """
    status: Literal["match", "too_early", "too_late", "fail"] = Field(
        ..., 
        description=(
            "判断结果: "
            "'match' (页面包含目标标题，是第一页), "
            "'too_early' (页面内容在目标章节之前，应'下一页'), "
            "'too_late' (页面内容已在目标章节内部，但不是第一页，应'上一页'), "
            "'fail' (内容完全无关或无法判断)"
        )
    )
    reason: str = Field(..., description="AI 做出判断的简要理由（例如：'找到标题' 或 '内容是附录'）。")