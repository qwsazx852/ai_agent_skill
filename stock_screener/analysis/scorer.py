"""
綜合評分模組 - 專業選股邏輯版

核心理念（取自 CANSLIM + 籌碼分析 + 技術分析）：
1. 「三軍一致」加分：技術/籌碼/基本面三者同時強 → 乘數加成
2. 「否決條件」折扣：任一維度嚴重惡化 → 上限壓制
3. 「市場環境」調整：大盤空頭時全面降低信心水位
4. 「超漲懲罰」：短期漲幅過大 = 追高風險，降低評分

評分權重：
- 技術面: 35% (含技術形態加分)
- 籌碼面: 35% (三大法人 + 大戶)
- 基本面: 15%
- 產業/主題: 15%
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

logger = logging.getLogger(__name__)


# ============================================================
# 評分門檻常數
# ============================================================

# 否決條件：達到這些條件時強制壓制最終分數上限
VETO_CONDITIONS = {
    "stage4_cap": 35,          # Stage 4 下跌趨勢（技術面 < 20）→ 上限 35
    "inst_sell_cap": 50,       # 三大法人持續賣超 → 上限 50
    "fund_negative_cap": 45,   # EPS 連續負成長且 ROE 低 → 上限 45
}

# 三軍一致加分 bonus
CONVICTION_THRESHOLDS = {
    "strong_all": 20,   # 三維度都 >= 70 → +20
    "strong_two": 10,   # 任兩維度 >= 70 → +10
    "weak_all": -15,    # 三維度都 < 40 → -15（避免平均中性但全部爛的情況）
}


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

    # 評分細節（用於診斷）
    score_detail: Dict = field(default_factory=dict)

    # 觀察重點摘要
    key_points: List[str] = field(default_factory=list)

    # 技術形態
    patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
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
            "score_detail": self.score_detail,
            "key_points": self.key_points,
            "patterns": self.patterns,
        }


def _check_veto_conditions(
    tech_score: float,
    fund_score: float,
    inst_score: float,
    indicators: Dict,
    inst_data: Dict,
    fin_data: Dict,
) -> Tuple[Optional[float], List[str]]:
    """
    檢查否決條件，回傳最高分上限（None = 無否決）與說明

    Returns:
        (cap: float|None, reasons: List[str])
    """
    cap = None
    reasons = []

    # ── 否決1: Stage 4 – 技術分析確認下跌趨勢 ──
    stage = indicators.get("stage", "")
    ma60 = indicators.get("ma60")
    price = indicators.get("price")
    if stage == "stage4" or (tech_score < 30 and ma60 and price and price < ma60 * 0.97):
        cap = max(cap or 0, VETO_CONDITIONS["stage4_cap"])
        reasons.append("🚫 Stage4下跌趨勢，強制上限35分")

    # ── 否決2: 籌碼極弱 – 外資+投信連續賣超且評分極低 ──
    if inst_score < 25:
        c = min(cap or 100, VETO_CONDITIONS["inst_sell_cap"])
        if c < (cap or 100):
            cap = c
        reasons.append("⚠️ 籌碼極弱，評分上限50分")

    # ── 否決3: 基本面負轉 – EPS 負成長且ROE低 ──
    eps_growth = fin_data.get("eps_growth")
    roe = fin_data.get("roe")
    if (eps_growth is not None and eps_growth < -0.2 and
            roe is not None and roe < 0.05 and fund_score < 30):
        c = min(cap or 100, VETO_CONDITIONS["fund_negative_cap"])
        if c < (cap or 100):
            cap = c
        reasons.append("⚠️ 基本面惡化，評分上限45分")

    return cap, reasons


def _calculate_conviction_bonus(
    tech_score: float,
    fund_score: float,
    inst_score: float,
    indicators: Dict,
) -> Tuple[float, List[str]]:
    """
    計算「三軍一致」加分 bonus

    核心邏輯：
    - 當技術/籌碼/基本面三者同步強勢 → 這是真正的強勢股，給予額外加分
    - 當三者都弱 → 給予額外懲罰（避免平均到「中性」）

    Returns:
        (bonus: float, reasons: List[str])
    """
    bonus = 0.0
    reasons = []

    # 高信心：三維度全強（技術 + 籌碼 + 基本面）
    strong_dims = sum([
        tech_score >= 70,
        inst_score >= 70,
        fund_score >= 65,
    ])

    if strong_dims == 3:
        bonus += CONVICTION_THRESHOLDS["strong_all"]
        reasons.append("💎 技術/籌碼/基本面三強共振 +20")
    elif strong_dims == 2:
        bonus += CONVICTION_THRESHOLDS["strong_two"]
        reasons.append("✅ 雙維度共振 +10")

    # 低信心懲罰：三維度全弱
    weak_dims = sum([
        tech_score < 40,
        inst_score < 40,
        fund_score < 40,
    ])
    if weak_dims == 3:
        bonus += CONVICTION_THRESHOLDS["weak_all"]
        reasons.append("⚠️ 三維度均弱，扣15分")

    # 量價齊揚加分
    vol_ratio = indicators.get("volume_ratio", 1)
    change_1d = indicators.get("change_1d", 0)
    if vol_ratio >= 1.5 and change_1d and change_1d > 2.0 and tech_score >= 65:
        bonus += 5
        reasons.append("🔥 量價齊揚配合技術強勢 +5")

    # 超漲懲罰：20日漲幅超過25% = 追高風險高
    change_20d = indicators.get("change_20d", 0)
    if change_20d and change_20d > 25:
        penalty = min(15, int((change_20d - 25) / 5) * 5)
        bonus -= penalty
        reasons.append(f"⚠️ 20日漲幅{change_20d:.0f}%，追高風險 -{penalty}")
    elif change_20d and change_20d > 15:
        bonus -= 5
        reasons.append(f"⚠️ 近期已漲{change_20d:.0f}%，注意追高 -5")

    return bonus, reasons


def _apply_market_adjustment(score: float, market_multiplier: float) -> float:
    """
    套用市場環境調整

    邏輯：
    - 多頭市場：分數全額
    - 震盪市場：分數打88-92折
    - 空頭市場：分數打78折（對高分股懲罰更重）
    """
    if market_multiplier >= 1.0:
        return score

    # 對已經高分的股票懲罰更重（大盤空頭時高分股也容易跌）
    if score >= 80:
        adjusted = score * market_multiplier * 0.97
    elif score >= 70:
        adjusted = score * market_multiplier
    else:
        # 低分股在空頭市場相對差異較小
        adjusted = score * (market_multiplier + (1 - market_multiplier) * 0.3)

    return adjusted


def calculate_composite_score(
    technical_score: float,
    fundamental_score: float,
    institutional_score: float,
    industry_score: float,
    weights: Optional[Dict] = None,
    indicators: Optional[Dict] = None,
    inst_data: Optional[Dict] = None,
    fin_data: Optional[Dict] = None,
    market_multiplier: float = 1.0,
) -> Tuple[float, Dict]:
    """
    專業選股綜合評分

    流程：
    1. 基礎加權平均
    2. 計算「三軍一致」加分/懲罰
    3. 檢查否決條件（強制上限）
    4. 套用市場環境調整

    Returns:
        (final_score, detail_dict)
    """
    if weights is None:
        weights = {
            "technical": 0.35,
            "fundamental": 0.15,
            "institutional": 0.35,
            "industry": 0.15,
        }

    indicators = indicators or {}
    inst_data = inst_data or {}
    fin_data = fin_data or {}

    # ── Step 1: 基礎加權平均 ──────────────────────────────
    base_score = (
        technical_score * weights["technical"] +
        fundamental_score * weights["fundamental"] +
        institutional_score * weights["institutional"] +
        industry_score * weights["industry"]
    )

    detail = {
        "base_score": round(base_score, 1),
        "conviction_bonus": 0,
        "veto_cap": None,
        "market_multiplier": market_multiplier,
        "veto_reasons": [],
        "conviction_reasons": [],
    }

    # ── Step 2: 三軍一致加分 ──────────────────────────────
    bonus, conviction_reasons = _calculate_conviction_bonus(
        technical_score, fundamental_score, institutional_score, indicators
    )
    detail["conviction_bonus"] = round(bonus, 1)
    detail["conviction_reasons"] = conviction_reasons

    adjusted_score = base_score + bonus

    # ── Step 3: 否決條件上限 ──────────────────────────────
    cap, veto_reasons = _check_veto_conditions(
        technical_score, fundamental_score, institutional_score,
        indicators, inst_data, fin_data
    )
    detail["veto_cap"] = cap
    detail["veto_reasons"] = veto_reasons

    if cap is not None:
        adjusted_score = min(adjusted_score, cap)

    # ── Step 4: 市場環境調整 ──────────────────────────────
    final_score = _apply_market_adjustment(adjusted_score, market_multiplier)
    final_score = max(0, min(100, final_score))

    return round(final_score, 1), detail


def get_grade(score: float) -> str:
    """
    根據評分給出評級

    A+ (88+):  極強，高信心買進候選
    A  (78-87): 強，買進候選
    B+ (68-77): 偏多，積極觀察
    B  (58-67): 中性偏多，列入觀察
    C+ (48-57): 中性
    C  (38-47): 偏弱
    D  (0-37):  迴避
    """
    if score >= 88:
        return "A+"
    elif score >= 78:
        return "A"
    elif score >= 68:
        return "B+"
    elif score >= 58:
        return "B"
    elif score >= 48:
        return "C+"
    elif score >= 38:
        return "C"
    else:
        return "D"


def get_grade_emoji(grade: str) -> str:
    emoji_map = {
        "A+": "🌟", "A": "⭐", "B+": "✅",
        "B": "🔵", "C+": "🟡", "C": "🟠", "D": "🔴",
    }
    return emoji_map.get(grade, "⚪")


def generate_key_points(stock: "StockScore") -> List[str]:
    """產生個股觀察重點摘要"""
    points = []

    # 信心程度
    detail = stock.score_detail
    conviction_reasons = detail.get("conviction_reasons", [])
    veto_reasons = detail.get("veto_reasons", [])

    if conviction_reasons:
        points.extend(conviction_reasons[:2])
    if veto_reasons:
        points.extend(veto_reasons[:1])

    # 各面向最強訊號
    for sig_list in [stock.technical_signals, stock.institutional_signals, stock.fundamental_signals]:
        for sig in sig_list[:1]:
            if sig not in points:
                points.append(sig)
                break

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
    weights: Optional[Dict] = None,
    market_multiplier: float = 1.0,
) -> "StockScore":
    """
    整合所有分析結果，產生完整股票評分
    """
    tech_score = float(technical_result.get("score", 50))
    fund_score = float(fundamental_result.get("score", 50))
    inst_score = float(institutional_result.get("score", 50))
    ind_score = float(industry_result.get("score", 50))

    indicators = technical_result.get("indicators", {})
    inst_data = institutional_result.get("data", {}) or {}
    fin_data = fundamental_result.get("data", {}) or {}

    composite, detail = calculate_composite_score(
        tech_score, fund_score, inst_score, ind_score,
        weights=weights,
        indicators=indicators,
        inst_data=inst_data,
        fin_data=fin_data,
        market_multiplier=market_multiplier,
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
        indicators=indicators,
        institutional_data=inst_data,
        financial_data=fin_data,
        industry_data=industry_result.get("industry_data", {}),
        score_detail=detail,
    )

    stock.key_points = generate_key_points(stock)
    return stock


def rank_stocks(stocks: List["StockScore"]) -> List["StockScore"]:
    """依綜合評分排名"""
    return sorted(stocks, key=lambda x: x.composite_score, reverse=True)


def filter_stocks(
    stocks: List["StockScore"],
    min_score: float = 60,
    min_grade: str = "B",
    required_signals: Optional[List[str]] = None
) -> List["StockScore"]:
    """過濾股票"""
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
