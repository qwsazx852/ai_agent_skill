"""
綜合評分模組
整合技術面、基本面、籌碼面、產業趨勢，計算最終綜合評分

評分權重:
- 技術面: 30%
- 基本面: 25%
- 籌碼面: 30%
- 產業趨勢: 15%
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StockScore:
    """單一股票的完整評分結果"""
    stock_id: str
    stock_name: str
    industry: str
    market: str

    # 各面向評分
    technical_score: float = 0
    fundamental_score: float = 0
    institutional_score: float = 0
    industry_score: float = 0

    # 綜合評分
    composite_score: float = 0

    # 評級
    grade: str = "C"

    # 各面向信號
    technical_signals: List[str] = field(default_factory=list)
    fundamental_signals: List[str] = field(default_factory=list)
    institutional_signals: List[str] = field(default_factory=list)
    industry_signals: List[str] = field(default_factory=list)

    # 技術指標
    indicators: Dict = field(default_factory=dict)

    # 籌碼資料
    institutional_data: Dict = field(default_factory=dict)

    # 基本面資料
    financial_data: Dict = field(default_factory=dict)

    # 產業資料
    industry_data: Dict = field(default_factory=dict)

    # 觀察重點摘要
    key_points: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """轉換為字典格式"""
        return {
            "stock_id": self.stock_id,
            "stock_name": self.stock_name,
            "industry": self.industry,
            "market": self.market,
            "composite_score": round(self.composite_score, 1),
            "grade": self.grade,
            "technical_score": round(self.technical_score, 1),
            "fundamental_score": round(self.fundamental_score, 1),
            "institutional_score": round(self.institutional_score, 1),
            "industry_score": round(self.industry_score, 1),
            "technical_signals": self.technical_signals,
            "fundamental_signals": self.fundamental_signals,
            "institutional_signals": self.institutional_signals,
            "industry_signals": self.industry_signals,
            "indicators": self.indicators,
            "institutional_data": self.institutional_data,
            "financial_data": self.financial_data,
            "industry_data": self.industry_data,
            "key_points": self.key_points,
        }


def calculate_composite_score(
    technical_score: float,
    fundamental_score: float,
    institutional_score: float,
    industry_score: float,
    weights: Optional[Dict] = None
) -> float:
    """
    計算綜合評分

    Args:
        technical_score: 技術面評分 (0-100)
        fundamental_score: 基本面評分 (0-100)
        institutional_score: 籌碼面評分 (0-100)
        industry_score: 產業評分 (0-100)
        weights: 自訂權重字典

    Returns:
        綜合評分 (0-100)
    """
    if weights is None:
        weights = {
            "technical": 0.30,
            "fundamental": 0.25,
            "institutional": 0.30,
            "industry": 0.15,
        }

    composite = (
        technical_score * weights["technical"] +
        fundamental_score * weights["fundamental"] +
        institutional_score * weights["institutional"] +
        industry_score * weights["industry"]
    )

    return round(composite, 2)


def get_grade(score: float) -> str:
    """
    根據評分給出評級

    A+ (90-100): 強力買進候選
    A  (80-89):  買進候選
    B+ (70-79):  偏多觀察
    B  (60-69):  中性偏多
    C+ (50-59):  中性
    C  (40-49):  中性偏弱
    D  (0-39):   弱勢迴避
    """
    if score >= 90:
        return "A+"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B+"
    elif score >= 60:
        return "B"
    elif score >= 50:
        return "C+"
    elif score >= 40:
        return "C"
    else:
        return "D"


def get_grade_emoji(grade: str) -> str:
    """評級對應 emoji"""
    emoji_map = {
        "A+": "🌟",
        "A": "⭐",
        "B+": "✅",
        "B": "🔵",
        "C+": "🟡",
        "C": "🟠",
        "D": "🔴",
    }
    return emoji_map.get(grade, "⚪")


def generate_key_points(stock: "StockScore") -> List[str]:
    """
    產生個股觀察重點摘要

    Args:
        stock: StockScore 物件

    Returns:
        重點清單 (最多5點)
    """
    points = []

    # 綜合評分描述
    if stock.composite_score >= 80:
        points.append(f"💎 綜合評分 {stock.composite_score:.0f} 分，各面向均表現優異")
    elif stock.composite_score >= 70:
        points.append(f"✅ 綜合評分 {stock.composite_score:.0f} 分，整體偏多")

    # 挑選最強訊號
    all_signals = (
        stock.technical_signals[:2] +
        stock.fundamental_signals[:1] +
        stock.institutional_signals[:2] +
        stock.industry_signals[:1]
    )

    for signal in all_signals[:4]:
        if signal not in points:
            points.append(signal)

    # 價格資訊
    price = stock.indicators.get("price")
    change_1d = stock.indicators.get("change_1d")
    if price and change_1d is not None:
        direction = "▲" if change_1d >= 0 else "▼"
        points.append(f"📊 現價 {price:.1f} ({direction}{abs(change_1d):.2f}%)")

    return points[:5]


def score_stock(
    stock_id: str,
    stock_name: str,
    industry: str,
    market: str,
    technical_result: Dict,
    fundamental_result: Dict,
    institutional_result: Dict,
    industry_result: Dict,
    weights: Optional[Dict] = None
) -> StockScore:
    """
    整合所有分析結果，產生完整股票評分

    Args:
        stock_id: 股票代號
        stock_name: 股票名稱
        industry: 產業別
        market: 市場別 (TWSE/OTC)
        technical_result: 技術分析結果
        fundamental_result: 基本面分析結果
        institutional_result: 籌碼分析結果
        industry_result: 產業分析結果
        weights: 自訂評分權重

    Returns:
        StockScore 物件
    """
    tech_score = technical_result.get("score", 50)
    fund_score = fundamental_result.get("score", 50)
    inst_score = institutional_result.get("score", 50)
    ind_score = industry_result.get("score", 50)

    composite = calculate_composite_score(
        tech_score, fund_score, inst_score, ind_score, weights
    )

    stock = StockScore(
        stock_id=stock_id,
        stock_name=stock_name,
        industry=industry,
        market=market,
        technical_score=tech_score,
        fundamental_score=fund_score,
        institutional_score=inst_score,
        industry_score=ind_score,
        composite_score=composite,
        grade=get_grade(composite),
        technical_signals=technical_result.get("signals", []),
        fundamental_signals=fundamental_result.get("signals", []),
        institutional_signals=institutional_result.get("signals", []),
        industry_signals=industry_result.get("signals", []),
        indicators=technical_result.get("indicators", {}),
        institutional_data=institutional_result.get("data", {}),
        financial_data=fundamental_result.get("data", {}),
        industry_data=industry_result.get("industry_data", {}),
    )

    stock.key_points = generate_key_points(stock)

    return stock


def rank_stocks(stocks: List[StockScore]) -> List[StockScore]:
    """
    依綜合評分排名

    Args:
        stocks: StockScore 清單

    Returns:
        排序後的清單
    """
    return sorted(stocks, key=lambda x: x.composite_score, reverse=True)


def filter_stocks(
    stocks: List[StockScore],
    min_score: float = 60,
    min_grade: str = "B",
    required_signals: Optional[List[str]] = None
) -> List[StockScore]:
    """
    過濾股票

    Args:
        stocks: StockScore 清單
        min_score: 最低綜合評分
        min_grade: 最低評級
        required_signals: 必須包含的訊號關鍵字

    Returns:
        過濾後的清單
    """
    grade_order = {"A+": 7, "A": 6, "B+": 5, "B": 4, "C+": 3, "C": 2, "D": 1}
    min_grade_val = grade_order.get(min_grade, 1)

    filtered = [
        s for s in stocks
        if (s.composite_score >= min_score and
            grade_order.get(s.grade, 0) >= min_grade_val)
    ]

    if required_signals:
        result = []
        for stock in filtered:
            all_signals = " ".join(
                stock.technical_signals +
                stock.fundamental_signals +
                stock.institutional_signals +
                stock.industry_signals
            )
            if any(kw in all_signals for kw in required_signals):
                result.append(stock)
        filtered = result

    return filtered
