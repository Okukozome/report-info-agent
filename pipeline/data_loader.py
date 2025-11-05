# pipeline/data_loader.py
import pandas as pd
from pathlib import Path
from functools import lru_cache
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
LIST_DIR = BASE_DIR / "all_name_lists"
CATEGORIES = {
    "Directors": "directors.csv",
    "Supervisors": "supervisors.csv",
    "SeniorManagement": "seniormanagement.csv"
}

@lru_cache(maxsize=None)
def _load_csv_to_dataframe(csv_path: Path) -> pd.DataFrame:
    """
    [缓存] 从CSV加载数据并设置多级索引
    """
    logger.info(f"[DataLoader] 正在加载并缓存文件: {csv_path.name} ...")
    try:
        df = pd.read_csv(csv_path)
        
        # 规范化索引键
        # 1. stkcd: 变为字符串，去除前导零
        df['stkcd'] = df['stkcd'].astype(str).str.lstrip('0')
        # 2. year: 提取年份，变为字符串
        df['year'] = pd.to_datetime(df['year'], errors='coerce').dt.year.astype(str)
        
        # 丢弃无法解析的行
        df.dropna(subset=['stkcd', 'year', 'name'], inplace=True)
        
        # 聚合相同 (stkcd, year) 的姓名到列表中
        # 确保姓名是唯一的（按客户要求）
        grouped = df.groupby(['stkcd', 'year'])['name'].apply(lambda x: list(pd.unique(x))).reset_index()
        
        # 设置索引以便快速查询
        grouped.set_index(['stkcd', 'year'], inplace=True)
        
        logger.info(f"[DataLoader] {csv_path.name} 加载并索引完毕。")
        return grouped
        
    except FileNotFoundError:
        logger.error(f"[DataLoader] 严重错误: 未找到标准名单文件: {csv_path}")
        raise
    except Exception as e:
        logger.error(f"[DataLoader] 加载 {csv_path.name} 时出错: {e}")
        raise

def get_target_lists(stkcd: str, year: str) -> Dict[str, List[str]]:
    """
    获取指定 stkcd 和 year 的三份标准名单
    
    Args:
        stkcd (str): 股票代码 (例如 "000014")
        year (str): 年份 (例如 "2014")
        
    Returns:
        Dict[str, List[str]]: 包含三类名单的字典
    """
    target_lists = {}
    
    # 规范化查询键 (stkcd 必须去除前导零以匹配索引)
    lookup_key = (stkcd.lstrip('0'), year)
    
    for category, filename in CATEGORIES.items():
        csv_path = LIST_DIR / filename
        try:
            df = _load_csv_to_dataframe(csv_path)
            
            # 使用 .loc 查询
            names = df.loc[lookup_key, 'name']
            target_lists[category] = names if isinstance(names, list) else [names] # 确保总是列表
            
        except KeyError:
            # .loc 查询失败，意味着该 (stkcd, year) 组合没有记录
            target_lists[category] = []
        except Exception as e:
            logger.warning(f"查询 {category} 名单 (key={lookup_key}) 时出错: {e}")
            target_lists[category] = []
            
    return target_lists